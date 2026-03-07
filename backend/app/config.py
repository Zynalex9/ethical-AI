"""
Configuration management using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

import os
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env" if os.path.exists(".env") else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = "Ethical AI Requirements Engineering Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api/v1"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ethical_ai"
    database_echo: bool = False
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # JWT Authentication
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # File Storage
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 500
    allowed_model_extensions: List[str] = [".pkl", ".joblib", ".pickle", ".h5", ".keras", ".pt", ".pth", ".onnx"]
    allowed_dataset_extensions: List[str] = [".csv", ".xlsx", ".parquet"]
    
    # MLflow - Use absolute path to avoid working directory issues between Celery and FastAPI
    mlflow_tracking_uri: str = "sqlite:///./mlflow.db"
    mlflow_experiment_name: str = "ethical-ai-validations"
    mlflow_artifact_location: str = "./mlruns"  # Will be converted to absolute path in __init__
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    def __init__(self, **data):
        """Initialize settings and convert relative paths to absolute."""
        super().__init__(**data)
        
        # Convert relative paths to absolute based on the backend directory
        # Get the directory where this config.py file is located (backend/app/)
        config_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(config_dir)  # Go up to backend/
        
        # Convert mlflow_artifact_location to absolute path
        if not os.path.isabs(self.mlflow_artifact_location):
            self.mlflow_artifact_location = os.path.abspath(
                os.path.join(backend_dir, self.mlflow_artifact_location)
            )
        
        # Convert mlflow_tracking_uri if it's a SQLite file URI
        if self.mlflow_tracking_uri.startswith("sqlite:///./"):
            db_path = self.mlflow_tracking_uri.replace("sqlite:///./", "")
            abs_db_path = os.path.abspath(os.path.join(backend_dir, db_path))
            self.mlflow_tracking_uri = f"sqlite:///{abs_db_path}"
        
        # Convert upload_dir to absolute path
        if not os.path.isabs(self.upload_dir):
            self.upload_dir = os.path.abspath(
                os.path.join(backend_dir, self.upload_dir)
            )
        
        # Log paths for debugging (use stdlib since our structured logger isn't ready yet)
        import logging as _log
        _log.getLogger("ethical_ai.config").info(
            "Config loaded – backend=%s  mlflow=%s  uploads=%s",
            backend_dir, self.mlflow_tracking_uri, self.upload_dir,
        )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to avoid reading .env file on every request.
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
