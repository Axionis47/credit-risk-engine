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
    """Initialize database connection and verify pgvector extension"""
    async with engine.begin() as conn:
        # Verify pgvector extension is available
        result = await conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        if not result.fetchone():
            raise RuntimeError("pgvector extension not found. Please install and enable it.")
        
        # Verify embeddings table exists
        result = await conn.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_name = 'embeddings' AND column_name = 'vector'")
        )
        if result.fetchone():
            print("✓ Database initialized with pgvector support")
        else:
            raise RuntimeError("Embeddings table not found - run migrations first")
