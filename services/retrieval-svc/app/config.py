import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/pp_final"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Service
    port: int = 8002
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Embedding service URL
    embed_service_url: str = "http://localhost:8001"
    
    # Retrieval configuration
    embed_namespace: str = "v1/openai/te3l-3072"
    max_ref_duration_seconds: int = 180
    max_candidates: int = 100
    max_alternates: int = 5
    
    # Performance reranking weights
    similarity_weight: float = 0.6
    performance_weight: float = 0.4
    
    # Recency decay for performance scoring
    recency_decay_days: int = 365  # 1 year
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
