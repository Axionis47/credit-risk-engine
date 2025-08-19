# Operations Runbook

## Overview
This runbook provides step-by-step procedures for deploying, managing, and troubleshooting the PP Final application across all environments.

## Prerequisites
- Google Cloud SDK installed and authenticated
- Docker installed
- Access to the appropriate environment (see `docs/envs.md`)
- Required environment variables set

## Deployment Procedures

### One-Command Deployments

#### Development Environment
```bash
make deploy-dev
```
Or manually:
```bash
export APP_ENV=dev
./scripts/setup-env-resources.sh dev
gcloud builds submit --config .github/workflows/deploy-dev.yml
```

#### Test/Staging Environment
```bash
make deploy-test
```
Or manually:
```bash
export APP_ENV=test
./scripts/setup-env-resources.sh test
python scripts/sanitize_from_prod.py --input-dir seeds/dev --output-dir seeds/test
gcloud builds submit --config .github/workflows/deploy-test.yml
```

#### Production Environment
```bash
make deploy-prod
```
Or manually:
```bash
export APP_ENV=prod
# Ensure you're on a tagged release
git tag v1.0.0
git push origin v1.0.0
# This triggers the production deployment pipeline
```

### Manual Deployment Steps

#### 1. Pre-deployment Checks
```bash
# Verify environment
echo $APP_ENV

# Run preflight checks
python scripts/preflight_check.py

# For production: verify no mock data
if [ "$APP_ENV" = "prod" ]; then
    echo "Scanning for mock data..."
    find . -name "*mock*" -o -name "*fixture*" -o -name "*sample*" | grep -v node_modules | grep -v .git
fi
```

#### 2. Build Images
```bash
# Build all service images
SERVICES=(ingest-svc embed-svc retrieval-svc editor-svc reddit-sync-svc gateway-api editor-frontend ideahunter-frontend)

for service in "${SERVICES[@]}"; do
    docker build -t "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$service:$APP_ENV-$(git rev-parse --short HEAD)" \
        -f "./apps/$service/Dockerfile" .
    docker push "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$service:$APP_ENV-$(git rev-parse --short HEAD)"
done
```

#### 3. Deploy Services
```bash
# Deploy to Cloud Run
for service in "${SERVICES[@]}"; do
    gcloud run deploy "$service-$APP_ENV" \
        --image="us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$service:$APP_ENV-$(git rev-parse --short HEAD)" \
        --region=us-central1 \
        --platform=managed \
        --set-env-vars="APP_ENV=$APP_ENV" \
        --quiet
done
```

## Database Management

### Running Migrations
```bash
# Connect to the appropriate database
export DB_HOST="script-improver-system-$APP_ENV"
export DB_NAME="script_improver_system_$APP_ENV"

# Run migrations (example with Alembic)
alembic upgrade head
```

### Creating Database Backups
```bash
# Development (not typically needed)
gcloud sql export sql script-improver-system-dev gs://script-improver-system-dev-data/backups/backup-$(date +%Y%m%d-%H%M%S).sql

# Test/Staging
gcloud sql export sql script-improver-system-test gs://script-improver-system-test-data/backups/backup-$(date +%Y%m%d-%H%M%S).sql

# Production
gcloud sql export sql script-improver-system-prod gs://script-improver-system-prod-data/backups/backup-$(date +%Y%m%d-%H%M%S).sql
```

### Restoring from Backup
```bash
# Stop services first
gcloud run services update gateway-api-$APP_ENV --no-traffic --region=us-central1

# Restore database
gcloud sql import sql script-improver-system-$APP_ENV gs://script-improver-system-$APP_ENV-data/backups/backup-YYYYMMDD-HHMMSS.sql

# Restart services
gcloud run services update gateway-api-$APP_ENV --traffic=100 --region=us-central1
```

## Vector Embeddings Management

### Snapshot Current Embeddings
```bash
# Create snapshot
python scripts/manage-embeddings.py snapshot $APP_ENV --output snapshots/embeddings-$APP_ENV-$(date +%Y%m%d-%H%M%S).json
```

### Create Environment-Scoped Indexes
```bash
# Create new environment index
python scripts/manage-embeddings.py create-index $APP_ENV

# Verify isolation
python scripts/manage-embeddings.py verify $APP_ENV
```

### Restore from Snapshot
```bash
# Restore embeddings (be careful with production!)
python scripts/manage-embeddings.py restore $APP_ENV snapshots/embeddings-prod-20240101-120000.json --sanitize
```

## Secret Management

### Rotating Secrets
```bash
# Generate new secret value
NEW_SECRET=$(openssl rand -base64 32)

# Update secret
echo "$NEW_SECRET" | gcloud secrets versions add jwt-secret-$APP_ENV --data-file=-

# Restart services to pick up new secret
gcloud run services update gateway-api-$APP_ENV --region=us-central1
```

### Viewing Secrets (Emergency Only)
```bash
# View secret (requires appropriate permissions)
gcloud secrets versions access latest --secret="jwt-secret-$APP_ENV"
```

## Monitoring and Troubleshooting

### Health Checks
```bash
# Check service health
curl -f "https://gateway-api-$APP_ENV-318093749175.us-central1.run.app/health"

# Check all services
SERVICES=(gateway-api editor-svc embed-svc retrieval-svc ingest-svc reddit-sync-svc)
for service in "${SERVICES[@]}"; do
    echo "Checking $service..."
    curl -f "https://$service-$APP_ENV-318093749175.us-central1.run.app/health" || echo "FAILED"
done
```

### Viewing Logs
```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gateway-api-$APP_ENV" --limit=50 --format=json

# Follow logs in real-time
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=gateway-api-$APP_ENV"
```

### Performance Monitoring
```bash
# Check resource usage
gcloud run services describe gateway-api-$APP_ENV --region=us-central1 --format="value(status.traffic[0].percent,spec.template.spec.containers[0].resources.limits)"

# View metrics in Cloud Console
echo "https://console.cloud.google.com/run/detail/us-central1/gateway-api-$APP_ENV/metrics"
```

## Rollback Procedures

### Quick Rollback
```bash
# Get previous revision
PREVIOUS_REVISION=$(gcloud run revisions list --service=gateway-api-$APP_ENV --region=us-central1 --limit=2 --format="value(metadata.name)" | tail -1)

# Rollback to previous revision
gcloud run services update-traffic gateway-api-$APP_ENV --to-revisions=$PREVIOUS_REVISION=100 --region=us-central1
```

### Full Environment Rollback
```bash
# Rollback all services to previous tag
PREVIOUS_TAG="v1.0.0"  # Replace with actual previous tag

for service in "${SERVICES[@]}"; do
    gcloud run deploy "$service-$APP_ENV" \
        --image="us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$service:$PREVIOUS_TAG" \
        --region=us-central1 \
        --quiet
done
```

## Emergency Procedures

### Service Down
1. Check service health endpoints
2. View recent logs for errors
3. Check resource limits and scaling
4. If needed, rollback to previous version
5. Escalate to on-call engineer

### Database Issues
1. Check database connectivity
2. Verify connection pool settings
3. Check for long-running queries
4. If needed, restart database connections
5. Consider read replica for read operations

### Mock Data in Production (CRITICAL)
1. **IMMEDIATELY** stop all affected services
2. Identify source of mock data
3. Remove mock data from production
4. Verify data integrity
5. Restart services with clean data
6. Investigate how mock data bypassed guards
7. Strengthen detection mechanisms

## Maintenance Windows

### Scheduled Maintenance
- Development: No maintenance window required
- Test/Staging: Sundays 2-4 AM UTC
- Production: Sundays 4-6 AM UTC (low traffic period)

### Emergency Maintenance
- Can be performed any time for critical security issues
- Requires approval from engineering manager for production
- Must follow incident response procedures

## Contact Information

### On-Call Rotation
- Primary: DevOps Engineer
- Secondary: Senior Backend Engineer
- Escalation: Engineering Manager

### Emergency Contacts
- Production Issues: [Slack #production-alerts]
- Security Issues: [Slack #security-incidents]
- Infrastructure Issues: [Slack #infrastructure]
