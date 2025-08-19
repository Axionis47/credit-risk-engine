import uuid
import os
import sys
import subprocess
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form, Query, Request, Response, Header
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, and_, or_
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import structlog
import uvicorn
import httpx
# Rate limiting temporarily disabled for deployment
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.util import get_remote_address
# from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import get_db, init_db
from app.models import User, Idea, UserFeedback
from app.auth import auth_service, get_current_user, get_current_user_optional
from app.service_client import service_client

def verify_csrf_token(request: Request):
    """Simple CSRF protection - check for X-Requested-With header"""
    x_requested_with = request.headers.get("X-Requested-With")
    if not x_requested_with or x_requested_with != "XMLHttpRequest":
        raise HTTPException(
            status_code=403,
            detail="CSRF protection: X-Requested-With header required"
        )

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

# Rate limiter temporarily disabled
# limiter = Limiter(key_func=get_remote_address)

def run_preflight_checks():
    """Run preflight checks before starting the service"""
    logger.info("Running preflight checks...")

    # Check APP_ENV
    app_env = os.getenv('APP_ENV')
    if not app_env:
        logger.error("APP_ENV environment variable is required")
        sys.exit(1)

    if app_env not in ['dev', 'test', 'prod']:
        logger.error(f"APP_ENV must be dev, test, or prod, got: {app_env}")
        sys.exit(1)

    logger.info(f"Environment: {app_env}")

    # Run full preflight check script if available
    try:
        result = subprocess.run([
            sys.executable,
            '/app/scripts/preflight_check.py'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.error(f"Preflight checks failed: {result.stderr}")
            sys.exit(2)

        logger.info("Preflight checks passed")

    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("Preflight check script not found or timed out, using basic checks")
        # Basic environment validation
        if app_env == 'prod':
            # In production, be extra strict
            if 'mock' in str(settings.database_url).lower():
                logger.error("Production cannot use mock database")
                sys.exit(2)
    except Exception as e:
        logger.error(f"Failed to run preflight checks: {e}")
        sys.exit(2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Run preflight checks first
    run_preflight_checks()

    # Startup
    await init_db()
    logger.info("Gateway API started",
                port=settings.port,
                allowed_origins=settings.allowed_origins)

    # Log environment info
    app_env = os.getenv('APP_ENV', 'unknown')
    logger.info(f"Service running in environment: {app_env}")
    logger.info(f"Database: {settings.database_url}")

    yield
    # Shutdown
    logger.info("Gateway API shutting down")

app = FastAPI(
    title="Gateway API",
    description="Main API gateway for PP Final application",
    version="1.0.0",
    lifespan=lifespan
)

# Rate limiting temporarily disabled
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with restricted permissions
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'"
    return response

# Request/Response models
class GoogleAuthRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=2048, description="Google OAuth token")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: Dict[str, Any]

class RetrieveRequest(BaseModel):
    draft_body: str

class ImproveRequest(BaseModel):
    draft_body: str
    reference: Optional[Dict[str, Any]] = None
    target_word_count: Optional[int] = None
    style_notes: Optional[str] = None

class IdeaFeedbackRequest(BaseModel):
    idea_id: str = Field(..., min_length=1, max_length=100, description="Idea ID")
    feedback_type: str = Field(..., pattern="^(reject|save|superlike)$", description="Feedback type")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional notes")

class RedditSyncRequest(BaseModel):
    subreddits: Optional[List[str]] = None
    max_posts_per_subreddit: Optional[int] = None
    min_score: Optional[int] = None
    max_age_hours: Optional[int] = None



# Public endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Gateway API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "gateway-api",
        "version": "1.0.0"
    }

@app.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check endpoint with database"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "gateway-api",
        "version": "1.0.0",
        "checks": {}
    }

    # Database connectivity check
    try:
        await db.execute(select(1))
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Service dependencies check (basic)
    health_status["checks"]["services"] = {
        "ingest_service": settings.ingest_service_url,
        "embed_service": settings.embed_service_url,
        "retrieval_service": settings.retrieval_service_url,
        "editor_service": settings.editor_service_url,
        "reddit_sync_service": settings.reddit_sync_service_url
    }

    return health_status

@app.get("/whoami")
async def whoami(current_user: Optional[User] = Depends(get_current_user_optional)):
    """Get current user info"""
    if current_user:
        return {
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "name": current_user.name,
                "picture": current_user.picture,
                "verified_email": current_user.verified_email
            },
            "authenticated": True
        }
    else:
        return {"authenticated": False}

# Authentication endpoints
@app.post("/api/oauth/google", response_model=TokenResponse)
async def google_oauth(google_request: GoogleAuthRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate with Google OAuth token"""
    try:
        # Verify Google token
        google_user_info = await auth_service.verify_google_token(google_request.token)
        
        # Get or create user
        user = await auth_service.get_or_create_user(google_user_info, db)
        
        # Create access token
        access_token = auth_service.create_access_token(user)

        # Set httpOnly cookie for secure token storage
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,  # HTTPS only
            samesite="strict",
            max_age=settings.jwt_expiration_hours * 3600
        )

        # Log authentication without PII in production
        app_env = os.getenv('APP_ENV', 'dev')
        if app_env == 'dev':
            logger.info("User authenticated", email=user.email, user_id=str(user.id))
        else:
            logger.info("User authenticated", user_id_hash=hash(str(user.id)))

        # Only return token in response body for development
        app_env = os.getenv('APP_ENV', 'dev')
        response_token = access_token if app_env == 'dev' else "***"  # Hide in production

        return TokenResponse(
            access_token=response_token,  # Hidden in production for security
            token_type="Bearer",
            expires_in=settings.jwt_expiration_hours * 3600,
            user={
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "verified_email": user.verified_email
            }
        )
        
    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    """Logout user by clearing authentication cookie"""
    verify_csrf_token(request)
    try:
        # Clear the httpOnly cookie
        response.delete_cookie(
            key="access_token",
            httponly=True,
            secure=True,
            samesite="strict"
        )

        logger.info("User logged out successfully")

        return {"success": True, "message": "Logged out successfully"}

    except Exception as e:
        logger.error("Logout failed", error=str(e))
        raise HTTPException(status_code=500, detail="Logout failed")

# Debug endpoint (public, for testing only)
@app.post("/api/debug/ingest/from-gcs")
async def debug_ingest_from_gcs():
    """Debug endpoint to test GCS ingest without authentication"""
    try:
        # Call ingest service directly
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ingest_service_url}/api/ingest/from-gcs",
                timeout=300.0
            )

        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ingest service error: {response.text}"
            )

    except Exception as e:
        logger.error("Debug GCS ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Debug GCS ingest failed: {str(e)}")

# Admin endpoints (protected)
@app.post("/api/ingest/auto")
async def auto_ingest(
    metrics_file: UploadFile = File(...),
    transcripts_file: UploadFile = File(...),
    force_role_override: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Auto-analyze and ingest CSV files"""
    try:
        # Read file contents
        metrics_content = await metrics_file.read()
        transcripts_content = await transcripts_file.read()
        
        # Call ingest service
        result = await service_client.ingest_auto(
            metrics_content, transcripts_content, force_role_override
        )
        
        # Trigger embedding sync after successful ingest
        if result.get("success") and result.get("data", {}).get("report", {}).get("successful", 0) > 0:
            try:
                await service_client.sync_embeddings()
            except Exception as e:
                logger.warning("Embedding sync failed after ingest", error=str(e))
        
        return result
        
    except Exception as e:
        logger.error("Auto ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")

@app.post("/api/ingest/from-gcs")
async def ingest_from_gcs(
    force_role_override: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Load and ingest CSV files from Google Cloud Storage"""
    try:
        # Call ingest service
        result = await service_client.ingest_from_gcs(force_role_override)

        # Trigger embedding sync after successful ingest
        if result.get("success") and result.get("data", {}).get("report", {}).get("successful", 0) > 0:
            try:
                await service_client.sync_embeddings()
            except Exception as e:
                logger.warning("Embedding sync failed after GCS ingest", error=str(e))

        return result

    except Exception as e:
        logger.error("GCS ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"GCS ingest failed: {str(e)}")

@app.post("/api/ideas/sync")
async def sync_ideas(
    request: RedditSyncRequest = RedditSyncRequest(),
    current_user: User = Depends(get_current_user)
):
    """Sync ideas from Reddit (admin endpoint)"""
    try:
        result = await service_client.sync_reddit_ideas(
            subreddits=request.subreddits,
            max_posts_per_subreddit=request.max_posts_per_subreddit,
            min_score=request.min_score,
            max_age_hours=request.max_age_hours
        )
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error("Reddit sync failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Reddit sync failed: {str(e)}")

# Script Improver endpoints (authenticated)
@app.post("/api/retrieve")
async def retrieve_reference(
    retrieve_request: RetrieveRequest,
    current_user: User = Depends(get_current_user)
):
    """Retrieve reference script for draft"""
    try:
        result = await service_client.retrieve_reference(retrieve_request.draft_body)
        
        # Add trace ID
        result["trace_id"] = str(uuid.uuid4())
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error("Retrieve failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail=f"Retrieve failed: {str(e)}")

@app.post("/api/improve")
async def improve_script(
    request: ImproveRequest,
    current_user: User = Depends(get_current_user)
):
    """Improve script using AI"""
    try:
        result = await service_client.improve_script(
            draft_body=request.draft_body,
            reference=request.reference,
            target_word_count=request.target_word_count,
            style_notes=request.style_notes
        )
        
        # Add trace ID
        result["trace_id"] = str(uuid.uuid4())
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error("Improve failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail=f"Improve failed: {str(e)}")

# Idea Hunter endpoints (authenticated)
@app.get("/api/ideas/deck")
async def get_ideas_deck(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get ideas deck (Tinder-style cards)"""
    try:
        # Get ideas that user hasn't given feedback on yet
        subquery = select(UserFeedback.idea_id).where(UserFeedback.user_id == current_user.id)
        
        query = select(Idea).where(
            ~Idea.id.in_(subquery)
        ).order_by(Idea.score.desc(), Idea.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        ideas = result.scalars().all()
        
        # Check if there are more ideas available
        total_query = select(Idea).where(~Idea.id.in_(subquery))
        total_result = await db.execute(total_query)
        total_available = len(total_result.scalars().all())
        
        ideas_data = []
        for idea in ideas:
            ideas_data.append({
                "idea_id": idea.idea_id,
                "title": idea.title,
                "snippet": idea.snippet,
                "source_url": idea.source_url,
                "subreddit": idea.subreddit,
                "score": idea.score,
                "num_comments": idea.num_comments,
                "created_at": idea.created_at.isoformat(),
                "fetched_at": idea.fetched_at.isoformat()
            })
        
        return {
            "success": True,
            "data": {
                "ideas": ideas_data,
                "has_more": total_available > len(ideas),
                "total_available": total_available
            }
        }
        
    except Exception as e:
        logger.error("Get deck failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail=f"Failed to get ideas deck: {str(e)}")

@app.post("/api/ideas/feedback")
async def submit_idea_feedback(
    request: IdeaFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit feedback on an idea"""
    try:
        # Validate feedback type
        if request.feedback_type not in ['reject', 'save', 'superlike']:
            raise HTTPException(status_code=400, detail="Invalid feedback type")
        
        # Find the idea
        idea_query = select(Idea).where(Idea.idea_id == request.idea_id)
        idea_result = await db.execute(idea_query)
        idea = idea_result.scalar_one_or_none()
        
        if not idea:
            raise HTTPException(status_code=404, detail="Idea not found")
        
        # Check if feedback already exists
        existing_query = select(UserFeedback).where(
            and_(UserFeedback.user_id == current_user.id, UserFeedback.idea_id == idea.id)
        )
        existing_result = await db.execute(existing_query)
        existing_feedback = existing_result.scalar_one_or_none()
        
        if existing_feedback:
            # Update existing feedback
            existing_feedback.feedback_type = request.feedback_type
            existing_feedback.notes = request.notes
            existing_feedback.created_at = datetime.now(timezone.utc)
        else:
            # Create new feedback
            feedback_data = {
                'user_id': current_user.id,
                'idea_id': idea.id,
                'feedback_type': request.feedback_type,
                'notes': request.notes,
                'created_at': datetime.now(timezone.utc)
            }
            await db.execute(insert(UserFeedback).values(**feedback_data))
        
        await db.commit()
        
        return {"success": True, "message": "Feedback submitted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Submit feedback failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")

@app.get("/api/ideas/accepted")
async def get_accepted_ideas(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's saved and superliked ideas"""
    try:
        # Get saved and superliked ideas
        query = select(Idea, UserFeedback).join(
            UserFeedback, Idea.id == UserFeedback.idea_id
        ).where(
            and_(
                UserFeedback.user_id == current_user.id,
                UserFeedback.feedback_type.in_(['save', 'superlike'])
            )
        ).order_by(UserFeedback.created_at.desc())
        
        result = await db.execute(query)
        rows = result.all()
        
        saved = []
        superliked = []
        
        for idea, feedback in rows:
            idea_data = {
                "idea_id": idea.idea_id,
                "title": idea.title,
                "snippet": idea.snippet,
                "source_url": idea.source_url,
                "subreddit": idea.subreddit,
                "score": idea.score,
                "num_comments": idea.num_comments,
                "created_at": idea.created_at.isoformat(),
                "fetched_at": idea.fetched_at.isoformat(),
                "notes": feedback.notes
            }
            
            if feedback.feedback_type == 'save':
                idea_data["saved_at"] = feedback.created_at.isoformat()
                saved.append(idea_data)
            elif feedback.feedback_type == 'superlike':
                idea_data["superliked_at"] = feedback.created_at.isoformat()
                superliked.append(idea_data)
        
        return {
            "success": True,
            "data": {
                "saved": saved,
                "superliked": superliked,
                "total_count": len(saved) + len(superliked)
            }
        }
        
    except Exception as e:
        logger.error("Get accepted ideas failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail=f"Failed to get accepted ideas: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
