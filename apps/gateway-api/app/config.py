import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Environment
    app_env: str = os.getenv("APP_ENV", "dev")

    # Database - environment-specific
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pp_final")

    # Redis - environment-specific
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Service URLs - environment-specific defaults
    ingest_service_url: str = os.getenv("INGEST_SERVICE_URL", "http://localhost:8001")
    embed_service_url: str = os.getenv("EMBED_SERVICE_URL", "http://localhost:8002")
    retrieval_service_url: str = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8003")
    editor_service_url: str = os.getenv("EDITOR_SERVICE_URL", "http://localhost:8004")
    reddit_sync_service_url: str = os.getenv("REDDIT_SYNC_SERVICE_URL", "http://localhost:8005")
    
    # Google OAuth - required environment variables
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    oauth_callback_url: str = os.getenv("OAUTH_CALLBACK_URL", "http://localhost:8000/api/oauth/callback")

    # JWT - required environment variables
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    # CORS - environment-specific
    allowed_origins: List[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
    
    # Service
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Rate limiting
    rate_limit_requests_per_minute: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    def __post_init__(self):
        """Validate required environment variables"""
        required_vars = []

        if not self.google_client_id:
            required_vars.append("GOOGLE_CLIENT_ID")
        if not self.google_client_secret:
            required_vars.append("GOOGLE_CLIENT_SECRET")
        if not self.jwt_secret:
            required_vars.append("JWT_SECRET")

        if required_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(required_vars)}")

settings = Settings()
