#!/bin/bash
set -euo pipefail

# Setup environment-scoped GCP resources for PP Final project
# Usage: ./setup-env-resources.sh <environment>
# Where environment is: dev, test, or prod

ENVIRONMENT=${1:-}
PROJECT_ID="script-improver-system-469119"
REGION="us-central1"

if [[ -z "$ENVIRONMENT" ]]; then
    echo "Usage: $0 <environment>"
    echo "Where environment is: dev, test, or prod"
    exit 1
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|test|prod)$ ]]; then
    echo "Error: Environment must be dev, test, or prod"
    exit 1
fi

echo "Setting up resources for environment: $ENVIRONMENT"

# Set up Cloud SQL instances
echo "Creating Cloud SQL instance for $ENVIRONMENT..."
if ! gcloud sql instances describe "script-improver-system-$ENVIRONMENT" --quiet 2>/dev/null; then
    gcloud sql instances create "script-improver-system-$ENVIRONMENT" \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region=$REGION \
        --storage-type=SSD \
        --storage-size=10GB \
        --backup-start-time=03:00 \
        --enable-bin-log \
        --maintenance-window-day=SUN \
        --maintenance-window-hour=04 \
        --deletion-protection
    
    echo "Waiting for SQL instance to be ready..."
    gcloud sql instances patch "script-improver-system-$ENVIRONMENT" --quiet
fi

# Create database
echo "Creating database..."
gcloud sql databases create "script_improver_system_$ENVIRONMENT" \
    --instance="script-improver-system-$ENVIRONMENT" \
    --quiet || echo "Database may already exist"

# Set up GCS buckets
echo "Creating GCS buckets for $ENVIRONMENT..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION "gs://script-improver-system-$ENVIRONMENT-data" || echo "Data bucket may already exist"
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION "gs://script-improver-system-$ENVIRONMENT-artifacts" || echo "Artifacts bucket may already exist"

# Set bucket policies
gsutil iam ch allUsers:objectViewer "gs://script-improver-system-$ENVIRONMENT-data" || true
gsutil lifecycle set - "gs://script-improver-system-$ENVIRONMENT-data" <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      }
    ]
  }
}
EOF

# Create service accounts
echo "Creating service account for $ENVIRONMENT..."
SERVICE_ACCOUNT="pp-final-$ENVIRONMENT"
gcloud iam service-accounts create $SERVICE_ACCOUNT \
    --display-name="PP Final $ENVIRONMENT Service Account" \
    --description="Service account for PP Final $ENVIRONMENT environment" \
    --quiet || echo "Service account may already exist"

# Grant necessary permissions
echo "Granting permissions to service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client" \
    --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin" \
    --condition="expression=resource.name.startsWith('projects/_/buckets/script-improver-system-$ENVIRONMENT')" \
    --quiet || echo "Conditional IAM binding may not be supported"

# Create environment-specific secrets
echo "Creating environment-specific secrets..."
SECRETS=(
    "google-client-id-$ENVIRONMENT"
    "google-client-secret-$ENVIRONMENT"
    "jwt-secret-$ENVIRONMENT"
    "openai-api-key-$ENVIRONMENT"
    "anthropic-api-key-$ENVIRONMENT"
    "reddit-client-id-$ENVIRONMENT"
    "reddit-client-secret-$ENVIRONMENT"
)

for secret in "${SECRETS[@]}"; do
    if ! gcloud secrets describe "$secret" --quiet 2>/dev/null; then
        echo "PLACEHOLDER_VALUE_FOR_$ENVIRONMENT" | gcloud secrets create "$secret" --data-file=-
        echo "Created secret: $secret (with placeholder value)"
    else
        echo "Secret already exists: $secret"
    fi
done

# Set up Pub/Sub topics (if needed)
echo "Creating Pub/Sub topics for $ENVIRONMENT..."
TOPICS=(
    "script-processing-$ENVIRONMENT"
    "embedding-sync-$ENVIRONMENT"
    "reddit-sync-$ENVIRONMENT"
)

for topic in "${TOPICS[@]}"; do
    gcloud pubsub topics create "$topic" --quiet || echo "Topic may already exist: $topic"
done

# Create Artifact Registry repository (shared across environments but with env-specific tags)
echo "Ensuring Artifact Registry repository exists..."
gcloud artifacts repositories create pp-final \
    --repository-format=docker \
    --location=$REGION \
    --description="PP Final Docker images" \
    --quiet || echo "Repository may already exist"

echo "Environment setup complete for: $ENVIRONMENT"
echo ""
echo "Next steps:"
echo "1. Update secrets with actual values:"
for secret in "${SECRETS[@]}"; do
    echo "   gcloud secrets versions add $secret --data-file=<path-to-secret-file>"
done
echo ""
echo "2. Configure database connection and run migrations"
echo "3. Set up vector store indexes for environment: scripts_$ENVIRONMENT"
echo "4. Deploy services with APP_ENV=$ENVIRONMENT"
