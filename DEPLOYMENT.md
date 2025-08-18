# 🚀 Deployment Guide

This guide will help you deploy the PP Final system to GitHub and Google Cloud Platform.

## Prerequisites

- **Google Cloud Account** with billing enabled
- **GitHub Account** 
- **gcloud CLI** installed and authenticated
- **Docker** installed locally
- **Terraform** installed (optional, handled by GitHub Actions)

## 🔧 Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your **Project ID** (not the project name)
4. Enable billing for the project

## 📁 Step 2: Create GitHub Repository

1. Go to [GitHub](https://github.com) and create a new repository
2. Name it `pp-final` (or your preferred name)
3. Make it **public** or **private** (your choice)
4. **Don't** initialize with README, .gitignore, or license (we have these)
5. Copy the repository URL (e.g., `https://github.com/username/pp-final.git`)

## 🔑 Step 3: Set Up API Keys

You already have the API keys configured in the `.env` file:
- ✅ OpenAI API Key (for embeddings)
- ✅ Anthropic API Key (for script improvement)

Additional keys needed:
- **Google OAuth** (for user authentication)
- **Reddit API** (for content sync)

### Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services > Credentials**
3. Click **Create Credentials > OAuth 2.0 Client IDs**
4. Choose **Web application**
5. Add authorized redirect URIs:
   - `http://localhost:8000/api/oauth/callback` (development)
   - `https://your-domain.com/api/oauth/callback` (production - will be provided after deployment)
6. Save the **Client ID** and **Client Secret**

### Reddit API Setup
1. Go to [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Click **Create App**
3. Choose **script** type
4. Fill in name and description
5. Save the **Client ID** and **Client Secret**

## 🚀 Step 4: Deploy to GitHub and Google Cloud

Run the automated deployment script:

```bash
# Replace with your actual values
./scripts/push-to-github.sh https://github.com/YOUR_USERNAME/pp-final.git
```

This will:
- Initialize git repository
- Add all files
- Commit with descriptive message
- Push to GitHub

## ☁️ Step 5: Set Up Google Cloud Deployment

```bash
# Replace YOUR_PROJECT_ID with your actual GCP project ID
./scripts/setup-github-deployment.sh YOUR_PROJECT_ID YOUR_USERNAME/pp-final
```

This script will:
- Enable required Google Cloud APIs
- Create Workload Identity Federation for GitHub Actions
- Set up service accounts and permissions
- Create Terraform state bucket
- Create Artifact Registry repository
- Set up secrets in Secret Manager

## 🔐 Step 6: Configure GitHub Secrets

The setup script will output GitHub secrets. Add these to your repository:

1. Go to your GitHub repository
2. Navigate to **Settings > Secrets and variables > Actions**
3. Add these repository secrets:

```
GCP_PROJECT_ID: your-gcp-project-id
WIF_PROVIDER: projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT: github-actions@your-project.iam.gserviceaccount.com
TF_STATE_BUCKET: your-project-terraform-state
```

## 🎯 Step 7: Trigger Deployment

Push any change to the `main` branch to trigger deployment:

```bash
git commit --allow-empty -m "Trigger deployment"
git push origin main
```

Or manually trigger the workflow:
1. Go to your GitHub repository
2. Click **Actions** tab
3. Select **CI/CD Pipeline** workflow
4. Click **Run workflow**

## 📊 Step 8: Monitor Deployment

1. **GitHub Actions**: Monitor progress in the Actions tab
2. **Google Cloud Console**: Check Cloud Run services
3. **Logs**: View application logs in Cloud Logging

## 🌐 Step 9: Access Your Applications

After successful deployment, you'll get URLs like:
- **Script Improver**: `https://editor-frontend-xxx-uc.a.run.app`
- **Idea Hunter**: `https://ideahunter-frontend-xxx-uc.a.run.app`
- **API Gateway**: `https://gateway-api-xxx-uc.a.run.app`

## 🔧 Step 10: Update OAuth Redirect URIs

1. Go back to Google Cloud Console > APIs & Services > Credentials
2. Edit your OAuth 2.0 Client ID
3. Add the production redirect URI:
   - `https://gateway-api-xxx-uc.a.run.app/api/oauth/callback`

## 📝 Step 11: Initial Data Setup

### Upload CSV Data
```bash
curl -X POST https://gateway-api-xxx-uc.a.run.app/api/ingest/auto \
  -F "metrics_file=@your-metrics.csv" \
  -F "transcripts_file=@your-transcripts.csv"
```

### Sync Reddit Ideas
```bash
curl -X POST https://gateway-api-xxx-uc.a.run.app/api/ideas/sync \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 🔍 Troubleshooting

### Common Issues

**GitHub Actions Failing**
- Check that all secrets are correctly set
- Verify GCP project ID is correct
- Ensure billing is enabled on GCP project

**Database Connection Issues**
- Check that Cloud SQL instance is running
- Verify VPC connector is properly configured
- Check service account permissions

**Authentication Issues**
- Verify OAuth redirect URIs are correct
- Check that Google OAuth is properly configured
- Ensure JWT secret is set

**API Key Issues**
- Verify secrets are properly stored in Secret Manager
- Check that service accounts have access to secrets
- Ensure API keys are valid and have sufficient quota

### Viewing Logs

```bash
# View service logs
gcloud logs read "resource.type=cloud_run_revision" --project=YOUR_PROJECT_ID --limit=50

# View specific service logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=gateway-api" --project=YOUR_PROJECT_ID
```

### Manual Deployment

If GitHub Actions fail, you can deploy manually:

```bash
# Build and push images
./scripts/build-and-push.sh YOUR_PROJECT_ID us-central1

# Deploy infrastructure
cd infra/terraform
terraform init -backend-config="bucket=YOUR_PROJECT_ID-terraform-state"
terraform apply -var="project_id=YOUR_PROJECT_ID"

# Run migrations
./scripts/migrate-db.sh YOUR_PROJECT_ID us-central1
```

## 🎉 Success!

Your PP Final system is now deployed and ready to use! 

- **Script Improver**: AI-powered script editing with reference matching
- **Idea Hunter**: Tinder-style content idea discovery
- **Microservices**: Scalable, maintainable architecture
- **AI Provider Isolation**: OpenAI for embeddings, Anthropic for editing
- **Production Ready**: Monitoring, logging, security, and scalability

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review GitHub Actions logs
3. Check Google Cloud Console for service status
4. Review application logs in Cloud Logging
