from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
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
    await init_db()
    logger.info("Embedding service started", 
                port=settings.port,
                model=settings.embed_model,
                dimensions=settings.embed_dimensions)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-12-01T00:00:00Z",
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
    (Admin endpoint - should be protected in production)
    
    Returns:
        Number of embeddings created
    """
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

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
