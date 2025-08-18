#!/bin/bash

# Set up local development environment
# Usage: ./scripts/dev-setup.sh

set -e

echo "Setting up PP Final development environment..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker and try again."
  exit 1
fi

# Check if required environment variables are set
if [ ! -f .env ]; then
  echo "Error: .env file not found. Please copy .env.example to .env and fill in the values."
  exit 1
fi

# Source environment variables
source .env

# Validate required API keys
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your-openai-api-key" ]; then
  echo "Error: OPENAI_API_KEY not set in .env file"
  exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your-anthropic-api-key" ]; then
  echo "Error: ANTHROPIC_API_KEY not set in .env file"
  exit 1
fi

echo "✓ Environment variables validated"

# Start infrastructure services
echo "Starting PostgreSQL and Redis..."
cd dev
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until docker-compose exec postgres pg_isready -U postgres >/dev/null 2>&1; do
  echo "  Waiting for PostgreSQL..."
  sleep 2
done

echo "✓ PostgreSQL is ready"

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until docker-compose exec redis redis-cli ping >/dev/null 2>&1; do
  echo "  Waiting for Redis..."
  sleep 2
done

echo "✓ Redis is ready"

# Run database migrations
echo "Running database migrations..."
docker-compose run --rm migrate

echo "✓ Database migrations completed"

# Install frontend dependencies
echo "Installing frontend dependencies..."

if [ -d "apps/editor-frontend" ]; then
  echo "Installing editor-frontend dependencies..."
  cd ../apps/editor-frontend
  npm install
  cd ../../dev
fi

if [ -d "apps/ideahunter-frontend" ]; then
  echo "Installing ideahunter-frontend dependencies..."
  cd ../apps/ideahunter-frontend
  npm install
  cd ../../dev
fi

echo "✓ Frontend dependencies installed"

# Start all services
echo "Starting all services..."
docker-compose up -d

echo ""
echo "🎉 Development environment is ready!"
echo ""
echo "Services:"
echo "  - Gateway API: http://localhost:8000"
echo "  - Embed Service: http://localhost:8001"
echo "  - Retrieval Service: http://localhost:8002"
echo "  - Editor Service: http://localhost:8003"
echo "  - Reddit Sync Service: http://localhost:8004"
echo "  - Ingest Service: http://localhost:8005"
echo ""
echo "Frontends:"
echo "  - Script Improver: http://localhost:3000"
echo "  - Idea Hunter: http://localhost:3001"
echo ""
echo "Infrastructure:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "To view logs: docker-compose logs -f [service-name]"
echo "To stop all services: docker-compose down"
echo ""
echo "Next steps:"
echo "1. Set up Google OAuth credentials"
echo "2. Set up Reddit API credentials"
echo "3. Upload some CSV data via the ingest endpoint"
echo "4. Start using the applications!"
