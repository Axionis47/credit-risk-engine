#!/bin/bash

# Run database migrations on Cloud SQL
# Usage: ./scripts/migrate-db.sh <project-id> <region>

set -e

PROJECT_ID=${1:-"your-gcp-project-id"}
REGION=${2:-"us-central1"}

echo "Running database migrations for project: ${PROJECT_ID}"

# Get database connection details from Terraform output
DB_CONNECTION_NAME=$(cd infra/terraform && terraform output -raw database_connection_name)
DB_PRIVATE_IP=$(cd infra/terraform && terraform output -raw database_private_ip)

echo "Database connection name: ${DB_CONNECTION_NAME}"
echo "Database private IP: ${DB_PRIVATE_IP}"

# Create a temporary Cloud Run job to run migrations
echo "Creating migration job..."

# Build migration image
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/pp-final/migrate:latest \
  -f infra/docker/Dockerfile.python \
  services/ingest-svc

docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/pp-final/migrate:latest

# Create and run migration job
gcloud run jobs create migrate-db \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/pp-final/migrate:latest \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --set-env-vars="DATABASE_URL=postgresql://pp_final:$(gcloud secrets versions access latest --secret=database-password --project=${PROJECT_ID})@${DB_PRIVATE_IP}:5432/pp_final" \
  --vpc-connector=pp-final-connector \
  --vpc-egress=private-ranges-only \
  --service-account=pp-final-cloud-run@${PROJECT_ID}.iam.gserviceaccount.com \
  --command=alembic \
  --args=upgrade,head \
  --max-retries=3 \
  --parallelism=1 \
  --task-count=1 \
  --cpu=1 \
  --memory=512Mi \
  --task-timeout=600 \
  || echo "Job might already exist, continuing..."

echo "Running migration job..."
gcloud run jobs execute migrate-db \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --wait

echo "Database migrations completed successfully!"

# Clean up the job
echo "Cleaning up migration job..."
gcloud run jobs delete migrate-db \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --quiet

echo "Migration job cleaned up."
