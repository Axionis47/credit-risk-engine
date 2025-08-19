from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database connection"""
    async with engine.begin() as conn:
        # Verify main tables exist
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_name IN ('users', 'ideas', 'user_feedback')")
        )
        tables = [row[0] for row in result]
        
        if len(tables) >= 3:
            print("✓ Database initialized for gateway API")
        else:
            raise RuntimeError(f"Missing tables - run migrations first. Found: {tables}")
