import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/pp_final"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Service URLs
    ingest_service_url: str = "http://localhost:8005"
    embed_service_url: str = "http://localhost:8001"
    retrieval_service_url: str = "http://localhost:8002"
    editor_service_url: str = "http://localhost:8003"
    reddit_sync_service_url: str = "http://localhost:8004"
    
    # Google OAuth
    google_client_id: str
    google_client_secret: str
    oauth_callback_url: str = "http://localhost:8000/api/oauth/callback"
    
    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # CORS
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    
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

settings = Settings()
