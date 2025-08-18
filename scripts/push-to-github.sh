#!/bin/bash

# Push code to GitHub repository
# Usage: ./scripts/push-to-github.sh <github-repo-url>

set -e

REPO_URL=${1:-""}

if [ -z "$REPO_URL" ]; then
  echo "Usage: ./scripts/push-to-github.sh <github-repo-url>"
  echo "Example: ./scripts/push-to-github.sh https://github.com/username/pp-final.git"
  exit 1
fi

echo "Pushing PP Final code to GitHub repository: ${REPO_URL}"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
  echo "Initializing git repository..."
  git init
  
  # Create .gitignore if it doesn't exist
  if [ ! -f ".gitignore" ]; then
    echo "Creating .gitignore..."
    cat > .gitignore << 'EOF'
# Dependencies
node_modules/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Build outputs
dist/
build/
*.egg-info/
.next/
out/

# Environment files
.env.local
.env.development.local
.env.test.local
.env.production.local

# Terraform
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl
tfplan

# Docker
.dockerignore

# Logs
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Runtime data
pids/
*.pid
*.seed
*.pid.lock

# Coverage directory used by tools like istanbul
coverage/

# nyc test coverage
.nyc_output

# Dependency directories
jspm_packages/

# Optional npm cache directory
.npm

# Optional REPL history
.node_repl_history

# Output of 'npm pack'
*.tgz

# Yarn Integrity file
.yarn-integrity

# parcel-bundler cache (https://parceljs.org/)
.cache
.parcel-cache

# next.js build output
.next

# nuxt.js build output
.nuxt

# vuepress build output
.vuepress/dist

# Serverless directories
.serverless

# FuseBox cache
.fusebox/

# DynamoDB Local files
.dynamodb/
EOF
  fi
else
  echo "Git repository already initialized"
fi

# Add all files
echo "Adding files to git..."
git add .

# Check if there are any changes to commit
if git diff --staged --quiet; then
  echo "No changes to commit"
else
  # Commit changes
  echo "Committing changes..."
  git commit -m "Initial commit: Complete PP Final system

- Microservices architecture with 6 backend services
- Two frontend applications (Script Improver & Idea Hunter)
- AI provider isolation (OpenAI for embeddings, Anthropic for editing)
- PostgreSQL with pgvector for vector search
- Redis for caching and sessions
- Docker Compose for local development
- Terraform for Google Cloud deployment
- GitHub Actions for CI/CD
- Complete documentation and setup scripts"
fi

# Add remote origin if it doesn't exist
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Adding remote origin..."
  git remote add origin ${REPO_URL}
else
  echo "Remote origin already exists, updating URL..."
  git remote set-url origin ${REPO_URL}
fi

# Create main branch if we're on master
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "master" ]; then
  echo "Renaming master branch to main..."
  git branch -M main
fi

# Push to GitHub
echo "Pushing to GitHub..."
git push -u origin main

echo ""
echo "✅ Code successfully pushed to GitHub!"
echo ""
echo "Repository: ${REPO_URL}"
echo "Branch: main"
echo ""
echo "Next steps:"
echo "1. Set up GitHub secrets for deployment (run ./scripts/setup-github-deployment.sh)"
echo "2. The GitHub Actions will automatically deploy when you push to main"
echo ""
echo "View your repository: ${REPO_URL//.git/}"
