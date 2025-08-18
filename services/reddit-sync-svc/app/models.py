from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()

class Idea(Base):
    __tablename__ = "ideas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id = Column(String(100), unique=True, nullable=False, index=True)  # Reddit post ID
    title = Column(String(300), nullable=False)
    snippet = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=False)
    subreddit = Column(String(50), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    num_comments = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)  # Reddit creation time
    fetched_at = Column(DateTime, default=datetime.utcnow)
