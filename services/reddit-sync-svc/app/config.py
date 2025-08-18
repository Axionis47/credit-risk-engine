import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/pp_final"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Reddit API
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str = "IdeaHunter/1.0"
    
    # Service
    port: int = 8004
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Default subreddits to sync
    default_subreddits: List[str] = [
        "AskReddit",
        "todayilearned",
        "LifeProTips",
        "explainlikeimfive",
        "Showerthoughts",
        "unpopularopinion",
        "relationship_advice",
        "AmItheAsshole",
        "tifu",
        "confession"
    ]
    
    # Sync configuration
    max_posts_per_subreddit: int = 50
    min_score: int = 10
    max_age_hours: int = 24
    
    # Rate limiting
    requests_per_minute: int = 60  # Reddit API limit
    cache_duration_minutes: int = 15
    
    # Content filtering
    max_title_length: int = 300
    max_snippet_length: int = 1000
    min_snippet_length: int = 50
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
