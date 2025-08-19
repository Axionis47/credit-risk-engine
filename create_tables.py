#!/usr/bin/env python3
import asyncio
import asyncpg

async def create_tables():
    # Connect to the database
    conn = await asyncpg.connect(
        host='35.202.108.58',
        port=5432,
        user='postgres',
        password='temp-password-123',
        database='pp_final'
    )
    
    try:
        # Create UUID extension
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        print("✅ UUID extension created")
        
        # Create users table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                picture VARCHAR(500),
                verified_email BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);')
        print("✅ Users table created")
        
        # Create ideas table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS ideas (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                idea_id VARCHAR(100) UNIQUE NOT NULL,
                title VARCHAR(300) NOT NULL,
                snippet TEXT NOT NULL,
                source_url VARCHAR(500) NOT NULL,
                subreddit VARCHAR(50) NOT NULL,
                score INTEGER NOT NULL,
                num_comments INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_ideas_idea_id ON ideas(idea_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_ideas_subreddit ON ideas(subreddit);')
        print("✅ Ideas table created")
        
        # Create user_feedback table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_feedback (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id UUID NOT NULL REFERENCES users(id),
                idea_id UUID NOT NULL REFERENCES ideas(id),
                feedback_type VARCHAR(20) NOT NULL,
                notes VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        print("✅ User feedback table created")

        # Create scripts table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS scripts (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                video_id VARCHAR(50) NOT NULL,
                version INTEGER DEFAULT 0 NOT NULL,
                title VARCHAR(500),
                content TEXT NOT NULL,
                estimated_duration FLOAT,
                published_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_scripts_video_id ON scripts(video_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_scripts_video_id_version ON scripts(video_id, version);')
        print("✅ Scripts table created")

        # Create performance_metrics table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                video_id VARCHAR(50) NOT NULL,
                asof_date TIMESTAMP,
                views INTEGER,
                retention_30s FLOAT,
                published_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_performance_metrics_video_id ON performance_metrics(video_id);')
        print("✅ Performance metrics table created")

        # Create pgvector extension and embeddings table
        await conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                video_id VARCHAR(50) NOT NULL,
                version INTEGER DEFAULT 0 NOT NULL,
                namespace VARCHAR(50) NOT NULL DEFAULT 'v1/openai/te3l-3072',
                vector vector(3072) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_embeddings_video_id ON embeddings(video_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_embeddings_video_id_version_namespace ON embeddings(video_id, version, namespace);')
        print("✅ Embeddings table created with pgvector support")

        # Verify tables exist
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_name IN ('users', 'ideas', 'user_feedback', 'scripts', 'performance_metrics', 'embeddings')"
        )
        print(f"✅ Verified tables: {[row['table_name'] for row in tables]}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(create_tables())
