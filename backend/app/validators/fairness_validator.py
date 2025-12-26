"""
Fairness Validator - Core fairness validation using Fairlearn library.

Implements validation for multiple fairness metrics:
- Demographic Parity (Statistical Parity)
- Equalized Odds
- Equal Opportunity
- Disparate Impact Ratio

Also provides:
- Group-wise confusion matrices
- Visualization generation (bar charts, heatmaps)
- Detailed fairness reports
"""

import io
import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, accuracy_score

# Fairlearn imports
from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_ratio,
    demographic_parity_difference,
    equalized_odds_ratio,
    equalized_odds_difference,
    selection_rate,
    true_positive_rate,
    false_positive_rate,
    true_negative_rate,
    false_negative_rate
)

logger = logging.getLogger(__name__)


@dataclass
class FairnessMetricResult:
    """Result for a single fairness metric."""
    metric_name: str
    overall_value: float
    by_group: Dict[str, float]
    threshold: float
    passed: bool
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "overall_value": self.overall_value,
            "by_group": self.by_group,
            "threshold": self.threshold,
            "passed": self.passed,
            "description": self.description
        }


@dataclass 
class GroupConfusionMatrix:
    """Confusion matrix for a specific group."""
    group_name: str
    tn: int
    fp: int
    fn: int
    tp: int
    accuracy: float
    tpr: float  # True Positive Rate (Recall/Sensitivity)
    fpr: float  # False Positive Rate
    tnr: float  # True Negative Rate (Specificity)
    fnr: float  # False Negative Rate
    precision: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_name": self.group_name,
            "confusion_matrix": {
                "tn": self.tn, "fp": self.fp,
                "fn": self.fn, "tp": self.tp
            },
            "accuracy": self.accuracy,
            "tpr": self.tpr,
            "fpr": self.fpr,
            "tnr": self.tnr,
            "fnr": self.fnr,
            "precision": self.precision
        }


@dataclass
class FairnessReport:
    """Complete fairness validation report."""
    sensitive_feature: str
    groups: List[str]
    sample_sizes: Dict[str, int]
    metrics: List[FairnessMetricResult]
    confusion_matrices: List[GroupConfusionMatrix]
    overall_passed: bool
    visualizations: Dict[str, str] = field(default_factory=dict)  # base64 encoded images
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensitive_feature": self.sensitive_feature,
            "groups": self.groups,
            "sample_sizes": self.sample_sizes,
            "metrics": [m.to_dict() for m in self.metrics],
            "confusion_matrices": [cm.to_dict() for cm in self.confusion_matrices],
            "overall_passed": self.overall_passed,
            "visualizations": self.visualizations
        }


class FairnessValidator:
    """
    Validates ML model predictions for fairness across demographic groups.
    
    Usage:
        validator = FairnessValidator(
            y_true=y_test,
            y_pred=model.predict(X_test),
            sensitive_features=df['gender']
        )
        
        # Run all fairness checks
        report = validator.validate_all(thresholds={
            'demographic_parity_ratio': 0.8,
            'equalized_odds_difference': 0.1
        })
        
        # Or check individual metrics
        dp_result = validator.demographic_parity(threshold=0.8)
    """
    
    # Default thresholds based on common standards (e.g., 80% rule)
    DEFAULT_THRESHOLDS = {
        "demographic_parity_ratio": 0.8,
        "demographic_parity_difference": 0.1,
        "equalized_odds_ratio": 0.8,
        "equalized_odds_difference": 0.1,
        "equal_opportunity_difference": 0.1,
        "disparate_impact_ratio": 0.8
    }
    
    def __init__(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        sensitive_features: Union[np.ndarray, pd.Series],
        y_prob: Optional[np.ndarray] = None
    ):
        """
        Initialize the fairness validator.
        
        Args:
            y_true: Ground truth labels (0/1 for binary classification)
            y_pred: Model predictions (0/1 for binary classification)
            sensitive_features: Sensitive attribute values for each sample
            y_prob: Optional probability predictions (for ROC-based metrics)
        """
        self.y_true = np.asarray(y_true).flatten()
        self.y_pred = np.asarray(y_pred).flatten()
        self.sensitive_features = np.asarray(sensitive_features).flatten()
        self.y_prob = np.asarray(y_prob).flatten() if y_prob is not None else None
        
        # Validate inputs
        if len(self.y_true) != len(self.y_pred):
            raise ValueError("y_true and y_pred must have the same length")
        if len(self.y_true) != len(self.sensitive_features):
            raise ValueError("y_true and sensitive_features must have the same length")
        
        # Get unique groups
        self.groups = np.unique(self.sensitive_features)
        self.group_names = [str(g) for g in self.groups]
        
        # Calculate sample sizes per group
        self.sample_sizes = {
            str(g): int(np.sum(self.sensitive_features == g))
            for g in self.groups
        }
        
        # Create MetricFrame for efficient group-wise calculations
        self._metric_frame = MetricFrame(
            metrics={
                'selection_rate': selection_rate,
                'accuracy': accuracy_score,
                'tpr': true_positive_rate,
                'fpr': false_positive_rate,
                'tnr': true_negative_rate,
                'fnr': false_negative_rate
            },
            y_true=self.y_true,
            y_pred=self.y_pred,
            sensitive_features=self.sensitive_features
        )
        
        logger.info(f"FairnessValidator initialized with {len(self.groups)} groups: {self.group_names}")
    
    def demographic_parity(
        self,
        threshold: Optional[float] = None
    ) -> FairnessMetricResult:
        """
        Calculate Demographic Parity (Statistical Parity).
        
        Demographic parity requires that the selection rate (positive prediction rate)
        is approximately equal across all groups.
        
        Metric: demographic_parity_ratio = min(selection_rate) / max(selection_rate)
        Passes if ratio >= threshold (default 0.8, the "80% rule")
        
        Args:
            threshold: Minimum acceptable ratio (default 0.8)
            
        Returns:
            FairnessMetricResult with metric details
        """
        threshold = threshold or self.DEFAULT_THRESHOLDS["demographic_parity_ratio"]
        
        # Calculate ratio
        ratio = demographic_parity_ratio(
            self.y_true,
            self.y_pred,
            sensitive_features=self.sensitive_features
        )
        
        # Get per-group selection rates
        by_group = self._metric_frame.by_group['selection_rate'].to_dict()
        by_group = {str(k): float(v) for k, v in by_group.items()}
        
        return FairnessMetricResult(
            metric_name="demographic_parity_ratio",
            overall_value=float(ratio),
            by_group=by_group,
            threshold=threshold,
            passed=ratio >= threshold,
            description=(
                f"Selection rate ratio: {ratio:.3f}. "
                f"Rates by group: {', '.join(f'{k}={v:.2%}' for k, v in by_group.items())}. "
                f"{'Passed' if ratio >= threshold else 'Failed'} threshold of {threshold:.2f}."
            )
        )
    
    def demographic_parity_diff(
        self,
        threshold: Optional[float] = None
    ) -> FairnessMetricResult:
        """
        Calculate Demographic Parity Difference.
        
        Measures the maximum difference in selection rates between any two groups.
        Difference = max(selection_rate) - min(selection_rate)
        Passes if difference <= threshold (default 0.1)
        """
        threshold = threshold or self.DEFAULT_THRESHOLDS["demographic_parity_difference"]
        
        diff = demographic_parity_difference(
            self.y_true,
            self.y_pred,
            sensitive_features=self.sensitive_features
        )
        
        by_group = self._metric_frame.by_group['selection_rate'].to_dict()
        by_group = {str(k): float(v) for k, v in by_group.items()}
        
        return FairnessMetricResult(
            metric_name="demographic_parity_difference",
            overall_value=float(diff),
            by_group=by_group,
            threshold=threshold,
            passed=diff <= threshold,
            description=(
                f"Selection rate difference: {diff:.3f}. "
                f"{'Passed' if diff <= threshold else 'Failed'} threshold of {threshold:.2f}."
            )
        )
    
    def equalized_odds(
        self,
        threshold: Optional[float] = None,
        use_ratio: bool = True
    ) -> FairnessMetricResult:
        """
        Calculate Equalized Odds.
        
        Equalized odds requires that both True Positive Rate (TPR) and 
        False Positive Rate (FPR) are equal across groups.
        
        Args:
            threshold: Threshold for the metric
            use_ratio: If True, use ratio metric (min/max). If False, use difference.
            
        Returns:
            FairnessMetricResult
        """
        if use_ratio:
            threshold = threshold or self.DEFAULT_THRESHOLDS["equalized_odds_ratio"]
            value = equalized_odds_ratio(
                self.y_true,
                self.y_pred,
                sensitive_features=self.sensitive_features
            )
            passed = value >= threshold
            metric_name = "equalized_odds_ratio"
        else:
            threshold = threshold or self.DEFAULT_THRESHOLDS["equalized_odds_difference"]
            value = equalized_odds_difference(
                self.y_true,
                self.y_pred,
                sensitive_features=self.sensitive_features
            )
            passed = value <= threshold
            metric_name = "equalized_odds_difference"
        
        # Get per-group TPR and FPR
        tpr_by_group = self._metric_frame.by_group['tpr'].to_dict()
        fpr_by_group = self._metric_frame.by_group['fpr'].to_dict()
        
        by_group = {
            str(k): {"tpr": float(tpr_by_group[k]), "fpr": float(fpr_by_group[k])}
            for k in tpr_by_group
        }
        
        return FairnessMetricResult(
            metric_name=metric_name,
            overall_value=float(value),
            by_group=by_group,
            threshold=threshold,
            passed=passed,
            description=(
                f"Equalized odds {'ratio' if use_ratio else 'difference'}: {value:.3f}. "
                f"{'Passed' if passed else 'Failed'} threshold of {threshold:.2f}."
            )
        )
    
    def equal_opportunity(
        self,
        threshold: Optional[float] = None
    ) -> FairnessMetricResult:
        """
        Calculate Equal Opportunity.
        
        Equal opportunity is a relaxation of equalized odds that only
        requires equal True Positive Rates (TPR) across groups.
        This ensures equal benefit for qualified individuals regardless of group.
        
        Args:
            threshold: Maximum acceptable TPR difference (default 0.1)
            
        Returns:
            FairnessMetricResult
        """
        threshold = threshold or self.DEFAULT_THRESHOLDS["equal_opportunity_difference"]
        
        # Get TPR by group
        tpr_by_group = self._metric_frame.by_group['tpr'].to_dict()
        tpr_values = list(tpr_by_group.values())
        
        # Calculate difference
        diff = max(tpr_values) - min(tpr_values)
        
        by_group = {str(k): float(v) for k, v in tpr_by_group.items()}
        
        return FairnessMetricResult(
            metric_name="equal_opportunity_difference",
            overall_value=float(diff),
            by_group=by_group,
            threshold=threshold,
            passed=diff <= threshold,
            description=(
                f"True Positive Rate difference: {diff:.3f}. "
                f"TPR by group: {', '.join(f'{k}={v:.2%}' for k, v in by_group.items())}. "
                f"{'Passed' if diff <= threshold else 'Failed'} threshold of {threshold:.2f}."
            )
        )
    
    def disparate_impact(
        self,
        threshold: Optional[float] = None
    ) -> FairnessMetricResult:
        """
        Calculate Disparate Impact Ratio.
        
        This is similar to demographic parity ratio but specifically
        measures the ratio of positive outcomes between groups.
        Common in legal contexts (80% rule in US employment law).
        
        Args:
            threshold: Minimum acceptable ratio (default 0.8)
            
        Returns:
            FairnessMetricResult
        """
        threshold = threshold or self.DEFAULT_THRESHOLDS["disparate_impact_ratio"]
        
        # Calculate selection rates
        by_group = self._metric_frame.by_group['selection_rate'].to_dict()
        rates = list(by_group.values())
        
        # Disparate impact = min_rate / max_rate
        if max(rates) > 0:
            ratio = min(rates) / max(rates)
        else:
            ratio = 1.0  # If no positive predictions, consider it fair
        
        by_group = {str(k): float(v) for k, v in by_group.items()}
        
        return FairnessMetricResult(
            metric_name="disparate_impact_ratio",
            overall_value=float(ratio),
            by_group=by_group,
            threshold=threshold,
            passed=ratio >= threshold,
            description=(
                f"Disparate impact ratio: {ratio:.3f}. "
                f"{'Passed' if ratio >= threshold else 'Failed'} 80% rule threshold of {threshold:.2f}."
            )
        )
    
    def compute_group_confusion_matrices(self) -> List[GroupConfusionMatrix]:
        """
        Calculate confusion matrix for each demographic group.
        
        Returns:
            List of GroupConfusionMatrix objects with detailed metrics per group
        """
        matrices = []
        
        for group in self.groups:
            mask = self.sensitive_features == group
            y_true_group = self.y_true[mask]
            y_pred_group = self.y_pred[mask]
            
            # Calculate confusion matrix
            cm = confusion_matrix(y_true_group, y_pred_group, labels=[0, 1])
            tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
            
            # Calculate rates
            total = tn + fp + fn + tp
            accuracy = (tn + tp) / total if total > 0 else 0
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0  # Sensitivity/Recall
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            tnr = tn / (tn + fp) if (tn + fp) > 0 else 0  # Specificity
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            
            matrices.append(GroupConfusionMatrix(
                group_name=str(group),
                tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp),
                accuracy=float(accuracy),
                tpr=float(tpr),
                fpr=float(fpr),
                tnr=float(tnr),
                fnr=float(fnr),
                precision=float(precision)
            ))
        
        return matrices
    
    def generate_visualizations(self) -> Dict[str, str]:
        """
        Generate visualization plots as base64-encoded PNG images.
        
        Returns:
            Dictionary mapping visualization names to base64 strings
        """
        visualizations = {}
        
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            # 1. Selection Rate Bar Chart
            fig, ax = plt.subplots(figsize=(10, 6))
            selection_rates = self._metric_frame.by_group['selection_rate']
            bars = ax.bar(
                [str(g) for g in selection_rates.index],
                selection_rates.values,
                color='steelblue',
                edgecolor='black'
            )
            ax.set_xlabel('Group', fontsize=12)
            ax.set_ylabel('Selection Rate', fontsize=12)
            ax.set_title('Selection Rate by Demographic Group', fontsize=14)
            ax.set_ylim(0, 1)
            
            # Add value labels
            for bar, rate in zip(bars, selection_rates.values):
                ax.text(
                    bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.02,
                    f'{rate:.2%}',
                    ha='center', va='bottom', fontsize=10
                )
            
            # Add 80% rule reference line
            min_rate = min(selection_rates.values)
            ax.axhline(y=min_rate / 0.8, color='red', linestyle='--', 
                      label=f'80% Rule Threshold ({min_rate/0.8:.2%})')
            ax.legend()
            
            plt.tight_layout()
            visualizations['selection_rate_chart'] = self._fig_to_base64(fig)
            plt.close(fig)
            
            # 2. TPR/FPR Comparison Chart
            fig, ax = plt.subplots(figsize=(10, 6))
            x = np.arange(len(self.groups))
            width = 0.35
            
            tpr_values = [self._metric_frame.by_group['tpr'][g] for g in self.groups]
            fpr_values = [self._metric_frame.by_group['fpr'][g] for g in self.groups]
            
            bars1 = ax.bar(x - width/2, tpr_values, width, label='TPR', color='green', alpha=0.7)
            bars2 = ax.bar(x + width/2, fpr_values, width, label='FPR', color='red', alpha=0.7)
            
            ax.set_xlabel('Group', fontsize=12)
            ax.set_ylabel('Rate', fontsize=12)
            ax.set_title('True Positive Rate vs False Positive Rate by Group', fontsize=14)
            ax.set_xticks(x)
            ax.set_xticklabels([str(g) for g in self.groups])
            ax.set_ylim(0, 1)
            ax.legend()
            
            plt.tight_layout()
            visualizations['tpr_fpr_chart'] = self._fig_to_base64(fig)
            plt.close(fig)
            
            # 3. Confusion Matrix Heatmaps
            cms = self.compute_group_confusion_matrices()
            n_groups = len(cms)
            fig, axes = plt.subplots(1, n_groups, figsize=(5*n_groups, 4))
            if n_groups == 1:
                axes = [axes]
            
            for ax, cm in zip(axes, cms):
                matrix = np.array([[cm.tn, cm.fp], [cm.fn, cm.tp]])
                sns.heatmap(
                    matrix, annot=True, fmt='d', cmap='Blues',
                    xticklabels=['Pred 0', 'Pred 1'],
                    yticklabels=['True 0', 'True 1'],
                    ax=ax
                )
                ax.set_title(f'Group: {cm.group_name}\nAcc: {cm.accuracy:.2%}')
            
            plt.suptitle('Confusion Matrices by Group', fontsize=14, y=1.02)
            plt.tight_layout()
            visualizations['confusion_matrices'] = self._fig_to_base64(fig)
            plt.close(fig)
            
        except Exception as e:
            logger.warning(f"Failed to generate visualizations: {e}")
        
        return visualizations
    
    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 string."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    
    def validate_all(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        include_visualizations: bool = True
    ) -> FairnessReport:
        """
        Run all fairness validations and generate comprehensive report.
        
        Args:
            thresholds: Dictionary mapping metric names to threshold values.
                       Uses defaults for any not specified.
            include_visualizations: Whether to generate visualization plots
            
        Returns:
            FairnessReport with all metrics and optional visualizations
        """
        thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        
        # Calculate all metrics
        metrics = [
            self.demographic_parity(thresholds.get('demographic_parity_ratio')),
            self.demographic_parity_diff(thresholds.get('demographic_parity_difference')),
            self.equalized_odds(thresholds.get('equalized_odds_ratio'), use_ratio=True),
            self.equalized_odds(thresholds.get('equalized_odds_difference'), use_ratio=False),
            self.equal_opportunity(thresholds.get('equal_opportunity_difference')),
            self.disparate_impact(thresholds.get('disparate_impact_ratio'))
        ]
        
        # Calculate confusion matrices
        confusion_matrices = self.compute_group_confusion_matrices()
        
        # Overall pass/fail
        overall_passed = all(m.passed for m in metrics)
        
        # Generate visualizations
        visualizations = {}
        if include_visualizations:
            visualizations = self.generate_visualizations()
        
        report = FairnessReport(
            sensitive_feature="sensitive_attribute",  # Can be customized
            groups=self.group_names,
            sample_sizes=self.sample_sizes,
            metrics=metrics,
            confusion_matrices=confusion_matrices,
            overall_passed=overall_passed,
            visualizations=visualizations
        )
        
        logger.info(
            f"Fairness validation complete. "
            f"Passed: {sum(m.passed for m in metrics)}/{len(metrics)} metrics. "
            f"Overall: {'PASSED' if overall_passed else 'FAILED'}"
        )
        
        return report
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a quick summary of fairness metrics without full report.
        
        Returns:
            Dictionary with key fairness metrics
        """
        dp = self.demographic_parity()
        eo = self.equalized_odds()
        di = self.disparate_impact()
        
        return {
            "groups": self.group_names,
            "sample_sizes": self.sample_sizes,
            "demographic_parity_ratio": dp.overall_value,
            "equalized_odds_ratio": eo.overall_value,
            "disparate_impact_ratio": di.overall_value,
            "selection_rates": dp.by_group,
            "overall_fair": dp.passed and eo.passed and di.passed
        }
