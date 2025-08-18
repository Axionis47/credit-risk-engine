"""Initial schema with pgvector support

Revision ID: 0001
Revises: 
Create Date: 2024-12-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('picture', sa.String(length=500), nullable=True),
        sa.Column('verified_email', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create scripts table
    op.create_table('scripts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', sa.String(length=50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('hook', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scripts_video_id'), 'scripts', ['video_id'], unique=False)
    op.create_index('ix_scripts_video_id_version', 'scripts', ['video_id', 'version'], unique=False)
    
    # Create performance_metrics table
    op.create_table('performance_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', sa.String(length=50), nullable=False),
        sa.Column('asof_date', sa.DateTime(), nullable=True),
        sa.Column('views', sa.Integer(), nullable=False),
        sa.Column('ctr', sa.Float(), nullable=True),
        sa.Column('avg_view_duration_s', sa.Float(), nullable=True),
        sa.Column('retention_30s', sa.Float(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_performance_metrics_video_id'), 'performance_metrics', ['video_id'], unique=False)
    
    # Create embeddings table with pgvector
    op.create_table('embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', sa.String(length=50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('namespace', sa.String(length=50), nullable=False),
        sa.Column('vector', postgresql.VECTOR(3072), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_embeddings_video_id'), 'embeddings', ['video_id'], unique=False)
    op.create_index('ix_embeddings_video_id_version_namespace', 'embeddings', ['video_id', 'version', 'namespace'], unique=False)
    
    # Create IVFFLAT index for vector similarity search
    op.execute('CREATE INDEX ix_embeddings_vector_ivfflat ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100)')
    
    # Create ideas table
    op.create_table('ideas',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idea_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('snippet', sa.Text(), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=False),
        sa.Column('subreddit', sa.String(length=50), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('num_comments', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ideas_idea_id'), 'ideas', ['idea_id'], unique=True)
    op.create_index(op.f('ix_ideas_subreddit'), 'ideas', ['subreddit'], unique=False)
    op.create_index('ix_ideas_subreddit_score', 'ideas', ['subreddit', 'score'], unique=False)
    op.create_index('ix_ideas_created_at', 'ideas', ['created_at'], unique=False)
    
    # Create user_feedback table
    op.create_table('user_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idea_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feedback_type', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['idea_id'], ['ideas.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_feedback_user_idea', 'user_feedback', ['user_id', 'idea_id'], unique=True)
    op.create_index('ix_user_feedback_feedback_type', 'user_feedback', ['feedback_type'], unique=False)


def downgrade() -> None:
    op.drop_table('user_feedback')
    op.drop_table('ideas')
    op.drop_table('embeddings')
    op.drop_table('performance_metrics')
    op.drop_table('scripts')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS vector')
