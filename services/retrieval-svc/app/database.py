from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
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
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        )
        if not result.fetchone():
            raise RuntimeError("pgvector extension not found. Please install and enable it.")
        
        # Verify IVFFLAT index exists
        result = await conn.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'embeddings' AND indexname = 'ix_embeddings_vector_ivfflat'"
        )
        if result.fetchone():
            print("✓ Database initialized with pgvector IVFFLAT index")
        else:
            print("⚠ IVFFLAT index not found - vector search may be slow")
