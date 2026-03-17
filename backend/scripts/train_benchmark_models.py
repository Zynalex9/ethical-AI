"""
Train quick benchmark model for local validation demos.

Produces:
- Adult Income classifier trained on the true `income` label.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "app" / "datasets" / "benchmark"
OUTPUT_DIR = BASE_DIR / "uploads" / "models" / "trained_benchmarks"


def _encode_features_for_linear_model(df: pd.DataFrame, drop_columns: list[str]) -> pd.DataFrame:
    """Encode object columns to integer codes so model.predict works with NumPy arrays."""
    X = df.drop(columns=drop_columns).copy()

    for col in X.columns:
        if X[col].dtype == "object":
            X[col] = pd.factorize(X[col].astype(str))[0]

    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    return X


def _train_logreg(X: pd.DataFrame, y: np.ndarray) -> Tuple[LogisticRegression, Dict[str, float]]:
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = LogisticRegression(max_iter=2500, solver="lbfgs", random_state=42)
    model.fit(X_train, y_train)

    metrics = {
        "train_accuracy": float(accuracy_score(y_train, model.predict(X_train))),
        "test_accuracy": float(accuracy_score(y_test, model.predict(X_test))),
    }
    return model, metrics


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    metadata: Dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "models": {},
    }

    # Adult Income Model
    adult_df = pd.read_csv(DATASET_DIR / "adult.csv")

    adult_target = (
        adult_df["income"]
        .astype(str)
        .str.strip()
        .str.contains(r">50k", case=False, regex=True)
        .astype(int)
        .to_numpy()
    )

    adult_X = _encode_features_for_linear_model(adult_df, ["income"])
    adult_model, adult_metrics = _train_logreg(adult_X, adult_target)

    adult_model_path = OUTPUT_DIR / f"adult_income_model_{timestamp}.joblib"
    joblib.dump(adult_model, adult_model_path)

    metadata["models"]["adult_income"] = {
        "path": str(adult_model_path),
        "dataset": str(DATASET_DIR / "adult.csv"),
        "target": "income (ground truth)",
        "features": list(adult_X.columns),
        "class_balance": {
            "negative": int((adult_target == 0).sum()),
            "positive": int((adult_target == 1).sum()),
        },
        "metrics": adult_metrics,
    }

    metadata_path = OUTPUT_DIR / f"training_metadata_{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("Training complete.")
    print(f"Adult model:  {adult_model_path}")
    print(f"Metadata:     {metadata_path}")


if __name__ == "__main__":
    main()
