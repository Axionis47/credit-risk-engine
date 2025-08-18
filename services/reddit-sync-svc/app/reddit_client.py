import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
import base64
from markdownify import markdownify
from simhash import Simhash
import structlog

from app.config import settings

logger = structlog.get_logger()

class RedditClient:
    """Reddit API client with OAuth authentication and rate limiting"""
    
    def __init__(self):
        self.client_id = settings.reddit_client_id
        self.client_secret = settings.reddit_client_secret
        self.user_agent = settings.reddit_user_agent
        
        self.access_token = None
        self.token_expires_at = None
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 60.0 / settings.requests_per_minute  # seconds between requests
    
    async def authenticate(self):
        """Authenticate with Reddit API using client credentials"""
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'User-Agent': self.user_agent
        }
        
        data = {
            'grant_type': 'client_credentials'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://www.reddit.com/api/v1/access_token',
                headers=headers,
                data=data,
                timeout=30.0
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = time.time() + expires_in - 60  # 1 minute buffer
            
            logger.info("Reddit authentication successful", expires_in=expires_in)
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if not self.access_token or time.time() >= self.token_expires_at:
            await self.authenticate()
    
    async def _rate_limit(self):
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def fetch_subreddit_posts(self, subreddit: str, limit: int = 50, 
                                  min_score: int = 10, max_age_hours: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch posts from a subreddit
        
        Args:
            subreddit: Subreddit name
            limit: Maximum number of posts to fetch
            min_score: Minimum score threshold
            max_age_hours: Maximum age in hours
            
        Returns:
            List of post data
        """
        await self._ensure_authenticated()
        await self._rate_limit()
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'User-Agent': self.user_agent
        }
        
        # Fetch hot posts
        url = f'https://oauth.reddit.com/r/{subreddit}/hot'
        params = {
            'limit': min(limit, 100),  # Reddit API limit
            'raw_json': 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            for post_data in data['data']['children']:
                post = post_data['data']
                
                # Skip if too old
                created_utc = datetime.utcfromtimestamp(post['created_utc'])
                if created_utc < cutoff_time:
                    continue
                
                # Skip if score too low
                if post['score'] < min_score:
                    continue
                
                # Skip if removed/deleted
                if post.get('removed_by_category') or post.get('selftext') == '[deleted]':
                    continue
                
                # Process post
                processed_post = await self._process_post(post, subreddit)
                if processed_post:
                    posts.append(processed_post)
            
            logger.info("Fetched subreddit posts", 
                       subreddit=subreddit, 
                       total_fetched=len(posts),
                       limit=limit)
            
            return posts
    
    async def _process_post(self, post: Dict[str, Any], subreddit: str) -> Optional[Dict[str, Any]]:
        """Process a single Reddit post"""
        try:
            # Extract basic info
            idea_id = post['id']
            title = post['title'].strip()
            score = post['score']
            num_comments = post['num_comments']
            created_at = datetime.utcfromtimestamp(post['created_utc'])
            source_url = f"https://reddit.com{post['permalink']}"
            
            # Create snippet from selftext or title
            snippet = ""
            if post.get('selftext') and post['selftext'].strip():
                # Convert markdown to text
                snippet = markdownify(post['selftext'], strip=['a', 'img'])
                snippet = snippet.strip()
            
            if not snippet:
                snippet = title
            
            # Validate lengths
            if len(title) > settings.max_title_length:
                title = title[:settings.max_title_length - 3] + "..."
            
            if len(snippet) > settings.max_snippet_length:
                snippet = snippet[:settings.max_snippet_length - 3] + "..."
            
            if len(snippet) < settings.min_snippet_length:
                return None  # Skip posts that are too short
            
            return {
                'idea_id': idea_id,
                'title': title,
                'snippet': snippet,
                'source_url': source_url,
                'subreddit': subreddit,
                'score': score,
                'num_comments': num_comments,
                'created_at': created_at,
                'fetched_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.warning("Failed to process post", post_id=post.get('id'), error=str(e))
            return None
