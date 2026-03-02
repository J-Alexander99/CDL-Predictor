"""
Map-specific match prediction
Predicts individual maps in a series for more accurate score predictions
"""
import sqlite3
from typing import Dict, List, Tuple, Optional
from src.database import DatabaseManager
import math


class MapPredictor:
    """Predict individual maps in a match series"""
    
    def __init__(self):
        self.db = DatabaseManager()
        # CDL typical map rotation (BO5)
        self.map_rotation = [
            'Hardpoint',
            'Search & Destroy',
            'Control',
            'Hardpoint',
            'Search & Destroy'
        ]
    
    def get_team_map_mode_stats(self, team: str, map_name: Optional[str], mode: str) -> Dict:
        """Get team's stats for a specific map-mode combination"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        if map_name:
            # Get specific map-mode stats
            cursor.execute("""
                SELECT wins, losses, win_rate, avg_score_for, avg_score_against
                FROM team_map_mode_stats
                WHERE team_name = ? AND map_name = ? AND mode = ?
            """, (team, map_name, mode))
        else:
            # Get mode-only stats (average across all maps of this mode)
            cursor.execute("""
                SELECT 
                    SUM(wins) as wins,
                    SUM(losses) as losses,
                    CASE WHEN SUM(wins) + SUM(losses) > 0 
                        THEN CAST(SUM(wins) AS REAL) / (SUM(wins) + SUM(losses))
                        ELSE 0.5 
                    END as win_rate,
                    AVG(avg_score_for) as avg_score_for,
                    AVG(avg_score_against) as avg_score_against
                FROM team_map_mode_stats
                WHERE team_name = ? AND mode = ?
            """, (team, mode))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'wins': row[0] or 0,
                'losses': row[1] or 0,
                'win_rate': row[2] or 0.5,
                'avg_score_for': row[3] or 0,
                'avg_score_against': row[4] or 0,
                'matches': (row[0] or 0) + (row[1] or 0)
            }
        
        # Return neutral defaults if no data
        return {
            'wins': 0,
            'losses': 0,
            'win_rate': 0.5,
            'avg_score_for': 0,
            'avg_score_against': 0,
            'matches': 0
        }
    
    def predict_single_map(self, team_a: str, team_b: str, mode: str, 
                          map_name: Optional[str] = None) -> Dict:
        """Predict the outcome of a single map"""
        
        # Get stats for both teams
        stats_a = self.get_team_map_mode_stats(team_a, map_name, mode)
        stats_b = self.get_team_map_mode_stats(team_b, map_name, mode)
        
        # If neither team has data, return 50-50
        if stats_a['matches'] == 0 and stats_b['matches'] == 0:
            return {
                'mode': mode,
                'map_name': map_name or 'Unknown',
                'team_a_probability': 50.0,
                'team_b_probability': 50.0,
                'predicted_winner': team_a,  # Default to team_a
                'confidence': 0.0,
                'data_quality': 'no_data',
                'team_a_matches': 0,
                'team_b_matches': 0
            }
        
        # Weight by sample size (more matches = more reliable)
        weight_a = min(stats_a['matches'] / 10, 1.0)  # Cap at 10 matches
        weight_b = min(stats_b['matches'] / 10, 1.0)
        
        # Calculate probability based on historical win rates
        # Use Bayesian approach with prior of 0.5
        prior = 0.5
        
        # Weighted average of win rate (more matches = more weight)
        prob_a = (prior + (stats_a['win_rate'] * weight_a)) / (1 + weight_a)
        prob_b = (prior + (stats_b['win_rate'] * weight_b)) / (1 + weight_b)
        
        # Normalize probabilities to sum to 100%
        total = prob_a + (1 - prob_b)
        if total > 0:
            prob_a_final = (prob_a / total) * 100
            prob_b_final = ((1 - prob_b) / total) * 100
        else:
            prob_a_final = 50.0
            prob_b_final = 50.0
        
        # Determine winner
        winner = team_a if prob_a_final > prob_b_final else team_b
        confidence = abs(prob_a_final - prob_b_final)
        
        # Data quality indicator
        if stats_a['matches'] >= 5 and stats_b['matches'] >= 5:
            data_quality = 'high'
        elif stats_a['matches'] >= 3 or stats_b['matches'] >= 3:
            data_quality = 'medium'
        else:
            data_quality = 'low'
        
        return {
            'mode': mode,
            'map_name': map_name or 'Unknown',
            'team_a_probability': round(prob_a_final, 1),
            'team_b_probability': round(prob_b_final, 1),
            'predicted_winner': winner,
            'confidence': round(confidence, 1),
            'data_quality': data_quality,
            'team_a_matches': stats_a['matches'],
            'team_b_matches': stats_b['matches']
        }
    
    def predict_series(self, team_a: str, team_b: str, 
                      map_names: Optional[List[str]] = None) -> Dict:
        """
        Predict a full BO5 series map-by-map
        
        Args:
            team_a: First team name
            team_b: Second team name
            map_names: Optional list of specific maps (must match rotation length)
        
        Returns:
            Dictionary with map-by-map predictions and overall score
        """
        
        if map_names and len(map_names) != len(self.map_rotation):
            raise ValueError(f"map_names must have {len(self.map_rotation)} maps")
        
        map_predictions = []
        team_a_maps = 0
        team_b_maps = 0
        
        # Predict each map
        for i, mode in enumerate(self.map_rotation):
            map_name = map_names[i] if map_names else None
            
            prediction = self.predict_single_map(team_a, team_b, mode, map_name)
            map_predictions.append(prediction)
            
            # Track map wins
            if prediction['predicted_winner'] == team_a:
                team_a_maps += 1
            else:
                team_b_maps += 1
            
            # Check if series is already won (first to 3)
            if team_a_maps == 3 or team_b_maps == 3:
                break
        
        # Determine overall winner and score
        if team_a_maps > team_b_maps:
            winner = team_a
            score = f"{team_a_maps}-{team_b_maps}"
        else:
            winner = team_b
            score = f"{team_b_maps}-{team_a_maps}"
        
        # Calculate overall confidence (average of map confidences)
        avg_confidence = sum(p['confidence'] for p in map_predictions) / len(map_predictions)
        
        # Calculate data quality score
        quality_scores = {'high': 3, 'medium': 2, 'low': 1, 'no_data': 0}
        avg_quality = sum(quality_scores[p['data_quality']] for p in map_predictions) / len(map_predictions)
        
        if avg_quality >= 2.5:
            overall_quality = 'high'
        elif avg_quality >= 1.5:
            overall_quality = 'medium'
        else:
            overall_quality = 'low'
        
        return {
            'team_a': team_a,
            'team_b': team_b,
            'predicted_winner': winner,
            'predicted_score': score,
            'team_a_maps': team_a_maps,
            'team_b_maps': team_b_maps,
            'confidence': round(avg_confidence, 1),
            'data_quality': overall_quality,
            'map_predictions': map_predictions,
            'maps_predicted': len(map_predictions)
        }
    
    def get_map_pool(self, mode: str) -> List[str]:
        """Get the current map pool for a given mode"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT map_name
            FROM map_results
            WHERE mode = ?
            ORDER BY map_name
        """, (mode,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
