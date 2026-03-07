"""
Differential Privacy Checker for EthicScan AI.

Measures ε-sensitivity of a dataset based on quasi-identifier columns,
optionally applies Laplace noise to achieve a target ε budget, and
reports whether the resulting ε satisfies the user-set budget.
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DPResult:
    """Result of a Differential Privacy check."""
    measured_epsilon: float
    target_epsilon: float
    budget_satisfied: bool
    sensitivities: Dict[str, float] = field(default_factory=dict)
    noise_applied: bool = False
    noised_epsilon: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DifferentialPrivacyChecker:
    """
    Measures and optionally enforces differential privacy on a dataset.

    Workflow:
    1. Compute per-column global sensitivity (range) for quasi-identifier columns.
    2. Estimate the current effective ε using sensitivity / noise_floor.
    3. Optionally apply calibrated Laplace noise to achieve a target ε budget.
    4. Return a ``DPResult`` with measured ε, budget compliance, etc.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        quasi_identifiers: List[str],
        target_epsilon: float = 1.0,
        apply_noise: bool = False,
    ) -> DPResult:
        """
        Run the DP check.

        Parameters
        ----------
        quasi_identifiers : list[str]
            Columns treated as quasi-identifiers whose sensitivity is measured.
        target_epsilon : float
            The privacy budget the user wants to satisfy (lower = more private).
        apply_noise : bool
            If True, Laplace noise calibrated to ``target_epsilon`` is added
            to numeric quasi-identifier columns (on a *copy* of the data).

        Returns
        -------
        DPResult
        """
        if not quasi_identifiers:
            return DPResult(
                measured_epsilon=0.0,
                target_epsilon=target_epsilon,
                budget_satisfied=True,
                details={"message": "No quasi-identifiers provided; nothing to measure."},
            )

        # Validate columns exist
        missing = [c for c in quasi_identifiers if c not in self.df.columns]
        if missing:
            raise ValueError(f"Columns not found in dataset: {missing}")

        # 1. Compute per-column sensitivity (global sensitivity = max − min)
        sensitivities: Dict[str, float] = {}
        for col in quasi_identifiers:
            sensitivities[col] = self._column_sensitivity(col)

        # 2. Aggregate ε estimate (sum of per-column ε via composition theorem)
        measured_epsilon = self._estimate_epsilon(sensitivities)

        budget_satisfied = measured_epsilon <= target_epsilon

        result = DPResult(
            measured_epsilon=round(measured_epsilon, 6),
            target_epsilon=target_epsilon,
            budget_satisfied=budget_satisfied,
            sensitivities={k: round(v, 6) for k, v in sensitivities.items()},
        )

        # 3. Optionally apply Laplace noise
        if apply_noise:
            noised_df, noised_eps = self._apply_laplace_noise(
                quasi_identifiers, sensitivities, target_epsilon
            )
            result.noise_applied = True
            result.noised_epsilon = round(noised_eps, 6)
            result.details["noise_scales"] = {
                col: round(sensitivities[col] / target_epsilon, 6)
                for col in quasi_identifiers
                if sensitivities[col] > 0
            }
            result.details["message"] = (
                f"Laplace noise applied to {len(quasi_identifiers)} column(s). "
                f"Post-noise ε ≈ {round(noised_eps, 6)}."
            )
        else:
            result.details["message"] = (
                f"Measured ε = {round(measured_epsilon, 6)} "
                f"(target = {target_epsilon}). "
                f"{'Budget SATISFIED.' if budget_satisfied else 'Budget EXCEEDED.'}"
            )

        logger.info(
            "DP check: measured_ε=%.4f target_ε=%.4f satisfied=%s noise=%s",
            measured_epsilon,
            target_epsilon,
            budget_satisfied,
            apply_noise,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _column_sensitivity(self, col: str) -> float:
        """Compute global sensitivity of a single column.

        For numeric columns: sensitivity = max − min.
        For categorical columns: sensitivity = 1.0 (Hamming distance).
        """
        series = self.df[col]
        if pd.api.types.is_numeric_dtype(series):
            col_min = series.min()
            col_max = series.max()
            if pd.isna(col_min) or pd.isna(col_max):
                return 1.0
            return float(col_max - col_min)
        # Categorical / string: use Hamming-style sensitivity
        return 1.0

    def _estimate_epsilon(self, sensitivities: Dict[str, float]) -> float:
        """
        Estimate the effective ε of the dataset.

        Uses a heuristic: for each quasi-identifier, ε_col ≈ Δf / σ_col
        where σ_col is the standard deviation (proxy for inherent noise).
        The total ε is the sum over columns (sequential composition).

        If σ is very small or zero the column is nearly constant and
        contributes a high ε (very identifiable).
        """
        total_epsilon = 0.0
        noise_floor = 1e-6  # avoid division by zero

        for col, sensitivity in sensitivities.items():
            if sensitivity == 0:
                continue
            series = self.df[col]
            if pd.api.types.is_numeric_dtype(series):
                sigma = float(series.std())
                sigma = max(sigma, noise_floor)
                col_epsilon = sensitivity / sigma
            else:
                # Categorical: ε = n_unique / n_rows (heuristic)
                n_unique = series.nunique()
                col_epsilon = n_unique / max(len(series), 1)
            total_epsilon += col_epsilon

        return total_epsilon

    def _apply_laplace_noise(
        self,
        quasi_identifiers: List[str],
        sensitivities: Dict[str, float],
        target_epsilon: float,
    ) -> tuple:
        """Apply Laplace noise to numeric quasi-identifier columns.

        Returns (noised_dataframe, achieved_epsilon).
        """
        df_noised = self.df.copy()
        per_col_epsilon = target_epsilon / max(len(quasi_identifiers), 1)

        for col in quasi_identifiers:
            sensitivity = sensitivities[col]
            if sensitivity == 0 or not pd.api.types.is_numeric_dtype(df_noised[col]):
                continue
            scale = sensitivity / per_col_epsilon
            noise = np.random.laplace(0, scale, size=len(df_noised))
            df_noised[col] = df_noised[col].astype(float) + noise

        # Re-estimate ε on the noised data
        checker = DifferentialPrivacyChecker(df_noised)
        new_sensitivities: Dict[str, float] = {}
        for col in quasi_identifiers:
            new_sensitivities[col] = checker._column_sensitivity(col)
        noised_epsilon = checker._estimate_epsilon(new_sensitivities)

        return df_noised, noised_epsilon
