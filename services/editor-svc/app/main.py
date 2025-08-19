from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import structlog
import uvicorn
import time
import re
from collections import defaultdict

from app.config import settings
from app.editor_service import EditorService

# Standardized error response
class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str

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

# CORS middleware - environment-specific origins
import os
allowed_origins = []
app_env = os.getenv('APP_ENV', 'dev')

if app_env == 'prod':
    allowed_origins = [
        "https://gateway-api-318093749175.us-central1.run.app"
    ]
elif app_env == 'test':
    allowed_origins = [
        "https://gateway-api-test-318093749175.us-central1.run.app"
    ]
else:  # dev
    allowed_origins = ["*"]  # Allow all in development

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Global service instance
editor_service = EditorService()

# Simple rate limiting (in production, use Redis or proper rate limiter)
request_counts = defaultdict(list)
RATE_LIMIT_REQUESTS = 10  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

def check_rate_limit(client_ip: str) -> bool:
    """Simple rate limiting check"""
    now = time.time()
    # Clean old requests
    request_counts[client_ip] = [req_time for req_time in request_counts[client_ip]
                                if now - req_time < RATE_LIMIT_WINDOW]

    # Check if under limit
    if len(request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False

    # Add current request
    request_counts[client_ip].append(now)
    return True

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return ""

    # Remove potentially dangerous patterns
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript URLs
        r'on\w+\s*=',  # Event handlers
        r'<iframe[^>]*>.*?</iframe>',  # Iframes
        r'<object[^>]*>.*?</object>',  # Objects
        r'<embed[^>]*>.*?</embed>',  # Embeds
    ]

    sanitized = text
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)

    # Limit length
    if len(sanitized) > settings.max_input_length:
        sanitized = sanitized[:settings.max_input_length]

    return sanitized.strip()

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
    """Health check endpoint with dependency verification"""
    from datetime import datetime, timezone

    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "editor-svc",
        "version": "1.0.0",
        "model": settings.model_name,
        "coherence_threshold": settings.coherence_threshold,
        "checks": {}
    }

    # Check Anthropic API key
    if settings.anthropic_api_key:
        health_status["checks"]["anthropic_api_key"] = "configured"
    else:
        health_status["checks"]["anthropic_api_key"] = "missing"
        health_status["status"] = "unhealthy"

    # Check Redis connection (if used)
    try:
        # Basic Redis check would go here
        health_status["checks"]["redis"] = "not_implemented"
    except Exception:
        health_status["checks"]["redis"] = "unavailable"

    return health_status

@app.post("/debug")
async def debug_claude_response(request: ImproveRequest):
    """Debug endpoint to see raw Claude response - DEV ONLY"""
    # Only allow in development environment
    app_env = os.getenv('APP_ENV', 'dev')
    if app_env != 'dev':
        raise HTTPException(status_code=404, detail="Endpoint not found")

    try:
        if not request.draft_body.strip():
            raise HTTPException(status_code=400, detail="Draft body cannot be empty")

        # Get raw response from Claude
        from app.prompt_renderer import PromptRenderer
        prompt_renderer = PromptRenderer()

        prompt = prompt_renderer.render_script_improver(
            draft_body=request.draft_body,
            reference_script=None,
            target_word_count=900,
            style_notes=None
        )

        response = editor_service.client.messages.create(
            model=editor_service.model,
            max_tokens=editor_service.max_tokens,
            temperature=editor_service.temperature,
            system="You are a world-class video script writer with deep expertise in creating viral, engaging content. You understand what makes viewers click, watch, and share. You analyze successful patterns and apply them creatively without copying content.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = response.content[0].text

        return {
            "raw_response": content,
            "length": len(content),
            "first_100_chars": content[:100],
            "last_100_chars": content[-100:] if len(content) > 100 else content
        }

    except Exception as e:
        logger.error("Debug failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@app.post("/improve", response_model=ImproveResponse)
async def improve_script(request: ImproveRequest, http_request: Request):
    """
    Improve a draft script using Anthropic Claude

    Args:
        request: Draft script and optional reference/settings

    Returns:
        Improved script with coherence validation
    """
    # Rate limiting check
    client_ip = http_request.client.host if http_request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )

    try:
        # Sanitize input
        sanitized_draft = sanitize_input(request.draft_body)
        if not sanitized_draft:
            raise HTTPException(status_code=400, detail="Draft body cannot be empty")

        # Sanitize optional fields
        sanitized_style_notes = sanitize_input(request.style_notes) if request.style_notes else None
        
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
        
        # Improve script with sanitized inputs
        result = await editor_service.improve_script(
            draft_body=sanitized_draft,
            reference_script=reference_dict,
            target_word_count=request.target_word_count,
            style_notes=sanitized_style_notes
        )
        
        # Coherence validation - only enforce in production
        app_env = os.getenv('APP_ENV', 'dev')
        if app_env == 'prod' and not result["result"]["coherence"]["passed"]:
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
