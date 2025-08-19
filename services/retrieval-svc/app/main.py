from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import structlog
import uvicorn

from app.config import settings
from app.database import get_db, init_db
from app.retrieval_service import RetrievalService

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
    title="Retrieval Service",
    description="Vector similarity search and performance reranking service",
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
retrieval_service = RetrievalService()

# Request/Response models
class RetrieveRequest(BaseModel):
    draft_body: str

class PerformanceMetrics(BaseModel):
    views: int
    ctr: Optional[float] = None
    avg_view_duration_s: Optional[float] = None
    retention_30s: Optional[float] = None

class ReferenceScript(BaseModel):
    video_id: str
    body: str
    duration_seconds: float
    performance: PerformanceMetrics
    similarity_score: float
    performance_score: float
    combined_score: float

class RetrieveResponse(BaseModel):
    ref: Optional[ReferenceScript] = None
    alternates: List[ReferenceScript] = []
    total_candidates: int
    search_time_ms: float
    reason: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    logger.info("Starting retrieval service...",
                port=settings.port,
                embed_service_url=settings.embed_service_url,
                database_url=settings.database_url[:50] + "..." if len(settings.database_url) > 50 else settings.database_url)

    # Don't fail startup if database is not available - handle it gracefully
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning("Database initialization failed, will retry on first request",
                      error=str(e),
                      error_type=type(e).__name__)

    logger.info("Retrieval service started successfully")

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-12-01T00:00:00Z",
        "service": "retrieval-svc",
        "version": "1.0.0",
        "embed_service_url": settings.embed_service_url
    }

@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_reference(
    request: RetrieveRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the best reference script for a draft
    
    Args:
        request: Draft body text
        
    Returns:
        Best reference script and alternates
    """
    try:
        if not request.draft_body.strip():
            raise HTTPException(status_code=400, detail="Draft body cannot be empty")
        
        if len(request.draft_body) > 10000:  # Reasonable limit
            raise HTTPException(status_code=400, detail="Draft body too long (max 10,000 characters)")
        
        # Retrieve reference
        result = await retrieval_service.retrieve_reference(request.draft_body, db)
        
        # Convert to response format
        ref = None
        if result["ref"]:
            ref_data = result["ref"]
            ref = ReferenceScript(
                video_id=ref_data["video_id"],
                body=ref_data["body"],
                duration_seconds=ref_data["duration_seconds"],
                performance=PerformanceMetrics(**ref_data["performance"]),
                similarity_score=ref_data["similarity_score"],
                performance_score=ref_data["performance_score"],
                combined_score=ref_data["combined_score"]
            )
        
        alternates = []
        for alt_data in result["alternates"]:
            alt = ReferenceScript(
                video_id=alt_data["video_id"],
                body=alt_data["body"],
                duration_seconds=alt_data["duration_seconds"],
                performance=PerformanceMetrics(**alt_data["performance"]),
                similarity_score=alt_data["similarity_score"],
                performance_score=alt_data["performance_score"],
                combined_score=alt_data["combined_score"]
            )
            alternates.append(alt)
        
        logger.info("Retrieved reference", 
                   draft_length=len(request.draft_body),
                   ref_found=ref is not None,
                   alternates_count=len(alternates))
        
        return RetrieveResponse(
            ref=ref,
            alternates=alternates,
            total_candidates=result["total_candidates"],
            search_time_ms=result["search_time_ms"],
            reason=result["reason"]
        )
        
    except Exception as e:
        logger.error("Failed to retrieve reference", error=str(e))
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
