"""
Train quick benchmark models for local validation demos.

Produces:
- Adult Income classifier trained on the true `income` label.
- German Credit classifier trained on a proxy risk label because
  `german_credit_data.csv` does not include a ground-truth target column.
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

    # Keep a dense numeric matrix for scikit-learn linear models.
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


def _build_german_proxy_target(df: pd.DataFrame) -> np.ndarray:
    """Construct a proxy binary risk target from available German Credit attributes."""
    checking = df["Checking account"].astype(str).str.lower()
    saving = df["Saving accounts"].astype(str).str.lower()
    credit_amount = pd.to_numeric(df["Credit amount"], errors="coerce").fillna(0)
    duration = pd.to_numeric(df["Duration"], errors="coerce").fillna(0)
    job = pd.to_numeric(df["Job"], errors="coerce").fillna(0)

    score = (
        checking.isin(["na", "little"]).astype(int)
        + saving.isin(["na", "little"]).astype(int)
        + (credit_amount > credit_amount.median()).astype(int)
        + (duration > duration.median()).astype(int)
        + (job <= 1).astype(int)
    )

    # Higher score means higher inferred risk.
    return (score >= 3).astype(int).to_numpy()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    metadata: Dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "models": {},
    }

    # 1) Adult Income (true target)
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

    # 2) German Credit (proxy target)
    german_df = pd.read_csv(DATASET_DIR / "german_credit_data.csv")
    german_target = _build_german_proxy_target(german_df)
    german_X = _encode_features_for_linear_model(german_df, [])
    german_model, german_metrics = _train_logreg(german_X, german_target)

    german_model_path = OUTPUT_DIR / f"german_credit_proxy_model_{timestamp}.joblib"
    joblib.dump(german_model, german_model_path)

    metadata["models"]["german_credit_proxy"] = {
        "path": str(german_model_path),
        "dataset": str(DATASET_DIR / "german_credit_data.csv"),
        "target": "proxy_risk (derived; no ground-truth label in source CSV)",
        "features": list(german_X.columns),
        "class_balance": {
            "negative": int((german_target == 0).sum()),
            "positive": int((german_target == 1).sum()),
        },
        "metrics": german_metrics,
    }

    metadata_path = OUTPUT_DIR / f"training_metadata_{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("Training complete.")
    print(f"Adult model:  {adult_model_path}")
    print(f"German model: {german_model_path}")
    print(f"Metadata:     {metadata_path}")


if __name__ == "__main__":
    main()
