#!/bin/bash

# Set up Google Cloud deployment for PP Final
# This script configures everything needed for automated deployment

set -e

echo "☁️  PP Final - Google Cloud Setup"
echo "================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found"
    echo ""
    echo "Please install Google Cloud CLI:"
    echo "1. Go to: https://cloud.google.com/sdk/docs/install"
    echo "2. Download and install for macOS"
    echo "3. Run: gcloud init"
    echo "4. Then run this script again"
    exit 1
fi

# Check if authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "🔐 Please authenticate with Google Cloud:"
    gcloud auth login
fi

echo "📋 Step 1: Project Setup"
echo ""

# Get project ID
read -p "Enter your Google Cloud Project ID: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Project ID is required"
    echo ""
    echo "To create a new project:"
    echo "1. Go to: https://console.cloud.google.com/"
    echo "2. Click 'Select a project' → 'New Project'"
    echo "3. Enter project name and note the Project ID"
    echo "4. Enable billing for the project"
    exit 1
fi

# Set the project
echo "Setting project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Get GitHub repository info
echo ""
echo "📋 Step 2: GitHub Repository Info"
echo ""

REPO_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REPO_URL" ]; then
    read -p "Enter your GitHub repository URL: " REPO_URL
fi

# Extract username/repo from URL
GITHUB_REPO=$(echo $REPO_URL | sed -E 's|https://github.com/([^/]+/[^/]+)(\.git)?/?|\1|' | sed 's/\.git$//')

echo "GitHub Repository: $GITHUB_REPO"
echo "Google Cloud Project: $PROJECT_ID"
echo ""

read -p "Continue with setup? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled"
    exit 1
fi

echo ""
echo "🔧 Step 3: Enabling APIs..."

# Enable required APIs
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  sql-component.googleapis.com \
  redis.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com

echo "✅ APIs enabled"

echo ""
echo "🔐 Step 4: Setting up Workload Identity..."

# Create Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  2>/dev/null || echo "Pool already exists"

# Create Workload Identity Provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  2>/dev/null || echo "Provider already exists"

# Create service account
gcloud iam service-accounts create github-actions \
  --project="$PROJECT_ID" \
  --display-name="GitHub Actions Service Account" \
  2>/dev/null || echo "Service account already exists"

echo "✅ Workload Identity configured"

echo ""
echo "🔑 Step 5: Setting up permissions..."

# Grant permissions
ROLES=(
  "roles/run.admin"
  "roles/cloudsql.admin" 
  "roles/redis.admin"
  "roles/artifactregistry.admin"
  "roles/secretmanager.admin"
  "roles/compute.networkAdmin"
  "roles/iam.serviceAccountUser"
)

for role in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="$role" \
    --quiet
done

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Allow GitHub to impersonate service account
gcloud iam service-accounts add-iam-policy-binding \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$GITHUB_REPO" \
  github-actions@$PROJECT_ID.iam.gserviceaccount.com

echo "✅ Permissions configured"

echo ""
echo "📦 Step 6: Creating infrastructure..."

# Create Terraform state bucket
BUCKET_NAME="$PROJECT_ID-terraform-state"
gsutil mb -p $PROJECT_ID -l us-central1 gs://$BUCKET_NAME 2>/dev/null || echo "Bucket already exists"
gsutil versioning set on gs://$BUCKET_NAME

# Create Artifact Registry
gcloud artifacts repositories create pp-final \
  --repository-format=docker \
  --location=us-central1 \
  --project=$PROJECT_ID \
  2>/dev/null || echo "Repository already exists"

echo "✅ Infrastructure created"

echo ""
echo "🔐 Step 7: Setting up secrets..."

# Function to create or update secret
create_or_update_secret() {
  local secret_name=$1
  local secret_value=$2
  
  if gcloud secrets describe $secret_name --project=$PROJECT_ID >/dev/null 2>&1; then
    echo "Updating secret: $secret_name"
    echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=- --project=$PROJECT_ID
  else
    echo "Creating secret: $secret_name"
    echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=- --project=$PROJECT_ID
  fi
}

# Your API keys from .env
OPENAI_KEY="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"
ANTHROPIC_KEY="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"

create_or_update_secret "OPENAI_API_KEY" "$OPENAI_KEY"
create_or_update_secret "ANTHROPIC_API_KEY" "$ANTHROPIC_KEY"

# Get additional secrets
echo ""
echo "Additional API keys needed:"
echo ""

read -p "Google OAuth Client ID (optional, press Enter to skip): " GOOGLE_CLIENT_ID
if [ ! -z "$GOOGLE_CLIENT_ID" ]; then
  create_or_update_secret "GOOGLE_CLIENT_ID" "$GOOGLE_CLIENT_ID"
fi

read -p "Google OAuth Client Secret (optional, press Enter to skip): " GOOGLE_CLIENT_SECRET
if [ ! -z "$GOOGLE_CLIENT_SECRET" ]; then
  create_or_update_secret "GOOGLE_CLIENT_SECRET" "$GOOGLE_CLIENT_SECRET"
fi

read -p "Reddit Client ID (optional, press Enter to skip): " REDDIT_CLIENT_ID
if [ ! -z "$REDDIT_CLIENT_ID" ]; then
  create_or_update_secret "REDDIT_CLIENT_ID" "$REDDIT_CLIENT_ID"
fi

read -p "Reddit Client Secret (optional, press Enter to skip): " REDDIT_CLIENT_SECRET
if [ ! -z "$REDDIT_CLIENT_SECRET" ]; then
  create_or_update_secret "REDDIT_CLIENT_SECRET" "$REDDIT_CLIENT_SECRET"
fi

echo "✅ Secrets configured"

echo ""
echo "🎯 Step 8: GitHub Secrets"
echo ""
echo "Add these secrets to your GitHub repository:"
echo "Go to: https://github.com/$GITHUB_REPO/settings/secrets/actions"
echo ""
echo "GCP_PROJECT_ID: $PROJECT_ID"
echo "WIF_PROVIDER: projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "WIF_SERVICE_ACCOUNT: github-actions@$PROJECT_ID.iam.gserviceaccount.com"
echo "TF_STATE_BUCKET: $BUCKET_NAME"
echo ""

echo "✅ Setup Complete!"
echo ""
echo "🚀 Next Steps:"
echo "1. Add the GitHub secrets shown above"
echo "2. Push any change to trigger deployment:"
echo "   git commit --allow-empty -m 'Deploy to production'"
echo "   git push origin main"
echo "3. Monitor deployment in GitHub Actions"
echo ""
echo "Your applications will be available at:"
echo "- Script Improver: https://editor-frontend-xxx-uc.a.run.app"
echo "- Idea Hunter: https://ideahunter-frontend-xxx-uc.a.run.app"
