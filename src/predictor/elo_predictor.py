"""
Elo/Glicko-style rating system for CDL teams
Dynamic ratings that update after each match based on results
"""
import logging
import math
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import pickle
from pathlib import Path

from src.database.db_manager import DatabaseManager
from config.settings import DATA_DIR


class EloPredictor:
    """Elo rating system for team predictions"""
    
    def __init__(self, k_factor: float = 32, initial_rating: float = 1500):
        """
        Initialize Elo predictor
        
        Args:
            k_factor: How much ratings change per match (default: 32)
            initial_rating: Starting rating for new team rosters (default: 1500)
        """
        self.db = DatabaseManager()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.ratings_file = DATA_DIR / "elo_ratings.pkl"
        
        # {(team_name, roster_hash): {'rating': float, 'matches': int, 'last_update': str}}
        self.ratings = self._load_ratings()
        
    def _load_ratings(self) -> Dict:
        """Load saved ratings from disk"""
        if self.ratings_file.exists():
            try:
                with open(self.ratings_file, 'rb') as f:
                    ratings = pickle.load(f)
                self.logger.info(f"Loaded {len(ratings)} Elo ratings from disk")
                return ratings
            except Exception as e:
                self.logger.warning(f"Failed to load ratings: {e}")
        return {}
    
    def _save_ratings(self):
        """Save current ratings to disk"""
        try:
            with open(self.ratings_file, 'wb') as f:
                pickle.dump(self.ratings, f)
        except Exception as e:
            self.logger.error(f"Failed to save ratings: {e}")
    
    def _get_roster_hash(self, roster: List[str]) -> str:
        """Create consistent hash from roster"""
        return "|".join(sorted(roster))
    
    def _get_team_key(self, team: str, roster: List[str]) -> Tuple[str, str]:
        """Get unique key for team+roster combination"""
        return (team, self._get_roster_hash(roster))
    
    def get_rating(self, team: str, roster: List[str]) -> Dict:
        """Get current Elo rating for team with specific roster
        
        Returns:
            Dict with rating, matches played, last update
        """
        key = self._get_team_key(team, roster)
        
        if key not in self.ratings:
            # New roster - inherit partial rating from team's other rosters
            inherited_rating = self._inherit_rating(team, roster)
            self.ratings[key] = {
                'rating': inherited_rating,
                'matches': 0,
                'last_update': datetime.now().strftime('%Y-%m-%d')
            }
        
        return self.ratings[key]
    
    def _inherit_rating(self, team: str, new_roster: List[str]) -> float:
        """Inherit rating from previous rosters based on player overlap"""
        # Find all rosters for this team
        team_rosters = [
            (roster_hash, data) 
            for (t, roster_hash), data in self.ratings.items() 
            if t == team
        ]
        
        if not team_rosters:
            return self.initial_rating
        
        # Calculate weighted average based on player overlap
        total_weight = 0
        weighted_rating = 0
        new_roster_set = set(new_roster)
        
        for roster_hash, data in team_rosters:
            old_roster = set(roster_hash.split('|'))
            overlap = len(new_roster_set & old_roster)
            weight = overlap / 4.0  # 4 players max
            
            if weight > 0:
                weighted_rating += data['rating'] * weight
                total_weight += weight
        
        if total_weight > 0:
            # Blend inherited rating with base rating (80% inherited, 20% base)
            inherited = weighted_rating / total_weight
            return inherited * 0.8 + self.initial_rating * 0.2
        
        return self.initial_rating
    
    def calculate_expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calculate expected win probability using Elo formula
        
        Args:
            rating_a: Team A's Elo rating
            rating_b: Team B's Elo rating
        
        Returns:
            Expected probability for Team A (0.0 to 1.0)
        """
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    def predict(self, team_a: str, team_b: str) -> Dict:
        """Predict match outcome using Elo ratings
        
        Args:
            team_a: First team name
            team_b: Second team name
        
        Returns:
            Dictionary with prediction results
        """
        # Get current rosters
        roster_a = self._get_current_roster(team_a)
        roster_b = self._get_current_roster(team_b)
        
        if not roster_a or not roster_b:
            raise ValueError(f"Could not find roster for one or both teams")
        
        # Get Elo ratings
        rating_data_a = self.get_rating(team_a, roster_a)
        rating_data_b = self.get_rating(team_b, roster_b)
        
        rating_a = rating_data_a['rating']
        rating_b = rating_data_b['rating']
        
        # Calculate probabilities
        prob_a = self.calculate_expected_score(rating_a, rating_b)
        prob_b = 1 - prob_a
        
        # Predict score based on probability
        if prob_a >= 0.75:
            predicted_score = "3-0"
        elif prob_a >= 0.65:
            predicted_score = "3-1"
        elif prob_a >= 0.55:
            predicted_score = "3-2"
        elif prob_a >= 0.45:
            predicted_score = "2-3"
        elif prob_a >= 0.35:
            predicted_score = "1-3"
        else:
            predicted_score = "0-3"
        
        return {
            'method': 'Elo Rating System',
            'team_a': team_a,
            'team_b': team_b,
            'team_a_roster': roster_a,
            'team_b_roster': roster_b,
            'team_a_rating': round(rating_a, 1),
            'team_b_rating': round(rating_b, 1),
            'team_a_matches': rating_data_a['matches'],
            'team_b_matches': rating_data_b['matches'],
            'team_a_win_probability': round(prob_a * 100, 1),
            'team_b_win_probability': round(prob_b * 100, 1),
            'predicted_winner': team_a if prob_a > prob_b else team_b,
            'predicted_score': predicted_score,
            'confidence': abs(prob_a - prob_b) * 100,
            'rating_difference': abs(rating_a - rating_b)
        }
    
    def update_ratings(self, team_a: str, roster_a: List[str], 
                      team_b: str, roster_b: List[str],
                      score_a: int, score_b: int, match_date: str):
        """Update Elo ratings after a match result
        
        Args:
            team_a: First team name
            roster_a: Team A roster
            team_b: Second team name  
            roster_b: Team B roster
            score_a: Team A map wins
            score_b: Team B map wins
            match_date: Date of match
        """
        key_a = self._get_team_key(team_a, roster_a)
        key_b = self._get_team_key(team_b, roster_b)
        
        # Get current ratings
        rating_data_a = self.get_rating(team_a, roster_a)
        rating_data_b = self.get_rating(team_b, roster_b)
        
        rating_a = rating_data_a['rating']
        rating_b = rating_data_b['rating']
        
        # Calculate expected scores
        expected_a = self.calculate_expected_score(rating_a, rating_b)
        expected_b = 1 - expected_a
        
        # Actual result (1 for win, 0 for loss)
        actual_a = 1 if score_a > score_b else 0
        actual_b = 1 - actual_a
        
        # Calculate rating changes
        # Use map score differential for magnitude (closer games = smaller swings)
        map_diff = abs(score_a - score_b)
        k_multiplier = 1.0 if map_diff <= 1 else 0.8  # Reduce K for blowouts
        
        change_a = k_multiplier * self.k_factor * (actual_a - expected_a)
        change_b = k_multiplier * self.k_factor * (actual_b - expected_b)
        
        # Update ratings
        new_rating_a = rating_a + change_a
        new_rating_b = rating_b + change_b
        
        # Update stored data
        self.ratings[key_a] = {
            'rating': new_rating_a,
            'matches': rating_data_a['matches'] + 1,
            'last_update': match_date
        }
        
        self.ratings[key_b] = {
            'rating': new_rating_b,
            'matches': rating_data_b['matches'] + 1,
            'last_update': match_date
        }
        
        self._save_ratings()
        
        self.logger.info(f"Updated Elo: {team_a} {rating_a:.1f} -> {new_rating_a:.1f} ({change_a:+.1f})")
        self.logger.info(f"Updated Elo: {team_b} {rating_b:.1f} -> {new_rating_b:.1f} ({change_b:+.1f})")
    
    def initialize_from_database(self, force: bool = False):
        """Initialize/recalculate all Elo ratings from match history
        
        Args:
            force: If True, recalculate even if ratings exist
        """
        if len(self.ratings) > 0 and not force:
            self.logger.info("Elo ratings already initialized. Use force=True to recalculate.")
            return
        
        self.logger.info("Initializing Elo ratings from match history...")
        self.ratings = {}
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Get all matches in chronological order
        cursor.execute("""
            SELECT match_id, team_a, team_b, team_a_score, team_b_score, match_date
            FROM matches
            ORDER BY match_date ASC, id ASC
        """)
        
        matches = cursor.fetchall()
        
        for match_id, team_a, team_b, score_a, score_b, match_date in matches:
            # Get rosters for this match
            cursor.execute("""
                SELECT DISTINCT player_name, team
                FROM player_match_stats
                WHERE match_id = ?
                ORDER BY team, player_name
            """, (match_id,))
            
            players = cursor.fetchall()
            roster_a = [p[0] for p in players if p[1] == team_a]
            roster_b = [p[0] for p in players if p[1] == team_b]
            
            if len(roster_a) == 4 and len(roster_b) == 4:
                # Update Elo ratings based on this match
                self.update_ratings(team_a, roster_a, team_b, roster_b, 
                                   score_a, score_b, match_date)
        
        conn.close()
        
        self.logger.info(f"Initialized {len(self.ratings)} team-roster Elo ratings from {len(matches)} matches")
        self._save_ratings()
    
    def _get_current_roster(self, team: str) -> List[str]:
        """Get current roster from most recent match"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT match_id 
                FROM matches 
                WHERE team_a = ? OR team_b = ?
                ORDER BY match_date DESC, id DESC
                LIMIT 1
            """, (team, team))
            
            result = cursor.fetchone()
            if not result:
                return []
            
            match_id = result[0]
            
            cursor.execute("""
                SELECT DISTINCT player_name
                FROM player_match_stats
                WHERE match_id = ? AND team = ?
            """, (match_id, team))
            
            roster = [row[0] for row in cursor.fetchall()]
            return roster
            
        finally:
            conn.close()
    
    def get_all_ratings(self) -> List[Dict]:
        """Get all current ratings sorted by rating (for leaderboard)"""
        ratings_list = []
        
        for (team, roster_hash), data in self.ratings.items():
            ratings_list.append({
                'team': team,
                'roster': roster_hash.split('|'),
                'rating': data['rating'],
                'matches': data['matches'],
                'last_update': data['last_update']
            })
        
        # Sort by rating descending
        ratings_list.sort(key=lambda x: x['rating'], reverse=True)
        return ratings_list
