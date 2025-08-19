# Environment Configuration

## Overview
This document describes the environment separation strategy for the PP Final project, including resource mapping, configuration, and access controls.

## Environment Definitions

### Development (dev)
- **Purpose**: Active development and feature testing
- **Data**: Mock/sample data allowed
- **Access**: All developers
- **Stability**: Unstable, frequent deployments

### Test/Staging (test)
- **Purpose**: Pre-production testing and validation
- **Data**: Sanitized production data
- **Access**: QA team, senior developers
- **Stability**: Stable, controlled deployments

### Production (prod)
- **Purpose**: Live user-facing environment
- **Data**: Real production data only
- **Access**: DevOps team, emergency access only
- **Stability**: Highly stable, change-controlled deployments

## Resource Mapping

### Cloud Run Services

| Service | Development | Test/Staging | Production |
|---------|-------------|--------------|------------|
| Gateway API | `gateway-api-dev` | `gateway-api-test` | `gateway-api` |
| Editor Service | `editor-svc-dev` | `editor-svc-test` | `editor-svc` |
| Embed Service | `embed-svc-dev` | `embed-svc-test` | `embed-svc` |
| Retrieval Service | `retrieval-svc-dev` | `retrieval-svc-test` | `retrieval-svc` |
| Ingest Service | `ingest-svc-dev` | `ingest-svc-test` | `ingest-svc` |
| Reddit Sync | `reddit-sync-svc-dev` | `reddit-sync-svc-test` | `reddit-sync-svc` |
| Editor Frontend | `editor-frontend-dev` | `editor-frontend-test` | `editor-frontend` |
| Idea Hunter Frontend | `ideahunter-frontend-dev` | `ideahunter-frontend-test` | `ideahunter-frontend` |

### Databases

| Environment | Instance Name | Database Name | Connection String |
|-------------|---------------|---------------|-------------------|
| Development | `script-improver-system-dev` | `script_improver_system_dev` | `postgresql://user:pass@script-improver-system-dev/script_improver_system_dev` |
| Test/Staging | `script-improver-system-test` | `script_improver_system_test` | `postgresql://user:pass@script-improver-system-test/script_improver_system_test` |
| Production | `script-improver-system-prod` | `script_improver_system_prod` | `postgresql://user:pass@script-improver-system-prod/script_improver_system_prod` |

### Vector Indexes

| Environment | Index Name | Namespace | Purpose |
|-------------|------------|-----------|---------|
| Development | `scripts_dev` | `dev` | Development embeddings |
| Test/Staging | `scripts_test` | `test` | Sanitized test embeddings |
| Production | `scripts_prod` | `prod` | Production embeddings |

### Storage Buckets

| Environment | Data Bucket | Artifacts Bucket |
|-------------|-------------|------------------|
| Development | `gs://script-improver-system-dev-data` | `gs://script-improver-system-dev-artifacts` |
| Test/Staging | `gs://script-improver-system-test-data` | `gs://script-improver-system-test-artifacts` |
| Production | `gs://script-improver-system-prod-data` | `gs://script-improver-system-prod-artifacts` |

### Secrets (Google Secret Manager)

| Secret Type | Development | Test/Staging | Production |
|-------------|-------------|--------------|------------|
| Google OAuth Client ID | `google-client-id-dev` | `google-client-id-test` | `google-client-id` |
| Google OAuth Client Secret | `google-client-secret-dev` | `google-client-secret-test` | `google-client-secret` |
| JWT Secret | `jwt-secret-dev` | `jwt-secret-test` | `jwt-secret` |
| OpenAI API Key | `openai-api-key-dev` | `openai-api-key-test` | `openai-api-key` |
| Anthropic API Key | `anthropic-api-key-dev` | `anthropic-api-key-test` | `anthropic-api-key` |
| Reddit Client ID | `reddit-client-id-dev` | `reddit-client-id-test` | `reddit-client-id` |
| Reddit Client Secret | `reddit-client-secret-dev` | `reddit-client-secret-test` | `reddit-client-secret` |

### Service Accounts

| Environment | Service Account | Permissions |
|-------------|-----------------|-------------|
| Development | `pp-final-dev@script-improver-system-469119.iam.gserviceaccount.com` | Cloud SQL Client, Storage Object Admin (dev buckets only) |
| Test/Staging | `pp-final-test@script-improver-system-469119.iam.gserviceaccount.com` | Cloud SQL Client, Storage Object Admin (test buckets only) |
| Production | `pp-final-prod@script-improver-system-469119.iam.gserviceaccount.com` | Cloud SQL Client, Storage Object Admin (prod buckets only) |

## Environment Variables

### Required for All Environments
- `APP_ENV`: Must be `dev`, `test`, or `prod`
- `GCP_PROJECT_ID`: `script-improver-system-469119`
- `GCP_REGION`: `us-central1`

### Environment-Specific Configuration
Configuration is loaded from:
- `config/defaults.yaml` (base configuration)
- `config/{APP_ENV}.yaml` (environment overrides)

## Access Controls

### Development Environment
- **Who**: All developers
- **Access Method**: Direct deployment via CI/CD on PR
- **Data Access**: Mock data, development secrets
- **Restrictions**: None

### Test/Staging Environment
- **Who**: QA team, senior developers, DevOps
- **Access Method**: Automatic deployment on merge to `develop`
- **Data Access**: Sanitized production data, test secrets
- **Restrictions**: No direct database access

### Production Environment
- **Who**: DevOps team only
- **Access Method**: Tagged releases with approval
- **Data Access**: Production data, production secrets
- **Restrictions**: All changes require approval, audit logging

## Network Security

### Firewall Rules
- Development: Open to all developers
- Test/Staging: Restricted to company IP ranges
- Production: Restricted to CDN and monitoring systems

### VPC Configuration
- Each environment runs in isolated VPC networks
- No cross-environment network access
- Private Google Access enabled for all environments

## Monitoring and Alerting

### Development
- Basic health checks
- Error logging to console
- No alerting

### Test/Staging
- Comprehensive monitoring
- Error tracking and reporting
- Performance monitoring
- No critical alerts

### Production
- Full monitoring suite
- Real-time alerting
- SLA monitoring
- Incident response integration

## Compliance and Auditing

### Data Handling
- Development: No real user data
- Test/Staging: Sanitized data only
- Production: Full data protection compliance

### Audit Logging
- All production changes logged
- Access to production resources audited
- Deployment history maintained

### Backup and Recovery
- Development: No backups required
- Test/Staging: Daily backups, 7-day retention
- Production: Continuous backups, 30-day retention, point-in-time recovery
