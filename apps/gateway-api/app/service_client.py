import httpx
from typing import Dict, Any, Optional
import structlog

from app.config import settings

logger = structlog.get_logger()

class ServiceClient:
    """Client for communicating with microservices"""
    
    def __init__(self):
        self.ingest_url = settings.ingest_service_url
        self.embed_url = settings.embed_service_url
        self.retrieval_url = settings.retrieval_service_url
        self.editor_url = settings.editor_service_url
        self.reddit_sync_url = settings.reddit_sync_service_url
        
        self.timeout = 60.0  # 60 second timeout for service calls
    
    async def ingest_auto(self, metrics_file: bytes, transcripts_file: bytes, 
                         force_override: Optional[str] = None) -> Dict[str, Any]:
        """Call ingest service auto endpoint"""
        files = {
            'metrics_file': ('metrics.csv', metrics_file, 'text/csv'),
            'transcripts_file': ('transcripts.csv', transcripts_file, 'text/csv')
        }
        
        data = {}
        if force_override:
            data['force_role_override'] = force_override
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ingest_url}/api/ingest/auto",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
    
    async def retrieve_reference(self, draft_body: str) -> Dict[str, Any]:
        """Call retrieval service to find reference script"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.retrieval_url}/retrieve",
                json={"draft_body": draft_body},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
    
    async def improve_script(self, draft_body: str, reference: Optional[Dict[str, Any]] = None,
                           target_word_count: Optional[int] = None, 
                           style_notes: Optional[str] = None) -> Dict[str, Any]:
        """Call editor service to improve script"""
        payload = {"draft_body": draft_body}
        
        if reference:
            payload["reference"] = reference
        if target_word_count:
            payload["target_word_count"] = target_word_count
        if style_notes:
            payload["style_notes"] = style_notes
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.editor_url}/improve",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
    
    async def sync_reddit_ideas(self, subreddits: Optional[list] = None,
                              max_posts_per_subreddit: Optional[int] = None,
                              min_score: Optional[int] = None,
                              max_age_hours: Optional[int] = None) -> Dict[str, Any]:
        """Call reddit sync service"""
        payload = {}
        if subreddits:
            payload["subreddits"] = subreddits
        if max_posts_per_subreddit:
            payload["max_posts_per_subreddit"] = max_posts_per_subreddit
        if min_score:
            payload["min_score"] = min_score
        if max_age_hours:
            payload["max_age_hours"] = max_age_hours
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.reddit_sync_url}/sync",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
    
    async def sync_embeddings(self) -> Dict[str, Any]:
        """Call embed service to sync embeddings"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.embed_url}/embed/sync",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

# Global service client instance
service_client = ServiceClient()
