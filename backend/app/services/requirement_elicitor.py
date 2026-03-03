"""
Requirement Elicitor Service — Phase 2 (Cognitive RE)

Automatically generates ethical AI requirements by analysing:
  - Dataset characteristics (class imbalance, PII, column count)
  - Model predictions (disparate impact, feature richness)

Each generated requirement is a Dict ready to be shown to the user for
review before being saved to the database.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset
from app.models.ml_model import MLModel
from app.services.model_loader import UniversalModelLoader

logger = logging.getLogger(__name__)

# ─── PII column-name signals (mirrors privacy_validator.py) ─────────────────
_PII_SIGNALS = [
    "name", "email", "phone", "ssn", "social", "address", "zip", "postcode",
    "dob", "birth", "passport", "license", "credit", "card", "account",
    "ip", "mac", "gender", "race", "religion", "nationality", "ethnicity",
]

# ─── Default threshold specs per principle ──────────────────────────────────
_DEFAULT_SPECS: Dict[str, Dict[str, Any]] = {
    "fairness": {
        "rules": [
            {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.8},
            {"metric": "equalized_odds_ratio",     "operator": ">=", "value": 0.8},
            {"metric": "disparate_impact_ratio",   "operator": ">=", "value": 0.8},
        ]
    },
    "transparency": {
        "rules": [
            {"metric": "shap_explanation_coverage", "operator": ">=", "value": 1.0},
            {"metric": "model_card_generated",      "operator": "==", "value": 1.0},
        ]
    },
    "privacy": {
        "rules": [
            {"metric": "k_anonymity_k",   "operator": ">=", "value": 5},
            {"metric": "pii_columns_detected", "operator": "==", "value": 0},
        ]
    },
    "accountability": {
        "rules": [
            {"metric": "audit_trail_exists", "operator": "==", "value": 1.0},
            {"metric": "mlflow_run_logged",  "operator": "==", "value": 1.0},
        ]
    },
}


class RequirementElicitor:
    """
    Analyses datasets and model behaviour to auto-generate ethical requirements.

    Generated requirements are returned as plain dicts — they are NOT persisted
    until the user explicitly accepts them via the API.
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _load_dataframe(file_path: str) -> pd.DataFrame:
        """Load CSV or Parquet from disk."""
        if file_path.endswith(".parquet"):
            return pd.read_parquet(file_path)
        return pd.read_csv(file_path, low_memory=False)

    @staticmethod
    def calculate_imbalance_ratio(series: pd.Series) -> float:
        """
        Returns the imbalance ratio of a categorical column.
        0.0 = perfectly balanced, 1.0 = only one class.
        """
        counts = series.dropna().value_counts(normalize=True)
        if len(counts) < 2:
            return 1.0
        return float(1.0 - counts.min())

    @staticmethod
    def detect_proxy_variables(df: pd.DataFrame, sensitive_attr: str) -> List[str]:
        """
        Identify numeric columns that are highly correlated with a sensitive attribute.
        Uses Cramér's V for categorical vs numeric (binarised) and Pearson for numeric.
        Returns column names with correlation > 0.5.
        """
        if sensitive_attr not in df.columns:
            return []

        proxies: List[str] = []
        sensitive = df[sensitive_attr].dropna()

        # If sensitive attr is categorical, encode it
        if sensitive.dtype == object or str(sensitive.dtype) == "category":
            codes = pd.Categorical(sensitive).codes
        else:
            codes = sensitive.values

        for col in df.select_dtypes(include=[np.number]).columns:
            if col == sensitive_attr:
                continue
            col_vals = df[col].dropna()
            # Align indices
            common = sensitive.index.intersection(col_vals.index)
            if len(common) < 10:
                continue
            try:
                corr = float(np.corrcoef(codes[common], col_vals.loc[common])[0, 1])
                if abs(corr) > 0.5:
                    proxies.append(col)
            except Exception:
                pass

        return proxies

    @staticmethod
    def _detect_pii_columns(df: pd.DataFrame) -> List[str]:
        """Return column names that look like PII by name matching."""
        pii_cols: List[str] = []
        for col in df.columns:
            col_norm = col.lower().replace("_", "").replace("-", "").replace(" ", "")
            if any(sig in col_norm for sig in _PII_SIGNALS):
                pii_cols.append(col)
        return pii_cols

    # ── public API ───────────────────────────────────────────────────────────

    async def elicit_from_dataset(
        self,
        dataset_id: UUID,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Analyse a dataset and return a list of auto-generated requirement dicts.

        Rules applied:
        - PII columns detected → privacy requirement
        - Sensitive attribute imbalance > 30%  → fairness requirement
        - Many columns (> 15) → transparency requirement
        - Always propose accountability requirement
        """
        # Load dataset metadata
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        df = self._load_dataframe(dataset.file_path)
        requirements: List[Dict[str, Any]] = []

        # 1. PII detection → privacy
        pii_cols = self._detect_pii_columns(df)
        if pii_cols:
            requirements.append(self._make_requirement(
                principle="privacy",
                name=f"Privacy Protection — {dataset.name}",
                description=(
                    f"Dataset contains {len(pii_cols)} potential PII column(s): "
                    f"{', '.join(pii_cols[:6])}{'…' if len(pii_cols) > 6 else ''}. "
                    "k-Anonymity (k≥5) and PII-free data are required before model training."
                ),
                reason=(
                    f"Privacy-sensitive columns detected by column-name analysis: {pii_cols}."
                ),
                confidence=0.90,
                spec_overrides={"pii_columns": pii_cols},
            ))

        # 2. Sensitive attribute imbalance → fairness
        sensitive_attrs = dataset.sensitive_attributes or []
        for attr in sensitive_attrs[:3]:   # Check up to 3 sensitive attrs
            if attr not in df.columns:
                continue
            imbalance = self.calculate_imbalance_ratio(df[attr])
            if imbalance > 0.30:
                proxies = self.detect_proxy_variables(df, attr)
                proxy_msg = (
                    f"  Proxy variables detected: {proxies}." if proxies else ""
                )
                requirements.append(self._make_requirement(
                    principle="fairness",
                    name=f"Fairness — Demographic Parity on '{attr}'",
                    description=(
                        f"Sensitive attribute '{attr}' has an imbalance ratio of "
                        f"{imbalance:.1%}, suggesting unequal group representation. "
                        f"Model must achieve Demographic Parity Ratio ≥ 0.80 and "
                        f"Equalized Odds Ratio ≥ 0.80 across groups.{proxy_msg}"
                    ),
                    reason=(
                        f"Imbalance ratio {imbalance:.2f} > 0.30 for sensitive attribute '{attr}'."
                        + (f" Proxy variables: {proxies}." if proxies else "")
                    ),
                    confidence=min(0.95, 0.60 + imbalance),
                ))

        # 3. High feature count → transparency
        if df.shape[1] > 15:
            requirements.append(self._make_requirement(
                principle="transparency",
                name=f"Transparency — Explainability for {df.shape[1]}-Feature Model",
                description=(
                    f"Dataset has {df.shape[1]} columns. "
                    "Models trained on high-dimensional data are harder to interpret. "
                    "SHAP global feature importance and per-prediction LIME explanations "
                    "are required, along with a Model Card."
                ),
                reason=f"Feature count {df.shape[1]} > 15 threshold.",
                confidence=0.80,
            ))

        # 4. Accountability — always recommend
        requirements.append(self._make_requirement(
            principle="accountability",
            name=f"Accountability — Audit Trail for '{dataset.name}'",
            description=(
                "An immutable audit trail must be maintained for every validation run. "
                "MLflow should log model metadata, dataset fingerprints, computed metrics, "
                "and pass/fail status for regulatory compliance."
            ),
            reason="Accountability is a fundamental requirement for all AI deployments.",
            confidence=1.0,
        ))

        logger.info(
            "Elicited %d requirements from dataset %s", len(requirements), dataset_id
        )
        return requirements

    async def elicit_from_model_and_dataset(
        self,
        model_id: UUID,
        dataset_id: UUID,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Run the model on the dataset and generate behaviour-based requirements.

        Analyses:
        - Prediction class imbalance → fairness
        - Number of model features → transparency
        - Sensitive attribute disparate impact → fairness
        """
        # Load DB objects
        model_result = await db.execute(select(MLModel).where(MLModel.id == model_id))
        model_obj = model_result.scalar_one_or_none()
        dataset_result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset_obj = dataset_result.scalar_one_or_none()

        if model_obj is None:
            raise ValueError(f"Model {model_id} not found")
        if dataset_obj is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        df = self._load_dataframe(dataset_obj.file_path)
        requirements: List[Dict[str, Any]] = []

        # Load model
        try:
            loader = UniversalModelLoader()
            model = loader.load(model_obj.file_path)
        except Exception as exc:
            logger.warning("Could not load model for elicitation: %s", exc)
            return requirements

        # Prepare features (drop target if known)
        target = dataset_obj.target_column
        feature_cols = [c for c in df.columns if c != target] if target else list(df.columns)
        sensitive_attrs = dataset_obj.sensitive_attributes or []

        X = df[feature_cols].copy()
        # Label-encode categorical columns so feature count matches what the model was trained on
        for col in X.select_dtypes(include=["object", "category"]).columns:
            X[col] = pd.factorize(X[col])[0].astype(float)
        X = X.fillna(0)

        if X.empty or len(X) == 0:
            logger.warning("No features after preprocessing — skipping model elicitation")
            return requirements

        logger.debug(
            "Elicitation feature matrix: %d rows × %d cols (model expects features from training)",
            X.shape[0], X.shape[1],
        )

        try:
            preds = model.predict(X.values)
        except Exception as exc:
            logger.warning("Model prediction failed during elicitation: %s", exc)
            return requirements

        # 1. Prediction class imbalance
        unique, counts = np.unique(preds, return_counts=True)
        if len(unique) >= 2:
            rates = counts / counts.sum()
            min_rate, max_rate = float(rates.min()), float(rates.max())
            imbalance = max_rate - min_rate
            if imbalance > 0.30:
                requirements.append(self._make_requirement(
                    principle="fairness",
                    name="Fairness — Prediction Imbalance Detected",
                    description=(
                        f"Model predictions are skewed: class rates are "
                        f"{', '.join(f'{u}→{r:.1%}' for u, r in zip(unique, rates))}. "
                        "Demographic Parity and Equalized Odds metrics must be validated."
                    ),
                    reason=f"Prediction imbalance {imbalance:.2f} > 0.30.",
                    confidence=min(0.92, 0.65 + imbalance),
                ))

        # 2. Disparate impact per sensitive attribute
        for attr in sensitive_attrs[:3]:
            if attr not in df.columns:
                continue
            groups = df[attr].dropna().unique()
            if len(groups) < 2:
                continue
            # Align predictions with full df
            pred_series = pd.Series(preds, index=X.index)
            group_rates: Dict[str, float] = {}
            for g in groups:
                mask = df[attr] == g
                idx = mask[mask].index.intersection(pred_series.index)
                if len(idx) == 0:
                    continue
                group_rates[str(g)] = float(pred_series.loc[idx].mean())

            if len(group_rates) >= 2:
                r_vals = list(group_rates.values())
                di = min(r_vals) / max(r_vals) if max(r_vals) > 0 else 1.0
                if di < 0.80:
                    rates_str = ", ".join(f"{k}={v:.1%}" for k, v in group_rates.items())
                    requirements.append(self._make_requirement(
                        principle="fairness",
                        name=f"Fairness — Disparate Impact on '{attr}'",
                        description=(
                            f"Predicted positive rates: {rates_str}. "
                            f"Disparate Impact Ratio = {di:.3f} (< 0.80 threshold). "
                            "The model may discriminate against certain groups."
                        ),
                        reason=f"Disparate Impact {di:.3f} < 0.80 for attribute '{attr}'.",
                        confidence=min(0.95, 0.80 + (0.80 - di)),
                    ))

        # 3. Feature count → transparency
        n_features = X.shape[1]
        if n_features > 10:
            requirements.append(self._make_requirement(
                principle="transparency",
                name=f"Transparency — {n_features}-Feature Model Explainability",
                description=(
                    f"Model uses {n_features} numeric features. "
                    "SHAP values and LIME explanations are mandatory to ensure "
                    "decision-makers can understand individual predictions."
                ),
                reason=f"Model feature count {n_features} > 10.",
                confidence=0.85,
            ))

        logger.info(
            "Elicited %d requirements from model+dataset (%s / %s)",
            len(requirements), model_id, dataset_id,
        )
        return requirements

    # ── internal factory ─────────────────────────────────────────────────────

    def _make_requirement(
        self,
        *,
        principle: str,
        name: str,
        description: str,
        reason: str,
        confidence: float,
        spec_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a requirement dict from elicitation findings."""
        spec = dict(_DEFAULT_SPECS.get(principle, {"rules": []}))
        if spec_overrides:
            spec.update(spec_overrides)
        return {
            "name": name,
            "principle": principle,
            "description": description,
            "specification": spec,
            "elicited_automatically": True,
            "elicitation_reason": reason,
            "confidence_score": round(max(0.0, min(1.0, confidence)), 4),
            "status": "draft",
        }
