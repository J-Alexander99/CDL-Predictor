"""
Database manager for CDL match data and statistics
"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from config.settings import DB_PATH


class DatabaseManager:
    """Manages SQLite database operations for CDL match data"""
    
    def __init__(self, db_path: str = None):
        """Initialize database manager
        
        Args:
            db_path: Path to SQLite database file. If None, uses default from settings
        """
        self.db_path = db_path or DB_PATH
        self.logger = logging.getLogger(self.__class__.__name__)
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Create database and tables if they don't exist"""
        # Create data directory if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Read schema file
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Execute schema
        conn = self.get_connection()
        try:
            conn.executescript(schema_sql)
            conn.commit()
            self.logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
        finally:
            conn.close()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection
        
        Returns:
            SQLite connection object
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def insert_match(self, match_data: Dict) -> int:
        """Insert a match and all related data into the database
        
        Args:
            match_data: Dictionary containing match info, map results, and player stats
        
        Returns:
            Database ID of inserted match
        """
        conn = self.get_connection()
        try:
            # Extract match info
            info = match_data['match_info']
            match_id = info['match_id']
            team_a = info['team_a']
            team_b = info['team_b']
            team_a_score = info['team_a_score']
            team_b_score = info['team_b_score']
            winner = team_a if team_a_score > team_b_score else team_b
            
            # Insert match
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO matches 
                (match_id, team_a, team_b, winner, team_a_score, team_b_score, 
                 tournament, match_date, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, team_a, team_b, winner, team_a_score, team_b_score,
                info.get('tournament'), info.get('date'), info.get('url')
            ))
            
            db_match_id = cursor.lastrowid
            
            # Insert map results
            for i, map_result in enumerate(match_data['map_results'], 1):
                map_winner = team_a if map_result['team_a_score'] > map_result['team_b_score'] else team_b
                cursor.execute("""
                    INSERT OR REPLACE INTO map_results
                    (match_id, map_number, mode, map_name, team_a_score, team_b_score, winner)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, i, map_result['mode'], map_result['map_name'],
                    map_result['team_a_score'], map_result['team_b_score'], map_winner
                ))
            
            # Insert player stats (series totals)
            for player in match_data['player_stats']['team_a']:
                cursor.execute("""
                    INSERT OR REPLACE INTO player_match_stats
                    (match_id, player_name, team, kills, deaths, kd, plus_minus, damage, rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, player['player'], team_a, player['kills'], 
                    player['deaths'], player['kd'], player['plus_minus'],
                    player['damage'], player['rating']
                ))
            
            for player in match_data['player_stats']['team_b']:
                cursor.execute("""
                    INSERT OR REPLACE INTO player_match_stats
                    (match_id, player_name, team, kills, deaths, kd, plus_minus, damage, rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, player['player'], team_b, player['kills'],
                    player['deaths'], player['kd'], player['plus_minus'],
                    player['damage'], player['rating']
                ))
            
            # Insert individual map stats
            if 'per_map' in match_data['player_stats']:
                for map_stat in match_data['player_stats']['per_map']:
                    # Get map info for this map number
                    map_num = map_stat['map_number']
                    if 0 < map_num <= len(match_data['map_results']):
                        map_info = match_data['map_results'][map_num - 1]
                        cursor.execute("""
                            INSERT OR REPLACE INTO player_map_stats
                            (match_id, map_number, player_name, team, mode, map_name, 
                             kills, deaths, kd, damage, rating)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            match_id, map_num, map_stat['player_name'], 
                            map_stat['team'], map_info['mode'], map_info['map_name'],
                            map_stat['kills'], map_stat['deaths'], map_stat['kd'],
                            map_stat['damage'], map_stat['rating']
                        ))
            
            conn.commit()
            self.logger.info(f"Inserted match {match_id} into database")
            return db_match_id
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to insert match: {e}")
            raise
        finally:
            conn.close()
    
    def update_all_stats(self):
        """Recalculate all aggregated statistics from raw match data"""
        self.logger.info("Updating all statistics...")
        
        self._update_team_stats()
        self._update_team_mode_stats()
        self._update_team_map_mode_stats()
        self._update_head_to_head()
        self._update_head_to_head_map_mode()
        self._update_player_stats()
        self._update_player_mode_stats()
        self._update_player_map_mode_stats()
        
        self.logger.info("Statistics update complete")
    
    def _update_team_stats(self):
        """Update overall team statistics"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all teams
            cursor.execute("SELECT DISTINCT team_a FROM matches UNION SELECT DISTINCT team_b FROM matches")
            teams = [row[0] for row in cursor.fetchall()]
            
            for team in teams:
                # Match wins/losses
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_matches,
                        SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN winner != ? THEN 1 ELSE 0 END) as losses
                    FROM matches
                    WHERE team_a = ? OR team_b = ?
                """, (team, team, team, team))
                
                row = cursor.fetchone()
                total_matches = row[0] or 0
                wins = row[1] or 0
                losses = row[2] or 0
                win_rate = (wins / total_matches * 100) if total_matches > 0 else 0.0
                
                # Map wins/losses
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as maps_won,
                        SUM(CASE WHEN mr.winner != ? THEN 1 ELSE 0 END) as maps_lost
                    FROM map_results mr
                    JOIN matches m ON mr.match_id = m.match_id
                    WHERE m.team_a = ? OR m.team_b = ?
                """, (team, team, team, team))
                
                row = cursor.fetchone()
                maps_won = row[0] or 0
                maps_lost = row[1] or 0
                total_maps = maps_won + maps_lost
                map_win_rate = (maps_won / total_maps * 100) if total_maps > 0 else 0.0
                
                # Insert/update
                cursor.execute("""
                    INSERT OR REPLACE INTO team_stats
                    (team_name, total_matches, wins, losses, win_rate, maps_won, maps_lost, map_win_rate, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (team, total_matches, wins, losses, win_rate, maps_won, maps_lost, map_win_rate))
            
            conn.commit()
            self.logger.info(f"Updated stats for {len(teams)} teams")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update team stats: {e}")
            raise
        finally:
            conn.close()
    
    def _update_team_mode_stats(self):
        """Update team statistics by game mode"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all team-mode combinations
            cursor.execute("""
                SELECT DISTINCT 
                    CASE WHEN m.team_a = ? THEN m.team_a ELSE m.team_b END as team,
                    mr.mode
                FROM map_results mr
                JOIN matches m ON mr.match_id = m.match_id
                CROSS JOIN (SELECT DISTINCT team_a as team FROM matches UNION SELECT DISTINCT team_b FROM matches) teams
                WHERE m.team_a = teams.team OR m.team_b = teams.team
            """, ('',))  # Empty string won't match, forces DISTINCT on all combinations
            
            # Simpler approach: get all teams and modes
            cursor.execute("SELECT DISTINCT team_a FROM matches UNION SELECT DISTINCT team_b FROM matches")
            teams = [row[0] for row in cursor.fetchall()]
            
            cursor.execute("SELECT DISTINCT mode FROM map_results")
            modes = [row[0] for row in cursor.fetchall()]
            
            for team in teams:
                for mode in modes:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as wins,
                            AVG(CASE WHEN m.team_a = ? THEN mr.team_a_score ELSE mr.team_b_score END) as avg_score_for,
                            AVG(CASE WHEN m.team_a = ? THEN mr.team_b_score ELSE mr.team_a_score END) as avg_score_against
                        FROM map_results mr
                        JOIN matches m ON mr.match_id = m.match_id
                        WHERE (m.team_a = ? OR m.team_b = ?) AND mr.mode = ?
                    """, (team, team, team, team, team, mode))
                    
                    row = cursor.fetchone()
                    total = row[0] or 0
                    
                    if total > 0:
                        wins = row[1] or 0
                        losses = total - wins
                        win_rate = (wins / total * 100) if total > 0 else 0.0
                        avg_score_for = row[2] or 0.0
                        avg_score_against = row[3] or 0.0
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO team_mode_stats
                            (team_name, mode, wins, losses, win_rate, avg_score_for, avg_score_against, last_updated)
                            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (team, mode, wins, losses, win_rate, avg_score_for, avg_score_against))
            
            conn.commit()
            self.logger.info(f"Updated mode stats for {len(teams)} teams across {len(modes)} modes")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update team mode stats: {e}")
            raise
        finally:
            conn.close()
    
    def _update_team_map_mode_stats(self):
        """Update team statistics by map-mode combination"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all teams, maps, and modes
            cursor.execute("SELECT DISTINCT team_a FROM matches UNION SELECT DISTINCT team_b FROM matches")
            teams = [row[0] for row in cursor.fetchall()]
            
            cursor.execute("SELECT DISTINCT map_name, mode FROM map_results")
            map_modes = cursor.fetchall()
            
            for team in teams:
                for map_name, mode in map_modes:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as wins,
                            AVG(CASE WHEN m.team_a = ? THEN mr.team_a_score ELSE mr.team_b_score END) as avg_score_for,
                            AVG(CASE WHEN m.team_a = ? THEN mr.team_b_score ELSE mr.team_a_score END) as avg_score_against,
                            MAX(m.match_date) as last_played
                        FROM map_results mr
                        JOIN matches m ON mr.match_id = m.match_id
                        WHERE (m.team_a = ? OR m.team_b = ?) 
                          AND mr.map_name = ? 
                          AND mr.mode = ?
                    """, (team, team, team, team, team, map_name, mode))
                    
                    row = cursor.fetchone()
                    total = row[0] or 0
                    
                    if total > 0:
                        wins = row[1] or 0
                        losses = total - wins
                        win_rate = (wins / total * 100) if total > 0 else 0.0
                        avg_score_for = row[2] or 0.0
                        avg_score_against = row[3] or 0.0
                        last_played = row[4]
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO team_map_mode_stats
                            (team_name, map_name, mode, wins, losses, win_rate, 
                             avg_score_for, avg_score_against, total_played, last_played, last_updated)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (team, map_name, mode, wins, losses, win_rate, 
                              avg_score_for, avg_score_against, total, last_played))
            
            conn.commit()
            self.logger.info(f"Updated map-mode stats for {len(teams)} teams")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update team map-mode stats: {e}")
            raise
        finally:
            conn.close()
    
    def _update_head_to_head(self):
        """Update head-to-head records between teams"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all team pairs
            cursor.execute("""
                SELECT DISTINCT 
                    CASE WHEN team_a < team_b THEN team_a ELSE team_b END as t1,
                    CASE WHEN team_a < team_b THEN team_b ELSE team_a END as t2
                FROM matches
            """)
            
            team_pairs = cursor.fetchall()
            
            for team_a, team_b in team_pairs:
                # Match wins
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as team_a_wins,
                        SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as team_b_wins,
                        MAX(match_date) as last_match_date
                    FROM matches
                    WHERE (team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?)
                """, (team_a, team_b, team_a, team_b, team_b, team_a))
                
                row = cursor.fetchone()
                team_a_wins = row[0] or 0
                team_b_wins = row[1] or 0
                last_match_date = row[2]
                
                # Map wins
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as team_a_map_wins,
                        SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as team_b_map_wins
                    FROM map_results mr
                    JOIN matches m ON mr.match_id = m.match_id
                    WHERE (m.team_a = ? AND m.team_b = ?) OR (m.team_a = ? AND m.team_b = ?)
                """, (team_a, team_b, team_a, team_b, team_b, team_a))
                
                row = cursor.fetchone()
                team_a_map_wins = row[0] or 0
                team_b_map_wins = row[1] or 0
                
                cursor.execute("""
                    INSERT OR REPLACE INTO head_to_head
                    (team_a, team_b, team_a_wins, team_b_wins, 
                     team_a_map_wins, team_b_map_wins, last_match_date, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (team_a, team_b, team_a_wins, team_b_wins, 
                      team_a_map_wins, team_b_map_wins, last_match_date))
            
            conn.commit()
            self.logger.info(f"Updated head-to-head for {len(team_pairs)} team pairs")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update head-to-head: {e}")
            raise
        finally:
            conn.close()
    
    def _update_head_to_head_map_mode(self):
        """Update head-to-head records by map-mode combination"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all team pairs with map-mode combinations
            cursor.execute("""
                SELECT DISTINCT 
                    CASE WHEN m.team_a < m.team_b THEN m.team_a ELSE m.team_b END as t1,
                    CASE WHEN m.team_a < m.team_b THEN m.team_b ELSE m.team_a END as t2,
                    mr.map_name,
                    mr.mode
                FROM map_results mr
                JOIN matches m ON mr.match_id = m.match_id
            """)
            
            combinations = cursor.fetchall()
            
            for team_a, team_b, map_name, mode in combinations:
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as team_a_wins,
                        SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as team_b_wins,
                        MAX(m.match_date) as last_played
                    FROM map_results mr
                    JOIN matches m ON mr.match_id = m.match_id
                    WHERE ((m.team_a = ? AND m.team_b = ?) OR (m.team_a = ? AND m.team_b = ?))
                      AND mr.map_name = ?
                      AND mr.mode = ?
                """, (team_a, team_b, team_a, team_b, team_b, team_a, map_name, mode))
                
                row = cursor.fetchone()
                team_a_wins = row[0] or 0
                team_b_wins = row[1] or 0
                last_played = row[2]
                
                if team_a_wins + team_b_wins > 0:
                    cursor.execute("""
                        INSERT OR REPLACE INTO head_to_head_map_mode
                        (team_a, team_b, map_name, mode, team_a_wins, team_b_wins, last_played, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (team_a, team_b, map_name, mode, team_a_wins, team_b_wins, last_played))
            
            conn.commit()
            self.logger.info(f"Updated head-to-head map-mode stats for {len(combinations)} combinations")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update head-to-head map-mode: {e}")
            raise
        finally:
            conn.close()
    
    def _update_player_stats(self):
        """Update player average statistics"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all players
            cursor.execute("SELECT DISTINCT player_name FROM player_match_stats")
            players = [row[0] for row in cursor.fetchall()]
            
            for player in players:
                cursor.execute("""
                    SELECT 
                        ? as player_name,
                        team as current_team,
                        COUNT(*) as total_matches,
                        AVG(kills) as avg_kills,
                        AVG(deaths) as avg_deaths,
                        AVG(kd) as avg_kd,
                        AVG(damage) as avg_damage,
                        AVG(rating) as avg_rating,
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        SUM(damage) as total_damage
                    FROM player_match_stats
                    WHERE player_name = ?
                    GROUP BY player_name
                """, (player, player))
                
                row = cursor.fetchone()
                if row:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_stats
                        (player_name, current_team, total_matches, avg_kills, avg_deaths, avg_kd,
                         avg_damage, avg_rating, total_kills, total_deaths, total_damage, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, tuple(row))
            
            conn.commit()
            self.logger.info(f"Updated stats for {len(players)} players")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update player stats: {e}")
            raise
        finally:
            conn.close()
    
    def _update_player_mode_stats(self):
        """Update player statistics by game mode"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all player-mode combinations
            cursor.execute("SELECT DISTINCT player_name FROM player_map_stats")
            players = [row[0] for row in cursor.fetchall()]
            
            cursor.execute("SELECT DISTINCT mode FROM player_map_stats")
            modes = [row[0] for row in cursor.fetchall()]
            
            for player in players:
                for mode in modes:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as maps_played,
                            AVG(kills) as avg_kills,
                            AVG(deaths) as avg_deaths,
                            AVG(kd) as avg_kd,
                            AVG(damage) as avg_damage,
                            AVG(rating) as avg_rating,
                            SUM(kills) as total_kills,
                            SUM(deaths) as total_deaths,
                            SUM(damage) as total_damage
                        FROM player_map_stats
                        WHERE player_name = ? AND mode = ?
                    """, (player, mode))
                    
                    row = cursor.fetchone()
                    maps_played = row[0] or 0
                    
                    if maps_played > 0:
                        cursor.execute("""
                            INSERT OR REPLACE INTO player_mode_stats
                            (player_name, mode, maps_played, avg_kills, avg_deaths, avg_kd,
                             avg_damage, avg_rating, total_kills, total_deaths, total_damage, last_updated)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (player, mode) + tuple(row))
            
            conn.commit()
            self.logger.info(f"Updated mode stats for {len(players)} players across {len(modes)} modes")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update player mode stats: {e}")
            raise
        finally:
            conn.close()
    
    def _update_player_map_mode_stats(self):
        """Update player statistics by map-mode combination"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all player-map-mode combinations
            cursor.execute("""
                SELECT DISTINCT player_name, map_name, mode 
                FROM player_map_stats
            """)
            combinations = cursor.fetchall()
            
            for player, map_name, mode in combinations:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as maps_played,
                        AVG(kills) as avg_kills,
                        AVG(deaths) as avg_deaths,
                        AVG(kd) as avg_kd,
                        AVG(damage) as avg_damage,
                        AVG(rating) as avg_rating,
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        SUM(damage) as total_damage
                    FROM player_map_stats
                    WHERE player_name = ? AND map_name = ? AND mode = ?
                """, (player, map_name, mode))
                
                row = cursor.fetchone()
                if row and row[0] > 0:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_map_mode_stats
                        (player_name, map_name, mode, maps_played, avg_kills, avg_deaths, avg_kd,
                         avg_damage, avg_rating, total_kills, total_deaths, total_damage, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (player, map_name, mode) + tuple(row))
            
            conn.commit()
            self.logger.info(f"Updated map-mode stats for {len(combinations)} player combinations")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update player map-mode stats: {e}")
            raise
        finally:
            conn.close()
    
    def get_head_to_head_count(self, team_a: str, team_b: str, year: str = None) -> int:
        """Get count of matches between two teams (optionally in a specific year)
        
        Args:
            team_a: First team name
            team_b: Second team name
            year: Optional year filter (e.g., "2026")
        
        Returns:
            Number of matches between the teams
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            if year:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM matches 
                    WHERE ((team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?))
                    AND strftime('%Y', match_date) = ?
                """, (team_a, team_b, team_b, team_a, year))
            else:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM matches 
                    WHERE (team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?)
                """, (team_a, team_b, team_b, team_a))
            
            return cursor.fetchone()[0]
            
        finally:
            conn.close()
    
    def get_team_map_mode_stats(self, team_name: str, map_name: str = None, mode: str = None) -> List[Dict]:
        """Get team statistics for specific map-mode combinations
        
        Args:
            team_name: Name of the team
            map_name: Optional map name filter
            mode: Optional mode filter
        
        Returns:
            List of stat dictionaries
        """
        conn = self.get_connection()
        try:
            query = "SELECT * FROM team_map_mode_stats WHERE team_name = ?"
            params = [team_name]
            
            if map_name:
                query += " AND map_name = ?"
                params.append(map_name)
            
            if mode:
                query += " AND mode = ?"
                params.append(mode)
            
            query += " ORDER BY total_played DESC"
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            return [dict(row) for row in cursor.fetchall()]
            
        finally:
            conn.close()
