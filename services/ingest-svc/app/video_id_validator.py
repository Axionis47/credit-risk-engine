import re
from typing import Optional

class VideoIdValidator:
    """Validates and normalizes video IDs"""
    
    def __init__(self):
        # Video ID pattern: 6-50 characters, alphanumeric plus underscore and dash
        self.video_id_pattern = re.compile(r'^[A-Za-z0-9_-]{6,50}$')
    
    def normalize_video_id(self, video_id: str) -> Optional[str]:
        """
        Normalize video ID: lowercase, trim, validate format
        
        Args:
            video_id: Raw video ID
            
        Returns:
            Normalized video ID or None if invalid
        """
        if not video_id or not isinstance(video_id, str):
            return None
        
        # Normalize: lowercase and trim
        normalized = video_id.lower().strip()
        
        # Validate format
        if self.video_id_pattern.match(normalized):
            return normalized
        
        return None
    
    def is_valid(self, video_id: str) -> bool:
        """Check if video ID is valid"""
        return self.normalize_video_id(video_id) is not None
