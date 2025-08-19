#!/usr/bin/env python3
"""
Vector embeddings management script for environment separation.
Handles snapshotting, environment-scoped indexes, and safe migrations.
"""

import os
import sys
import json
import asyncio
import asyncpg
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import click

# Database connection settings
DB_CONFIGS = {
    'prod': {
        'host': 'script-improver-system-prod',
        'database': 'script_improver_system_prod',
        'user': 'postgres',
    },
    'test': {
        'host': 'script-improver-system-test', 
        'database': 'script_improver_system_test',
        'user': 'postgres',
    },
    'dev': {
        'host': 'script-improver-system-dev',
        'database': 'script_improver_system_dev', 
        'user': 'postgres',
    }
}

class EmbeddingsManager:
    def __init__(self, environment: str):
        self.environment = environment
        self.db_config = DB_CONFIGS.get(environment)
        if not self.db_config:
            raise ValueError(f"Unknown environment: {environment}")
    
    async def get_connection(self) -> asyncpg.Connection:
        """Get database connection for the environment"""
        password = os.getenv(f'DB_PASSWORD_{self.environment.upper()}')
        if not password:
            raise ValueError(f"DB_PASSWORD_{self.environment.upper()} not set")
        
        return await asyncpg.connect(
            host=self.db_config['host'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=password
        )
    
    async def snapshot_embeddings(self, output_path: str) -> Dict[str, Any]:
        """Create a snapshot of current embeddings"""
        click.echo(f"Creating embeddings snapshot for {self.environment}...")
        
        conn = await self.get_connection()
        try:
            # Get embeddings with metadata
            query = """
            SELECT 
                video_id,
                version,
                embedding,
                created_at,
                updated_at
            FROM embeddings 
            ORDER BY created_at
            """
            
            rows = await conn.fetch(query)
            
            snapshot_data = {
                'environment': self.environment,
                'timestamp': datetime.utcnow().isoformat(),
                'count': len(rows),
                'embeddings': []
            }
            
            for row in rows:
                embedding_data = {
                    'video_id': row['video_id'],
                    'version': row['version'],
                    'embedding': row['embedding'].tolist() if row['embedding'] else None,
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                }
                snapshot_data['embeddings'].append(embedding_data)
            
            # Write snapshot to file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(snapshot_data, f, indent=2)
            
            click.echo(f"Snapshot created: {output_file}")
            click.echo(f"Embeddings count: {len(rows)}")
            
            return snapshot_data
            
        finally:
            await conn.close()
    
    async def create_env_scoped_index(self, source_env: Optional[str] = None) -> bool:
        """Create environment-scoped vector index"""
        click.echo(f"Creating vector index for {self.environment}...")
        
        conn = await self.get_connection()
        try:
            # Create embeddings table if it doesn't exist
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS embeddings_{self.environment} (
                id SERIAL PRIMARY KEY,
                video_id VARCHAR(255) NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                embedding vector(3072),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(video_id, version)
            );
            
            CREATE INDEX IF NOT EXISTS idx_embeddings_{self.environment}_video_id 
            ON embeddings_{self.environment}(video_id);
            
            CREATE INDEX IF NOT EXISTS idx_embeddings_{self.environment}_embedding 
            ON embeddings_{self.environment} USING ivfflat (embedding vector_cosine_ops);
            """
            
            await conn.execute(create_table_query)
            
            # If source environment specified, copy data
            if source_env and source_env != self.environment:
                if source_env not in DB_CONFIGS:
                    raise ValueError(f"Unknown source environment: {source_env}")
                
                # This would require cross-database connection
                # For now, we'll use snapshots for data migration
                click.echo(f"Use snapshot/restore for copying from {source_env} to {self.environment}")
            
            click.echo(f"Vector index created for {self.environment}")
            return True
            
        except Exception as e:
            click.echo(f"Error creating index: {e}")
            return False
        finally:
            await conn.close()
    
    async def restore_from_snapshot(self, snapshot_path: str, sanitize: bool = False) -> bool:
        """Restore embeddings from snapshot"""
        click.echo(f"Restoring embeddings to {self.environment} from {snapshot_path}...")
        
        if not Path(snapshot_path).exists():
            click.echo(f"Snapshot file not found: {snapshot_path}")
            return False
        
        with open(snapshot_path) as f:
            snapshot_data = json.load(f)
        
        conn = await self.get_connection()
        try:
            # Clear existing data (be careful!)
            if self.environment != 'prod':
                await conn.execute(f"TRUNCATE TABLE embeddings_{self.environment}")
            
            # Insert embeddings
            insert_query = f"""
            INSERT INTO embeddings_{self.environment} 
            (video_id, version, embedding, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (video_id, version) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                updated_at = EXCLUDED.updated_at
            """
            
            for embedding_data in snapshot_data['embeddings']:
                video_id = embedding_data['video_id']
                
                # Sanitize data for non-prod environments
                if sanitize and self.environment != 'prod':
                    # Mask sensitive data
                    if 'test' in video_id.lower() or 'sample' in video_id.lower():
                        video_id = f"sanitized_{hash(video_id) % 10000:04d}"
                
                await conn.execute(
                    insert_query,
                    video_id,
                    embedding_data['version'],
                    embedding_data['embedding'],
                    datetime.fromisoformat(embedding_data['created_at']) if embedding_data['created_at'] else None,
                    datetime.fromisoformat(embedding_data['updated_at']) if embedding_data['updated_at'] else None
                )
            
            click.echo(f"Restored {len(snapshot_data['embeddings'])} embeddings")
            return True
            
        except Exception as e:
            click.echo(f"Error restoring snapshot: {e}")
            return False
        finally:
            await conn.close()
    
    async def verify_isolation(self) -> bool:
        """Verify environment isolation"""
        click.echo(f"Verifying isolation for {self.environment}...")
        
        conn = await self.get_connection()
        try:
            # Check table exists
            table_query = f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'embeddings_{self.environment}'
            )
            """
            table_exists = await conn.fetchval(table_query)
            
            if not table_exists:
                click.echo(f"❌ Table embeddings_{self.environment} does not exist")
                return False
            
            # Check data isolation
            count_query = f"SELECT COUNT(*) FROM embeddings_{self.environment}"
            count = await conn.fetchval(count_query)
            
            click.echo(f"✅ Environment {self.environment} has {count} embeddings")
            
            # Check for cross-environment contamination
            if self.environment == 'prod':
                # In prod, check for test/dev data
                test_data_query = f"""
                SELECT COUNT(*) FROM embeddings_{self.environment} 
                WHERE video_id ILIKE '%test%' OR video_id ILIKE '%dev%' OR video_id ILIKE '%sample%'
                """
                test_count = await conn.fetchval(test_data_query)
                
                if test_count > 0:
                    click.echo(f"❌ Found {test_count} test/dev records in production!")
                    return False
                else:
                    click.echo("✅ No test/dev data found in production")
            
            return True
            
        except Exception as e:
            click.echo(f"Error verifying isolation: {e}")
            return False
        finally:
            await conn.close()

@click.group()
def cli():
    """Vector embeddings management for environment separation"""
    pass

@cli.command()
@click.argument('environment', type=click.Choice(['dev', 'test', 'prod']))
@click.option('--output', '-o', default='snapshots/embeddings-{env}-{timestamp}.json', 
              help='Output file path')
def snapshot(environment: str, output: str):
    """Create embeddings snapshot"""
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    output_path = output.format(env=environment, timestamp=timestamp)
    
    manager = EmbeddingsManager(environment)
    asyncio.run(manager.snapshot_embeddings(output_path))

@cli.command()
@click.argument('environment', type=click.Choice(['dev', 'test', 'prod']))
@click.option('--source', '-s', help='Source environment to copy from')
def create_index(environment: str, source: Optional[str]):
    """Create environment-scoped vector index"""
    manager = EmbeddingsManager(environment)
    success = asyncio.run(manager.create_env_scoped_index(source))
    
    if success:
        click.echo("✅ Index created successfully")
    else:
        click.echo("❌ Index creation failed")
        sys.exit(1)

@cli.command()
@click.argument('environment', type=click.Choice(['dev', 'test', 'prod']))
@click.argument('snapshot_path', type=click.Path(exists=True))
@click.option('--sanitize', is_flag=True, help='Sanitize data for non-prod environments')
def restore(environment: str, snapshot_path: str, sanitize: bool):
    """Restore embeddings from snapshot"""
    if environment == 'prod' and sanitize:
        click.echo("❌ Cannot sanitize data when restoring to production")
        sys.exit(1)
    
    manager = EmbeddingsManager(environment)
    success = asyncio.run(manager.restore_from_snapshot(snapshot_path, sanitize))
    
    if success:
        click.echo("✅ Restore completed successfully")
    else:
        click.echo("❌ Restore failed")
        sys.exit(1)

@cli.command()
@click.argument('environment', type=click.Choice(['dev', 'test', 'prod']))
def verify(environment: str):
    """Verify environment isolation"""
    manager = EmbeddingsManager(environment)
    success = asyncio.run(manager.verify_isolation())
    
    if success:
        click.echo("✅ Environment isolation verified")
    else:
        click.echo("❌ Environment isolation issues detected")
        sys.exit(1)

if __name__ == '__main__':
    cli()
