"""
Track prediction accuracy over time
Log predictions before matches and compare to actual results
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from src.database import DatabaseManager


class AccuracyTracker:
    """Track and analyze prediction accuracy"""
    
    def __init__(self, db_path: str = "data/predictions.db"):
        self.db_path = db_path
        self._ensure_database()
    
    def _ensure_database(self):
        """Create predictions database if it doesn't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_date TEXT NOT NULL,
                team_a TEXT NOT NULL,
                team_b TEXT NOT NULL,
                
                -- Predictions
                statistical_winner TEXT,
                statistical_score TEXT,
                statistical_probability REAL,
                
                elo_winner TEXT,
                elo_score TEXT,
                elo_probability REAL,
                
                ml_winner TEXT,
                ml_score TEXT,
                ml_probability REAL,
                
                ensemble_winner TEXT,
                ensemble_score TEXT,
                ensemble_probability REAL,
                ensemble_confidence REAL,
                
                -- Actual result (NULL until match is played)
                actual_winner TEXT,
                actual_score TEXT,
                
                -- Metadata
                prediction_timestamp TEXT NOT NULL,
                result_timestamp TEXT,
                notes TEXT,
                
                UNIQUE(match_date, team_a, team_b)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_prediction(self, team_a: str, team_b: str, predictions: Dict, 
                       match_date: str, notes: str = None):
        """Save a prediction before the match"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stat = predictions['predictions'].get('statistical', {})
        elo = predictions['predictions'].get('elo', {})
        ml = predictions['predictions'].get('ml', {})
        ens = predictions.get('ensemble', {})
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO predictions (
                    match_date, team_a, team_b,
                    statistical_winner, statistical_score, statistical_probability,
                    elo_winner, elo_score, elo_probability,
                    ml_winner, ml_score, ml_probability,
                    ensemble_winner, ensemble_score, ensemble_probability, ensemble_confidence,
                    prediction_timestamp, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_date, team_a, team_b,
                stat.get('predicted_winner'), stat.get('predicted_score'), stat.get('team_a_probability'),
                elo.get('predicted_winner'), elo.get('predicted_score'), elo.get('team_a_probability'),
                ml.get('predicted_winner'), ml.get('predicted_score'), ml.get('team_a_probability'),
                ens.get('predicted_winner'), ens.get('predicted_score'), ens.get('team_a_probability'),
                ens.get('confidence'),
                datetime.now().isoformat(), notes
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving prediction: {e}")
            return False
        finally:
            conn.close()
    
    def record_result(self, team_a: str, team_b: str, match_date: str, 
                     winner: str, score: str):
        """Record the actual result of a match"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE predictions 
                SET actual_winner = ?, actual_score = ?, result_timestamp = ?
                WHERE match_date = ? AND team_a = ? AND team_b = ?
            """, (winner, score, datetime.now().isoformat(), match_date, team_a, team_b))
            
            if cursor.rowcount == 0:
                print(f"No prediction found for {team_a} vs {team_b} on {match_date}")
                return False
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error recording result: {e}")
            return False
        finally:
            conn.close()
    
    def get_accuracy_stats(self, min_predictions: int = 1) -> Dict:
        """Calculate accuracy statistics for all models"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all predictions with actual results
        cursor.execute("""
            SELECT 
                statistical_winner, elo_winner, ml_winner, ensemble_winner,
                statistical_score, elo_score, ml_score, ensemble_score,
                actual_winner, actual_score,
                ensemble_confidence
            FROM predictions
            WHERE actual_winner IS NOT NULL
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < min_predictions:
            return {
                'total_predictions': len(rows),
                'message': f'Not enough data (minimum {min_predictions} predictions needed)'
            }
        
        stats = {
            'statistical': {'correct': 0, 'correct_score': 0, 'total': 0},
            'elo': {'correct': 0, 'correct_score': 0, 'total': 0},
            'ml': {'correct': 0, 'correct_score': 0, 'total': 0},
            'ensemble': {'correct': 0, 'correct_score': 0, 'total': 0, 
                        'high_conf_correct': 0, 'high_conf_total': 0}
        }
        
        for row in rows:
            stat_win, elo_win, ml_win, ens_win = row[0], row[1], row[2], row[3]
            stat_score, elo_score, ml_score, ens_score = row[4], row[5], row[6], row[7]
            actual_win, actual_score = row[8], row[9]
            ens_conf = row[10]
            
            # Statistical model
            if stat_win:
                stats['statistical']['total'] += 1
                if stat_win == actual_win:
                    stats['statistical']['correct'] += 1
                    if stat_score == actual_score:
                        stats['statistical']['correct_score'] += 1
            
            # Elo model
            if elo_win:
                stats['elo']['total'] += 1
                if elo_win == actual_win:
                    stats['elo']['correct'] += 1
                    if elo_score == actual_score:
                        stats['elo']['correct_score'] += 1
            
            # ML model
            if ml_win:
                stats['ml']['total'] += 1
                if ml_win == actual_win:
                    stats['ml']['correct'] += 1
                    if ml_score == actual_score:
                        stats['ml']['correct_score'] += 1
            
            # Ensemble
            if ens_win:
                stats['ensemble']['total'] += 1
                if ens_win == actual_win:
                    stats['ensemble']['correct'] += 1
                    if ens_score == actual_score:
                        stats['ensemble']['correct_score'] += 1
                
                # Track high confidence predictions
                if ens_conf and ens_conf > 30:
                    stats['ensemble']['high_conf_total'] += 1
                    if ens_win == actual_win:
                        stats['ensemble']['high_conf_correct'] += 1
        
        # Calculate percentages
        for model in stats:
            if stats[model]['total'] > 0:
                stats[model]['accuracy'] = stats[model]['correct'] / stats[model]['total'] * 100
                stats[model]['score_accuracy'] = stats[model]['correct_score'] / stats[model]['total'] * 100
            
            if model == 'ensemble' and stats[model].get('high_conf_total', 0) > 0:
                stats[model]['high_conf_accuracy'] = (
                    stats[model]['high_conf_correct'] / stats[model]['high_conf_total'] * 100
                )
        
        return stats
    
    def get_pending_predictions(self) -> List[Dict]:
        """Get predictions that haven't been verified yet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT match_date, team_a, team_b, ensemble_winner, ensemble_score, 
                   ensemble_probability, ensemble_confidence
            FROM predictions
            WHERE actual_winner IS NULL
            ORDER BY match_date ASC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'match_date': row[0],
                'team_a': row[1],
                'team_b': row[2],
                'predicted_winner': row[3],
                'predicted_score': row[4],
                'probability': row[5],
                'confidence': row[6]
            }
            for row in rows
        ]
    
    def get_recent_predictions(self, limit: int = 10) -> List[Dict]:
        """Get recent predictions with results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT match_date, team_a, team_b, 
                   ensemble_winner, ensemble_score, ensemble_probability,
                   actual_winner, actual_score,
                   (ensemble_winner = actual_winner) as correct
            FROM predictions
            WHERE actual_winner IS NOT NULL
            ORDER BY result_timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'match_date': row[0],
                'team_a': row[1],
                'team_b': row[2],
                'predicted_winner': row[3],
                'predicted_score': row[4],
                'probability': row[5],
                'actual_winner': row[6],
                'actual_score': row[7],
                'correct': bool(row[8])
            }
            for row in rows
        ]
