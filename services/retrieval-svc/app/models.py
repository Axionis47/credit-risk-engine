from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()

class Script(Base):
    __tablename__ = "scripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String(50), nullable=False, index=True)
    version = Column(Integer, default=0, nullable=False)
    source = Column(String(20), default='draft', nullable=False)
    body = Column(Text, nullable=False)
    title = Column(String(500), nullable=True)
    hook = Column(Text, nullable=True)
    word_count = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PerformanceMetrics(Base):
    __tablename__ = "performance_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String(50), nullable=False, index=True)
    asof_date = Column(DateTime, nullable=True)
    views = Column(Integer, nullable=False)
    ctr = Column(Float, nullable=True)
    avg_view_duration_s = Column(Float, nullable=True)
    retention_30s = Column(Float, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Embedding(Base):
    __tablename__ = "embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String(50), nullable=False, index=True)
    version = Column(Integer, default=0, nullable=False)
    namespace = Column(String(50), nullable=False, default='v1/openai/te3l-3072')
    vector = Column(Vector(3072), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
