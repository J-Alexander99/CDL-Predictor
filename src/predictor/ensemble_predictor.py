"""
Ensemble predictor that combinines multiple prediction methods
Allows for comparison and weighted averaging of different models
"""
import logging
from typing import Dict, List, Optional

from src.predictor.match_predictor import MatchPredictor
from src.predictor.elo_predictor import EloPredictor
from src.predictor.ml_predictor import MLPredictor


class EnsemblePredictor:
    """Combines multiple prediction methods for ensemble predictions"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize all predictors
        self.statistical = MatchPredictor()
        self.elo = EloPredictor()
        
        # ML predictor may not be available if not trained
        try:
            self.ml = MLPredictor()
            self.ml_available = self.ml.is_trained
            if not self.ml_available:
                self.logger.warning("ML model not trained. Run 'python main.py train-ml' first.")
        except Exception as e:
            self.logger.warning(f"ML predictor not available: {e}")
            self.ml = None
            self.ml_available = False
    
    def predict_all(self, team_a: str, team_b: str) -> Dict:
        """Run predictions using all available methods
        
        Args:
            team_a: First team name
            team_b: Second team name
        
        Returns:
            Dict containing predictions from all methods plus ensemble
        """
        results = {
            'team_a': team_a,
            'team_b': team_b,
            'predictions': {}
        }
        
        # Statistical prediction (your original model)
        try:
            stat_pred = self.statistical.predict(team_a, team_b)
            results['predictions']['statistical'] = {
                'method': 'Statistical Model',
                'team_a_probability': stat_pred['team_a_win_probability'],
                'team_b_probability': stat_pred['team_b_win_probability'],
                'predicted_winner': stat_pred['predicted_winner'],
                'predicted_score': stat_pred['predicted_score'],
                'confidence': stat_pred['confidence'],
                'details': stat_pred
            }
        except Exception as e:
            self.logger.error(f"Statistical prediction failed: {e}")
            results['predictions']['statistical'] = {'error': str(e)}
        
        # Elo prediction
        try:
            elo_pred = self.elo.predict(team_a, team_b)
            results['predictions']['elo'] = {
                'method': 'Elo Rating System',
                'team_a_probability': elo_pred['team_a_win_probability'],
                'team_b_probability': elo_pred['team_b_win_probability'],
                'predicted_winner': elo_pred['predicted_winner'],
                'predicted_score': elo_pred['predicted_score'],
                'confidence': elo_pred['confidence'],
                'team_a_rating': elo_pred['team_a_rating'],
                'team_b_rating': elo_pred['team_b_rating'],
                'details': elo_pred
            }
        except Exception as e:
            self.logger.error(f"Elo prediction failed: {e}")
            results['predictions']['elo'] = {'error': str(e)}
        
        # ML prediction (if available)
        if self.ml_available:
            try:
                ml_pred = self.ml.predict(team_a, team_b)
                results['predictions']['ml'] = {
                    'method': 'Machine Learning',
                    'team_a_probability': ml_pred['team_a_win_probability'],
                    'team_b_probability': ml_pred['team_b_win_probability'],
                    'predicted_winner': ml_pred['predicted_winner'],
                    'predicted_score': ml_pred['predicted_score'],
                    'confidence': ml_pred['confidence'],
                    'details': ml_pred
                }
            except Exception as e:
                self.logger.error(f"ML prediction failed: {e}")
                results['predictions']['ml'] = {'error': str(e)}
        
        # Ensemble prediction (weighted average)
        results['ensemble'] = self._calculate_ensemble(results['predictions'])
        
        return results
    
    def _calculate_ensemble(self, predictions: Dict, 
                          weights: Optional[Dict] = None) -> Dict:
        """Calculate ensemble prediction from multiple models
        
        Args:
            predictions: Dict of predictions from different models
            weights: Optional custom weights for each model
        
        Returns:
            Ensemble prediction
        """
        # Weights tuned based on backtest accuracy (ML: 90.3%, Statistical: 79.0%, Elo: 69.4%)
        if weights is None:
            weights = {
                'ml': 0.45,           # Best performer (90.3% backtest accuracy)
                'statistical': 0.35,  # Strong performer (79.0% backtest accuracy)
                'elo': 0.20           # Baseline performer (69.4% backtest accuracy)
            }
        
        # Collect valid predictions
        valid_predictions = []
        used_models = []
        team_a_name = None
        team_b_name = None
        
        for model_name, pred in predictions.items():
            if 'error' not in pred and 'team_a_probability' in pred:
                valid_predictions.append({
                    'name': model_name,
                    'prob_a': pred['team_a_probability'],
                    'prob_b': pred['team_b_probability'],
                    'weight': weights.get(model_name, 1.0),
                    'winner': pred['predicted_winner']
                })
                used_models.append(model_name)
                
                # Get team names from first valid prediction
                if team_a_name is None and 'details' in pred:
                    team_a_name = pred['details'].get('team_a')
                    team_b_name = pred['details'].get('team_b')
        
        if not valid_predictions:
            return {'error': 'No valid predictions available'}
        
        # Normalize weights
        total_weight = sum(p['weight'] for p in valid_predictions)
        for p in valid_predictions:
            p['normalized_weight'] = p['weight'] / total_weight
        
        # Calculate weighted average
        ensemble_prob_a = sum(p['prob_a'] * p['normalized_weight'] for p in valid_predictions)
        ensemble_prob_b = sum(p['prob_b'] * p['normalized_weight'] for p in valid_predictions)
        
        # Normalize to 100%
        total = ensemble_prob_a + ensemble_prob_b
        ensemble_prob_a = (ensemble_prob_a / total) * 100
        ensemble_prob_b = (ensemble_prob_b / total) * 100
        
        # Predict score
        if ensemble_prob_a >= 75:
            predicted_score = "3-0"
        elif ensemble_prob_a >= 65:
            predicted_score = "3-1"
        elif ensemble_prob_a >= 55:
            predicted_score = "3-2"
        elif ensemble_prob_a >= 45:
            predicted_score = "2-3"
        elif ensemble_prob_a >= 35:
            predicted_score = "1-3"
        else:
            predicted_score = "0-3"
        
        # Check agreement between models
        winners = [p['winner'] for p in valid_predictions]
        agreement = len(set(winners)) == 1  # All models agree
        
        # Determine ensemble winner
        if ensemble_prob_a > ensemble_prob_b:
            predicted_winner = team_a_name if team_a_name else winners[0]
        else:
            predicted_winner = team_b_name if team_b_name else winners[0]
        
        return {
            'method': 'Ensemble (Weighted Average)',
            'team_a_probability': round(ensemble_prob_a, 1),
            'team_b_probability': round(ensemble_prob_b, 1),
            'predicted_winner': predicted_winner,
            'predicted_score': predicted_score,
            'confidence': abs(ensemble_prob_a - ensemble_prob_b),
            'models_used': used_models,
            'weights_used': {p['name']: round(p['normalized_weight'], 2) for p in valid_predictions},
            'models_agree': agreement
        }
    
    def predict_single(self, team_a: str, team_b: str, method: str = 'ensemble') -> Dict:
        """Get prediction from a single method or ensemble
        
        Args:
            team_a: First team name
            team_b: Second team name
            method: 'statistical', 'elo', 'ml', or 'ensemble'
        
        Returns:
            Prediction result
        """
        if method == 'ensemble':
            all_preds = self.predict_all(team_a, team_b)
            return all_preds['ensemble']
        elif method == 'statistical':
            return self.statistical.predict(team_a, team_b)
        elif method == 'elo':
            return self.elo.predict(team_a, team_b)
        elif method == 'ml':
            if not self.ml_available:
                raise ValueError("ML model not available or not trained")
            return self.ml.predict(team_a, team_b)
        else:
            raise ValueError(f"Unknown method: {method}")
