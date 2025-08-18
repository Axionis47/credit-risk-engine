# PP Final - AI-Powered Content Creation Platform

A comprehensive microservices platform featuring two AI-powered applications:
- **Script Improver**: AI-enhanced script editing with reference matching
- **Idea Hunter**: Tinder-style content idea discovery from Reddit

## 🏗️ Architecture

### Microservices Backend
- **Gateway API** (Port 8000): Main API gateway with authentication
- **Embed Service** (Port 8001): OpenAI text-embedding-3-large integration
- **Retrieval Service** (Port 8002): Vector similarity search with performance reranking
- **Editor Service** (Port 8003): Anthropic Claude Sonnet script improvement
- **Reddit Sync Service** (Port 8004): Reddit API integration with deduplication
- **Ingest Service** (Port 8005): CSV analysis and data ingestion

### Frontend Applications
- **Script Improver** (Port 3000): Professional script editing interface
- **Idea Hunter** (Port 3001): Swipeable content idea discovery

### Infrastructure
- **PostgreSQL** with pgvector extension for embeddings
- **Redis** for caching and session management
- **Google Cloud Run** for production deployment
- **Terraform** for infrastructure as code

## 🚀 Quick Start (Local Development)

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.12+ (for backend development)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd PP_Final
# The .env file is already configured with your API keys
```

### 2. Start Development Environment
```bash
./scripts/dev-setup.sh
```

This script will:
- Start PostgreSQL and Redis containers
- Run database migrations
- Install frontend dependencies
- Start all microservices

### 3. Access Applications
- **Script Improver**: http://localhost:3000
- **Idea Hunter**: http://localhost:3001
- **API Gateway**: http://localhost:8000

## 🔧 Configuration

Your API keys are already configured in the .env file:
- **OpenAI API Key**: For text embeddings (embed-svc only)
- **Anthropic API Key**: For script improvement (editor-svc only)

Additional setup needed:
- **Google OAuth**: For user authentication
- **Reddit API**: For content idea sync

## 🧠 AI Provider Isolation

The system enforces strict AI provider isolation:
- **OpenAI**: Only used in embed-svc for text-embedding-3-large
- **Anthropic**: Only used in editor-svc for Claude Sonnet script improvement

This ensures:
- Clear cost attribution
- Provider-specific optimizations
- Reduced vendor lock-in
- Better error isolation
- **Site B - Idea Hunter**: Tinder-style interface for discovering Reddit ideas
- **Shared Backend**: FastAPI gateway with microservices for embedding, retrieval, editing, and Reddit sync
- **Database**: PostgreSQL with pgvector for embeddings
- **Cache**: Redis for performance
- **Deployment**: Google Cloud Run with Terraform IaC

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.12+
- Docker & Docker Compose
- Google Cloud CLI (for deployment)
- Terraform (for infrastructure)

### Local Development

1. **Clone and setup**:
   ```bash
   git clone <repo-url>
   cd PP_Final
   npm install
   ```

2. **Environment setup**:
   ```bash
   cp dev/env.example .env
   # Edit .env with your API keys
   ```

3. **Start local development**:
   ```bash
   npm run dev
   ```

   This starts:
   - Editor Frontend: http://localhost:3000
   - Idea Hunter Frontend: http://localhost:3001
   - Gateway API: http://localhost:8000
   - PostgreSQL with pgvector
   - Redis
   - All microservices

### CSV Data Processing

1. Place your CSV files in `dev/csv/`:
   - `video_metrics.csv` - Performance metrics
   - `video_transcripts.csv` - Video transcripts

2. Auto-analyze and ingest:
   ```bash
   curl -X POST http://localhost:8000/api/ingest/auto \
     -F "metrics=@dev/csv/video_metrics.csv" \
     -F "transcripts=@dev/csv/video_transcripts.csv"
   ```

## Deployment to Google Cloud

### 1. Setup GCP Project

```bash
# Create project
gcloud projects create your-project-id
gcloud config set project your-project-id

# Enable APIs
gcloud services enable run.googleapis.com
gcloud services enable sql-component.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 2. Setup Workload Identity Federation

```bash
# Create workload identity pool
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --description="GitHub Actions pool"

# Create provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --workload-identity-pool="github-pool" \
  --location="global" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"

# Create service account
gcloud iam service-accounts create "github-actions" \
  --description="Service account for GitHub Actions"

# Bind service account
gcloud iam service-accounts add-iam-policy-binding \
  "github-actions@your-project-id.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/your-username/your-repo"
```

### 3. Set GitHub Secrets

In your GitHub repository settings, add these secrets:

```
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
GCP_WORKLOAD_IDENTITY_PROVIDER=projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider
GCP_SERVICE_ACCOUNT_EMAIL=github-actions@your-project-id.iam.gserviceaccount.com
```

### 4. Deploy Infrastructure

```bash
cd infra/terraform
terraform init
terraform plan -var="project_id=your-project-id" -var="region=us-central1"
terraform apply -var="project_id=your-project-id" -var="region=us-central1"
```

### 5. Set API Keys in Secret Manager

```bash
# OpenAI API Key (for embeddings only)
echo -n "your-openai-key" | gcloud secrets create OPENAI_API_KEY --data-file=-

# Anthropic API Key (for rewriting only)
echo -n "your-anthropic-key" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-

# Google OAuth
echo -n "your-google-client-id" | gcloud secrets create GOOGLE_CLIENT_ID --data-file=-
echo -n "your-google-client-secret" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=-

# Reddit API
echo -n "your-reddit-client-id" | gcloud secrets create REDDIT_CLIENT_ID --data-file=-
echo -n "your-reddit-client-secret" | gcloud secrets create REDDIT_CLIENT_SECRET --data-file=-

# JWT Secret
openssl rand -base64 32 | gcloud secrets create JWT_SECRET --data-file=-
```

### 6. Deploy Application

Push to main branch to trigger GitHub Actions deployment:

```bash
git add .
git commit -m "Deploy to production"
git push origin main
```

## API Endpoints

### Public
- `GET /healthz` - Health check
- `GET /whoami` - User info (authenticated)

### Admin
- `POST /api/ingest/auto` - Auto-analyze and ingest CSVs
- `POST /api/ideas/sync` - Sync ideas from Reddit

### Script Improver
- `POST /api/retrieve` - Find reference script
- `POST /api/improve` - Improve script with AI

### Idea Hunter
- `GET /api/ideas/deck` - Get idea cards
- `POST /api/ideas/feedback` - Save feedback
- `GET /api/ideas/accepted` - Get saved ideas

## Data Processing Rules

### CSV Analysis
- Auto-detects metrics vs transcripts by headers
- Supports CLI override for ambiguous cases
- Processes only video_ids present in both CSVs

### Timestamp Cleaning
- Strips `[mm:ss]`, `[hh:mm:ss]` from line starts
- Removes ranges like `00:00–00:30`
- Handles compact formats `1h02m`, `2m15s`, `90s`
- Preserves ordinary numeric text

### Embedding Policy
- One 3072-D vector per script using OpenAI text-embedding-3-large
- Namespace: `v1/openai/te3l-3072`
- Dataset-relative 14-day age rule
- Only scripts ≤180s eligible as references

### Coherence Gate
- Title↔Body coherence must be ≥0.85
- Single tuner pass if initial coherence fails
- Length ~900 words is advisory, not blocking

## Security

- **Provider Isolation**: OpenAI keys only in embed-svc, Anthropic only in editor-svc
- **Google OAuth**: JWT verification on all protected routes
- **Secret Management**: All keys in GCP Secret Manager
- **IAM**: Least privilege access per service
- **CI Guards**: Fail if wrong provider imported in wrong service

## Monitoring

All services expose `/healthz` endpoints for monitoring. Cloud Run health checks ensure service availability.

## Support

For issues or questions, check the logs in Google Cloud Console or run locally for debugging.
