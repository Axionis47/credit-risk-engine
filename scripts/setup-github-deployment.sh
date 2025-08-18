#!/bin/bash

# Setup GitHub repository and Google Cloud for deployment
# Usage: ./scripts/setup-github-deployment.sh <project-id> <github-repo>

set -e

PROJECT_ID=${1:-"your-gcp-project-id"}
GITHUB_REPO=${2:-"your-username/pp-final"}
REGION="us-central1"

echo "Setting up GitHub deployment for project: ${PROJECT_ID}"
echo "GitHub repository: ${GITHUB_REPO}"

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
  echo "Please authenticate with gcloud first:"
  echo "gcloud auth login"
  exit 1
fi

# Set the project
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  sql-component.googleapis.com \
  redis.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com

# Create Workload Identity Pool
echo "Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create "github-pool" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  || echo "Pool might already exist"

# Create Workload Identity Provider
echo "Creating Workload Identity Provider..."
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  || echo "Provider might already exist"

# Create service account for GitHub Actions
echo "Creating service account for GitHub Actions..."
gcloud iam service-accounts create github-actions \
  --project="${PROJECT_ID}" \
  --display-name="GitHub Actions Service Account" \
  || echo "Service account might already exist"

# Grant necessary permissions to the service account
echo "Granting permissions to service account..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/redis.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/compute.networkAdmin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Allow GitHub Actions to impersonate the service account
echo "Setting up Workload Identity Federation..."
gcloud iam service-accounts add-iam-policy-binding \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}" \
  github-actions@${PROJECT_ID}.iam.gserviceaccount.com

# Create Terraform state bucket
echo "Creating Terraform state bucket..."
BUCKET_NAME="${PROJECT_ID}-terraform-state"
gsutil mb -p ${PROJECT_ID} -l ${REGION} gs://${BUCKET_NAME} || echo "Bucket might already exist"
gsutil versioning set on gs://${BUCKET_NAME}

# Create Artifact Registry repository
echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create pp-final \
  --repository-format=docker \
  --location=${REGION} \
  --project=${PROJECT_ID} \
  || echo "Repository might already exist"

# Output GitHub Secrets
echo ""
echo "🔐 Add these secrets to your GitHub repository:"
echo "Repository: https://github.com/${GITHUB_REPO}/settings/secrets/actions"
echo ""
echo "GCP_PROJECT_ID: ${PROJECT_ID}"
echo "WIF_PROVIDER: projects/$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "WIF_SERVICE_ACCOUNT: github-actions@${PROJECT_ID}.iam.gserviceaccount.com"
echo "TF_STATE_BUCKET: ${BUCKET_NAME}"
echo ""

# Setup secrets in Secret Manager
echo "Setting up secrets in Secret Manager..."
./scripts/setup-secrets.sh ${PROJECT_ID}

echo ""
echo "✅ GitHub deployment setup complete!"
echo ""
echo "Next steps:"
echo "1. Add the GitHub secrets shown above to your repository"
echo "2. Push your code to GitHub"
echo "3. The GitHub Actions will automatically deploy your infrastructure and applications"
echo ""
echo "Manual deployment commands:"
echo "  ./scripts/build-and-push.sh ${PROJECT_ID} ${REGION}"
echo "  cd infra/terraform && terraform init && terraform apply -var='project_id=${PROJECT_ID}'"
