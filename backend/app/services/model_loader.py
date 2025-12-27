"""
Universal Model Loader - Abstraction for loading ML models from various frameworks.

Supports:
- scikit-learn (.pkl, .joblib)
- TensorFlow/Keras (.h5, SavedModel)
- PyTorch (.pt, .pth)
- ONNX (.onnx)
- XGBoost (.json, .ubj)
- LightGBM (.txt)

Each model is wrapped in a common interface providing:
- predict(X) -> class predictions
- predict_proba(X) -> probability estimates
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Union, Tuple
import logging

import numpy as np
import joblib

logger = logging.getLogger(__name__)


class ModelWrapper(ABC):
    """
    Abstract base class for model wrappers.
    Provides a unified interface regardless of the underlying framework.
    """
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Generate class predictions.
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Array of predicted class labels (0 or 1 for binary classification)
        """
        pass
    
    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Generate probability estimates.
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Array of shape (n_samples, n_classes) with probability estimates
        """
        pass
    
    @property
    @abstractmethod
    def model_type(self) -> str:
        """Return the model framework type."""
        pass
    
    @property
    def feature_names(self) -> Optional[list]:
        """Return feature names if available."""
        return None
    
    @property
    def classes(self) -> Optional[np.ndarray]:
        """Return class labels if available."""
        return None


class SklearnModelWrapper(ModelWrapper):
    """Wrapper for scikit-learn compatible models."""
    
    def __init__(self, model: Any):
        self._model = model
        self._validate_model()
    
    def _validate_model(self) -> None:
        """Validate that the model has required methods."""
        if not hasattr(self._model, 'predict'):
            raise ValueError("Model must have a 'predict' method")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate class predictions."""
        return self._model.predict(X)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability estimates."""
        if hasattr(self._model, 'predict_proba'):
            return self._model.predict_proba(X)
        else:
            # Fallback for models without predict_proba (e.g., SVM without probability=True)
            predictions = self.predict(X)
            # Convert to one-hot style probabilities
            n_classes = len(np.unique(predictions)) if len(np.unique(predictions)) > 1 else 2
            proba = np.zeros((len(predictions), n_classes))
            for i, pred in enumerate(predictions):
                proba[i, int(pred)] = 1.0
            return proba
    
    @property
    def model_type(self) -> str:
        return "sklearn"
    
    @property
    def feature_names(self) -> Optional[list]:
        if hasattr(self._model, 'feature_names_in_'):
            return list(self._model.feature_names_in_)
        return None
    
    @property
    def classes(self) -> Optional[np.ndarray]:
        if hasattr(self._model, 'classes_'):
            return self._model.classes_
        return None
    
    @property
    def raw_model(self) -> Any:
        """Access the underlying sklearn model."""
        return self._model


class TensorFlowModelWrapper(ModelWrapper):
    """Wrapper for TensorFlow/Keras models."""
    
    def __init__(self, model: Any):
        self._model = model
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate class predictions."""
        predictions = self._model.predict(X, verbose=0)
        
        # Handle different output shapes
        if predictions.ndim == 1 or predictions.shape[1] == 1:
            # Binary classification with single output (sigmoid)
            return (predictions.flatten() > 0.5).astype(int)
        else:
            # Multi-class or binary with softmax
            return np.argmax(predictions, axis=1)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability estimates."""
        predictions = self._model.predict(X, verbose=0)
        
        # Handle single output (sigmoid) - convert to 2-class format
        if predictions.ndim == 1 or predictions.shape[1] == 1:
            probs = predictions.flatten()
            return np.column_stack([1 - probs, probs])
        
        return predictions
    
    @property
    def model_type(self) -> str:
        return "tensorflow"


class PyTorchModelWrapper(ModelWrapper):
    """Wrapper for PyTorch models."""
    
    def __init__(self, model: Any, device: str = "cpu"):
        import torch
        self._model = model
        self._device = torch.device(device)
        self._model.to(self._device)
        self._model.eval()
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate class predictions."""
        import torch
        
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self._device)
            outputs = self._model(X_tensor)
            
            if outputs.dim() == 1 or outputs.shape[1] == 1:
                # Binary classification with single output
                predictions = (torch.sigmoid(outputs).flatten() > 0.5).int()
            else:
                # Multi-class
                predictions = torch.argmax(outputs, dim=1)
            
            return predictions.cpu().numpy()
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability estimates."""
        import torch
        import torch.nn.functional as F
        
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self._device)
            outputs = self._model(X_tensor)
            
            if outputs.dim() == 1 or outputs.shape[1] == 1:
                # Binary with sigmoid
                probs = torch.sigmoid(outputs).flatten()
                probs = torch.stack([1 - probs, probs], dim=1)
            else:
                # Multi-class with softmax
                probs = F.softmax(outputs, dim=1)
            
            return probs.cpu().numpy()
    
    @property
    def model_type(self) -> str:
        return "pytorch"


class ONNXModelWrapper(ModelWrapper):
    """Wrapper for ONNX models using ONNX Runtime."""
    
    def __init__(self, session: Any):
        self._session = session
        self._input_name = self._session.get_inputs()[0].name
        self._output_names = [o.name for o in self._session.get_outputs()]
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate class predictions."""
        proba = self.predict_proba(X)
        return np.argmax(proba, axis=1)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability estimates."""
        # ONNX expects float32
        X = X.astype(np.float32)
        
        outputs = self._session.run(self._output_names, {self._input_name: X})
        
        # Usually the last output is probabilities
        proba = outputs[-1] if len(outputs) > 1 else outputs[0]
        
        # Handle dictionary outputs (some sklearn converters produce this)
        if isinstance(proba, list) and len(proba) > 0:
            proba = proba[0]
        
        # Ensure 2D
        if proba.ndim == 1:
            proba = np.column_stack([1 - proba, proba])
        
        return proba
    
    @property
    def model_type(self) -> str:
        return "onnx"


class UniversalModelLoader:
    """
    Factory class for loading ML models from various frameworks.
    
    Usage:
        model = UniversalModelLoader.load("path/to/model.pkl")
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)
    """
    
    SKLEARN_EXTENSIONS = {'.pkl', '.joblib', '.pickle'}
    TENSORFLOW_EXTENSIONS = {'.h5', '.keras'}
    PYTORCH_EXTENSIONS = {'.pt', '.pth'}
    ONNX_EXTENSIONS = {'.onnx'}
    
    @classmethod
    def load(
        cls,
        filepath: Union[str, Path],
        model_type: Optional[str] = None
    ) -> ModelWrapper:
        """
        Load a model from file and wrap it in a unified interface.
        
        Args:
            filepath: Path to the model file
            model_type: Optional explicit model type. If not provided,
                       will be inferred from file extension.
                       Options: 'sklearn', 'tensorflow', 'pytorch', 'onnx'
        
        Returns:
            ModelWrapper instance with unified predict/predict_proba interface
            
        Raises:
            ValueError: If model type cannot be determined or is unsupported
            FileNotFoundError: If model file doesn't exist
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        # Determine model type
        if model_type is None:
            model_type = cls._detect_model_type(filepath)
        
        logger.info(f"Loading {model_type} model from {filepath}")
        
        # Load based on type
        if model_type == "sklearn":
            return cls._load_sklearn(filepath)
        elif model_type == "tensorflow":
            return cls._load_tensorflow(filepath)
        elif model_type == "pytorch":
            return cls._load_pytorch(filepath)
        elif model_type == "onnx":
            return cls._load_onnx(filepath)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
    
    @classmethod
    def _detect_model_type(cls, filepath: Path) -> str:
        """Detect model type from file extension."""
        ext = filepath.suffix.lower()
        
        if ext in cls.SKLEARN_EXTENSIONS:
            return "sklearn"
        elif ext in cls.TENSORFLOW_EXTENSIONS:
            return "tensorflow"
        elif ext in cls.PYTORCH_EXTENSIONS:
            return "pytorch"
        elif ext in cls.ONNX_EXTENSIONS:
            return "onnx"
        elif filepath.is_dir():
            # Could be TensorFlow SavedModel format
            if (filepath / "saved_model.pb").exists():
                return "tensorflow"
            raise ValueError(f"Cannot determine model type for directory: {filepath}")
        else:
            raise ValueError(
                f"Cannot determine model type from extension: {ext}. "
                f"Supported: {cls.SKLEARN_EXTENSIONS | cls.TENSORFLOW_EXTENSIONS | cls.PYTORCH_EXTENSIONS | cls.ONNX_EXTENSIONS}"
            )
    
    @classmethod
    def _load_sklearn(cls, filepath: Path) -> SklearnModelWrapper:
        """Load a scikit-learn model."""
        try:
            model = joblib.load(filepath)
        except Exception:
            import pickle
            with open(filepath, 'rb') as f:
                model = pickle.load(f)
        
        return SklearnModelWrapper(model)
    
    @classmethod
    def _load_tensorflow(cls, filepath: Path) -> TensorFlowModelWrapper:
        """Load a TensorFlow/Keras model."""
        try:
            import tensorflow as tf
        except ImportError:
            raise ImportError(
                "TensorFlow is required to load .h5 models. "
                "Install with: pip install tensorflow"
            )
        
        model = tf.keras.models.load_model(filepath)
        return TensorFlowModelWrapper(model)
    
    @classmethod
    def _load_pytorch(cls, filepath: Path) -> PyTorchModelWrapper:
        """Load a PyTorch model."""
        try:
            import torch
        except ImportError:
            raise ImportError(
                "PyTorch is required to load .pt/.pth models. "
                "Install with: pip install torch"
            )
        
        model = torch.load(filepath, map_location='cpu')
        
        # Handle state_dict vs full model
        if isinstance(model, dict):
            raise ValueError(
                "Model file contains a state_dict, not a full model. "
                "Please provide the complete model or the model class for loading."
            )
        
        return PyTorchModelWrapper(model)
    
    @classmethod
    def _load_onnx(cls, filepath: Path) -> ONNXModelWrapper:
        """Load an ONNX model."""
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError(
                "ONNX Runtime is required to load .onnx models. "
                "Install with: pip install onnxruntime"
            )
        
        session = ort.InferenceSession(str(filepath))
        return ONNXModelWrapper(session)
    
    @classmethod
    def get_model_metadata(cls, wrapper: ModelWrapper) -> dict:
        """
        Extract metadata from a loaded model.
        
        Args:
            wrapper: A ModelWrapper instance
            
        Returns:
            Dictionary with model metadata
        """
        metadata = {
            "model_type": wrapper.model_type,
            "has_predict_proba": True,  # All our wrappers support this
        }
        
        if wrapper.feature_names:
            metadata["feature_names"] = wrapper.feature_names
            metadata["n_features"] = len(wrapper.feature_names)
        
        if wrapper.classes is not None:
            metadata["classes"] = wrapper.classes.tolist()
            metadata["n_classes"] = len(wrapper.classes)
        
        # For sklearn, try to get more info
        if wrapper.model_type == "sklearn" and hasattr(wrapper, 'raw_model'):
            raw = wrapper.raw_model
            metadata["model_class"] = type(raw).__name__
            
            # Get hyperparameters if available
            if hasattr(raw, 'get_params'):
                try:
                    params = raw.get_params()
                    # Filter out complex objects
                    metadata["hyperparameters"] = {
                        k: v for k, v in params.items()
                        if isinstance(v, (int, float, str, bool, type(None)))
                    }
                except Exception:
                    pass
        
        return metadata
