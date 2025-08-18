from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, VECTOR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    picture = Column(String(500), nullable=True)
    verified_email = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Script(Base):
    __tablename__ = "scripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String(50), nullable=False, index=True)
    version = Column(Integer, default=0, nullable=False)
    source = Column(String(20), default='draft', nullable=False)  # 'draft', 'improved'
    body = Column(Text, nullable=False)
    title = Column(String(500), nullable=True)
    hook = Column(Text, nullable=True)
    word_count = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite index for video_id + version
    __table_args__ = (
        Index('ix_scripts_video_id_version', 'video_id', 'version'),
    )

class PerformanceMetrics(Base):
    __tablename__ = "performance_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String(50), nullable=False, index=True)
    asof_date = Column(DateTime, nullable=True)
    views = Column(Integer, nullable=False)
    ctr = Column(Float, nullable=True)  # Click-through rate
    avg_view_duration_s = Column(Float, nullable=True)
    retention_30s = Column(Float, nullable=True)  # 30-second retention rate
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Embedding(Base):
    __tablename__ = "embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String(50), nullable=False, index=True)
    version = Column(Integer, default=0, nullable=False)
    namespace = Column(String(50), nullable=False, default='v1/openai/te3l-3072')
    vector = Column(VECTOR(3072), nullable=False)  # 3072-dimensional vector
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite index for video_id + version + namespace
    __table_args__ = (
        Index('ix_embeddings_video_id_version_namespace', 'video_id', 'version', 'namespace'),
        # IVFFLAT index for vector similarity search (created in migration)
    )

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
    
    # Index for filtering by subreddit and score
    __table_args__ = (
        Index('ix_ideas_subreddit_score', 'subreddit', 'score'),
        Index('ix_ideas_created_at', 'created_at'),
    )

class UserFeedback(Base):
    __tablename__ = "user_feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    idea_id = Column(UUID(as_uuid=True), ForeignKey('ideas.id'), nullable=False)
    feedback_type = Column(String(20), nullable=False)  # 'reject', 'save', 'superlike'
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    idea = relationship("Idea")
    
    # Composite index for user + idea (prevent duplicates)
    __table_args__ = (
        Index('ix_user_feedback_user_idea', 'user_id', 'idea_id', unique=True),
        Index('ix_user_feedback_feedback_type', 'feedback_type'),
    )
