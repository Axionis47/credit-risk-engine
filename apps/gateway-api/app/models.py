from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
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

class Idea(Base):
    __tablename__ = "ideas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(300), nullable=False)
    snippet = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=False)
    subreddit = Column(String(50), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    num_comments = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)

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
