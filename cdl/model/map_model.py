"""P(team 1 wins a map) from point-in-time features.

A symmetric logistic regression: every training row is also added from the
other team's perspective (negated features, flipped label) and there is no
intercept, so P(A beats B) == 1 - P(B beats A) by construction. Older maps get
exponentially less weight.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from cdl.model.features import FEATURES


class MapModel:
    def __init__(self, C: float = 0.5, half_life_days: float = 720.0):
        self.C = C
        self.half_life_days = half_life_days
        self.clf: LogisticRegression | None = None
        self.n_train = 0

    def fit(self, df: pd.DataFrame, as_of: pd.Timestamp | None = None) -> MapModel:
        if as_of is not None:
            df = df[df.datetime < as_of]
        if len(df) < 30:
            self.clf = None
            self.n_train = len(df)
            return self
        ref = as_of if as_of is not None else df.datetime.max()
        age = (ref - df.datetime).dt.total_seconds().to_numpy() / 86400.0
        w = 0.5 ** (age / self.half_life_days)
        X = df[FEATURES].to_numpy(dtype=float)
        y = df["y"].to_numpy(dtype=int)
        Xa = np.vstack([X, -X])
        ya = np.concatenate([y, 1 - y])
        wa = np.concatenate([w, w])
        self.clf = LogisticRegression(C=self.C, fit_intercept=False, max_iter=1000)
        self.clf.fit(Xa, ya, sample_weight=wa)
        self.n_train = len(df)
        return self

    def predict(self, feats: dict[str, float] | pd.DataFrame) -> float | np.ndarray:
        if isinstance(feats, dict):
            X = np.array([[feats[f] for f in FEATURES]], dtype=float)
            single = True
        else:
            X = feats[FEATURES].to_numpy(dtype=float)
            single = False
        if self.clf is None:
            # Untrained fallback: plain Elo on the team difference
            p = 1.0 / (1.0 + 10 ** (-X[:, 0] * 100 / 400))
        else:
            p = self.clf.predict_proba(X)[:, 1]
        return float(p[0]) if single else p

    def coefficients(self) -> dict[str, float]:
        if self.clf is None:
            return {}
        return dict(zip(FEATURES, (float(c) for c in self.clf.coef_[0]), strict=True))
