"""
Explainability Engine - Transparency validation using SHAP and LIME.

Implements:
- Global SHAP explanations (feature importance across dataset)
- Local SHAP explanations (individual prediction explanations)
- LIME explanations (local interpretable model-agnostic)
- Model card generation
- Visualization artifacts (summary plots, force plots, waterfall)

Reference: Implements "design publicity" concept from Loi et al. (2021)
- Value Transparency: What the model is designed to achieve
- Translation Transparency: How goals became mathematical objectives  
- Performance Transparency: How well goals were achieved
"""

import io
import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Callable
from pathlib import Path
import logging
import warnings

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Suppress warnings from SHAP/LIME
warnings.filterwarnings('ignore', category=UserWarning)


@dataclass
class FeatureImportance:
    """Single feature importance result."""
    feature_name: str
    importance: float
    rank: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "importance": self.importance,
            "rank": self.rank
        }


@dataclass
class LocalExplanation:
    """Explanation for a single prediction."""
    instance_index: int
    prediction: int
    prediction_probability: float
    feature_contributions: Dict[str, float]  # feature -> contribution
    base_value: float
    explanation_type: str  # "shap" or "lime"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_index": self.instance_index,
            "prediction": self.prediction,
            "prediction_probability": self.prediction_probability,
            "feature_contributions": self.feature_contributions,
            "base_value": self.base_value,
            "explanation_type": self.explanation_type
        }


@dataclass
class GlobalExplanation:
    """Global model explanation (feature importances)."""
    feature_importances: List[FeatureImportance]
    method: str  # "shap" or "permutation"
    n_samples_used: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_importances": [fi.to_dict() for fi in self.feature_importances],
            "method": self.method,
            "n_samples_used": self.n_samples_used
        }
    
    def top_features(self, n: int = 10) -> List[FeatureImportance]:
        """Get top N most important features."""
        return sorted(
            self.feature_importances, 
            key=lambda x: abs(x.importance), 
            reverse=True
        )[:n]


@dataclass
class TransparencyReport:
    """Complete transparency/explainability report."""
    global_explanation: Optional[GlobalExplanation]
    local_explanations: List[LocalExplanation]
    model_card: Dict[str, Any]
    visualizations: Dict[str, str]  # name -> base64 encoded image
    validation_passed: bool
    validation_details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "global_explanation": self.global_explanation.to_dict() if self.global_explanation else None,
            "local_explanations": [le.to_dict() for le in self.local_explanations],
            "model_card": self.model_card,
            "visualizations": self.visualizations,
            "validation_passed": self.validation_passed,
            "validation_details": self.validation_details
        }


class ExplainabilityEngine:
    """
    Engine for generating model explanations using SHAP and LIME.
    
    Provides both global (model-level) and local (instance-level) explanations
    to satisfy transparency requirements.
    
    Usage:
        engine = ExplainabilityEngine(
            model=model,  # Must have predict/predict_proba methods
            X_train=X_train,  # Background data for SHAP
            feature_names=feature_names
        )
        
        # Get global explanation
        global_exp = engine.explain_global(X_test)
        
        # Get local explanation for specific instance
        local_exp = engine.explain_local(X_test[0:1])
        
        # Generate full report
        report = engine.generate_report(X_test, n_local_samples=5)
    """
    
    def __init__(
        self,
        model: Any,
        X_train: np.ndarray,
        feature_names: Optional[List[str]] = None,
        class_names: Optional[List[str]] = None,
        model_name: str = "Unknown Model",
        model_description: str = ""
    ):
        """
        Initialize the explainability engine.
        
        Args:
            model: Trained model with predict/predict_proba methods
            X_train: Training data for background sampling (SHAP)
            feature_names: Names of features (optional, will use indices if not provided)
            class_names: Names of classes for classification
            model_name: Name of the model for documentation
            model_description: Description of what the model does
        """
        self.model = model
        self.X_train = np.asarray(X_train)
        self.n_features = self.X_train.shape[1]
        
        # Set feature names
        if feature_names is not None:
            self.feature_names = list(feature_names)
        else:
            self.feature_names = [f"feature_{i}" for i in range(self.n_features)]
        
        self.class_names = class_names or ["Class 0", "Class 1"]
        self.model_name = model_name
        self.model_description = model_description
        
        # SHAP explainer (lazy initialization)
        self._shap_explainer = None
        self._shap_values = None
        
        logger.info(f"ExplainabilityEngine initialized for {model_name} with {self.n_features} features")
    
    def _get_predict_fn(self) -> Callable:
        """Get prediction function for SHAP/LIME."""
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba
        else:
            return self.model.predict
    
    def _init_shap_explainer(self, background_samples: int = 100) -> None:
        """Initialize SHAP KernelExplainer with background data."""
        try:
            import shap
            
            # Sample background data if training set is large
            if len(self.X_train) > background_samples:
                indices = np.random.choice(
                    len(self.X_train), 
                    background_samples, 
                    replace=False
                )
                background = self.X_train[indices]
            else:
                background = self.X_train
            
            # Use KernelExplainer for model-agnostic explanations
            self._shap_explainer = shap.KernelExplainer(
                self._get_predict_fn(),
                background
            )
            
            logger.info(f"SHAP KernelExplainer initialized with {len(background)} background samples")
            
        except ImportError:
            raise ImportError("SHAP is required. Install with: pip install shap")
    
    def explain_global_shap(
        self,
        X: np.ndarray,
        max_samples: int = 200
    ) -> GlobalExplanation:
        """
        Generate global SHAP explanation (feature importances).
        
        Args:
            X: Data to explain (test set)
            max_samples: Maximum samples to use for SHAP calculation
            
        Returns:
            GlobalExplanation with feature importances
        """
        import shap
        
        if self._shap_explainer is None:
            self._init_shap_explainer()
        
        # Sample if data is too large
        if len(X) > max_samples:
            indices = np.random.choice(len(X), max_samples, replace=False)
            X_sample = X[indices]
        else:
            X_sample = X
        
        logger.info(f"Computing SHAP values for {len(X_sample)} samples...")
        
        # Compute SHAP values
        shap_values = self._shap_explainer.shap_values(X_sample)
        
        # Handle multi-output (binary classification returns list)
        if isinstance(shap_values, list):
            # Use positive class SHAP values
            shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        
        # Store for visualization
        self._shap_values = shap_values
        self._X_explained = X_sample
        
        # Calculate mean absolute SHAP values per feature
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        
        # Create feature importance list
        importances = []
        for i, (name, importance) in enumerate(zip(self.feature_names, mean_abs_shap)):
            importances.append(FeatureImportance(
                feature_name=name,
                importance=float(importance),
                rank=0  # Will be set after sorting
            ))
        
        # Sort and assign ranks
        importances.sort(key=lambda x: abs(x.importance), reverse=True)
        for rank, fi in enumerate(importances, 1):
            fi.rank = rank
        
        return GlobalExplanation(
            feature_importances=importances,
            method="shap",
            n_samples_used=len(X_sample)
        )
    
    def explain_local_shap(
        self,
        X: np.ndarray,
        instance_indices: Optional[List[int]] = None
    ) -> List[LocalExplanation]:
        """
        Generate local SHAP explanations for specific instances.
        
        Args:
            X: Data containing instances to explain
            instance_indices: Indices of instances to explain (default: all)
            
        Returns:
            List of LocalExplanation objects
        """
        import shap
        
        if self._shap_explainer is None:
            self._init_shap_explainer()
        
        if instance_indices is None:
            instance_indices = list(range(len(X)))
        
        explanations = []
        
        for idx in instance_indices:
            instance = X[idx:idx+1]
            
            # Compute SHAP values for this instance
            shap_values = self._shap_explainer.shap_values(instance)
            
            # Handle multi-output
            if isinstance(shap_values, list):
                values = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
            else:
                values = shap_values[0]
            
            # Get prediction
            pred = self.model.predict(instance)[0]
            
            # Get probability
            if hasattr(self.model, 'predict_proba'):
                prob = self.model.predict_proba(instance)[0]
                pred_prob = prob[1] if len(prob) > 1 else prob[0]
            else:
                pred_prob = float(pred)
            
            # Create feature contribution dict
            contributions = {
                name: float(value)
                for name, value in zip(self.feature_names, values)
            }
            
            explanations.append(LocalExplanation(
                instance_index=idx,
                prediction=int(pred),
                prediction_probability=float(pred_prob),
                feature_contributions=contributions,
                base_value=float(self._shap_explainer.expected_value[1] 
                               if isinstance(self._shap_explainer.expected_value, (list, np.ndarray))
                               else self._shap_explainer.expected_value),
                explanation_type="shap"
            ))
        
        return explanations
    
    def explain_local_lime(
        self,
        X: np.ndarray,
        instance_indices: Optional[List[int]] = None,
        num_features: int = 10
    ) -> List[LocalExplanation]:
        """
        Generate local LIME explanations for specific instances.
        
        LIME (Local Interpretable Model-agnostic Explanations) fits a
        simple linear model around each prediction to explain it.
        
        Args:
            X: Data containing instances to explain
            instance_indices: Indices of instances to explain
            num_features: Number of top features to include in explanation
            
        Returns:
            List of LocalExplanation objects
        """
        try:
            from lime.lime_tabular import LimeTabularExplainer
        except ImportError:
            raise ImportError("LIME is required. Install with: pip install lime")
        
        # Initialize LIME explainer
        explainer = LimeTabularExplainer(
            training_data=self.X_train,
            feature_names=self.feature_names,
            class_names=self.class_names,
            mode='classification'
        )
        
        if instance_indices is None:
            instance_indices = list(range(len(X)))
        
        explanations = []
        
        for idx in instance_indices:
            instance = X[idx]
            
            # Generate LIME explanation
            exp = explainer.explain_instance(
                instance,
                self._get_predict_fn(),
                num_features=num_features,
                top_labels=1
            )
            
            # Get prediction
            pred = self.model.predict(instance.reshape(1, -1))[0]
            
            # Get probability
            if hasattr(self.model, 'predict_proba'):
                prob = self.model.predict_proba(instance.reshape(1, -1))[0]
                pred_prob = prob[1] if len(prob) > 1 else prob[0]
            else:
                pred_prob = float(pred)
            
            # Extract feature contributions
            label = exp.available_labels()[0]
            contributions = {}
            for feature, weight in exp.as_list(label=label):
                # Parse feature name from LIME format (e.g., "age > 30")
                # Extract the base feature name
                for name in self.feature_names:
                    if name in feature:
                        contributions[name] = float(weight)
                        break
            
            explanations.append(LocalExplanation(
                instance_index=idx,
                prediction=int(pred),
                prediction_probability=float(pred_prob),
                feature_contributions=contributions,
                base_value=0.5,  # LIME doesn't have base value like SHAP
                explanation_type="lime"
            ))
        
        return explanations
    
    def generate_model_card(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a model card documenting the model's characteristics.
        
        Based on "Model Cards for Model Reporting" by Mitchell et al.
        Implements design publicity from Loi et al.
        
        Args:
            X_test: Test features
            y_test: Test labels
            additional_info: Additional metadata to include
            
        Returns:
            Model card as dictionary
        """
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        # Get predictions
        y_pred = self.model.predict(X_test)
        
        # Calculate metrics
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1_score": float(f1_score(y_test, y_pred, zero_division=0))
        }
        
        # Build model card
        model_card = {
            "model_details": {
                "name": self.model_name,
                "description": self.model_description,
                "model_type": type(self.model).__name__,
                "n_features": self.n_features,
                "feature_names": self.feature_names,
                "class_names": self.class_names
            },
            "intended_use": {
                "primary_use": "Binary classification",
                "out_of_scope": "Not specified",
                "users": "AI developers and auditors"
            },
            "training_data": {
                "n_samples": len(self.X_train),
                "n_features": self.n_features
            },
            "evaluation_data": {
                "n_samples": len(X_test)
            },
            "performance_metrics": metrics,
            "ethical_considerations": {
                "fairness_validated": False,
                "transparency_validated": True,
                "privacy_validated": False
            }
        }
        
        # Add additional info
        if additional_info:
            model_card["additional_info"] = additional_info
        
        return model_card
    
    def generate_visualizations(
        self,
        X: Optional[np.ndarray] = None,
        include_summary: bool = True,
        include_bar: bool = True,
        include_waterfall: bool = True,
        local_instance_idx: int = 0
    ) -> Dict[str, str]:
        """
        Generate SHAP visualization plots as base64 images.
        
        Args:
            X: Data to explain (uses stored values if None)
            include_summary: Include SHAP summary plot
            include_bar: Include feature importance bar plot
            include_waterfall: Include waterfall plot for single instance
            local_instance_idx: Instance index for waterfall plot
            
        Returns:
            Dictionary mapping plot names to base64 strings
        """
        import shap
        import matplotlib.pyplot as plt
        
        visualizations = {}
        
        # Ensure we have SHAP values
        if self._shap_values is None and X is not None:
            self.explain_global_shap(X)
        
        if self._shap_values is None:
            logger.warning("No SHAP values available for visualization")
            return visualizations
        
        try:
            # 1. Summary Plot (beeswarm)
            if include_summary:
                plt.figure(figsize=(10, 8))
                shap.summary_plot(
                    self._shap_values,
                    self._X_explained,
                    feature_names=self.feature_names,
                    show=False
                )
                plt.title("SHAP Summary Plot", fontsize=14)
                plt.tight_layout()
                visualizations['shap_summary'] = self._fig_to_base64(plt.gcf())
                plt.close()
            
            # 2. Bar Plot (feature importance)
            if include_bar:
                plt.figure(figsize=(10, 6))
                shap.summary_plot(
                    self._shap_values,
                    self._X_explained,
                    feature_names=self.feature_names,
                    plot_type="bar",
                    show=False
                )
                plt.title("Feature Importance (Mean |SHAP|)", fontsize=14)
                plt.tight_layout()
                visualizations['shap_bar'] = self._fig_to_base64(plt.gcf())
                plt.close()
            
            # 3. Waterfall for single instance
            if include_waterfall and local_instance_idx < len(self._shap_values):
                try:
                    # Create Explanation object for waterfall
                    explanation = shap.Explanation(
                        values=self._shap_values[local_instance_idx],
                        base_values=self._shap_explainer.expected_value[1] 
                            if isinstance(self._shap_explainer.expected_value, (list, np.ndarray))
                            else self._shap_explainer.expected_value,
                        data=self._X_explained[local_instance_idx],
                        feature_names=self.feature_names
                    )
                    
                    plt.figure(figsize=(10, 6))
                    shap.plots.waterfall(explanation, show=False)
                    plt.title(f"SHAP Waterfall (Instance {local_instance_idx})", fontsize=14)
                    plt.tight_layout()
                    visualizations['shap_waterfall'] = self._fig_to_base64(plt.gcf())
                    plt.close()
                except Exception as e:
                    logger.warning(f"Could not generate waterfall plot: {e}")
            
        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")
        
        return visualizations
    
    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 string."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    
    def validate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate transparency requirements.
        
        Args:
            X_test: Test features
            y_test: Test labels
            requirements: Transparency requirements to validate
            
        Returns:
            Validation results dictionary
        """
        default_requirements = {
            "global_explanation_required": True,
            "local_explanation_required": True,
            "min_features_documented": 5,
            "shap_required": True,
            "lime_required": False,
            "model_card_required": True
        }
        
        reqs = {**default_requirements, **(requirements or {})}
        
        results = {
            "passed": True,
            "checks": []
        }
        
        # Check 1: Global explanation
        if reqs["global_explanation_required"]:
            try:
                global_exp = self.explain_global_shap(X_test)
                n_documented = len(global_exp.feature_importances)
                check_passed = n_documented >= reqs["min_features_documented"]
                results["checks"].append({
                    "name": "global_explanation",
                    "passed": check_passed,
                    "details": f"Documented {n_documented} features (required: {reqs['min_features_documented']})"
                })
                if not check_passed:
                    results["passed"] = False
            except Exception as e:
                results["checks"].append({
                    "name": "global_explanation",
                    "passed": False,
                    "details": f"Failed to generate: {str(e)}"
                })
                results["passed"] = False
        
        # Check 2: Local explanation
        if reqs["local_explanation_required"]:
            try:
                local_exp = self.explain_local_shap(X_test, [0])
                results["checks"].append({
                    "name": "local_explanation",
                    "passed": True,
                    "details": "Successfully generated local SHAP explanation"
                })
            except Exception as e:
                results["checks"].append({
                    "name": "local_explanation",
                    "passed": False,
                    "details": f"Failed to generate: {str(e)}"
                })
                results["passed"] = False
        
        # Check 3: LIME explanation
        if reqs["lime_required"]:
            try:
                lime_exp = self.explain_local_lime(X_test, [0])
                results["checks"].append({
                    "name": "lime_explanation",
                    "passed": True,
                    "details": "Successfully generated LIME explanation"
                })
            except Exception as e:
                results["checks"].append({
                    "name": "lime_explanation",
                    "passed": False,
                    "details": f"Failed to generate: {str(e)}"
                })
                results["passed"] = False
        
        # Check 4: Model card
        if reqs["model_card_required"]:
            try:
                model_card = self.generate_model_card(X_test, y_test)
                results["checks"].append({
                    "name": "model_card",
                    "passed": True,
                    "details": "Model card generated successfully"
                })
                results["model_card"] = model_card
            except Exception as e:
                results["checks"].append({
                    "name": "model_card",
                    "passed": False,
                    "details": f"Failed to generate: {str(e)}"
                })
                results["passed"] = False
        
        return results
    
    def generate_report(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        n_local_samples: int = 5,
        include_visualizations: bool = True,
        requirements: Optional[Dict[str, Any]] = None
    ) -> TransparencyReport:
        """
        Generate comprehensive transparency report.
        
        Args:
            X_test: Test features
            y_test: Test labels
            n_local_samples: Number of instances for local explanations
            include_visualizations: Whether to generate visualization plots
            requirements: Requirements to validate against
            
        Returns:
            TransparencyReport with all explanations and validation results
        """
        logger.info("Generating comprehensive transparency report...")
        
        # Global explanation
        global_exp = self.explain_global_shap(X_test)
        
        # Local explanations (sample instances)
        indices = np.random.choice(len(X_test), min(n_local_samples, len(X_test)), replace=False)
        local_exps = self.explain_local_shap(X_test, list(indices))
        
        # Generate model card
        model_card = self.generate_model_card(X_test, y_test)
        
        # Generate visualizations
        visualizations = {}
        if include_visualizations:
            visualizations = self.generate_visualizations()
        
        # Validate requirements
        validation = self.validate(X_test, y_test, requirements)
        
        report = TransparencyReport(
            global_explanation=global_exp,
            local_explanations=local_exps,
            model_card=model_card,
            visualizations=visualizations,
            validation_passed=validation["passed"],
            validation_details=validation
        )
        
        logger.info(f"Transparency report generated. Validation: {'PASSED' if report.validation_passed else 'FAILED'}")
        
        return report
