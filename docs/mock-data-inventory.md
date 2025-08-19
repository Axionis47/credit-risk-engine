# Mock Data Inventory

## Overview
This document catalogs all mock, fixture, sample, and test data in the PP Final project to ensure proper environment separation and prevent mock data from reaching production.

## Mock Data Locations

| Path | Type | Purpose | Consumer(s) | Can Sanitize? | Risk Level |
|------|------|---------|-------------|---------------|------------|
| `sample_data/sample_transcripts.csv` | Sample Data | Development/testing video transcripts | Ingest Service | Y | HIGH |
| `sample_data/sample_metrics.csv` | Sample Data | Development/testing performance metrics | Ingest Service | Y | HIGH |
| `test_service.py` | Test Script | Service testing utilities | Manual testing | Y | LOW |
| `cloudbuild-test.yaml` | CI Config | Test build configuration | CI/CD Pipeline | Y | LOW |
| `apps/editor-frontend/src/app/page.tsx` | Mock Auth | Demo user bypass authentication | Frontend | Y | CRITICAL |
| `apps/ideahunter-frontend/src/app/page.tsx` | Mock Auth | Demo user bypass authentication | Frontend | Y | CRITICAL |

## Mock Data Patterns Detected

### High-Risk Patterns (MUST be removed from PROD)
- `demo@example.com` - Mock email addresses in frontend authentication
- `mock-google-token` - Fake OAuth tokens
- `Demo User` - Hardcoded test user names
- Sample CSV files with realistic but fabricated content

### Code Patterns That Toggle Mock Mode
- Frontend authentication bypass logic in `page.tsx` files
- Conditional mock user creation based on auth failures
- Direct service calls bypassing authentication

## Environment-Specific Data Sources

### DEV Environment
- **Database**: `script-improver-system-dev`
- **Vector Index**: `scripts_dev`
- **GCS Bucket**: `gs://script-improver-system-dev-data`
- **Sample Data**: `/seeds/dev/` (allowed)

### TEST Environment  
- **Database**: `script-improver-system-test`
- **Vector Index**: `scripts_test`
- **GCS Bucket**: `gs://script-improver-system-test-data`
- **Sample Data**: `/seeds/test/` (sanitized from prod)

### PROD Environment
- **Database**: `script-improver-system-prod`
- **Vector Index**: `scripts_prod`
- **GCS Bucket**: `gs://script-improver-system-prod-data`
- **Sample Data**: NONE (fail-closed if detected)

## Remediation Plan

### Immediate Actions (Critical)
1. Move `sample_data/` to `seeds/dev/`
2. Remove hardcoded mock authentication from frontends
3. Add runtime guards to detect mock patterns in PROD
4. Create environment-scoped database resources

### CI/CD Guards
1. Scan built artifacts for mock signatures before PROD deployment
2. Fail deployment if any mock patterns detected in PROD builds
3. Verify environment-specific resource targeting

### Mock Signature Regex Patterns
```regex
/(^|[\\/])(mocks?|fixtures?|samples?|devdata|seeds)([\\/]|$)/i
/lorem ipsum/i
/example\.com/i
/example@/i
/testuser/i
/^fake_/i
/^dummy_/i
/seed_/i
/demo@example\.com/i
/mock-.*-token/i
/Demo User/i
```

## Verification Checklist
- [ ] No mock data in production Docker images
- [ ] Environment variables properly scoped
- [ ] Database connections environment-specific
- [ ] Vector indexes isolated per environment
- [ ] CI/CD gates prevent mock data deployment
- [ ] Runtime preflight checks implemented
- [ ] Production embeddings snapshotted and protected

## Emergency Procedures
If mock data is detected in production:
1. Immediately stop affected services
2. Rollback to last known good deployment
3. Investigate how mock data bypassed guards
4. Strengthen detection patterns
5. Re-deploy with verified clean artifacts

## Maintenance
- Review this inventory monthly
- Update regex patterns as new mock data is added
- Verify environment isolation quarterly
- Test fail-closed mechanisms regularly
