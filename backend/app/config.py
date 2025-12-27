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
    max_upload_size_mb: int = 100
    allowed_model_extensions: List[str] = [".pkl", ".joblib", ".h5", ".pt", ".pth", ".onnx"]
    allowed_dataset_extensions: List[str] = [".csv", ".parquet", ".json"]
    
    # MLflow
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    mlflow_experiment_name: str = "ethical-ai-validations"
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to avoid reading .env file on every request.
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
