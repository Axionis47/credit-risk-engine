# PP Final Project Makefile
# One-command deployments and environment management

.PHONY: help setup-dev setup-test setup-prod deploy-dev deploy-test deploy-prod clean test lint preflight

# Default target
help:
	@echo "PP Final Project - Environment Management"
	@echo ""
	@echo "Available commands:"
	@echo "  setup-dev     - Set up development environment resources"
	@echo "  setup-test    - Set up test/staging environment resources"
	@echo "  setup-prod    - Set up production environment resources"
	@echo "  deploy-dev    - Deploy to development environment"
	@echo "  deploy-test   - Deploy to test/staging environment"
	@echo "  deploy-prod   - Deploy to production environment"
	@echo "  preflight     - Run preflight checks"
	@echo "  test          - Run test suite"
	@echo "  lint          - Run linting and formatting"
	@echo "  clean         - Clean up build artifacts"
	@echo "  sanitize      - Create sanitized test data from dev data"
	@echo "  snapshot-embeddings - Create embeddings snapshot"
	@echo ""

# Environment setup
setup-dev:
	@echo "🔧 Setting up development environment..."
	@export APP_ENV=dev && ./scripts/setup-env-resources.sh dev
	@echo "✅ Development environment setup complete"

setup-test:
	@echo "🔧 Setting up test/staging environment..."
	@export APP_ENV=test && ./scripts/setup-env-resources.sh test
	@echo "✅ Test/staging environment setup complete"

setup-prod:
	@echo "🔧 Setting up production environment..."
	@export APP_ENV=prod && ./scripts/setup-env-resources.sh prod
	@echo "✅ Production environment setup complete"

# Preflight checks
preflight:
	@echo "🔍 Running preflight checks..."
	@python scripts/preflight_check.py
	@echo "✅ Preflight checks passed"

preflight-prod:
	@echo "🔍 Running production preflight checks..."
	@export APP_ENV=prod && python scripts/preflight_check.py
	@echo "✅ Production preflight checks passed"

# Data management
sanitize:
	@echo "🧹 Creating sanitized test data..."
	@python scripts/sanitize_from_prod.py --input-dir seeds/dev --output-dir seeds/test
	@echo "✅ Sanitized test data created"

snapshot-embeddings:
	@echo "📸 Creating embeddings snapshot..."
	@python scripts/manage-embeddings.py snapshot prod --output snapshots/embeddings-prod-$(shell date +%Y%m%d-%H%M%S).json
	@echo "✅ Embeddings snapshot created"

# Development deployment
deploy-dev: preflight
	@echo "🚀 Deploying to development environment..."
	@export APP_ENV=dev
	@export SHORT_SHA=$(shell git rev-parse --short HEAD)
	@echo "Building and deploying services..."
	@for service in ingest-svc embed-svc retrieval-svc editor-svc reddit-sync-svc gateway-api editor-frontend ideahunter-frontend; do \
		echo "Deploying $$service..."; \
		docker build -t "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:dev-$$SHORT_SHA" \
			-f "./apps/$$service/Dockerfile" . || exit 1; \
		docker push "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:dev-$$SHORT_SHA" || exit 1; \
		gcloud run deploy "$$service-dev" \
			--image="us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:dev-$$SHORT_SHA" \
			--region=us-central1 \
			--platform=managed \
			--allow-unauthenticated \
			--set-env-vars="APP_ENV=dev" \
			--memory=1Gi \
			--cpu=1 \
			--max-instances=10 \
			--quiet || exit 1; \
	done
	@echo "✅ Development deployment complete"
	@echo "🌐 Frontend URLs:"
	@echo "  Editor: https://editor-frontend-dev-318093749175.us-central1.run.app"
	@echo "  Idea Hunter: https://ideahunter-frontend-dev-318093749175.us-central1.run.app"

# Test/staging deployment
deploy-test: preflight sanitize
	@echo "🚀 Deploying to test/staging environment..."
	@export APP_ENV=test
	@export SHORT_SHA=$(shell git rev-parse --short HEAD)
	@echo "Building and deploying services..."
	@for service in ingest-svc embed-svc retrieval-svc editor-svc reddit-sync-svc gateway-api editor-frontend ideahunter-frontend; do \
		echo "Deploying $$service..."; \
		docker build -t "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:test-$$SHORT_SHA" \
			-f "./apps/$$service/Dockerfile" . || exit 1; \
		docker push "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:test-$$SHORT_SHA" || exit 1; \
		gcloud run deploy "$$service-test" \
			--image="us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:test-$$SHORT_SHA" \
			--region=us-central1 \
			--platform=managed \
			--allow-unauthenticated \
			--set-env-vars="APP_ENV=test" \
			--memory=2Gi \
			--cpu=2 \
			--max-instances=20 \
			--quiet || exit 1; \
	done
	@echo "✅ Test/staging deployment complete"
	@echo "🌐 Frontend URLs:"
	@echo "  Editor: https://editor-frontend-test-318093749175.us-central1.run.app"
	@echo "  Idea Hunter: https://ideahunter-frontend-test-318093749175.us-central1.run.app"

# Production deployment (requires tag)
deploy-prod: preflight-prod
	@echo "🚀 Deploying to production environment..."
	@if [ -z "$(shell git describe --exact-match --tags HEAD 2>/dev/null)" ]; then \
		echo "❌ Production deployment requires a git tag"; \
		exit 1; \
	fi
	@export APP_ENV=prod
	@export TAG=$(shell git describe --exact-match --tags HEAD)
	@echo "Deploying tagged version: $$TAG"
	@echo "🔍 Running production safety checks..."
	@# Scan for mock data
	@if find . -type d -name "mocks" -o -name "fixtures" -o -name "sample_data" -o -name "__mocks__" | grep -v node_modules | grep -v .git | head -1; then \
		echo "❌ Mock directories found in production build"; \
		exit 1; \
	fi
	@if find . -type f \( -name "*mock*" -o -name "*fixture*" -o -name "*sample*" \) \
		-not -path "./node_modules/*" -not -path "./.git/*" -not -path "./docs/*" \
		-not -path "./.github/*" -not -path "./scripts/*" -not -path "./seeds/dev/*" \
		-not -path "./seeds/test/*" | head -1; then \
		echo "❌ Mock files found in production build"; \
		exit 1; \
	fi
	@echo "✅ Production safety checks passed"
	@echo "Building and deploying services with canary strategy..."
	@for service in ingest-svc embed-svc retrieval-svc editor-svc reddit-sync-svc gateway-api editor-frontend ideahunter-frontend; do \
		echo "Deploying $$service to production..."; \
		docker build -t "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:$$TAG" \
			-f "./apps/$$service/Dockerfile" . || exit 1; \
		docker push "us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:$$TAG" || exit 1; \
		gcloud run deploy "$$service" \
			--image="us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:$$TAG" \
			--region=us-central1 \
			--platform=managed \
			--no-traffic \
			--tag=canary \
			--set-env-vars="APP_ENV=prod" \
			--memory=4Gi \
			--cpu=4 \
			--max-instances=100 \
			--quiet || exit 1; \
		echo "Starting canary deployment for $$service..."; \
		gcloud run services update-traffic "$$service" --to-tags=canary=10 --region=us-central1 --quiet || exit 1; \
		sleep 30; \
		gcloud run services update-traffic "$$service" --to-tags=canary=50 --region=us-central1 --quiet || exit 1; \
		sleep 30; \
		gcloud run services update-traffic "$$service" --to-tags=canary=100 --region=us-central1 --quiet || exit 1; \
	done
	@echo "✅ Production deployment complete"
	@echo "🌐 Production URLs:"
	@echo "  Editor: https://editor-frontend-318093749175.us-central1.run.app"
	@echo "  Idea Hunter: https://ideahunter-frontend-318093749175.us-central1.run.app"
	@echo "  Gateway API: https://gateway-api-318093749175.us-central1.run.app"

# Testing and quality
test:
	@echo "🧪 Running test suite..."
	@find . -name "test_*.py" -exec python -m pytest {} \; || true
	@find . -name package.json -not -path "*/node_modules/*" -execdir npm test \; || true
	@echo "✅ Test suite complete"

lint:
	@echo "🔍 Running linting and formatting..."
	@echo "Python linting..."
	@flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || true
	@black --check . || true
	@isort --check-only . || true
	@echo "TypeScript/JavaScript linting..."
	@find . -name package.json -not -path "*/node_modules/*" -execdir npm run lint \; || true
	@echo "✅ Linting complete"

# Health checks
health-dev:
	@echo "🏥 Checking development environment health..."
	@curl -f "https://gateway-api-dev-318093749175.us-central1.run.app/health" || echo "❌ Gateway API failed"
	@curl -f "https://editor-svc-dev-318093749175.us-central1.run.app/health" || echo "❌ Editor Service failed"
	@echo "✅ Health check complete"

health-test:
	@echo "🏥 Checking test/staging environment health..."
	@curl -f "https://gateway-api-test-318093749175.us-central1.run.app/health" || echo "❌ Gateway API failed"
	@curl -f "https://editor-svc-test-318093749175.us-central1.run.app/health" || echo "❌ Editor Service failed"
	@echo "✅ Health check complete"

health-prod:
	@echo "🏥 Checking production environment health..."
	@curl -f "https://gateway-api-318093749175.us-central1.run.app/health" || echo "❌ Gateway API failed"
	@curl -f "https://editor-svc-318093749175.us-central1.run.app/health" || echo "❌ Editor Service failed"
	@echo "✅ Health check complete"

# Cleanup
clean:
	@echo "🧹 Cleaning up build artifacts..."
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "node_modules" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".next" -type d -exec rm -rf {} + 2>/dev/null || true
	@docker system prune -f
	@echo "✅ Cleanup complete"

# Rollback (emergency)
rollback-prod:
	@echo "🔄 Rolling back production to previous version..."
	@if [ -z "$(PREVIOUS_TAG)" ]; then \
		echo "❌ PREVIOUS_TAG environment variable required"; \
		echo "Usage: make rollback-prod PREVIOUS_TAG=v1.0.0"; \
		exit 1; \
	fi
	@for service in ingest-svc embed-svc retrieval-svc editor-svc reddit-sync-svc gateway-api editor-frontend ideahunter-frontend; do \
		echo "Rolling back $$service to $(PREVIOUS_TAG)..."; \
		gcloud run deploy "$$service" \
			--image="us-central1-docker.pkg.dev/script-improver-system-469119/pp-final/$$service:$(PREVIOUS_TAG)" \
			--region=us-central1 \
			--quiet || exit 1; \
	done
	@echo "✅ Production rollback complete"
