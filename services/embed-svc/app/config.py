import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/pp_final"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # OpenAI API (ONLY for this service)
    openai_api_key: str
    
    # Service
    port: int = 8001
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Embedding configuration
    embed_namespace: str = "v1/openai/te3l-3072"
    embed_model: str = "text-embedding-3-large"
    embed_dimensions: int = 3072
    
    # Rate limiting
    max_requests_per_minute: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
