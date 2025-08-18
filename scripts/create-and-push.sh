#!/bin/bash

# Create GitHub repository and push code
# This script will guide you through the process

set -e

echo "🚀 PP Final - GitHub Repository Setup"
echo "====================================="
echo ""

# Check if git is configured
if ! git config user.name >/dev/null 2>&1; then
    echo "⚠️  Git user.name not configured. Please run:"
    echo "   git config --global user.name 'Your Name'"
    echo "   git config --global user.email 'your.email@example.com'"
    echo ""
    read -p "Press Enter after configuring git..."
fi

echo "📝 Step 1: Create GitHub Repository"
echo ""
echo "Please go to: https://github.com/new"
echo ""
echo "Repository settings:"
echo "  - Repository name: pp-final"
echo "  - Description: AI-Powered Content Creation Platform"
echo "  - Visibility: ✅ Private"
echo "  - ❌ Do NOT initialize with README, .gitignore, or license"
echo ""
echo "After creating the repository, GitHub will show you the repository URL."
echo "It will look like: https://github.com/YOUR_USERNAME/pp-final.git"
echo ""

read -p "Enter your GitHub repository URL: " REPO_URL

if [ -z "$REPO_URL" ]; then
    echo "❌ Repository URL is required"
    exit 1
fi

echo ""
echo "📦 Step 2: Pushing code to GitHub..."
echo "Repository: $REPO_URL"
echo ""

# Add remote origin
if git remote get-url origin >/dev/null 2>&1; then
    echo "Updating remote origin..."
    git remote set-url origin "$REPO_URL"
else
    echo "Adding remote origin..."
    git remote add origin "$REPO_URL"
fi

# Ensure we're on main branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "Creating main branch..."
    git checkout -b main 2>/dev/null || git checkout main
fi

# Push to GitHub
echo "Pushing to GitHub..."
if git push -u origin main; then
    echo ""
    echo "✅ Code successfully pushed to GitHub!"
    echo ""
    echo "🔗 Repository: ${REPO_URL//.git/}"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Set up Google Cloud project"
    echo "2. Configure deployment secrets"
    echo "3. Deploy to production"
    echo ""
    echo "Run the next script:"
    echo "  ./scripts/setup-cloud-deployment.sh"
    echo ""
else
    echo ""
    echo "❌ Failed to push to GitHub"
    echo ""
    echo "Common solutions:"
    echo "1. Make sure you have access to the repository"
    echo "2. Check if you need to authenticate with GitHub:"
    echo "   - Generate a Personal Access Token at: https://github.com/settings/tokens"
    echo "   - Use it as your password when prompted"
    echo "3. Or use SSH instead of HTTPS"
    echo ""
    exit 1
fi
