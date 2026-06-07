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
    api_job_store_path: str = os.getenv("API_JOB_STORE_PATH", "./results/api_jobs.sqlite3")
    api_inline_worker_enabled: bool = os.getenv("API_INLINE_WORKER_ENABLED", "0") == "1"
    api_worker_lease_seconds: int = int(os.getenv("API_WORKER_LEASE_SECONDS", "300"))
    api_worker_heartbeat_interval_seconds: float = float(os.getenv("API_WORKER_HEARTBEAT_INTERVAL_SECONDS", "30"))
    api_validated_runner_enabled: bool = os.getenv("API_VALIDATED_RUNNER_ENABLED", "0") == "1"
    api_validated_runner_profiles_path: str = os.getenv(
        "API_VALIDATED_RUNNER_PROFILES_PATH",
        "./config/api_validated_runner_profiles",
    )
    api_validated_runner_timeout_seconds: int = int(os.getenv("API_VALIDATED_RUNNER_TIMEOUT_SECONDS", "3600"))
    api_result_manifest_signing_key: str = os.getenv(
        "API_RESULT_MANIFEST_SIGNING_KEY",
        "local-dev-result-manifest-signing-key-change-me",
    )
    api_result_manifest_key_id: str = os.getenv("API_RESULT_MANIFEST_KEY_ID", "local-dev")
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))
    redis_db: int = int(os.getenv("REDIS_DB", 0))
    product_api_auth_required: bool = os.getenv("PRODUCT_API_AUTH_REQUIRED", "0") == "1"
    product_api_token: str = os.getenv("PRODUCT_API_TOKEN", "")
    product_api_rate_limit_per_minute: int = int(os.getenv("PRODUCT_API_RATE_LIMIT_PER_MINUTE", "120"))
    product_api_max_payload_bytes: int = int(os.getenv("PRODUCT_API_MAX_PAYLOAD_BYTES", "10485760"))
    product_api_audit_log_path: str = os.getenv("PRODUCT_API_AUDIT_LOG_PATH", "./results/product_audit_log.jsonl")
    product_api_hosted_exposure_approved: bool = os.getenv("PRODUCT_API_HOSTED_EXPOSURE_APPROVED", "0") == "1"
    product_api_tls_termination_operator_verified: bool = os.getenv("PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED", "0") == "1"

settings = Settings()
