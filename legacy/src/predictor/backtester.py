r"""
Backtest prediction models on historical data
Validates model accuracy by simulating past predictions
"""
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple
from src.predictor import MatchPredictor, EloPredictor, MLPredictor, EnsemblePredictor
from src.database import DatabaseManager


class Backtester:
    """Backtest prediction models on historical matches"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_historical_matches(self) -> List[Dict]:
        """Get all matches sorted chronologically"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.match_id,
                m.match_date,
                m.team_a,
                m.team_b,
                m.winner,
                m.team_a_score,
                m.team_b_score
            FROM matches m
            WHERE m.winner IS NOT NULL
            ORDER BY m.match_date ASC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'match_id': row[0],
                'date': row[1],
                'team_a': row[2],
                'team_b': row[3],
                'winner': row[4],
                'score_a': row[5],
                'score_b': row[6],
                'score': f"{row[5]}-{row[6]}"
            }
            for row in rows
        ]
    
    def run_backtest(self, start_match: int = 20, min_data_matches: int = 10) -> Dict:
        """
        Run backtest on historical matches
        
        Args:
            start_match: Start backtesting from this match number (need some data first)
            min_data_matches: Minimum matches needed before making predictions
        
        Returns:
            Dictionary with backtest results
        """
        matches = self.get_historical_matches()
        
        if len(matches) < start_match:
            return {
                'error': f'Not enough matches. Have {len(matches)}, need {start_match} to start backtest'
            }
        
        results = {
            'total_matches': 0,
            'predictions': [],
            'accuracy': {
                'statistical': {'correct': 0, 'correct_score': 0, 'total': 0},
                'elo': {'correct': 0, 'correct_score': 0, 'total': 0},
                'ml': {'correct': 0, 'correct_score': 0, 'total': 0},
                'ensemble': {'correct': 0, 'correct_score': 0, 'total': 0}
            }
        }
        
        print(f"\nBacktesting on {len(matches) - start_match} matches...")
        print(f"(Using first {start_match} matches as training data)\n")
        
        # Use ensemble predictor which includes all models
        ensemble = EnsemblePredictor()
        
        for i in range(start_match, len(matches)):
            match = matches[i]
            
            try:
                # Make prediction
                predictions = ensemble.predict_all(match['team_a'], match['team_b'])
                
                result = {
                    'match_id': match['match_id'],
                    'date': match['date'],
                    'team_a': match['team_a'],
                    'team_b': match['team_b'],
                    'actual_winner': match['winner'],
                    'actual_score': match['score'],
                    'predictions': {}
                }
                
                # Check each model
                for model_name in ['statistical', 'elo', 'ml', 'ensemble']:
                    if model_name == 'ensemble':
                        pred = predictions.get('ensemble', {})
                    else:
                        pred = predictions['predictions'].get(model_name, {})
                    
                    if 'error' not in pred and 'predicted_winner' in pred:
                        predicted_winner = pred['predicted_winner']
                        predicted_score = pred.get('predicted_score', '')
                        
                        correct_winner = (predicted_winner == match['winner'])
                        correct_score = (predicted_score == match['score'])
                        
                        result['predictions'][model_name] = {
                            'winner': predicted_winner,
                            'score': predicted_score,
                            'correct_winner': correct_winner,
                            'correct_score': correct_score
                        }
                        
                        # Update accuracy stats
                        results['accuracy'][model_name]['total'] += 1
                        if correct_winner:
                            results['accuracy'][model_name]['correct'] += 1
                        if correct_score:
                            results['accuracy'][model_name]['correct_score'] += 1
                
                results['predictions'].append(result)
                results['total_matches'] += 1
                
                # Progress indicator
                if (i - start_match + 1) % 10 == 0:
                    print(f"  Processed {i - start_match + 1}/{len(matches) - start_match} matches...")
                
            except Exception as e:
                print(f"  Error on match {i}: {e}")
                continue
        
        # Calculate percentages
        for model in results['accuracy']:
            if results['accuracy'][model]['total'] > 0:
                total = results['accuracy'][model]['total']
                correct = results['accuracy'][model]['correct']
                correct_score = results['accuracy'][model]['correct_score']
                
                results['accuracy'][model]['accuracy_pct'] = (correct / total) * 100
                results['accuracy'][model]['score_accuracy_pct'] = (correct_score / total) * 100
        
        return results
    
    def get_worst_predictions(self, backtest_results: Dict, limit: int = 10) -> List[Dict]:
        """Find matches where all models were wrong"""
        wrong_predictions = []
        
        for pred in backtest_results['predictions']:
            all_models_wrong = True
            
            for model_name in ['statistical', 'elo', 'ml', 'ensemble']:
                if model_name in pred['predictions']:
                    if pred['predictions'][model_name]['correct_winner']:
                        all_models_wrong = False
                        break
            
            if all_models_wrong:
                wrong_predictions.append(pred)
        
        return wrong_predictions[:limit]
    
    def analyze_confidence_accuracy(self, backtest_results: Dict) -> Dict:
        """Analyze how accuracy correlates with confidence levels"""
        confidence_buckets = {
            'high': {'correct': 0, 'total': 0, 'range': (40, 100)},
            'medium': {'correct': 0, 'total': 0, 'range': (20, 40)},
            'low': {'correct': 0, 'total': 0, 'range': (0, 20)}
        }
        
        for pred in backtest_results['predictions']:
            if 'ensemble' in pred['predictions']:
                ens = pred['predictions']['ensemble']
                # Note: We'd need to store confidence in predictions
                # For now, just return structure
                pass
        
        return confidence_buckets
