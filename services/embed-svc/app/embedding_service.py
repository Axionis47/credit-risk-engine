import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import numpy as np
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, and_
import structlog

from app.config import settings
from app.models import Script, PerformanceMetrics, Embedding

logger = structlog.get_logger()

class EmbeddingService:
    """Service for generating and managing embeddings using OpenAI"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embed_model
        self.dimensions = settings.embed_dimensions
        self.namespace = settings.embed_namespace
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI text-embedding-3-large
        
        Args:
            text: Text to embed
            
        Returns:
            3072-dimensional embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions
            )
            
            embedding = response.data[0].embedding
            
            # Verify dimensions
            if len(embedding) != self.dimensions:
                raise ValueError(f"Expected {self.dimensions} dimensions, got {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e), text_length=len(text))
            raise
    
    async def create_embeddings_for_eligible_scripts(self, db: AsyncSession) -> int:
        """
        Create embeddings for scripts that are eligible (age >= 14 days) but don't have embeddings yet
        
        Returns:
            Number of embeddings created
        """
        # Calculate cutoff date (14 days ago from dataset last date)
        cutoff_date = await self._get_embed_cutoff_date(db)
        
        # Find eligible scripts without embeddings
        eligible_scripts = await self._find_eligible_scripts_without_embeddings(db, cutoff_date)
        
        embeddings_created = 0
        
        for script in eligible_scripts:
            try:
                # Generate embedding for the entire script body
                embedding_vector = await self.generate_embedding(script.body)
                
                # Store embedding
                await self._store_embedding(db, script.video_id, script.version, embedding_vector)
                
                embeddings_created += 1
                logger.info("Created embedding", 
                           video_id=script.video_id, 
                           version=script.version,
                           body_length=len(script.body))
                
                # Rate limiting - avoid hitting OpenAI limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error("Failed to create embedding", 
                           video_id=script.video_id, 
                           error=str(e))
                continue
        
        await db.commit()
        return embeddings_created
    
    async def generate_ephemeral_embedding(self, text: str) -> List[float]:
        """
        Generate ephemeral embedding for draft text (not persisted)
        Used by retrieval service for finding similar scripts
        
        Args:
            text: Draft text to embed
            
        Returns:
            3072-dimensional embedding vector
        """
        return await self.generate_embedding(text)
    
    async def _get_embed_cutoff_date(self, db: AsyncSession) -> datetime:
        """Calculate the embedding cutoff date (dataset_last_date - 14 days)"""
        
        # Find the latest date from performance metrics
        result = await db.execute(
            select(PerformanceMetrics.published_at, PerformanceMetrics.asof_date)
            .where(
                (PerformanceMetrics.published_at.isnot(None)) | 
                (PerformanceMetrics.asof_date.isnot(None))
            )
        )
        
        dates = []
        for row in result:
            if row.published_at:
                dates.append(row.published_at)
            if row.asof_date:
                dates.append(row.asof_date)
        
        if not dates:
            # Fallback to current date if no dates found
            dataset_last_date = datetime.utcnow()
        else:
            dataset_last_date = max(dates)
        
        # 14-day cutoff
        return dataset_last_date - timedelta(days=14)
    
    async def _find_eligible_scripts_without_embeddings(self, db: AsyncSession, cutoff_date: datetime) -> List[Script]:
        """Find scripts eligible for embedding that don't have embeddings yet"""
        
        # Query for scripts that:
        # 1. Have performance metrics with published_at <= cutoff_date OR asof_date <= cutoff_date
        # 2. Don't already have embeddings in our namespace
        # 3. Have duration <= 180 seconds (reference eligibility)
        
        query = select(Script).join(
            PerformanceMetrics, Script.video_id == PerformanceMetrics.video_id
        ).outerjoin(
            Embedding, 
            and_(
                Script.video_id == Embedding.video_id,
                Script.version == Embedding.version,
                Embedding.namespace == self.namespace
            )
        ).where(
            and_(
                # Age requirement
                (
                    (PerformanceMetrics.published_at <= cutoff_date) |
                    (
                        PerformanceMetrics.published_at.is_(None) &
                        (PerformanceMetrics.asof_date <= cutoff_date)
                    )
                ),
                # Duration requirement
                Script.duration_seconds <= 180,
                # No existing embedding
                Embedding.id.is_(None)
            )
        ).distinct()
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def _store_embedding(self, db: AsyncSession, video_id: str, version: int, vector: List[float]):
        """Store embedding in database"""
        
        embedding_data = {
            'video_id': video_id,
            'version': version,
            'namespace': self.namespace,
            'vector': vector,
            'created_at': datetime.utcnow()
        }
        
        await db.execute(insert(Embedding).values(**embedding_data))
