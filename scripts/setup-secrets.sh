#!/bin/bash

# Set up secrets in Google Secret Manager
# Usage: ./scripts/setup-secrets.sh <project-id>

set -e

PROJECT_ID=${1:-"your-gcp-project-id"}

echo "Setting up secrets in Google Secret Manager for project: ${PROJECT_ID}"

# Check if secrets already exist and create them if they don't
create_secret_if_not_exists() {
  local secret_name=$1
  local secret_value=$2
  
  if gcloud secrets describe ${secret_name} --project=${PROJECT_ID} >/dev/null 2>&1; then
    echo "Secret ${secret_name} already exists, updating..."
    echo -n "${secret_value}" | gcloud secrets versions add ${secret_name} --data-file=- --project=${PROJECT_ID}
  else
    echo "Creating secret ${secret_name}..."
    echo -n "${secret_value}" | gcloud secrets create ${secret_name} --data-file=- --project=${PROJECT_ID}
  fi
}

# Read API keys from environment or prompt user
if [ -z "$OPENAI_API_KEY" ]; then
  echo "Enter your OpenAI API key:"
  read -s OPENAI_API_KEY
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "Enter your Anthropic API key:"
  read -s ANTHROPIC_API_KEY
fi

if [ -z "$REDDIT_CLIENT_ID" ]; then
  echo "Enter your Reddit Client ID:"
  read REDDIT_CLIENT_ID
fi

if [ -z "$REDDIT_CLIENT_SECRET" ]; then
  echo "Enter your Reddit Client Secret:"
  read -s REDDIT_CLIENT_SECRET
fi

if [ -z "$GOOGLE_CLIENT_ID" ]; then
  echo "Enter your Google OAuth Client ID:"
  read GOOGLE_CLIENT_ID
fi

if [ -z "$GOOGLE_CLIENT_SECRET" ]; then
  echo "Enter your Google OAuth Client Secret:"
  read -s GOOGLE_CLIENT_SECRET
fi

# Create secrets
create_secret_if_not_exists "OPENAI_API_KEY" "${OPENAI_API_KEY}"
create_secret_if_not_exists "ANTHROPIC_API_KEY" "${ANTHROPIC_API_KEY}"
create_secret_if_not_exists "REDDIT_CLIENT_ID" "${REDDIT_CLIENT_ID}"
create_secret_if_not_exists "REDDIT_CLIENT_SECRET" "${REDDIT_CLIENT_SECRET}"
create_secret_if_not_exists "GOOGLE_CLIENT_ID" "${GOOGLE_CLIENT_ID}"
create_secret_if_not_exists "GOOGLE_CLIENT_SECRET" "${GOOGLE_CLIENT_SECRET}"

echo "All secrets have been set up successfully!"
echo ""
echo "Note: JWT secret and database password will be generated automatically by Terraform."
