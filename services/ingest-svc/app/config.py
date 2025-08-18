import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/pp_final"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Service
    port: int = 8005
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Embedding namespace
    embed_namespace: str = "v1/openai/te3l-3072"
    
    # Duration limits
    max_ref_duration_seconds: int = 180
    
    # Word count estimation (words per minute for speech)
    words_per_minute: int = 160
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
