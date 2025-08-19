#!/bin/bash
set -e

# Production deployment script with comprehensive safety checks
# This script ensures no mock data reaches production

echo "🚀 Starting production deployment..."

# Check if we're on a tagged release
if [ -z "$(git describe --exact-match --tags HEAD 2>/dev/null)" ]; then
    echo "❌ Production deployment requires a git tag"
    echo "Create a tag first: git tag v1.0.0 && git push origin v1.0.0"
    exit 1
fi

TAG=$(git describe --exact-match --tags HEAD)
echo "📦 Deploying tagged version: $TAG"

# Set production environment
export APP_ENV=prod
export PROJECT_ID=script-improver-system-469119
export REGION=us-central1
export REGISTRY=us-central1-docker.pkg.dev

# Run comprehensive preflight checks
echo "🔍 Running production preflight checks..."
python scripts/preflight_check.py || {
    echo "❌ Preflight checks failed"
    exit 1
}

# Scan for mock data signatures
echo "🔍 Scanning for mock data signatures..."

# Check for mock directories
if find . -type d -name "mocks" -o -name "fixtures" -o -name "sample_data" -o -name "__mocks__" | grep -v node_modules | grep -v .git | head -1; then
    echo "❌ Mock directories found in production build"
    exit 1
fi

# Check for mock files
if find . -type f \( -name "*mock*" -o -name "*fixture*" -o -name "*sample*" -o -name "*test*" \) \
   -not -path "./node_modules/*" \
   -not -path "./.git/*" \
   -not -path "./docs/*" \
   -not -path "./.github/*" \
   -not -path "./scripts/*" \
   -not -path "./seeds/dev/*" \
   -not -path "./seeds/test/*" | head -1; then
    echo "❌ Mock files found in production build"
    exit 1
fi

# Check file contents for mock patterns
echo "🔍 Scanning file contents for mock patterns..."
if grep -r -i --include="*.py" --include="*.js" --include="*.ts" --include="*.tsx" --include="*.json" \
   --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=seeds \
   "lorem ipsum\|example\.com\|testuser\|fake_\|faker\|example@\|dummy\|Demo User" . | head -1; then
    echo "❌ Mock content found in production build"
    exit 1
fi

# Verify production configuration
echo "🔍 Verifying production configuration..."
if [ ! -f "config/prod.yaml" ]; then
    echo "❌ Production config file not found"
    exit 1
fi

if grep -q "mock_data_allowed: true" config/prod.yaml; then
    echo "❌ mock_data_allowed is true in production config"
    exit 1
fi

if grep -q "debug_mode: true" config/prod.yaml; then
    echo "❌ debug_mode is true in production config"
    exit 1
fi

echo "✅ All safety checks passed"

# Build and push images
echo "🏗️ Building production images..."
SERVICES=(ingest-svc embed-svc retrieval-svc editor-svc reddit-sync-svc gateway-api editor-frontend ideahunter-frontend)

for service in "${SERVICES[@]}"; do
    echo "Building $service..."
    
    # Determine Dockerfile location
    if [ -f "apps/$service/Dockerfile" ]; then
        DOCKERFILE="apps/$service/Dockerfile"
    elif [ -f "services/$service/Dockerfile" ]; then
        DOCKERFILE="services/$service/Dockerfile"
    else
        echo "❌ Dockerfile not found for $service"
        exit 1
    fi
    
    # Build image
    docker build -t "$REGISTRY/$PROJECT_ID/pp-final/$service:$TAG" \
        -f "$DOCKERFILE" . || {
        echo "❌ Failed to build $service"
        exit 1
    }
    
    # Push image
    docker push "$REGISTRY/$PROJECT_ID/pp-final/$service:$TAG" || {
        echo "❌ Failed to push $service"
        exit 1
    }
done

echo "✅ All images built and pushed successfully"

# Deploy with canary strategy
echo "🚀 Deploying to production with canary strategy..."

for service in "${SERVICES[@]}"; do
    echo "Deploying $service to production..."
    
    # Deploy new revision with 0% traffic
    gcloud run deploy "$service" \
        --image="$REGISTRY/$PROJECT_ID/pp-final/$service:$TAG" \
        --region=$REGION \
        --platform=managed \
        --no-traffic \
        --tag=canary \
        --set-env-vars="APP_ENV=prod" \
        --memory=4Gi \
        --cpu=4 \
        --max-instances=100 \
        --quiet || {
        echo "❌ Failed to deploy $service"
        exit 1
    }
    
    echo "Starting canary deployment for $service..."
    
    # Gradual traffic shift
    gcloud run services update-traffic "$service" \
        --to-tags=canary=10 \
        --region=$REGION \
        --quiet || {
        echo "❌ Failed to shift traffic for $service"
        exit 1
    }
    
    echo "⏳ Waiting 30 seconds for health check..."
    sleep 30
    
    # Check health
    SERVICE_URL=$(gcloud run services describe "$service" --region=$REGION --format="value(status.url)")
    if ! curl -f -s "$SERVICE_URL/health" > /dev/null 2>&1 && ! curl -f -s "$SERVICE_URL/healthz" > /dev/null 2>&1; then
        echo "❌ Health check failed for $service, rolling back..."
        gcloud run services update-traffic "$service" \
            --to-tags=canary=0 \
            --region=$REGION \
            --quiet
        exit 1
    fi
    
    # Continue traffic shift
    gcloud run services update-traffic "$service" \
        --to-tags=canary=50 \
        --region=$REGION \
        --quiet
    
    sleep 30
    
    # Final traffic shift
    gcloud run services update-traffic "$service" \
        --to-tags=canary=100 \
        --region=$REGION \
        --quiet
    
    echo "✅ $service deployed successfully"
done

# Final verification
echo "🔍 Final production verification..."

PROD_SERVICES=(
    "https://gateway-api-318093749175.us-central1.run.app/health"
    "https://editor-svc-318093749175.us-central1.run.app/healthz"
    "https://embed-svc-318093749175.us-central1.run.app/healthz"
)

for service_url in "${PROD_SERVICES[@]}"; do
    echo "Testing $service_url..."
    if ! curl -f -s "$service_url" > /dev/null; then
        echo "❌ Production service failed: $service_url"
        exit 1
    fi
done

echo "✅ All production services are healthy"
echo "🎉 Production deployment completed successfully!"
echo ""
echo "🌐 Production URLs:"
echo "  Editor: https://editor-frontend-318093749175.us-central1.run.app"
echo "  Idea Hunter: https://ideahunter-frontend-318093749175.us-central1.run.app"
echo "  Gateway API: https://gateway-api-318093749175.us-central1.run.app"
echo ""
echo "📊 Deployment Summary:"
echo "  Version: $TAG"
echo "  Environment: production"
echo "  Services: ${#SERVICES[@]}"
echo "  Strategy: Canary deployment"
echo "  Status: ✅ SUCCESS"
