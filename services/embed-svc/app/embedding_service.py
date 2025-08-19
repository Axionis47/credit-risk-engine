import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import numpy as np
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, and_, or_, tuple_
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
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # Verify dimensions
            if len(embedding) != self.dimensions:
                raise ValueError(f"Expected {self.dimensions} dimensions, got {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e), text_length=len(text))
            raise
    
    async def create_embeddings_for_eligible_scripts(self, db: AsyncSession, batch_size: int = 10) -> int:
        """
        Create embeddings for scripts that are eligible (age >= 14 days) but don't have embeddings yet

        Args:
            db: Database session
            batch_size: Number of scripts to process in each batch

        Returns:
            Number of embeddings created
        """
        try:
            # Calculate cutoff date (14 days ago from dataset last date)
            cutoff_date = await self._get_embed_cutoff_date(db)
            logger.info("Embedding cutoff date calculated", cutoff_date=cutoff_date.isoformat())

            # Find eligible scripts without embeddings (limit to batch_size)
            eligible_scripts = await self._find_eligible_scripts_without_embeddings(db, cutoff_date, limit=batch_size)
            logger.info("Found eligible scripts", count=len(eligible_scripts))

            if not eligible_scripts:
                logger.info("No eligible scripts found for embedding")
                return 0

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
            logger.info("Batch embedding completed", embeddings_created=embeddings_created)
            return embeddings_created

        except Exception as e:
            logger.error("Failed to create embeddings batch", error=str(e))
            await db.rollback()
            raise
    
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
    
    async def _find_eligible_scripts_without_embeddings(self, db: AsyncSession, cutoff_date: datetime, limit: int = None) -> List[Script]:
        """Find scripts eligible for embedding that don't have embeddings yet"""

        try:
            # Step 1: Find video_ids that have performance metrics meeting age requirement
            # This is much faster than joining all tables at once
            perf_query = select(PerformanceMetrics.video_id).where(
                or_(
                    PerformanceMetrics.published_at <= cutoff_date,
                    and_(
                        PerformanceMetrics.published_at.is_(None),
                        PerformanceMetrics.asof_date <= cutoff_date
                    )
                )
            ).distinct()

            perf_result = await db.execute(perf_query)
            eligible_video_ids = [row[0] for row in perf_result.fetchall()]

            if not eligible_video_ids:
                logger.info("No videos meet age requirements")
                return []

            logger.info("Found videos meeting age requirements", count=len(eligible_video_ids))

            # Step 2: Find video_ids that already have embeddings in our namespace
            embed_query = select(Embedding.video_id, Embedding.version).where(
                and_(
                    Embedding.video_id.in_(eligible_video_ids),
                    Embedding.namespace == self.namespace
                )
            )

            embed_result = await db.execute(embed_query)
            existing_embeddings = set((row[0], row[1]) for row in embed_result.fetchall())

            logger.info("Found existing embeddings", count=len(existing_embeddings))

            # Step 3: Find scripts that meet all criteria
            script_query = select(Script).where(
                and_(
                    Script.video_id.in_(eligible_video_ids),
                    Script.duration_seconds <= 180,
                    # Exclude scripts that already have embeddings
                    ~tuple_(Script.video_id, Script.version).in_(existing_embeddings) if existing_embeddings else True
                )
            )

            # Add limit if specified
            if limit:
                script_query = script_query.limit(limit)

            result = await db.execute(script_query)
            scripts = result.scalars().all()

            logger.info("Found eligible scripts without embeddings", count=len(scripts))
            return scripts

        except Exception as e:
            logger.error("Error finding eligible scripts", error=str(e))
            # Fallback to simpler query if complex query fails
            return await self._find_eligible_scripts_simple(db, limit)

    async def _find_eligible_scripts_simple(self, db: AsyncSession, limit: int = None) -> List[Script]:
        """Simplified fallback query for finding scripts without embeddings"""
        try:
            # Just find scripts that don't have embeddings, ignore age requirements
            embed_query = select(Embedding.video_id, Embedding.version).where(
                Embedding.namespace == self.namespace
            )

            embed_result = await db.execute(embed_query)
            existing_embeddings = set((row[0], row[1]) for row in embed_result.fetchall())

            # Find scripts without embeddings
            script_query = select(Script).where(
                and_(
                    Script.duration_seconds <= 180,
                    ~tuple_(Script.video_id, Script.version).in_(existing_embeddings) if existing_embeddings else True
                )
            )

            if limit:
                script_query = script_query.limit(limit)

            result = await db.execute(script_query)
            scripts = result.scalars().all()

            logger.info("Fallback query found scripts", count=len(scripts))
            return scripts

        except Exception as e:
            logger.error("Even fallback query failed", error=str(e))
            return []
    
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
