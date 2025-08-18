#!/bin/bash

# Build and push all container images to Google Artifact Registry
# Usage: ./scripts/build-and-push.sh <project-id> <region>

set -e

PROJECT_ID=${1:-"your-gcp-project-id"}
REGION=${2:-"us-central1"}
REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/pp-final"

echo "Building and pushing images to ${REGISTRY_URL}"

# Authenticate with gcloud
echo "Authenticating with Google Cloud..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push backend services
services=(
  "ingest-svc:services/ingest-svc"
  "embed-svc:services/embed-svc"
  "retrieval-svc:services/retrieval-svc"
  "editor-svc:services/editor-svc"
  "reddit-sync-svc:services/reddit-sync-svc"
  "gateway-api:apps/gateway-api"
)

for service_info in "${services[@]}"; do
  IFS=':' read -r service_name service_path <<< "$service_info"
  
  echo "Building ${service_name}..."
  docker build -t ${REGISTRY_URL}/${service_name}:latest \
    -f infra/docker/Dockerfile.python \
    ${service_path}
  
  echo "Pushing ${service_name}..."
  docker push ${REGISTRY_URL}/${service_name}:latest
done

# Build and push frontend services
frontends=(
  "editor-frontend:apps/editor-frontend"
  "ideahunter-frontend:apps/ideahunter-frontend"
)

for frontend_info in "${frontends[@]}"; do
  IFS=':' read -r frontend_name frontend_path <<< "$frontend_info"
  
  echo "Building ${frontend_name}..."
  docker build -t ${REGISTRY_URL}/${frontend_name}:latest \
    -f infra/docker/Dockerfile.nextjs \
    ${frontend_path}
  
  echo "Pushing ${frontend_name}..."
  docker push ${REGISTRY_URL}/${frontend_name}:latest
done

echo "All images built and pushed successfully!"
echo ""
echo "Next steps:"
echo "1. Set up secrets in Google Secret Manager"
echo "2. Run terraform apply to deploy infrastructure"
echo "3. Run database migrations"
