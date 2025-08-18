import time
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
import structlog

from app.config import settings
from app.models import Idea
from app.reddit_client import RedditClient
from app.deduplicator import Deduplicator

logger = structlog.get_logger()

class SyncService:
    """Service for syncing ideas from Reddit"""
    
    def __init__(self):
        self.reddit_client = RedditClient()
    
    async def sync_ideas(self, subreddits: List[str] = None, max_posts_per_subreddit: int = None,
                        min_score: int = None, max_age_hours: int = None, db: AsyncSession = None) -> Dict[str, Any]:
        """
        Sync ideas from Reddit subreddits
        
        Args:
            subreddits: List of subreddit names (default: from settings)
            max_posts_per_subreddit: Max posts per subreddit (default: from settings)
            min_score: Minimum score threshold (default: from settings)
            max_age_hours: Maximum age in hours (default: from settings)
            db: Database session
            
        Returns:
            Sync report with statistics
        """
        start_time = time.time()
        
        # Use defaults if not provided
        if subreddits is None:
            subreddits = settings.default_subreddits
        if max_posts_per_subreddit is None:
            max_posts_per_subreddit = settings.max_posts_per_subreddit
        if min_score is None:
            min_score = settings.min_score
        if max_age_hours is None:
            max_age_hours = settings.max_age_hours
        
        logger.info("Starting Reddit sync", 
                   subreddits=subreddits,
                   max_posts_per_subreddit=max_posts_per_subreddit,
                   min_score=min_score,
                   max_age_hours=max_age_hours)
        
        # Initialize deduplicator with existing ideas
        deduplicator = Deduplicator()
        await self._load_existing_ideas(deduplicator, db)
        
        # Fetch posts from all subreddits
        all_posts = []
        errors = []
        subreddits_processed = []
        
        for subreddit in subreddits:
            try:
                posts = await self.reddit_client.fetch_subreddit_posts(
                    subreddit=subreddit,
                    limit=max_posts_per_subreddit,
                    min_score=min_score,
                    max_age_hours=max_age_hours
                )
                all_posts.extend(posts)
                subreddits_processed.append(subreddit)
                
                logger.info("Fetched posts from subreddit", 
                           subreddit=subreddit, 
                           posts_count=len(posts))
                
            except Exception as e:
                error_msg = f"Failed to fetch from r/{subreddit}: {str(e)}"
                errors.append(error_msg)
                logger.error("Subreddit fetch failed", subreddit=subreddit, error=str(e))
        
        # Deduplicate posts
        unique_posts = deduplicator.deduplicate_posts(all_posts)
        
        # Insert unique posts into database
        inserted_count = 0
        for post in unique_posts:
            try:
                await self._insert_idea(post, db)
                inserted_count += 1
            except Exception as e:
                error_msg = f"Failed to insert idea {post['idea_id']}: {str(e)}"
                errors.append(error_msg)
                logger.error("Idea insertion failed", idea_id=post['idea_id'], error=str(e))
        
        await db.commit()
        
        processing_time = time.time() - start_time
        
        logger.info("Reddit sync completed", 
                   total_fetched=len(all_posts),
                   unique_posts=len(unique_posts),
                   inserted=inserted_count,
                   duplicates_skipped=len(all_posts) - len(unique_posts),
                   processing_time_seconds=processing_time)
        
        return {
            "inserted": inserted_count,
            "skipped_duplicates": len(all_posts) - len(unique_posts),
            "errors": errors,
            "processing_time_seconds": processing_time,
            "subreddits_processed": subreddits_processed
        }
    
    async def _load_existing_ideas(self, deduplicator: Deduplicator, db: AsyncSession):
        """Load existing ideas for deduplication"""
        query = select(Idea.idea_id, Idea.title, Idea.snippet, Idea.source_url)
        result = await db.execute(query)
        
        existing_ideas = []
        for row in result:
            existing_ideas.append({
                'idea_id': row.idea_id,
                'title': row.title,
                'snippet': row.snippet,
                'source_url': row.source_url
            })
        
        deduplicator.add_existing_ideas(existing_ideas)
        
        logger.info("Loaded existing ideas for deduplication", count=len(existing_ideas))
    
    async def _insert_idea(self, post: Dict[str, Any], db: AsyncSession):
        """Insert a new idea into the database"""
        idea_data = {
            'idea_id': post['idea_id'],
            'title': post['title'],
            'snippet': post['snippet'],
            'source_url': post['source_url'],
            'subreddit': post['subreddit'],
            'score': post['score'],
            'num_comments': post['num_comments'],
            'created_at': post['created_at'],
            'fetched_at': post['fetched_at']
        }
        
        await db.execute(insert(Idea).values(**idea_data))
