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
import json
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List, Optional, Literal
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset
from app.models.ml_model import MLModel
from app.services.model_loader import UniversalModelLoader

logger = logging.getLogger(__name__)


class ElicitationFeatureMismatchError(Exception):
    """Raised when dataset features are incompatible with the selected model."""


ElicitationMode = Literal["strict", "normal", "lenient"]

# ─── PII column-name signals (mirrors privacy_validator.py) ─────────────────
_PII_SIGNALS = [
    "name", "email", "phone", "ssn", "social", "address", "zip", "postcode",
    "dob", "birth", "passport", "license", "credit", "card", "account",
    "ip", "mac", "gender", "race", "religion", "nationality", "ethnicity",
]

@lru_cache(maxsize=1)
def _load_elicitation_config() -> Dict[str, Any]:
    """Load elicitation thresholds/specs from JSON config."""
    config_path = Path(__file__).with_name("elicitation_config.json")
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


class RequirementElicitor:
    """
    Analyses datasets and model behaviour to auto-generate ethical requirements.

    Generated requirements are returned as plain dicts — they are NOT persisted
    until the user explicitly accepts them via the API.
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_mode(mode: Optional[str]) -> ElicitationMode:
        if mode in ("strict", "normal", "lenient"):
            return mode
        return "normal"

    @staticmethod
    def _check_result(
        *,
        check_id: str,
        status: str,
        reason: str,
        value: Optional[Any] = None,
        threshold: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "check_id": check_id,
            "status": status,
            "value": value,
            "threshold": threshold,
            "reason": reason,
            "metadata": metadata or {},
        }

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

    @staticmethod
    def _get_expected_feature_count(model: Any) -> Optional[int]:
        """Infer expected input feature count from loaded model metadata if available."""
        feature_names = getattr(model, "feature_names", None)
        if isinstance(feature_names, list) and len(feature_names) > 0:
            return len(feature_names)

        raw_model = getattr(model, "raw_model", None)
        if raw_model is not None and hasattr(raw_model, "n_features_in_"):
            try:
                return int(raw_model.n_features_in_)
            except Exception:
                return None
        return None

    # ── public API ───────────────────────────────────────────────────────────

    async def elicit_from_dataset(
        self,
        dataset_id: UUID,
        db: AsyncSession,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
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

        resolved_mode = self._resolve_mode(mode)
        config = _load_elicitation_config()
        mode_thresholds = config["modes"][resolved_mode]

        df = self._load_dataframe(dataset.file_path)
        requirements: List[Dict[str, Any]] = []
        checks: List[Dict[str, Any]] = []

        # 1. PII detection → privacy
        pii_cols = self._detect_pii_columns(df)
        if pii_cols:
            checks.append(self._check_result(
                check_id="dataset_pii_detection",
                status="triggered",
                value=len(pii_cols),
                reason=f"Detected potential PII columns: {', '.join(pii_cols)}",
                metadata={"pii_columns": pii_cols},
            ))
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
                config=config,
            ))
        else:
            checks.append(self._check_result(
                check_id="dataset_pii_detection",
                status="not_triggered",
                value=0,
                reason="No PII-like column names detected.",
            ))

        # 2. Sensitive attribute imbalance → fairness
        sensitive_attrs = dataset.sensitive_attributes or []
        if not sensitive_attrs:
            checks.append(self._check_result(
                check_id="dataset_sensitive_attributes_available",
                status="skipped",
                reason="Dataset has no configured sensitive attributes.",
            ))

        for attr in sensitive_attrs[:3]:   # Check up to 3 sensitive attrs
            if attr not in df.columns:
                checks.append(self._check_result(
                    check_id=f"dataset_sensitive_attr_{attr}",
                    status="skipped",
                    reason=f"Sensitive attribute '{attr}' is not present in dataset columns.",
                ))
                continue
            imbalance = self.calculate_imbalance_ratio(df[attr])
            threshold = float(mode_thresholds["imbalance_threshold"])
            if imbalance > threshold:
                proxies = self.detect_proxy_variables(df, attr)
                proxy_msg = (
                    f"  Proxy variables detected: {proxies}." if proxies else ""
                )
                checks.append(self._check_result(
                    check_id=f"dataset_imbalance_{attr}",
                    status="triggered",
                    value=round(imbalance, 4),
                    threshold=threshold,
                    reason=f"Imbalance {imbalance:.2f} exceeded threshold {threshold:.2f} for '{attr}'.",
                    metadata={"proxy_variables": proxies},
                ))
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
                        f"Imbalance ratio {imbalance:.2f} > {threshold:.2f} for sensitive attribute '{attr}'."
                        + (f" Proxy variables: {proxies}." if proxies else "")
                    ),
                    confidence=min(0.95, 0.60 + imbalance),
                    config=config,
                ))
            else:
                checks.append(self._check_result(
                    check_id=f"dataset_imbalance_{attr}",
                    status="not_triggered",
                    value=round(imbalance, 4),
                    threshold=threshold,
                    reason=f"Imbalance {imbalance:.2f} is within threshold {threshold:.2f} for '{attr}'.",
                ))

        # 3. High feature count → transparency
        feature_count_threshold = int(mode_thresholds["dataset_feature_count_threshold"])
        if df.shape[1] > feature_count_threshold:
            checks.append(self._check_result(
                check_id="dataset_feature_count",
                status="triggered",
                value=int(df.shape[1]),
                threshold=feature_count_threshold,
                reason=f"Feature count {df.shape[1]} exceeded threshold {feature_count_threshold}.",
            ))
            requirements.append(self._make_requirement(
                principle="transparency",
                name=f"Transparency — Explainability for {df.shape[1]}-Feature Model",
                description=(
                    f"Dataset has {df.shape[1]} columns. "
                    "Models trained on high-dimensional data are harder to interpret. "
                    "SHAP global feature importance and per-prediction LIME explanations "
                    "are required, along with a Model Card."
                ),
                reason=f"Feature count {df.shape[1]} > {feature_count_threshold} threshold.",
                confidence=0.80,
                config=config,
            ))
        else:
            checks.append(self._check_result(
                check_id="dataset_feature_count",
                status="not_triggered",
                value=int(df.shape[1]),
                threshold=feature_count_threshold,
                reason=f"Feature count {df.shape[1]} is within threshold {feature_count_threshold}.",
            ))

        # 4. Accountability — always recommend
        checks.append(self._check_result(
            check_id="dataset_accountability_baseline",
            status="triggered",
            reason="Baseline accountability recommendation is always added.",
        ))
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
            config=config,
        ))

        logger.info(
            "Elicited %d requirements from dataset %s using mode=%s",
            len(requirements), dataset_id, resolved_mode,
        )
        return {
            "mode": resolved_mode,
            "suggestions": requirements,
            "evaluated_checks": checks,
        }

    async def elicit_from_model_and_dataset(
        self,
        model_id: UUID,
        dataset_id: UUID,
        db: AsyncSession,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
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

        resolved_mode = self._resolve_mode(mode)
        config = _load_elicitation_config()
        mode_thresholds = config["modes"][resolved_mode]

        df = self._load_dataframe(dataset_obj.file_path)
        requirements: List[Dict[str, Any]] = []
        checks: List[Dict[str, Any]] = []

        # Load model
        try:
            loader = UniversalModelLoader()
            model = loader.load(model_obj.file_path)
        except Exception as exc:
            logger.warning("Could not load model for elicitation: %s", exc)
            raise ValueError(f"Could not load model for elicitation: {exc}") from exc

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
            checks.append(self._check_result(
                check_id="model_feature_matrix_non_empty",
                status="not_triggered",
                reason="No features left after preprocessing.",
            ))
            return {
                "mode": resolved_mode,
                "suggestions": requirements,
                "evaluated_checks": checks,
            }

        logger.debug(
            "Elicitation feature matrix: %d rows × %d cols (model expects features from training)",
            X.shape[0], X.shape[1],
        )

        expected_n_features = self._get_expected_feature_count(model)
        if expected_n_features is not None and X.shape[1] != expected_n_features:
            checks.append(self._check_result(
                check_id="model_feature_compatibility",
                status="failed",
                value=int(X.shape[1]),
                threshold=int(expected_n_features),
                reason="Dataset feature count does not match model expected feature count.",
            ))
            raise ElicitationFeatureMismatchError(
                "Model and dataset feature mismatch: "
                f"model expects {expected_n_features} features, dataset provides {X.shape[1]} features. "
                "Please use the same dataset schema used during training (same columns and preprocessing)."
            )
        checks.append(self._check_result(
            check_id="model_feature_compatibility",
            status="triggered",
            value=int(X.shape[1]),
            threshold=int(expected_n_features) if expected_n_features is not None else None,
            reason="Feature compatibility check passed.",
        ))

        try:
            preds = model.predict(X.values)
        except Exception as exc:
            msg = str(exc)
            mismatch = re.search(r"Expected\s+(\d+)\s+features?,\s+got\s+(\d+)", msg, re.IGNORECASE)
            if mismatch:
                expected = mismatch.group(1)
                got = mismatch.group(2)
                raise ElicitationFeatureMismatchError(
                    "Model and dataset feature mismatch: "
                    f"model expects {expected} features, dataset provides {got} features. "
                    "Please use the same dataset schema used during training (same columns and preprocessing)."
                ) from exc
            logger.warning("Model prediction failed during elicitation: %s", exc)
            raise ValueError(
                "Model prediction failed during elicitation. "
                "Verify model compatibility and preprocessing for the selected dataset."
            ) from exc

        # 1. Prediction class imbalance
        unique, counts = np.unique(preds, return_counts=True)
        if len(unique) >= 2:
            rates = counts / counts.sum()
            min_rate, max_rate = float(rates.min()), float(rates.max())
            imbalance = max_rate - min_rate
            imbalance_threshold = float(mode_thresholds["prediction_imbalance_threshold"])
            if imbalance > imbalance_threshold:
                checks.append(self._check_result(
                    check_id="model_prediction_imbalance",
                    status="triggered",
                    value=round(imbalance, 4),
                    threshold=imbalance_threshold,
                    reason=f"Prediction imbalance {imbalance:.2f} exceeded threshold {imbalance_threshold:.2f}.",
                ))
                requirements.append(self._make_requirement(
                    principle="fairness",
                    name="Fairness — Prediction Imbalance Detected",
                    description=(
                        f"Model predictions are skewed: class rates are "
                        f"{', '.join(f'{u}→{r:.1%}' for u, r in zip(unique, rates))}. "
                        "Demographic Parity and Equalized Odds metrics must be validated."
                    ),
                    reason=f"Prediction imbalance {imbalance:.2f} > {imbalance_threshold:.2f}.",
                    confidence=min(0.92, 0.65 + imbalance),
                    config=config,
                ))
            else:
                checks.append(self._check_result(
                    check_id="model_prediction_imbalance",
                    status="not_triggered",
                    value=round(imbalance, 4),
                    threshold=imbalance_threshold,
                    reason=f"Prediction imbalance {imbalance:.2f} is within threshold {imbalance_threshold:.2f}.",
                ))
        else:
            checks.append(self._check_result(
                check_id="model_prediction_imbalance",
                status="skipped",
                reason="Predictions contain fewer than 2 classes, imbalance check skipped.",
            ))

        # 2. Disparate impact per sensitive attribute
        for attr in sensitive_attrs[:3]:
            if attr not in df.columns:
                checks.append(self._check_result(
                    check_id=f"model_disparate_impact_{attr}",
                    status="skipped",
                    reason=f"Sensitive attribute '{attr}' not found in dataset.",
                ))
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
                di_threshold = float(mode_thresholds["disparate_impact_threshold"])
                if di < di_threshold:
                    rates_str = ", ".join(f"{k}={v:.1%}" for k, v in group_rates.items())
                    checks.append(self._check_result(
                        check_id=f"model_disparate_impact_{attr}",
                        status="triggered",
                        value=round(di, 4),
                        threshold=di_threshold,
                        reason=f"Disparate impact {di:.3f} is below threshold {di_threshold:.2f} for '{attr}'.",
                        metadata={"group_positive_rates": group_rates},
                    ))
                    requirements.append(self._make_requirement(
                        principle="fairness",
                        name=f"Fairness — Disparate Impact on '{attr}'",
                        description=(
                            f"Predicted positive rates: {rates_str}. "
                            f"Disparate Impact Ratio = {di:.3f} (< {di_threshold:.2f} threshold). "
                            "The model may discriminate against certain groups."
                        ),
                        reason=f"Disparate Impact {di:.3f} < {di_threshold:.2f} for attribute '{attr}'.",
                        confidence=min(0.95, 0.80 + (0.80 - di)),
                        config=config,
                    ))
                else:
                    checks.append(self._check_result(
                        check_id=f"model_disparate_impact_{attr}",
                        status="not_triggered",
                        value=round(di, 4),
                        threshold=di_threshold,
                        reason=f"Disparate impact {di:.3f} is within threshold {di_threshold:.2f} for '{attr}'.",
                        metadata={"group_positive_rates": group_rates},
                    ))
            else:
                checks.append(self._check_result(
                    check_id=f"model_disparate_impact_{attr}",
                    status="skipped",
                    reason=f"Could not compute disparate impact for '{attr}' (insufficient group data).",
                ))

        # 3. Feature count → transparency
        n_features = X.shape[1]
        model_feature_count_threshold = int(mode_thresholds["model_feature_count_threshold"])
        if n_features > model_feature_count_threshold:
            checks.append(self._check_result(
                check_id="model_feature_count",
                status="triggered",
                value=n_features,
                threshold=model_feature_count_threshold,
                reason=(
                    f"Model inference used {n_features} features, exceeding threshold {model_feature_count_threshold}."
                ),
            ))
            requirements.append(self._make_requirement(
                principle="transparency",
                name=f"Transparency — {n_features}-Feature Model Explainability",
                description=(
                    f"Model uses {n_features} numeric features. "
                    "SHAP values and LIME explanations are mandatory to ensure "
                    "decision-makers can understand individual predictions."
                ),
                reason=f"Model feature count {n_features} > {model_feature_count_threshold}.",
                confidence=0.85,
                config=config,
            ))
        else:
            checks.append(self._check_result(
                check_id="model_feature_count",
                status="not_triggered",
                value=n_features,
                threshold=model_feature_count_threshold,
                reason=(
                    f"Model inference used {n_features} features, within threshold {model_feature_count_threshold}."
                ),
            ))

        # 4. No triggered findings → add explicit baseline recommendation
        if not requirements:
            checks.append(self._check_result(
                check_id="model_baseline_monitoring",
                status="triggered",
                reason="No high-risk checks triggered; baseline monitoring recommendation added.",
            ))
            requirements.append(self._make_requirement(
                principle="accountability",
                name="Baseline Monitoring — No Immediate Model Risks Triggered",
                description=(
                    "No high-risk fairness or transparency conditions were triggered by the current "
                    "elicitation heuristics for this model-dataset pair. "
                    "Maintain baseline accountability controls: audit trail, periodic fairness checks, "
                    "and monitoring for drift before and after deployment."
                ),
                reason=(
                    "Model elicitation completed successfully with zero risk triggers under current thresholds."
                ),
                confidence=0.70,
                spec_overrides={
                    "rules": [
                        {"metric": "audit_trail_exists", "operator": "==", "value": 1.0},
                        {"metric": "mlflow_run_logged", "operator": "==", "value": 1.0},
                    ],
                    "elicitation_outcome": "no_risk_triggers",
                },
                config=config,
            ))

        logger.info(
            "Elicited %d requirements from model+dataset (%s / %s) using mode=%s",
            len(requirements), model_id, dataset_id, resolved_mode,
        )
        return {
            "mode": resolved_mode,
            "suggestions": requirements,
            "evaluated_checks": checks,
        }

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
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a requirement dict from elicitation findings."""
        loaded_config = config or _load_elicitation_config()
        spec = dict(loaded_config.get("default_specs", {}).get(principle, {"rules": []}))
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
