import re
from typing import Tuple

class TextCleaner:
    """Cleans video transcripts by removing timestamps and estimating duration"""
    
    def __init__(self, words_per_minute: int = 160):
        self.words_per_minute = words_per_minute
        
        # Regex patterns for timestamp removal
        self.timestamp_patterns = [
            # [mm:ss] or [hh:mm:ss] at line start
            r'^\[(?:\d{1,2}:)?\d{1,2}:\d{2}\]\s*',
            # [mm:ss–mm:ss] ranges
            r'\[(?:\d{1,2}:)?\d{1,2}:\d{2}[–-](?:\d{1,2}:)?\d{1,2}:\d{2}\]',
            # Compact formats: 1h02m, 2m15s, 90s
            r'\b\d+h\d+m\b|\b\d+m\d+s\b|\b\d+s\b',
            # Standalone timestamps in brackets
            r'\[(?:\d{1,2}:)?\d{1,2}:\d{2}\]',
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.MULTILINE) for pattern in self.timestamp_patterns]
    
    def clean_transcript(self, text: str) -> Tuple[str, float]:
        """
        Clean transcript text and estimate duration
        
        Args:
            text: Raw transcript text
            
        Returns:
            Tuple of (cleaned_text, estimated_duration_seconds)
        """
        if not text or not isinstance(text, str):
            return "", 0.0
        
        cleaned = text
        
        # Remove timestamps using compiled patterns
        for pattern in self.compiled_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Estimate duration based on word count
        word_count = len(cleaned.split())
        duration_seconds = round((word_count * 60) / self.words_per_minute, 1)
        
        return cleaned, duration_seconds
    
    def is_valid_duration(self, duration_seconds: float, max_duration: int = 180) -> bool:
        """Check if duration is within acceptable limits for reference eligibility"""
        return 0 < duration_seconds <= max_duration
