"""
Train a small real-world model zoo for platform validation.

This script uses benchmark datasets already present in `app/datasets/benchmark`
and trains multiple sklearn models per dataset. Outputs are written to:

- uploads/models/model_zoo/<dataset_key>/<algorithm>_<timestamp>.joblib
- uploads/models/model_zoo/model_zoo_metadata_<timestamp>.json

Why this exists:
- Quickly generate many realistic uploadable models.
- Stress-test validations across different data domains.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "app" / "datasets" / "benchmark"
OUTPUT_DIR = BASE_DIR / "uploads" / "models" / "model_zoo"


def _safe_numeric_matrix(df: pd.DataFrame, drop_columns: list[str]) -> pd.DataFrame:
    """Convert mixed-type features into a dense numeric frame."""
    X = df.drop(columns=[c for c in drop_columns if c in df.columns]).copy()

    for col in X.columns:
        if X[col].dtype == "object":
            X[col] = pd.factorize(X[col].astype(str))[0]
        else:
            X[col] = pd.to_numeric(X[col], errors="coerce")

    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    return X


def _adult_target(df: pd.DataFrame) -> Tuple[np.ndarray, list[str], str]:
    y = (
        df["income"]
        .astype(str)
        .str.strip()
        .str.contains(r">50k", case=False, regex=True)
        .astype(int)
        .to_numpy()
    )
    return y, ["income"], "income (>50k=1)"


def _bank_target(df: pd.DataFrame) -> Tuple[np.ndarray, list[str], str]:
    col = "deposit" if "deposit" in df.columns else "y"
    y = df[col].astype(str).str.lower().isin(["yes", "y", "1", "true"]).astype(int).to_numpy()
    return y, [col], f"{col} (yes=1)"


def _compas_target(df: pd.DataFrame) -> Tuple[np.ndarray, list[str], str]:
    # ProPublica raw extract in this repo does not include a direct recidivism outcome.
    # Use high risk score as a proxy label for model stress-testing.
    decile = pd.to_numeric(df.get("DecileScore", 0), errors="coerce").fillna(0)
    y = (decile >= 7).astype(int).to_numpy()
    drop_cols = [
        "DecileScore",
        "RawScore",
        "ScoreText",
        "LastName",
        "FirstName",
        "MiddleName",
        "DateOfBirth",
        "Screening_Date",
        "Case_ID",
        "AssessmentID",
        "Person_ID",
    ]
    return y, drop_cols, "DecileScore>=7 (proxy high-risk label)"


def _diabetes_target(df: pd.DataFrame) -> Tuple[np.ndarray, list[str], str]:
    # Convert readmission outcome to binary: any readmission vs none.
    y = df["readmitted"].astype(str).str.upper().ne("NO").astype(int).to_numpy()
    drop_cols = ["readmitted", "encounter_id", "patient_nbr"]
    return y, drop_cols, "readmitted!=NO (binary)"


def _german_target(df: pd.DataFrame) -> Tuple[np.ndarray, list[str], str]:
    # Handle either translated or compact German-credit schema.
    if "kredit" in df.columns:
        y = pd.to_numeric(df["kredit"], errors="coerce").fillna(2).astype(int)
        # Common coding: 1=good credit, 2=bad credit.
        y = (y == 2).astype(int).to_numpy()
        if len(np.unique(y)) > 1:
            return y, ["kredit"], "kredit==2 (bad credit)"

        # Some extracted files have a constant kredit label; fallback to proxy risk.
        duration_col = "laufzeit" if "laufzeit" in df.columns else None
        amount_col = "hoehe" if "hoehe" in df.columns else None
        if duration_col and amount_col:
            duration = pd.to_numeric(df[duration_col], errors="coerce").fillna(0)
            amount = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
            y = ((duration > duration.median()) & (amount > amount.median())).astype(int).to_numpy()
            return y, ["kredit"], "proxy_risk: laufzeit>median and hoehe>median"

    if "Risk" in df.columns:
        y = df["Risk"].astype(str).str.lower().isin(["bad", "1", "yes"]).astype(int).to_numpy()
        return y, ["Risk"], "Risk=bad/1"

    # Fallback proxy when no explicit target exists.
    amount_col = "Credit amount" if "Credit amount" in df.columns else None
    duration_col = "Duration" if "Duration" in df.columns else None
    if amount_col and duration_col:
        amount = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        duration = pd.to_numeric(df[duration_col], errors="coerce").fillna(0)
        y = ((amount > amount.median()) & (duration > duration.median())).astype(int).to_numpy()
        return y, [], "proxy_risk: amount>median and duration>median"

    raise ValueError("Could not infer German Credit target column")


def _train_one_model(X: pd.DataFrame, y: np.ndarray, estimator) -> Tuple[object, Dict[str, float]]:
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y if len(np.unique(y)) > 1 else None,
    )

    model = clone(estimator)
    model.fit(X_train, y_train)

    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    return model, {
        "train_accuracy": float(accuracy_score(y_train, y_pred_train)),
        "test_accuracy": float(accuracy_score(y_test, y_pred_test)),
        "test_f1": float(f1_score(y_test, y_pred_test, zero_division=0)),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    dataset_specs: Dict[str, Dict[str, object]] = {
        "adult_income": {
            "filename": "adult.csv",
            "target_fn": _adult_target,
        },
        "bank_marketing": {
            "filename": "bank_marketing.csv",
            "target_fn": _bank_target,
        },
        "compas": {
            "filename": "compas-scores-raw.csv",
            "target_fn": _compas_target,
        },
        "diabetes_readmission": {
            "filename": "diabetes_130_us_hospitals.csv",
            "target_fn": _diabetes_target,
        },
        "german_credit": {
            "filename": "german_credit_data.csv",
            "target_fn": _german_target,
        },
    }

    algorithms = {
        "logistic_regression": Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("lr", LogisticRegression(max_iter=6000, solver="saga", random_state=42)),
            ]
        ),
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
        "gradient_boosting": GradientBoostingClassifier(random_state=42),
    }

    metadata: Dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "output_dir": str(OUTPUT_DIR),
        "datasets": {},
        "models": [],
    }

    total_models = 0

    for dataset_key, spec in dataset_specs.items():
        dataset_path = DATASET_DIR / str(spec["filename"])
        if not dataset_path.exists():
            print(f"[SKIP] {dataset_key}: missing {dataset_path}")
            continue

        df = pd.read_csv(dataset_path)
        target_fn: Callable[[pd.DataFrame], Tuple[np.ndarray, list[str], str]] = spec["target_fn"]  # type: ignore[assignment]
        y, drop_cols, target_desc = target_fn(df)
        X = _safe_numeric_matrix(df, drop_cols)

        unique_labels = np.unique(y)
        if unique_labels.size < 2:
            print(f"[SKIP] {dataset_key}: target has only one class {unique_labels.tolist()}")
            continue

        class_counts = {
            "negative": int((y == 0).sum()),
            "positive": int((y == 1).sum()),
        }

        dataset_output_dir = OUTPUT_DIR / dataset_key
        dataset_output_dir.mkdir(parents=True, exist_ok=True)

        metadata["datasets"][dataset_key] = {
            "path": str(dataset_path),
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "target": target_desc,
            "features_used": list(X.columns),
            "class_balance": class_counts,
        }

        for algo_name, estimator in algorithms.items():
            try:
                model, metrics = _train_one_model(X, y, estimator)
            except Exception as exc:
                print(f"[SKIP] {dataset_key:<22} {algo_name:<20} -> training failed: {exc}")
                continue
            model_path = dataset_output_dir / f"{algo_name}_{timestamp}.joblib"
            joblib.dump(model, model_path)

            metadata["models"].append(
                {
                    "dataset_key": dataset_key,
                    "algorithm": algo_name,
                    "model_path": str(model_path),
                    "metrics": metrics,
                }
            )
            total_models += 1
            print(f"[OK] {dataset_key:<22} {algo_name:<20} -> {model_path.name}")

    metadata_path = OUTPUT_DIR / f"model_zoo_metadata_{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("\nModel zoo training complete.")
    print(f"Models trained: {total_models}")
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
