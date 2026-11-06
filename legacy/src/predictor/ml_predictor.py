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
    from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
    from sklearn.model_selection import TimeSeriesSplit
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
        self.model = LogisticRegression(random_state=42, max_iter=2000)
        self.calibrator = None
        self.scaler = StandardScaler()
        self.model_file = DATA_DIR / "ml_model.pkl"
        self.calibrator_file = DATA_DIR / "ml_calibrator.pkl"
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
                if self.calibrator_file.exists():
                    with open(self.calibrator_file, 'rb') as f:
                        self.calibrator = pickle.load(f)
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
            if self.calibrator is not None:
                with open(self.calibrator_file, 'wb') as f:
                    pickle.dump(self.calibrator, f)
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
                               h2h: Dict = None,
                               context_a: Dict = None,
                               context_b: Dict = None) -> np.ndarray:
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
        11. Recent win rate differential
        12. Recent map win rate differential
        13. Roster stability differential
        14. Rest days differential
        15. Opponent strength differential
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
        
        # H2H record (if available) - with confidence weighting to prevent overfitting
        if h2h and h2h['total_matches'] >= 3:
            # Only use H2H diff if there are at least 3 matches
            h2h_wr_a = h2h['team_a_wins'] / h2h['total_matches']
            h2h_wr_b = h2h['team_b_wins'] / h2h['total_matches']
            # Apply confidence weighting: scales from 0.2 at 1 match to 1.0 at 5+ matches
            confidence = min(h2h['total_matches'] / 5.0, 1.0)
            features.append((h2h_wr_a - h2h_wr_b) * confidence)
        else:
            features.append(0.0)  # No H2H history or insufficient matches (< 3)

        context_a = context_a or {}
        context_b = context_b or {}

        # Recent form and scheduling context
        features.append(context_a.get('recent_win_rate', 0.0) - context_b.get('recent_win_rate', 0.0))
        features.append(context_a.get('recent_map_win_rate', 0.0) - context_b.get('recent_map_win_rate', 0.0))
        features.append(context_a.get('roster_stability', 0.0) - context_b.get('roster_stability', 0.0))
        features.append(context_a.get('rest_days', 0.0) - context_b.get('rest_days', 0.0))
        features.append(context_a.get('opponent_strength', 0.0) - context_b.get('opponent_strength', 0.0))
        
        return np.array(features).reshape(1, -1)

    def _calculate_roster_overlap(self, roster_a: List[str], roster_b: List[str]) -> float:
        """Calculate roster overlap as a fraction from 0.0 to 1.0."""
        if not roster_a or not roster_b:
            return 0.0
        return len(set(roster_a) & set(roster_b)) / 4.0

    def _calculate_time_weight(self, match_date: str) -> float:
        """Weight recent matches more heavily using exponential decay."""
        try:
            match_dt = datetime.strptime(match_date, '%Y-%m-%d')
            reference_dt = datetime.now()
            days_ago = (reference_dt - match_dt).days
            decay_rate = 0.693 / 30
            weight = np.exp(-decay_rate * days_ago)
            return float(max(0.01, min(1.0, weight)))
        except Exception:
            return 0.5

    def _get_recent_team_context(
        self,
        team: str,
        roster: List[str],
        before_date: str = None,
        last_n: int = 5,
    ) -> Dict:
        """Capture recent form, roster stability, and scheduling context for a team."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cutoff_date = before_date or datetime.now().strftime('%Y-%m-%d')

            cursor.execute("""
                SELECT match_id, team_a, team_b, winner, match_date
                FROM matches
                WHERE (team_a = ? OR team_b = ?) AND match_date < ?
                ORDER BY match_date DESC, id DESC
                LIMIT ?
            """, (team, team, cutoff_date, max(last_n * 4, 12)))

            matches = cursor.fetchall()
            if not matches:
                return {
                    'recent_win_rate': 0.0,
                    'recent_map_win_rate': 0.0,
                    'roster_stability': 0.0,
                    'rest_days': 30.0,
                    'opponent_strength': 0.0,
                }

            weighted_wins = 0.0
            weighted_maps_won = 0.0
            weighted_maps_played = 0.0
            total_weight = 0.0
            roster_overlap_total = 0.0
            valid_matches = 0
            opponent_strength_total = 0.0
            rest_days = 30.0

            cutoff_dt = datetime.strptime(cutoff_date, '%Y-%m-%d')

            for idx, (match_id, team_a, team_b, winner, match_date) in enumerate(matches):
                cursor.execute("""
                    SELECT DISTINCT player_name
                    FROM player_match_stats
                    WHERE match_id = ? AND team = ?
                """, (match_id, team))

                match_roster = [row[0] for row in cursor.fetchall()]
                overlap = self._calculate_roster_overlap(roster, match_roster)
                if overlap == 0:
                    continue

                time_weight = self._calculate_time_weight(match_date)
                weight = overlap * time_weight
                if weight <= 0:
                    continue

                valid_matches += 1
                total_weight += weight
                roster_overlap_total += overlap

                if idx == 0:
                    try:
                        match_dt = datetime.strptime(match_date, '%Y-%m-%d')
                        rest_days = float(max((cutoff_dt - match_dt).days, 0))
                    except Exception:
                        rest_days = 30.0

                if winner == team:
                    weighted_wins += weight

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM map_results
                    WHERE match_id = ? AND winner = ?
                """, (match_id, team))
                maps_won = cursor.fetchone()[0] or 0

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM map_results
                    WHERE match_id = ?
                """, (match_id,))
                maps_played = cursor.fetchone()[0] or 0

                weighted_maps_won += maps_won * weight
                weighted_maps_played += maps_played * weight

                opponent = team_b if team_a == team else team_a
                cursor.execute("""
                    SELECT DISTINCT player_name
                    FROM player_match_stats
                    WHERE match_id = ? AND team = ?
                """, (match_id, opponent))
                opponent_roster = [row[0] for row in cursor.fetchall()]
                if opponent_roster:
                    opponent_stats = self._get_team_stats(opponent, opponent_roster, match_date)
                    opponent_strength_total += opponent_stats['win_rate'] * weight

                if valid_matches >= last_n:
                    break

            if total_weight <= 0:
                return {
                    'recent_win_rate': 0.0,
                    'recent_map_win_rate': 0.0,
                    'roster_stability': 0.0,
                    'rest_days': rest_days,
                    'opponent_strength': 0.0,
                }

            return {
                'recent_win_rate': round((weighted_wins / total_weight) * 100, 1),
                'recent_map_win_rate': round((weighted_maps_won / weighted_maps_played) * 100, 1)
                if weighted_maps_played > 0 else 0.0,
                'roster_stability': round((roster_overlap_total / max(valid_matches, 1)) * 100.0, 1),
                'rest_days': round(rest_days, 1),
                'opponent_strength': round(opponent_strength_total / total_weight, 1),
            }
        finally:
            conn.close()

    def _build_training_dataset(self, min_matches: int = 10):
        """Collect historical matches and convert them into a feature matrix."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

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
                stats_a = self._get_team_stats(team_a, roster_a, match_date)
                stats_b = self._get_team_stats(team_b, roster_b, match_date)
                context_a = self._get_recent_team_context(team_a, roster_a, before_date=match_date)
                context_b = self._get_recent_team_context(team_b, roster_b, before_date=match_date)

                if stats_a['matches_played'] < min_matches or stats_b['matches_played'] < min_matches:
                    skipped += 1
                    continue

                h2h = self._get_h2h(team_a, team_b, before_date=match_date)
                features = self._create_feature_vector(stats_a, stats_b, h2h, context_a, context_b)
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

        return np.vstack(X_list), np.array(y_list), skipped

    def _evaluate_time_series_cv(
        self,
        X: np.ndarray,
        y: np.ndarray,
        candidate_params: Optional[List[Dict]] = None,
        max_splits: int = 5,
    ) -> Dict:
        """Evaluate candidate LogisticRegression settings using chronological CV."""
        if candidate_params is None:
            candidate_params = [
                {'C': 0.1, 'class_weight': None, 'solver': 'lbfgs', 'penalty': 'l2'},
                {'C': 0.3, 'class_weight': None, 'solver': 'lbfgs', 'penalty': 'l2'},
                {'C': 1.0, 'class_weight': None, 'solver': 'lbfgs', 'penalty': 'l2'},
                {'C': 0.3, 'class_weight': 'balanced', 'solver': 'lbfgs', 'penalty': 'l2'},
                {'C': 0.3, 'class_weight': 'balanced', 'solver': 'liblinear', 'penalty': 'l1'},
                {'C': 1.0, 'class_weight': 'balanced', 'solver': 'liblinear', 'penalty': 'l2'},
                {'C': 0.1, 'class_weight': 'balanced', 'solver': 'liblinear', 'penalty': 'l1'},
            ]

        n_samples = len(X)
        n_splits = min(max_splits, max(2, n_samples // 20))
        n_splits = min(n_splits, n_samples - 1)

        if n_splits < 2:
            raise ValueError("Not enough samples for time-series cross-validation")

        cv = TimeSeriesSplit(n_splits=n_splits)
        evaluated_candidates = []

        for params in candidate_params:
            fold_scores = []
            fold_losses = []
            fold_sizes = []

            for train_idx, val_idx in cv.split(X):
                scaler = StandardScaler()
                X_train = scaler.fit_transform(X[train_idx])
                X_val = scaler.transform(X[val_idx])

                model = LogisticRegression(
                    random_state=42,
                    max_iter=2000,
                    C=params['C'],
                    class_weight=params.get('class_weight'),
                    solver=params.get('solver', 'lbfgs'),
                    penalty=params.get('penalty', 'l2')
                )

                model.fit(X_train, y[train_idx])
                probabilities = model.predict_proba(X_val)[:, 1]
                predictions = (probabilities >= 0.5).astype(int)

                fold_scores.append(accuracy_score(y[val_idx], predictions))
                fold_losses.append(log_loss(y[val_idx], probabilities, labels=[0, 1]))
                fold_sizes.append(len(val_idx))

            evaluated_candidates.append({
                'params': params,
                'mean_accuracy': float(np.mean(fold_scores)),
                'mean_log_loss': float(np.mean(fold_losses)),
                'fold_accuracies': [float(score) for score in fold_scores],
                'fold_log_losses': [float(loss) for loss in fold_losses],
                'fold_sizes': fold_sizes,
            })

        best_candidate = sorted(
            evaluated_candidates,
            key=lambda item: (-item['mean_accuracy'], item['mean_log_loss'])
        )[0]

        return {
            'n_splits': n_splits,
            'candidates': evaluated_candidates,
            'best_candidate': best_candidate,
        }

    def _collect_oof_probabilities(self, X: np.ndarray, y: np.ndarray, params: Dict, n_splits: int) -> np.ndarray:
        """Collect out-of-fold probabilities for the chosen model."""
        cv = TimeSeriesSplit(n_splits=n_splits)
        oof_probabilities = np.zeros(len(X), dtype=float)

        for train_idx, val_idx in cv.split(X):
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X[train_idx])
            X_val = scaler.transform(X[val_idx])

            model = LogisticRegression(
                random_state=42,
                max_iter=2000,
                C=params['C'],
                class_weight=params.get('class_weight'),
                solver=params.get('solver', 'lbfgs'),
                penalty=params.get('penalty', 'l2')
            )

            model.fit(X_train, y[train_idx])
            oof_probabilities[val_idx] = model.predict_proba(X_val)[:, 1]

        return oof_probabilities

    def evaluate(self, min_matches: int = 10) -> Dict:
        """Evaluate model candidates with chronological cross-validation."""
        X, y, skipped = self._build_training_dataset(min_matches=min_matches)
        cv_results = self._evaluate_time_series_cv(X, y)
        best_params = cv_results['best_candidate']['params']
        oof_probabilities = self._collect_oof_probabilities(X, y, best_params, cv_results['n_splits'])
        calibrator = LogisticRegression(random_state=42, max_iter=2000)
        calibrator.fit(oof_probabilities.reshape(-1, 1), y)
        calibrated_probabilities = calibrator.predict_proba(oof_probabilities.reshape(-1, 1))[:, 1]

        calibrated_log_loss = log_loss(y, calibrated_probabilities, labels=[0, 1])
        calibrated_brier = brier_score_loss(y, calibrated_probabilities)

        return {
            'training_samples': len(X),
            'skipped_matches': skipped,
            'cv_results': cv_results,
            'calibrated_log_loss': calibrated_log_loss,
            'calibrated_brier_score': calibrated_brier,
        }
    
    def train(self, min_matches: int = 10):
        """Train model on historical match data
        
        Args:
            min_matches: Minimum matches a team must have to be included
        """
        self.logger.info("Training ML model on historical data...")

        X, y, skipped = self._build_training_dataset(min_matches=min_matches)
        cv_results = self._evaluate_time_series_cv(X, y)
        best_params = cv_results['best_candidate']['params']

        self.model = LogisticRegression(
            random_state=42,
            max_iter=2000,
            C=best_params['C'],
            class_weight=best_params.get('class_weight'),
            solver=best_params.get('solver', 'lbfgs'),
            penalty=best_params.get('penalty', 'l2')
        )

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True

        oof_probabilities = self._collect_oof_probabilities(X, y, best_params, cv_results['n_splits'])
        self.calibrator = LogisticRegression(random_state=42, max_iter=2000)
        self.calibrator.fit(oof_probabilities.reshape(-1, 1), y)
        calibrated_oof_probabilities = self.calibrator.predict_proba(oof_probabilities.reshape(-1, 1))[:, 1]
        
        # Calculate training accuracy
        train_acc = self.model.score(X_scaled, y)
        validation_acc = cv_results['best_candidate']['mean_accuracy']
        validation_log_loss = cv_results['best_candidate']['mean_log_loss']
        calibrated_log_loss = log_loss(y, calibrated_oof_probabilities, labels=[0, 1])
        calibrated_brier = brier_score_loss(y, calibrated_oof_probabilities)
        
        self.logger.info(f"Model trained on {len(X)} matches (skipped {skipped})")
        self.logger.info(f"Training accuracy: {train_acc:.1%}")
        self.logger.info(
            f"Validation accuracy: {validation_acc:.1%} | Validation log loss: {validation_log_loss:.4f}"
        )
        self.logger.info(
            f"Calibrated log loss: {calibrated_log_loss:.4f} | Calibrated Brier score: {calibrated_brier:.4f}"
        )
        self.logger.info(f"Best hyperparameters: {best_params}")
        
        # Save model
        self._save_model()
        
        return {
            'training_samples': len(X),
            'skipped_matches': skipped,
            'training_accuracy': train_acc,
            'validation_accuracy': validation_acc,
            'validation_log_loss': validation_log_loss,
            'calibrated_log_loss': calibrated_log_loss,
            'calibrated_brier_score': calibrated_brier,
            'best_params': best_params,
            'cv_results': cv_results,
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
            'h2h_diff',
            'recent_win_rate_diff',
            'recent_map_win_rate_diff',
            'roster_stability_diff',
            'rest_days_diff',
            'opponent_strength_diff'
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
        context_a = self._get_recent_team_context(team_a, roster_a)
        context_b = self._get_recent_team_context(team_b, roster_b)
        
        # Get H2H
        h2h = self._get_h2h(team_a, team_b)
        
        # Create feature vector
        features = self._create_feature_vector(stats_a, stats_b, h2h, context_a, context_b)
        features_scaled = self.scaler.transform(features)
        
        # Predict probability
        raw_prob_a = self.model.predict_proba(features_scaled)[0][1]
        if self.calibrator is not None:
            prob_a = self.calibrator.predict_proba(np.array([[raw_prob_a]]))[:, 1][0]
        else:
            prob_a = raw_prob_a
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
