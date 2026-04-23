# api/config.py

from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    app_name: str = "MICF API Server"
    admin_email: str = "admin@example.com"
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    # database_url: str = os.getenv("DATABASE_URL", "sqlite:///./micf.db")
    model_storage_path: str = "./models/" # Path to load models from
    results_storage_path: str = "./results/" # Path to store results
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))
    redis_db: int = int(os.getenv("REDIS_DB", 0))

settings = Settings()
