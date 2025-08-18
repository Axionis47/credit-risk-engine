from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
import structlog
import uvicorn

from app.config import settings
from app.database import get_db, init_db
from app.sync_service import SyncService

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(
    title="Reddit Sync Service",
    description="Reddit API integration for fetching and storing ideas",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
sync_service = SyncService()

# Request/Response models
class SyncRequest(BaseModel):
    subreddits: Optional[List[str]] = None
    max_posts_per_subreddit: Optional[int] = None
    min_score: Optional[int] = None
    max_age_hours: Optional[int] = None

class SyncResponse(BaseModel):
    inserted: int
    skipped_duplicates: int
    errors: List[str]
    processing_time_seconds: float
    subreddits_processed: List[str]

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    await init_db()
    logger.info("Reddit sync service started", 
                port=settings.port,
                default_subreddits=settings.default_subreddits)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-12-01T00:00:00Z",
        "service": "reddit-sync-svc",
        "version": "1.0.0",
        "default_subreddits": settings.default_subreddits
    }

@app.post("/sync", response_model=SyncResponse)
async def sync_ideas(
    request: SyncRequest = SyncRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync ideas from Reddit subreddits
    
    Args:
        request: Sync configuration (optional, uses defaults if not provided)
        
    Returns:
        Sync report with statistics
    """
    try:
        # Validate subreddits if provided
        if request.subreddits:
            for subreddit in request.subreddits:
                if not subreddit.replace('_', '').replace('-', '').isalnum():
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid subreddit name: {subreddit}"
                    )
        
        # Validate limits
        if request.max_posts_per_subreddit and request.max_posts_per_subreddit > 100:
            raise HTTPException(
                status_code=400,
                detail="max_posts_per_subreddit cannot exceed 100"
            )
        
        if request.max_age_hours and request.max_age_hours > 168:  # 1 week
            raise HTTPException(
                status_code=400,
                detail="max_age_hours cannot exceed 168 (1 week)"
            )
        
        # Perform sync
        result = await sync_service.sync_ideas(
            subreddits=request.subreddits,
            max_posts_per_subreddit=request.max_posts_per_subreddit,
            min_score=request.min_score,
            max_age_hours=request.max_age_hours,
            db=db
        )
        
        logger.info("Sync completed successfully", 
                   inserted=result["inserted"],
                   skipped_duplicates=result["skipped_duplicates"],
                   errors_count=len(result["errors"]))
        
        return SyncResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sync failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
