from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text, tuple_
from pydantic import BaseModel
from typing import List
import asyncio
import structlog
import uvicorn

from app.config import settings
from app.database import get_db, init_db
from app.embedding_service import EmbeddingService

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
    title="Embedding Service",
    description="OpenAI embedding generation service (text-embedding-3-large only)",
    version="1.0.0"
)

# CORS middleware - environment-specific origins
import os
allowed_origins = []
app_env = os.getenv('APP_ENV', 'dev')

if app_env == 'prod':
    allowed_origins = [
        "https://gateway-api-318093749175.us-central1.run.app",
        "https://editor-frontend-318093749175.us-central1.run.app",
        "https://ideahunter-frontend-318093749175.us-central1.run.app"
    ]
elif app_env == 'test':
    allowed_origins = [
        "https://gateway-api-test-318093749175.us-central1.run.app",
        "https://editor-frontend-test-318093749175.us-central1.run.app",
        "https://ideahunter-frontend-test-318093749175.us-central1.run.app"
    ]
else:  # dev
    allowed_origins = ["*"]  # Allow all in development

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Global service instance
embedding_service = EmbeddingService()

# Request/Response models
class EmbedRequest(BaseModel):
    text: str
    ephemeral: bool = False  # If True, don't persist

class EmbedResponse(BaseModel):
    embedding: List[float]
    dimensions: int
    model: str
    namespace: str

class BatchEmbedRequest(BaseModel):
    texts: List[str]
    ephemeral: bool = False

class BatchEmbedResponse(BaseModel):
    embeddings: List[List[float]]
    count: int
    dimensions: int
    model: str
    namespace: str

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning("Database initialization failed, will retry on first request", error=str(e))

    logger.info("Embedding service started",
                port=settings.port,
                model=settings.embed_model,
                dimensions=settings.embed_dimensions)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "embed-svc",
        "version": "1.0.0",
        "model": settings.embed_model,
        "dimensions": settings.embed_dimensions
    }

@app.post("/embed", response_model=EmbedResponse)
async def create_embedding(
    request: EmbedRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate embedding for text
    
    Args:
        request: Text to embed and options
        
    Returns:
        3072-dimensional embedding vector
    """
    try:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        if len(request.text) > 50000:  # Reasonable limit
            raise HTTPException(status_code=400, detail="Text too long (max 50,000 characters)")
        
        # Generate embedding
        embedding = await embedding_service.generate_embedding(request.text)
        
        logger.info("Generated embedding", 
                   text_length=len(request.text),
                   ephemeral=request.ephemeral)
        
        return EmbedResponse(
            embedding=embedding,
            dimensions=len(embedding),
            model=settings.embed_model,
            namespace=settings.embed_namespace
        )
        
    except Exception as e:
        logger.error("Failed to generate embedding", error=str(e))
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

@app.post("/embed/batch", response_model=BatchEmbedResponse)
async def create_batch_embeddings(
    request: BatchEmbedRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate embeddings for multiple texts
    
    Args:
        request: List of texts to embed
        
    Returns:
        List of 3072-dimensional embedding vectors
    """
    try:
        if not request.texts:
            raise HTTPException(status_code=400, detail="Texts list cannot be empty")
        
        if len(request.texts) > 100:  # Reasonable batch limit
            raise HTTPException(status_code=400, detail="Too many texts (max 100 per batch)")
        
        embeddings = []
        for text in request.texts:
            if not text.strip():
                raise HTTPException(status_code=400, detail="Text cannot be empty")
            
            embedding = await embedding_service.generate_embedding(text)
            embeddings.append(embedding)
        
        logger.info("Generated batch embeddings", 
                   count=len(embeddings),
                   ephemeral=request.ephemeral)
        
        return BatchEmbedResponse(
            embeddings=embeddings,
            count=len(embeddings),
            dimensions=settings.embed_dimensions,
            model=settings.embed_model,
            namespace=settings.embed_namespace
        )
        
    except Exception as e:
        logger.error("Failed to generate batch embeddings", error=str(e))
        raise HTTPException(status_code=500, detail=f"Batch embedding generation failed: {str(e)}")

@app.post("/embed/sync")
async def sync_embeddings(db: AsyncSession = Depends(get_db)):
    """
    Create embeddings for all eligible scripts that don't have embeddings yet
    (Admin endpoint - protected in production)

    Returns:
        Number of embeddings created
    """
    # Only allow in development environment
    app_env = os.getenv('APP_ENV', 'dev')
    if app_env == 'prod':
        raise HTTPException(status_code=404, detail="Endpoint not found")

    try:
        embeddings_created = await embedding_service.create_embeddings_for_eligible_scripts(db)
        
        logger.info("Sync embeddings completed", embeddings_created=embeddings_created)
        
        return {
            "success": True,
            "data": {
                "embeddings_created": embeddings_created,
                "namespace": settings.embed_namespace,
                "model": settings.embed_model
            }
        }
        
    except Exception as e:
        logger.error("Failed to sync embeddings", error=str(e))
        raise HTTPException(status_code=500, detail=f"Embedding sync failed: {str(e)}")

@app.post("/embed/sync-simple")
async def sync_embeddings_simple(limit: int = 5, db: AsyncSession = Depends(get_db)):
    """
    Simple sync that bypasses age requirements and processes a few scripts at a time
    (Debug endpoint - DEV ONLY)
    """
    # Only allow in development environment
    app_env = os.getenv('APP_ENV', 'dev')
    if app_env != 'dev':
        raise HTTPException(status_code=404, detail="Endpoint not found")

    try:
        # Find scripts without embeddings (ignore age requirements)
        from app.models import Script, Embedding

        # Get scripts that don't have embeddings yet
        embed_query = select(Embedding.video_id, Embedding.version).where(
            Embedding.namespace == settings.embed_namespace
        )
        embed_result = await db.execute(embed_query)
        existing_embeddings = set((row[0], row[1]) for row in embed_result.fetchall())

        # Find scripts without embeddings
        script_query = select(Script).limit(limit)
        if existing_embeddings:
            script_query = script_query.where(
                ~tuple_(Script.video_id, Script.version).in_(existing_embeddings)
            )

        result = await db.execute(script_query)
        scripts = result.scalars().all()

        logger.info("Found scripts for simple sync", count=len(scripts))

        embeddings_created = 0
        for script in scripts:
            try:
                # Generate embedding
                embedding_vector = await embedding_service.generate_embedding(script.body)

                # Store embedding
                await embedding_service._store_embedding(db, script.video_id, script.version, embedding_vector)

                embeddings_created += 1
                logger.info("Created embedding (simple sync)",
                           video_id=script.video_id,
                           version=script.version)

                # Rate limiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error("Failed to create embedding (simple sync)",
                           video_id=script.video_id,
                           error=str(e))
                continue

        await db.commit()

        return {
            "success": True,
            "data": {
                "embeddings_created": embeddings_created,
                "scripts_processed": len(scripts),
                "namespace": settings.embed_namespace
            }
        }

    except Exception as e:
        logger.error("Failed to sync embeddings (simple)", error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Simple embedding sync failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
