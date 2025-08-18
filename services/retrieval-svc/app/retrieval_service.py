import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
import httpx
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_
import structlog

from app.config import settings
from app.models import Script, PerformanceMetrics, Embedding

logger = structlog.get_logger()

class RetrievalService:
    """Service for retrieving similar scripts using vector search and performance reranking"""
    
    def __init__(self):
        self.embed_service_url = settings.embed_service_url
        self.namespace = settings.embed_namespace
        self.max_duration = settings.max_ref_duration_seconds
        self.max_candidates = settings.max_candidates
        self.max_alternates = settings.max_alternates
        
        # Scoring weights
        self.similarity_weight = settings.similarity_weight
        self.performance_weight = settings.performance_weight
        self.recency_decay_days = settings.recency_decay_days
    
    async def retrieve_reference(self, draft_body: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Retrieve the best reference script for a draft
        
        Args:
            draft_body: Draft script text
            db: Database session
            
        Returns:
            Dictionary with ref, alternates, and metadata
        """
        start_time = time.time()
        
        try:
            # Generate ephemeral embedding for draft
            draft_embedding = await self._get_draft_embedding(draft_body)
            
            # Find similar scripts using vector search
            candidates = await self._vector_search(draft_embedding, db)
            
            if not candidates:
                return {
                    "ref": None,
                    "alternates": [],
                    "total_candidates": 0,
                    "search_time_ms": (time.time() - start_time) * 1000,
                    "reason": "No eligible reference scripts found (≤180s duration with embeddings)"
                }
            
            # Rerank by performance
            ranked_candidates = await self._performance_rerank(candidates, db)
            
            # Format results
            ref = ranked_candidates[0] if ranked_candidates else None
            alternates = ranked_candidates[1:self.max_alternates + 1] if len(ranked_candidates) > 1 else []
            
            search_time_ms = (time.time() - start_time) * 1000
            
            logger.info("Retrieved reference", 
                       candidates_found=len(candidates),
                       ref_video_id=ref['video_id'] if ref else None,
                       search_time_ms=search_time_ms)
            
            return {
                "ref": ref,
                "alternates": alternates,
                "total_candidates": len(candidates),
                "search_time_ms": search_time_ms,
                "reason": None
            }
            
        except Exception as e:
            logger.error("Retrieval failed", error=str(e))
            return {
                "ref": None,
                "alternates": [],
                "total_candidates": 0,
                "search_time_ms": (time.time() - start_time) * 1000,
                "reason": f"Retrieval error: {str(e)}"
            }
    
    async def _get_draft_embedding(self, text: str) -> List[float]:
        """Get ephemeral embedding for draft text from embed service"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.embed_service_url}/embed",
                json={"text": text, "ephemeral": True},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["embedding"]
    
    async def _vector_search(self, query_embedding: List[float], db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using pgvector
        
        Args:
            query_embedding: Query vector
            db: Database session
            
        Returns:
            List of candidate scripts with similarity scores
        """
        # Convert embedding to string format for SQL
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        # Vector similarity search with cosine distance
        # Join with scripts and performance metrics to get all needed data
        query = text("""
            SELECT 
                s.video_id,
                s.version,
                s.body,
                s.duration_seconds,
                e.vector <=> :query_vector AS similarity_distance,
                1 - (e.vector <=> :query_vector) AS similarity_score
            FROM embeddings e
            JOIN scripts s ON e.video_id = s.video_id AND e.version = s.version
            WHERE e.namespace = :namespace
              AND s.duration_seconds <= :max_duration
            ORDER BY e.vector <=> :query_vector
            LIMIT :max_candidates
        """)
        
        result = await db.execute(
            query,
            {
                "query_vector": embedding_str,
                "namespace": self.namespace,
                "max_duration": self.max_duration,
                "max_candidates": self.max_candidates
            }
        )
        
        candidates = []
        for row in result:
            candidates.append({
                "video_id": row.video_id,
                "version": row.version,
                "body": row.body,
                "duration_seconds": row.duration_seconds,
                "similarity_score": float(row.similarity_score)
            })
        
        return candidates
    
    async def _performance_rerank(self, candidates: List[Dict[str, Any]], db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Rerank candidates by combining similarity and performance scores
        
        Args:
            candidates: List of candidate scripts
            db: Database session
            
        Returns:
            Reranked list of candidates
        """
        if not candidates:
            return []
        
        # Get performance metrics for all candidates
        video_ids = [c["video_id"] for c in candidates]
        
        query = select(PerformanceMetrics).where(
            PerformanceMetrics.video_id.in_(video_ids)
        )
        
        result = await db.execute(query)
        metrics_by_video_id = {m.video_id: m for m in result.scalars().all()}
        
        # Calculate combined scores
        scored_candidates = []
        
        for candidate in candidates:
            video_id = candidate["video_id"]
            metrics = metrics_by_video_id.get(video_id)
            
            if not metrics:
                continue  # Skip candidates without metrics
            
            # Calculate performance score
            performance_score = self._calculate_performance_score(metrics)
            
            # Combine similarity and performance scores
            combined_score = (
                self.similarity_weight * candidate["similarity_score"] +
                self.performance_weight * performance_score
            )
            
            # Add performance data to candidate
            candidate.update({
                "performance": {
                    "views": metrics.views,
                    "ctr": metrics.ctr,
                    "avg_view_duration_s": metrics.avg_view_duration_s,
                    "retention_30s": metrics.retention_30s
                },
                "performance_score": performance_score,
                "combined_score": combined_score
            })
            
            scored_candidates.append(candidate)
        
        # Sort by combined score (descending)
        scored_candidates.sort(key=lambda x: x["combined_score"], reverse=True)
        
        return scored_candidates
    
    def _calculate_performance_score(self, metrics: PerformanceMetrics) -> float:
        """
        Calculate normalized performance score for a video
        
        Args:
            metrics: Performance metrics
            
        Returns:
            Normalized performance score (0-1)
        """
        score = 0.0
        components = 0
        
        # Views component (log-normalized)
        if metrics.views > 0:
            # Log scale for views, normalized to 0-1 range
            # Assume 1M views = score of 1.0
            views_score = min(1.0, np.log10(metrics.views) / 6.0)  # log10(1M) = 6
            score += views_score
            components += 1
        
        # CTR component
        if metrics.ctr is not None and metrics.ctr > 0:
            # Assume 10% CTR = score of 1.0
            ctr_score = min(1.0, metrics.ctr / 0.10)
            score += ctr_score
            components += 1
        
        # Retention component
        if metrics.retention_30s is not None and metrics.retention_30s > 0:
            # retention_30s is already a ratio (0-1)
            score += metrics.retention_30s
            components += 1
        
        # Average view duration component
        if metrics.avg_view_duration_s is not None and metrics.avg_view_duration_s > 0:
            # Assume 60s average view duration = score of 1.0
            duration_score = min(1.0, metrics.avg_view_duration_s / 60.0)
            score += duration_score
            components += 1
        
        # Apply recency decay if we have published_at
        if metrics.published_at:
            days_old = (datetime.utcnow() - metrics.published_at).days
            recency_factor = max(0.1, 1.0 - (days_old / self.recency_decay_days))
            score *= recency_factor
        
        # Return average score across components
        return score / max(1, components)
