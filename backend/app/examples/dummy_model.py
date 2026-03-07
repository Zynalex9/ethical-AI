from __future__ import annotations

import numpy as np


class ToyBinaryModel:
    """Simple deterministic binary classifier for upload/validation smoke tests."""

    def __init__(self, weights: np.ndarray, bias: float = 0.0):
        self.weights = np.asarray(weights, dtype=float)
        self.bias = float(bias)
        self.n_features_in_ = int(self.weights.shape[0])
        self.feature_names_in_ = np.array([f"feature_{i}" for i in range(self.n_features_in_)], dtype=object)
        self.classes_ = np.array([0, 1], dtype=int)

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2:
            raise ValueError("X must be 2D")
        if X.shape[1] != self.n_features_in_:
            raise ValueError(f"Expected {self.n_features_in_} features, got {X.shape[1]}")
        return X @ self.weights + self.bias

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.decision_function(X) >= 0.0).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        logits = self.decision_function(X)
        prob_1 = 1.0 / (1.0 + np.exp(-logits))
        prob_0 = 1.0 - prob_1
        return np.column_stack([prob_0, prob_1])
