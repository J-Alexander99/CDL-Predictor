"""
Machine Learning predictor using Logistic Regression
Learns optimal feature weights from historical match outcomes
"""
import logging
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import pickle
from pathlib import Path

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    
from src.database.db_manager import DatabaseManager
from config.settings import DATA_DIR


class MLPredictor:
    """Machine Learning predictor using historical match data"""
    
    def __init__(self):
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn not installed. Install with: pip install scikit-learn"
            )
        
        self.db = DatabaseManager()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = LogisticRegression(random_state=42, max_iter=1000)
        self.scaler = StandardScaler()
        self.model_file = DATA_DIR / "ml_model.pkl"
        self.scaler_file = DATA_DIR / "ml_scaler.pkl"
        self.is_trained = False
        
        self._load_model()
    
    def _load_model(self):
        """Load trained model from disk"""
        if self.model_file.exists() and self.scaler_file.exists():
            try:
                with open(self.model_file, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                self.logger.info("Loaded trained ML model from disk")
            except Exception as e:
                self.logger.warning(f"Failed to load model: {e}")
    
    def _save_model(self):
        """Save trained model to disk"""
        try:
            with open(self.model_file, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)
            self.logger.info("Saved trained ML model to disk")
        except Exception as e:
            self.logger.error(f"Failed to save model: {e}")
    
    def _get_team_stats(self, team: str, roster: List[str], as_of_date: str = None) -> Dict:
        """Get comprehensive team statistics for feature extraction
        
        This mimics the statistical predictor's calculations but simplified
        """
        from src.predictor.match_predictor import MatchPredictor
        
        stat_predictor = MatchPredictor()
        
        # Get weighted stats
        stats = stat_predictor._calculate_weighted_stats(team, roster)
        
        # Get roster quality
        quality = stat_predictor._calculate_roster_quality(roster)
        stats['roster_quality'] = quality
        
        # Get momentum
        momentum = stat_predictor._calculate_momentum(team, roster)
        stats['momentum'] = momentum
        
        return stats
    
    def _create_feature_vector(self, team_a_stats: Dict, team_b_stats: Dict, 
                               h2h: Dict = None) -> np.ndarray:
        """Convert team statistics into ML feature vector
        
        Features:
        1. Win rate differential
        2. Map win rate differential  
        3. K/D differential
        4. Rating differential
        5. Damage differential
        6. Momentum differential
        7. Weighted matches (team A)
        8. Weighted matches (team B)
        9. Experience product (weighted_a * weighted_b)
        10. H2H win rate differential (if available)
        """
        features = []
        
        # Win rate differential
        features.append(team_a_stats['win_rate'] - team_b_stats['win_rate'])
        
        # Map win rate differential
        features.append(team_a_stats['map_win_rate'] - team_b_stats['map_win_rate'])
        
        # Roster quality differentials
        quality_a = team_a_stats['roster_quality']
        quality_b = team_b_stats['roster_quality']
        features.append(quality_a['avg_kd'] - quality_b['avg_kd'])
        features.append(quality_a['avg_rating'] - quality_b['avg_rating'])
        features.append(quality_a['avg_damage'] - quality_b['avg_damage'])
        
        # Momentum differential
        momentum_a = team_a_stats.get('momentum', 0)
        momentum_b = team_b_stats.get('momentum', 0)
        features.append(momentum_a - momentum_b)
        
        # Experience levels
        features.append(team_a_stats['weighted_matches'])
        features.append(team_b_stats['weighted_matches'])
        
        # Experience interaction (both experienced = more predictable)
        features.append(team_a_stats['weighted_matches'] * team_b_stats['weighted_matches'])
        
        # H2H record (if available)
        if h2h and h2h['total_matches'] > 0:
            h2h_wr_a = h2h['team_a_wins'] / h2h['total_matches']
            h2h_wr_b = h2h['team_b_wins'] / h2h['total_matches']
            features.append(h2h_wr_a - h2h_wr_b)
        else:
            features.append(0.0)  # No H2H history
        
        return np.array(features).reshape(1, -1)
    
    def train(self, min_matches: int = 10):
        """Train model on historical match data
        
        Args:
            min_matches: Minimum matches a team must have to be included
        """
        self.logger.info("Training ML model on historical data...")
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Get all matches
        cursor.execute("""
            SELECT match_id, team_a, team_b, winner, match_date
            FROM matches
            ORDER BY match_date ASC
        """)
        
        matches = cursor.fetchall()
        
        X_list = []
        y_list = []
        skipped = 0
        
        for match_id, team_a, team_b, winner, match_date in matches:
            # Get rosters
            cursor.execute("""
                SELECT DISTINCT player_name, team
                FROM player_match_stats
                WHERE match_id = ?
            """, (match_id,))
            
            players = cursor.fetchall()
            roster_a = [p[0] for p in players if p[1] == team_a]
            roster_b = [p[0] for p in players if p[1] == team_b]
            
            if len(roster_a) != 4 or len(roster_b) != 4:
                skipped += 1
                continue
            
            try:
                # Get stats for both teams
                stats_a = self._get_team_stats(team_a, roster_a, match_date)
                stats_b = self._get_team_stats(team_b, roster_b, match_date)
                
                # Skip if insufficient data
                if stats_a['matches_played'] < 2 or stats_b['matches_played'] < 2:
                    skipped += 1
                    continue
                
                # Get H2H
                h2h = self._get_h2h(team_a, team_b, before_date=match_date)
                
                # Create feature vector
                features = self._create_feature_vector(stats_a, stats_b, h2h)
                
                # Label: 1 if team_a won, 0 if team_b won
                label = 1 if winner == team_a else 0
                
                X_list.append(features.flatten())
                y_list.append(label)
                
            except Exception as e:
                self.logger.debug(f"Skipped match {match_id}: {e}")
                skipped += 1
                continue
        
        conn.close()
        
        if len(X_list) < 20:
            raise ValueError(
                f"Insufficient training data: only {len(X_list)} matches. Need at least 20."
            )
        
        # Convert to numpy arrays
        X = np.vstack(X_list)
        y = np.array(y_list)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled, y)
        self.is_trained = True
        
        # Calculate training accuracy
        train_acc = self.model.score(X_scaled, y)
        
        self.logger.info(f"Model trained on {len(X_list)} matches (skipped {skipped})")
        self.logger.info(f"Training accuracy: {train_acc:.1%}")
        
        # Save model
        self._save_model()
        
        return {
            'training_samples': len(X_list),
            'skipped_matches': skipped,
            'training_accuracy': train_acc,
            'feature_importance': self._get_feature_importance()
        }
    
    def _get_feature_importance(self) -> Dict:
        """Get feature importance from model coefficients"""
        if not self.is_trained:
            return {}
        
        feature_names = [
            'win_rate_diff',
            'map_win_rate_diff',
            'kd_diff',
            'rating_diff',
            'damage_diff',
            'momentum_diff',
            'weighted_matches_a',
            'weighted_matches_b',
            'experience_interaction',
            'h2h_diff'
        ]
        
        coefficients = self.model.coef_[0]
        importance = dict(zip(feature_names, coefficients))
        
        # Sort by absolute value
        importance = dict(sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True))
        return importance
    
    def _get_h2h(self, team_a: str, team_b: str, before_date: str = None) -> Dict:
        """Get H2H record between teams (optionally before a certain date)"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as team_a_wins,
                    SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as team_b_wins
                FROM matches
                WHERE (team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?)
            """
            params = [team_a, team_b, team_a, team_b, team_b, team_a]
            
            if before_date:
                query += " AND match_date < ?"
                params.append(before_date)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            return {
                'total_matches': row[0] or 0,
                'team_a_wins': row[1] or 0,
                'team_b_wins': row[2] or 0
            }
        finally:
            conn.close()
    
    def predict(self, team_a: str, team_b: str) -> Dict:
        """Predict match outcome using ML model
        
        Args:
            team_a: First team name
            team_b: Second team name
        
        Returns:
            Dictionary with prediction results
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first or load a trained model.")
        
        # Get current rosters
        roster_a = self._get_current_roster(team_a)
        roster_b = self._get_current_roster(team_b)
        
        if not roster_a or not roster_b:
            raise ValueError(f"Could not find roster for one or both teams")
        
        # Get stats
        stats_a = self._get_team_stats(team_a, roster_a)
        stats_b = self._get_team_stats(team_b, roster_b)
        
        # Get H2H
        h2h = self._get_h2h(team_a, team_b)
        
        # Create feature vector
        features = self._create_feature_vector(stats_a, stats_b, h2h)
        features_scaled = self.scaler.transform(features)
        
        # Predict probability
        prob_a = self.model.predict_proba(features_scaled)[0][1]
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
            'method': 'Machine Learning (Logistic Regression)',
            'team_a': team_a,
            'team_b': team_b,
            'team_a_roster': roster_a,
            'team_b_roster': roster_b,
            'team_a_win_probability': round(prob_a * 100, 1),
            'team_b_win_probability': round(prob_b * 100, 1),
            'predicted_winner': team_a if prob_a > prob_b else team_b,
            'predicted_score': predicted_score,
            'confidence': abs(prob_a - prob_b) * 100,
            'team_a_stats': stats_a,
            'team_b_stats': stats_b,
            'head_to_head': h2h
        }
    
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
