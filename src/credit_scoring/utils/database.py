"""Database connection management."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class ScoringResult(Base):
    __tablename__ = "scoring_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(String, index=True)
    borrower_id = Column(String, index=True)
    credit_score = Column(Integer)
    pd_value = Column(Float)
    lgd_value = Column(Float)
    ead_value = Column(Float)
    expected_loss = Column(Float)
    fraud_score = Column(Float)
    decision = Column(String)
    model_version = Column(String)
    scored_at = Column(DateTime, default=datetime.utcnow)


class DriftMetric(Base):
    __tablename__ = "drift_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_name = Column(String)
    psi_value = Column(Float)
    status = Column(String)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class FairnessMetric(Base):
    __tablename__ = "fairness_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String)
    group_name = Column(String)
    value = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class DatabaseManager:
    """Manage PostgreSQL connections via SQLAlchemy."""

    def __init__(self, url: str, pool_size: int = 10, echo: bool = False):
        self.engine = create_engine(url, pool_size=pool_size, echo=echo)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Session:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
