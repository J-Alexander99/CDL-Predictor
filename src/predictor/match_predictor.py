"""
Match outcome predictor using roster-weighted statistics
"""
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from src.database.db_manager import DatabaseManager


class MatchPredictor:
    """Predicts match outcomes using roster-aware weighted statistics"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def predict(self, team_a: str, team_b: str) -> Dict:
        """
        Predict match outcome between two teams
        
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
        
        # Calculate weighted stats for both teams
        stats_a = self._calculate_weighted_stats(team_a, roster_a)
        stats_b = self._calculate_weighted_stats(team_b, roster_b)
        
        # Calculate roster quality from player stats
        quality_a = self._calculate_roster_quality(roster_a)
        quality_b = self._calculate_roster_quality(roster_b)
        
        stats_a['roster_quality'] = quality_a
        stats_b['roster_quality'] = quality_b
        
        # Get head-to-head history
        h2h = self._get_head_to_head(team_a, team_b)
        
        # Calculate win probabilities
        prob_a, prob_b = self._calculate_win_probability(stats_a, stats_b, h2h)
        
        # Predict map count using mode-specific stats
        map_prediction = self._predict_map_by_map(team_a, team_b, roster_a, roster_b, h2h)
        
        # Predict specific map picks/bans
        pick_ban_prediction = self._predict_pick_ban(team_a, team_b, roster_a, roster_b, h2h)
        
        return {
            'team_a': team_a,
            'team_b': team_b,
            'team_a_roster': roster_a,
            'team_b_roster': roster_b,
            'team_a_win_probability': prob_a,
            'team_b_win_probability': prob_b,
            'predicted_winner': map_prediction['winner'],
            'predicted_score': map_prediction['score'],
            'map_predictions': map_prediction['maps'],
            'pick_ban_prediction': pick_ban_prediction,
            'confidence': abs(prob_a - prob_b),
            'team_a_stats': stats_a,
            'team_b_stats': stats_b,
            'head_to_head': h2h
        }
    
    def _get_current_roster(self, team: str) -> List[str]:
        """Get current roster from most recent match"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            # Find most recent match for this team
            cursor.execute("""
                SELECT match_id, match_date 
                FROM matches 
                WHERE team_a = ? OR team_b = ?
                ORDER BY match_date DESC, id DESC
                LIMIT 1
            """, (team, team))
            
            result = cursor.fetchone()
            if not result:
                return []
            
            match_id = result[0]
            
            # Get players from that match
            cursor.execute("""
                SELECT DISTINCT player_name
                FROM player_match_stats
                WHERE match_id = ? AND team = ?
            """, (match_id, team))
            
            roster = [row[0] for row in cursor.fetchall()]
            return roster
            
        finally:
            conn.close()
    
    def _calculate_roster_overlap(self, current_roster: List[str], match_roster: List[str]) -> float:
        """Calculate roster overlap weight (0.0 to 1.0)"""
        current_set = set(current_roster)
        match_set = set(match_roster)
        overlap = len(current_set & match_set)
        
        # 4/4 = 1.0, 3/4 = 0.75, 2/4 = 0.5, 1/4 = 0.25, 0/4 = 0.0
        return overlap / 4.0
    
    def _calculate_weighted_stats(self, team: str, current_roster: List[str]) -> Dict:
        """Calculate team stats with roster overlap weighting"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all matches for this team
            cursor.execute("""
                SELECT m.match_id, m.team_a, m.team_b, m.winner, m.match_date,
                       mr.mode, mr.winner as map_winner
                FROM matches m
                LEFT JOIN map_results mr ON m.match_id = mr.match_id
                WHERE m.team_a = ? OR m.team_b = ?
                ORDER BY m.match_date DESC
            """, (team, team))
            
            matches = cursor.fetchall()
            
            if not matches:
                return self._empty_stats()
            
            # Group by match
            match_data = {}
            for row in matches:
                match_id = row[0]
                if match_id not in match_data:
                    match_data[match_id] = {
                        'team_a': row[1],
                        'team_b': row[2],
                        'winner': row[3],
                        'date': row[4],
                        'maps': []
                    }
                if row[5]:  # mode exists
                    match_data[match_id]['maps'].append({
                        'mode': row[5],
                        'winner': row[6]
                    })
            
            # Calculate weighted statistics
            total_weight = 0.0
            weighted_wins = 0.0
            weighted_maps_won = 0.0
            weighted_maps_played = 0.0
            match_count = 0
            
            for match_id, data in match_data.items():
                # Get roster for this match
                cursor.execute("""
                    SELECT DISTINCT player_name
                    FROM player_match_stats
                    WHERE match_id = ? AND team = ?
                """, (match_id, team))
                
                match_roster = [row[0] for row in cursor.fetchall()]
                weight = self._calculate_roster_overlap(current_roster, match_roster)
                
                if weight == 0:
                    continue
                
                # Apply weight
                total_weight += weight
                match_count += 1
                
                if data['winner'] == team:
                    weighted_wins += weight
                
                # Count maps
                for map_result in data['maps']:
                    weighted_maps_played += weight
                    if map_result['winner'] == team:
                        weighted_maps_won += weight
            
            if total_weight == 0:
                return self._empty_stats()
            
            # Calculate averages
            win_rate = (weighted_wins / total_weight) * 100 if total_weight > 0 else 0
            map_win_rate = (weighted_maps_won / weighted_maps_played) * 100 if weighted_maps_played > 0 else 0
            
            return {
                'matches_played': match_count,
                'weighted_matches': round(total_weight, 2),
                'win_rate': round(win_rate, 1),
                'map_win_rate': round(map_win_rate, 1),
                'weighted_wins': round(weighted_wins, 2),
                'weighted_maps_won': round(weighted_maps_won, 2),
                'weighted_maps_played': round(weighted_maps_played, 2)
            }
            
        finally:
            conn.close()
    
    def _empty_stats(self) -> Dict:
        """Return empty stats structure"""
        return {
            'matches_played': 0,
            'weighted_matches': 0,
            'win_rate': 0,
            'map_win_rate': 0,
            'weighted_wins': 0,
            'weighted_maps_won': 0,
            'weighted_maps_played': 0
        }
    
    def _calculate_roster_quality(self, roster: List[str]) -> Dict:
        """Calculate roster quality from individual player statistics"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            total_kd = 0.0
            total_rating = 0.0
            total_damage = 0.0
            player_count = 0
            
            for player in roster:
                cursor.execute("""
                    SELECT avg_kd, avg_rating, avg_damage
                    FROM player_stats
                    WHERE player_name = ?
                """, (player,))
                
                row = cursor.fetchone()
                if row:
                    total_kd += row[0] or 0
                    total_rating += row[1] or 0
                    total_damage += row[2] or 0
                    player_count += 1
            
            if player_count == 0:
                return {
                    'avg_kd': 0.0,
                    'avg_rating': 0.0,
                    'avg_damage': 0.0,
                    'player_count': 0
                }
            
            return {
                'avg_kd': round(total_kd / player_count, 2),
                'avg_rating': round(total_rating / player_count, 2),
                'avg_damage': round(total_damage / player_count, 0),
                'player_count': player_count
            }
            
        finally:
            conn.close()
    
    def _get_head_to_head(self, team_a: str, team_b: str) -> Dict:
        """Get head-to-head record between teams"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as team_a_wins,
                    SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as team_b_wins
                FROM matches
                WHERE (team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?)
            """, (team_a, team_b, team_a, team_b, team_b, team_a))
            
            row = cursor.fetchone()
            
            return {
                'total_matches': row[0] or 0,
                'team_a_wins': row[1] or 0,
                'team_b_wins': row[2] or 0
            }
            
        finally:
            conn.close()
    
    def _calculate_win_probability(self, stats_a: Dict, stats_b: Dict, h2h: Dict) -> Tuple[float, float]:
        """Calculate win probability for each team"""
        
        # Component 1: Team Chemistry (weighted roster performance)
        wr_a = stats_a['win_rate']
        wr_b = stats_b['win_rate']
        mwr_a = stats_a['map_win_rate']
        mwr_b = stats_b['map_win_rate']
        
        # Calculate chemistry score
        if wr_a + wr_b > 0:
            chemistry_prob_a = (wr_a / (wr_a + wr_b)) * 100
            chemistry_prob_b = (wr_b / (wr_a + wr_b)) * 100
            
            # Blend in map win rate
            if mwr_a + mwr_b > 0:
                map_prob_a = (mwr_a / (mwr_a + mwr_b)) * 100
                map_prob_b = (mwr_b / (mwr_a + mwr_b)) * 100
                chemistry_prob_a = chemistry_prob_a * 0.7 + map_prob_a * 0.3
                chemistry_prob_b = chemistry_prob_b * 0.7 + map_prob_b * 0.3
        else:
            chemistry_prob_a = 50.0
            chemistry_prob_b = 50.0
        
        # Component 2: Roster Quality (player stats)
        quality_a = stats_a['roster_quality']
        quality_b = stats_b['roster_quality']
        
        # Calculate quality score from K/D (60%), Rating (30%), Damage (10%)
        if quality_a['player_count'] > 0 and quality_b['player_count'] > 0:
            # K/D comparison
            kd_total = quality_a['avg_kd'] + quality_b['avg_kd']
            if kd_total > 0:
                kd_prob_a = (quality_a['avg_kd'] / kd_total) * 100
                kd_prob_b = (quality_b['avg_kd'] / kd_total) * 100
            else:
                kd_prob_a = kd_prob_b = 50.0
            
            # Rating comparison
            rating_total = quality_a['avg_rating'] + quality_b['avg_rating']
            if rating_total > 0:
                rating_prob_a = (quality_a['avg_rating'] / rating_total) * 100
                rating_prob_b = (quality_b['avg_rating'] / rating_total) * 100
            else:
                rating_prob_a = rating_prob_b = 50.0
            
            # Damage comparison
            damage_total = quality_a['avg_damage'] + quality_b['avg_damage']
            if damage_total > 0:
                damage_prob_a = (quality_a['avg_damage'] / damage_total) * 100
                damage_prob_b = (quality_b['avg_damage'] / damage_total) * 100
            else:
                damage_prob_a = damage_prob_b = 50.0
            
            # Weighted quality score
            quality_prob_a = kd_prob_a * 0.6 + rating_prob_a * 0.3 + damage_prob_a * 0.1
            quality_prob_b = kd_prob_b * 0.6 + rating_prob_b * 0.3 + damage_prob_b * 0.1
        else:
            quality_prob_a = 50.0
            quality_prob_b = 50.0
        
        # Determine weighting between chemistry and quality
        # More team history = more weight on chemistry
        # Less team history = more weight on player quality
        weighted_matches = stats_a['weighted_matches'] + stats_b['weighted_matches']
        if weighted_matches >= 8:
            # Lots of history: 70% chemistry, 30% quality
            chemistry_weight = 0.7
            quality_weight = 0.3
        elif weighted_matches >= 4:
            # Moderate history: 50% chemistry, 50% quality
            chemistry_weight = 0.5
            quality_weight = 0.5
        else:
            # Little history: 30% chemistry, 70% quality
            chemistry_weight = 0.3
            quality_weight = 0.7
        
        # Blend chemistry and quality
        prob_a = chemistry_prob_a * chemistry_weight + quality_prob_a * quality_weight
        prob_b = chemistry_prob_b * chemistry_weight + quality_prob_b * quality_weight
        
        # Adjust for head-to-head (if they've played before)
        if h2h['total_matches'] > 0:
            h2h_weight = min(h2h['total_matches'] * 0.05, 0.15)  # Max 15% influence
            h2h_prob_a = (h2h['team_a_wins'] / h2h['total_matches']) * 100
            h2h_prob_b = (h2h['team_b_wins'] / h2h['total_matches']) * 100
            
            prob_a = prob_a * (1 - h2h_weight) + h2h_prob_a * h2h_weight
            prob_b = prob_b * (1 - h2h_weight) + h2h_prob_b * h2h_weight
        
        # Normalize to 100%
        total = prob_a + prob_b
        prob_a = (prob_a / total) * 100
        prob_b = (prob_b / total) * 100
        
        return round(prob_a, 1), round(prob_b, 1)
    
    def _get_mode_stats(self, team: str, mode: str, roster: List[str]) -> Dict:
        """Get team stats for specific mode with roster weighting and score differential"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all maps of this mode for the team
            cursor.execute("""
                SELECT mr.match_id, mr.winner, mr.team_a_score, mr.team_b_score,
                       m.team_a, m.team_b
                FROM map_results mr
                JOIN matches m ON mr.match_id = m.match_id
                WHERE (m.team_a = ? OR m.team_b = ?) AND mr.mode = ?
            """, (team, team, mode))
            
            maps = cursor.fetchall()
            
            if not maps:
                return {
                    'win_rate': 0, 
                    'weighted_maps': 0,
                    'avg_score_diff': 0,
                    'maps_played': 0
                }
            
            total_weight = 0.0
            weighted_wins = 0.0
            total_score_diff = 0.0
            maps_played = 0
            
            for map_row in maps:
                match_id = map_row[0]
                winner = map_row[1]
                team_a_score = map_row[2]
                team_b_score = map_row[3]
                match_team_a = map_row[4]
                match_team_b = map_row[5]
                
                # Get roster for this match
                cursor.execute("""
                    SELECT DISTINCT player_name
                    FROM player_match_stats
                    WHERE match_id = ? AND team = ?
                """, (match_id, team))
                
                match_roster = [row[0] for row in cursor.fetchall()]
                weight = self._calculate_roster_overlap(roster, match_roster)
                
                if weight == 0:
                    continue
                
                # Calculate score differential
                if team == match_team_a:
                    score_diff = team_a_score - team_b_score
                else:
                    score_diff = team_b_score - team_a_score
                
                # Add weighted contribution based on score differential
                # Normalize score diff to a 0-1 multiplier (0.5 for close games, 1.0 for blowouts)
                # For modes with scores, weight wins by margin
                if team_a_score is not None and team_b_score is not None:
                    # Calculate differential weight (0.5 to 1.5 range)
                    # Close game (diff < 20): ~0.7-0.9
                    # Medium game (diff 20-100): ~0.9-1.2
                    # Blowout (diff > 100): 1.2-1.5
                    abs_diff = abs(score_diff)
                    diff_weight = 1.0 + (abs_diff / 300.0)  # Normalize to reasonable range
                    diff_weight = max(0.5, min(1.5, diff_weight))  # Cap between 0.5 and 1.5
                else:
                    # No score (Search & Destroy) - standard weight
                    diff_weight = 1.0
                
                total_weight += weight * diff_weight
                total_score_diff += score_diff * weight
                maps_played += 1
                
                if winner == team:
                    weighted_wins += weight * diff_weight
            
            if total_weight == 0:
                return {
                    'win_rate': 0, 
                    'weighted_maps': 0,
                    'avg_score_diff': 0,
                    'maps_played': 0
                }
            
            win_rate = (weighted_wins / total_weight) * 100
            avg_score_diff = total_score_diff / maps_played if maps_played > 0 else 0
            
            return {
                'win_rate': round(win_rate, 1),
                'weighted_maps': round(total_weight, 1),
                'avg_score_diff': round(avg_score_diff, 1),
                'maps_played': maps_played
            }
            
        finally:
            conn.close()
    
    def _predict_mode_winner(self, team_a: str, team_b: str, mode: str, 
                            roster_a: List[str], roster_b: List[str],
                            quality_a: Dict, quality_b: Dict, h2h: Dict) -> Dict:
        """Predict winner for a specific mode using full logic with H2H adjustment"""
        
        # Get mode-specific chemistry
        mode_stats_a = self._get_mode_stats(team_a, mode, roster_a)
        mode_stats_b = self._get_mode_stats(team_b, mode, roster_b)
        
        # Calculate chemistry probability for this mode
        wr_a = mode_stats_a['win_rate']
        wr_b = mode_stats_b['win_rate']
        
        if wr_a + wr_b > 0:
            chemistry_prob_a = (wr_a / (wr_a + wr_b)) * 100
            chemistry_prob_b = (wr_b / (wr_a + wr_b)) * 100
        else:
            chemistry_prob_a = 50.0
            chemistry_prob_b = 50.0
        
        # Calculate quality probability (from overall player stats)
        if quality_a['player_count'] > 0 and quality_b['player_count'] > 0:
            # K/D comparison
            kd_total = quality_a['avg_kd'] + quality_b['avg_kd']
            if kd_total > 0:
                kd_prob_a = (quality_a['avg_kd'] / kd_total) * 100
                kd_prob_b = (quality_b['avg_kd'] / kd_total) * 100
            else:
                kd_prob_a = kd_prob_b = 50.0
            
            # Rating comparison
            rating_total = quality_a['avg_rating'] + quality_b['avg_rating']
            if rating_total > 0:
                rating_prob_a = (quality_a['avg_rating'] / rating_total) * 100
                rating_prob_b = (quality_b['avg_rating'] / rating_total) * 100
            else:
                rating_prob_a = rating_prob_b = 50.0
            
            # Damage comparison
            damage_total = quality_a['avg_damage'] + quality_b['avg_damage']
            if damage_total > 0:
                damage_prob_a = (quality_a['avg_damage'] / damage_total) * 100
                damage_prob_b = (quality_b['avg_damage'] / damage_total) * 100
            else:
                damage_prob_a = damage_prob_b = 50.0
            
            # Weighted quality score
            quality_prob_a = kd_prob_a * 0.6 + rating_prob_a * 0.3 + damage_prob_a * 0.1
            quality_prob_b = kd_prob_b * 0.6 + rating_prob_b * 0.3 + damage_prob_b * 0.1
        else:
            quality_prob_a = 50.0
            quality_prob_b = 50.0
        
        # Determine weighting for THIS mode
        weighted_maps = mode_stats_a['weighted_maps'] + mode_stats_b['weighted_maps']
        if weighted_maps >= 6:
            # Lots of mode history: 70% chemistry, 30% quality
            chemistry_weight = 0.7
            quality_weight = 0.3
        elif weighted_maps >= 3:
            # Moderate mode history: 50% chemistry, 50% quality
            chemistry_weight = 0.5
            quality_weight = 0.5
        else:
            # Little mode history: 30% chemistry, 70% quality
            chemistry_weight = 0.3
            quality_weight = 0.7
        
        # Blend chemistry and quality for this mode
        prob_a = chemistry_prob_a * chemistry_weight + quality_prob_a * quality_weight
        prob_b = chemistry_prob_b * chemistry_weight + quality_prob_b * quality_weight
        
        # Apply head-to-head adjustment to mode prediction
        if h2h['total_matches'] > 0:
            h2h_weight = min(h2h['total_matches'] * 0.05, 0.15)  # Max 15% influence
            h2h_prob_a = (h2h['team_a_wins'] / h2h['total_matches']) * 100
            h2h_prob_b = (h2h['team_b_wins'] / h2h['total_matches']) * 100
            
            prob_a = prob_a * (1 - h2h_weight) + h2h_prob_a * h2h_weight
            prob_b = prob_b * (1 - h2h_weight) + h2h_prob_b * h2h_weight
        
        # Normalize
        total = prob_a + prob_b
        prob_a = (prob_a / total) * 100
        prob_b = (prob_b / total) * 100
        
        return {
            'team_a_probability': round(prob_a, 1),
            'team_b_probability': round(prob_b, 1),
            'predicted_winner': team_a if prob_a > prob_b else team_b,
            'team_a_mode_stats': mode_stats_a,
            'team_b_mode_stats': mode_stats_b
        }
    
    def _predict_map_by_map(self, team_a: str, team_b: str, roster_a: List[str], roster_b: List[str], h2h: Dict) -> Dict:
        """Predict each map based on typical CDL format with H2H adjustment"""
        
        # Get roster quality (used for all modes)
        quality_a = self._calculate_roster_quality(roster_a)
        quality_b = self._calculate_roster_quality(roster_b)
        
        # Typical CDL Best of 5 format
        map_sequence = [
            'Hardpoint',
            'Search & Destroy',
            'Overload',
            'Hardpoint',
            'Search & Destroy'
        ]
        
        team_a_wins = 0
        team_b_wins = 0
        map_predictions = []
        
        for map_num, mode in enumerate(map_sequence, 1):
            # Predict this specific mode using full logic with H2H
            mode_prediction = self._predict_mode_winner(
                team_a, team_b, mode, roster_a, roster_b, quality_a, quality_b, h2h
            )
            
            # Track wins
            if mode_prediction['predicted_winner'] == team_a:
                team_a_wins += 1
            else:
                team_b_wins += 1
            
            map_predictions.append({
                'map_number': map_num,
                'mode': mode,
                'predicted_winner': mode_prediction['predicted_winner'],
                'team_a_probability': mode_prediction['team_a_probability'],
                'team_b_probability': mode_prediction['team_b_probability'],
                'team_a_mode_stats': mode_prediction['team_a_mode_stats'],
                'team_b_mode_stats': mode_prediction['team_b_mode_stats']
            })
            
            # Check if match is over (first to 3)
            if team_a_wins == 3 or team_b_wins == 3:
                break
        
        # Determine winner and score
        if team_a_wins > team_b_wins:
            winner = team_a
            score = f"{team_a_wins}-{team_b_wins}"
        else:
            winner = team_b
            score = f"{team_b_wins}-{team_a_wins}"
        
        return {
            'winner': winner,
            'score': score,
            'team_a_map_wins': team_a_wins,
            'team_b_map_wins': team_b_wins,
            'maps': map_predictions
        }
    
    def _predict_map_count(self, prob_a: float, prob_b: float, stats_a: Dict, stats_b: Dict) -> str:
        """Predict final map score"""
        
        # Determine winner
        if prob_a > prob_b:
            winner_prob = prob_a
        else:
            winner_prob = prob_b
        
        # Map count based on win probability confidence
        if winner_prob >= 70:
            # Dominant win
            return "3-0" if prob_a > prob_b else "0-3"
        elif winner_prob >= 60:
            # Comfortable win
            return "3-1" if prob_a > prob_b else "1-3"
        else:
            # Close match
            return "3-2" if prob_a > prob_b else "2-3"
    
    def _get_map_performance(self, team: str, mode: str, roster: List[str]) -> Dict[str, Dict]:
        """Get team's performance on each specific map for a mode"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get performance on each map
            cursor.execute("""
                SELECT mr.map_name, mr.winner, mr.team_a_score, mr.team_b_score,
                       m.team_a, m.team_b, mr.match_id
                FROM map_results mr
                JOIN matches m ON mr.match_id = m.match_id
                WHERE (m.team_a = ? OR m.team_b = ?) AND mr.mode = ?
            """, (team, team, mode))
            
            maps_data = cursor.fetchall()
            
            map_stats = {}
            
            for map_name, winner, team_a_score, team_b_score, match_team_a, match_team_b, match_id in maps_data:
                # Get roster for this match
                cursor.execute("""
                    SELECT DISTINCT player_name
                    FROM player_match_stats
                    WHERE match_id = ? AND team = ?
                """, (match_id, team))
                
                match_roster = [row[0] for row in cursor.fetchall()]
                weight = self._calculate_roster_overlap(roster, match_roster)
                
                if weight == 0:
                    continue
                
                if map_name not in map_stats:
                    map_stats[map_name] = {
                        'weighted_plays': 0,
                        'weighted_wins': 0,
                        'win_rate': 0
                    }
                
                map_stats[map_name]['weighted_plays'] += weight
                if winner == team:
                    map_stats[map_name]['weighted_wins'] += weight
            
            # Calculate win rates
            for map_name in map_stats:
                if map_stats[map_name]['weighted_plays'] > 0:
                    map_stats[map_name]['win_rate'] = (
                        map_stats[map_name]['weighted_wins'] / map_stats[map_name]['weighted_plays']
                    ) * 100
            
            return map_stats
            
        finally:
            conn.close()
    
    def _predict_pick_ban(self, team_a: str, team_b: str, roster_a: List[str], roster_b: List[str], h2h: Dict) -> Dict:
        """Predict map pick/ban phase and resulting map pool"""
        
        # Get map pool for each mode
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get available maps per mode
            cursor.execute("""
                SELECT DISTINCT mode, map_name 
                FROM map_results 
                ORDER BY mode, map_name
            """)
            
            mode_maps = {}
            for mode, map_name in cursor.fetchall():
                if mode not in mode_maps:
                    mode_maps[mode] = []
                mode_maps[mode].append(map_name)
            
        finally:
            conn.close()
        
        # For each mode in the series, predict picks/bans
        map_sequence = ['Hardpoint', 'Search & Destroy', 'Overload', 'Hardpoint', 'Search & Destroy']
        predicted_maps = []
        used_maps_per_mode = {}  # Track which maps have been used for each mode
        
        for map_num, mode in enumerate(map_sequence, 1):
            if mode not in mode_maps:
                predicted_maps.append({
                    'map_number': map_num,
                    'mode': mode,
                    'predicted_map': 'Unknown',
                    'reasoning': 'No map data available'
                })
                continue
            
            # Initialize tracking for this mode
            if mode not in used_maps_per_mode:
                used_maps_per_mode[mode] = []
            
            # Get performance for both teams on each map
            team_a_perf = self._get_map_performance(team_a, mode, roster_a)
            team_b_perf = self._get_map_performance(team_b, mode, roster_b)
            
            # Calculate preference scores for each map (excluding already used maps for this mode)
            map_scores = {}
            for map_name in mode_maps[mode]:
                # Skip if this map was already used for this mode
                if map_name in used_maps_per_mode[mode]:
                    continue
                
                a_wr = team_a_perf.get(map_name, {}).get('win_rate', 50)
                b_wr = team_b_perf.get(map_name, {}).get('win_rate', 50)
                a_plays = team_a_perf.get(map_name, {}).get('weighted_plays', 0)
                b_plays = team_b_perf.get(map_name, {}).get('weighted_plays', 0)
                
                # Team A's advantage on this map
                advantage_a = a_wr - b_wr
                
                # Confidence factor (more plays = more confidence)
                confidence = min(a_plays + b_plays, 10) / 10
                
                map_scores[map_name] = {
                    'advantage_a': advantage_a * confidence,
                    'team_a_wr': a_wr,
                    'team_b_wr': b_wr,
                    'team_a_plays': a_plays,
                    'team_b_plays': b_plays
                }
            
            # Predict likely map:
            # Teams will pick maps where they have advantage
            # Most likely map is one where the "picking team" has highest advantage
            # Simplification: Pick the map with highest combined play rate and best balance
            if map_scores:
                # Find map with most data and closest to 50/50 or slight advantage to better team
                best_map = max(map_scores.items(), 
                              key=lambda x: x[1]['team_a_plays'] + x[1]['team_b_plays'])
                
                # Mark this map as used for this mode
                used_maps_per_mode[mode].append(best_map[0])
                
                predicted_maps.append({
                    'map_number': map_num,
                    'mode': mode,
                    'predicted_map': best_map[0],
                    'team_a_winrate': round(best_map[1]['team_a_wr'], 1),
                    'team_b_winrate': round(best_map[1]['team_b_wr'], 1),
                    'team_a_plays': round(best_map[1]['team_a_plays'], 1),
                    'team_b_plays': round(best_map[1]['team_b_plays'], 1),
                    'reasoning': f"Most played map in pool ({best_map[1]['team_a_plays'] + best_map[1]['team_b_plays']:.1f} combined weighted plays)"
                })
            else:
                # Fallback: find any unused map for this mode
                available = [m for m in mode_maps[mode] if m not in used_maps_per_mode[mode]]
                if available:
                    chosen_map = available[0]
                    used_maps_per_mode[mode].append(chosen_map)
                    predicted_maps.append({
                        'map_number': map_num,
                        'mode': mode,
                        'predicted_map': chosen_map,
                        'reasoning': 'Insufficient data, selected unused map from pool'
                    })
                else:
                    predicted_maps.append({
                        'map_number': map_num,
                        'mode': mode,
                        'predicted_map': mode_maps[mode][0] if mode_maps[mode] else 'Unknown',
                        'reasoning': 'All maps used, defaulting to first map in pool'
                    })
        
        return {
            'predicted_maps': predicted_maps
        }
