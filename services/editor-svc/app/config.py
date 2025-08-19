import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Anthropic API (ONLY for this service)
    anthropic_api_key: str
    
    # Service
    port: int = 8003
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Redis - environment-specific
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # AI Configuration
    model_name: str = "claude-3-5-sonnet-20241022"  # Latest Sonnet
    max_tokens: int = 4000
    temperature: float = 0.7
    
    # Coherence scoring
    coherence_threshold: float = 0.85
    max_tuner_passes: int = 1
    
    # Content limits
    max_input_length: int = 10000
    target_word_count: int = 900
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
