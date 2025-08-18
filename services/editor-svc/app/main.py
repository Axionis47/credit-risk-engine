from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import structlog
import uvicorn

from app.config import settings
from app.editor_service import EditorService

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
    title="Editor Service",
    description="Script improvement service using Anthropic Claude (Sonnet only)",
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
editor_service = EditorService()

# Request/Response models
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

class ImproveRequest(BaseModel):
    draft_body: str
    reference: Optional[ReferenceScript] = None
    target_word_count: Optional[int] = None
    style_notes: Optional[str] = None

class CoherenceScore(BaseModel):
    score: float
    passed: bool
    notes: str

class ImprovedScript(BaseModel):
    title: str
    hook: str
    body: str
    word_count: int
    coherence: CoherenceScore
    diff_summary: Optional[str] = None
    style_principles: List[str] = []

class ImproveResponse(BaseModel):
    result: ImprovedScript
    warnings: List[str]
    processing_time_ms: float
    tuner_passes: int

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Editor service started", 
                port=settings.port,
                model=settings.model_name,
                coherence_threshold=settings.coherence_threshold)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-12-01T00:00:00Z",
        "service": "editor-svc",
        "version": "1.0.0",
        "model": settings.model_name,
        "coherence_threshold": settings.coherence_threshold
    }

@app.post("/improve", response_model=ImproveResponse)
async def improve_script(request: ImproveRequest):
    """
    Improve a draft script using Anthropic Claude
    
    Args:
        request: Draft script and optional reference/settings
        
    Returns:
        Improved script with coherence validation
    """
    try:
        if not request.draft_body.strip():
            raise HTTPException(status_code=400, detail="Draft body cannot be empty")
        
        if len(request.draft_body) > settings.max_input_length:
            raise HTTPException(
                status_code=400, 
                detail=f"Draft body too long (max {settings.max_input_length} characters)"
            )
        
        # Convert reference script to dict if provided
        reference_dict = None
        if request.reference:
            reference_dict = {
                "video_id": request.reference.video_id,
                "body": request.reference.body,
                "duration_seconds": request.reference.duration_seconds,
                "performance": {
                    "views": request.reference.performance.views,
                    "ctr": request.reference.performance.ctr,
                    "avg_view_duration_s": request.reference.performance.avg_view_duration_s,
                    "retention_30s": request.reference.performance.retention_30s
                },
                "similarity_score": request.reference.similarity_score,
                "performance_score": request.reference.performance_score,
                "combined_score": request.reference.combined_score
            }
        
        # Improve script
        result = await editor_service.improve_script(
            draft_body=request.draft_body,
            reference_script=reference_dict,
            target_word_count=request.target_word_count,
            style_notes=request.style_notes
        )
        
        # Check coherence threshold
        if not result["result"]["coherence"]["passed"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Coherence threshold not met",
                    "coherence_score": result["result"]["coherence"]["score"],
                    "threshold": settings.coherence_threshold,
                    "notes": result["result"]["coherence"]["notes"],
                    "suggestion": "Consider adjusting the draft or reference script for better alignment"
                }
            )
        
        logger.info("Script improved successfully", 
                   draft_length=len(request.draft_body),
                   final_word_count=result["result"]["word_count"],
                   coherence_score=result["result"]["coherence"]["score"])
        
        return ImproveResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to improve script", error=str(e))
        raise HTTPException(status_code=500, detail=f"Script improvement failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
