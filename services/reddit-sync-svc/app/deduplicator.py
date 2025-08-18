from typing import List, Dict, Any, Set
from simhash import Simhash
import re
import structlog

logger = structlog.get_logger()

class Deduplicator:
    """Deduplicates Reddit posts using SimHash and text similarity"""
    
    def __init__(self, simhash_threshold: int = 3):
        self.simhash_threshold = simhash_threshold  # Hamming distance threshold
        self.seen_urls: Set[str] = set()
        self.seen_simhashes: List[int] = []
        self.seen_titles: Set[str] = set()
    
    def add_existing_ideas(self, existing_ideas: List[Dict[str, Any]]):
        """Add existing ideas to deduplication tracking"""
        for idea in existing_ideas:
            self.seen_urls.add(self._normalize_url(idea['source_url']))
            self.seen_titles.add(self._normalize_title(idea['title']))
            
            # Calculate simhash for existing content
            content = f"{idea['title']} {idea['snippet']}"
            simhash = Simhash(self._tokenize(content))
            self.seen_simhashes.append(simhash.value)
    
    def is_duplicate(self, post: Dict[str, Any]) -> bool:
        """Check if a post is a duplicate"""
        
        # Check URL duplicates
        normalized_url = self._normalize_url(post['source_url'])
        if normalized_url in self.seen_urls:
            logger.debug("Duplicate URL detected", url=normalized_url)
            return True
        
        # Check exact title duplicates
        normalized_title = self._normalize_title(post['title'])
        if normalized_title in self.seen_titles:
            logger.debug("Duplicate title detected", title=normalized_title)
            return True
        
        # Check SimHash similarity
        content = f"{post['title']} {post['snippet']}"
        post_simhash = Simhash(self._tokenize(content))
        
        for existing_simhash in self.seen_simhashes:
            distance = post_simhash.distance(Simhash(existing_simhash))
            if distance <= self.simhash_threshold:
                logger.debug("Similar content detected", 
                           distance=distance, 
                           threshold=self.simhash_threshold)
                return True
        
        return False
    
    def add_post(self, post: Dict[str, Any]):
        """Add a post to the deduplication tracking"""
        self.seen_urls.add(self._normalize_url(post['source_url']))
        self.seen_titles.add(self._normalize_title(post['title']))
        
        content = f"{post['title']} {post['snippet']}"
        simhash = Simhash(self._tokenize(content))
        self.seen_simhashes.append(simhash.value)
    
    def deduplicate_posts(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate a list of posts"""
        unique_posts = []
        
        for post in posts:
            if not self.is_duplicate(post):
                unique_posts.append(post)
                self.add_post(post)
            else:
                logger.debug("Skipping duplicate post", idea_id=post['idea_id'])
        
        logger.info("Deduplication completed", 
                   original_count=len(posts),
                   unique_count=len(unique_posts),
                   duplicates_removed=len(posts) - len(unique_posts))
        
        return unique_posts
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        # Remove query parameters and fragments
        url = url.split('?')[0].split('#')[0]
        # Remove trailing slash
        url = url.rstrip('/')
        # Convert to lowercase
        return url.lower()
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison"""
        # Convert to lowercase
        title = title.lower()
        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        # Remove common prefixes/suffixes
        prefixes = ['[serious]', '[nsfw]', '[update]', '[meta]']
        for prefix in prefixes:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
        
        return title
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for SimHash"""
        # Convert to lowercase
        text = text.lower()
        # Remove special characters and split into words
        words = re.findall(r'\b\w+\b', text)
        # Filter out very short words
        words = [word for word in words if len(word) > 2]
        return words
