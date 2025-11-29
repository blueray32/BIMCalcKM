# BIMCalc Deployment Validation Checklist

**Purpose:** Pre-deployment validation checklist to ensure BIMCalc is production-ready.

**Instructions:** Check each item before deploying to staging or production. Mark items as:
- ✅ Complete and verified
- ⚠️ Complete with warnings
- ❌ Not complete (blocking)
- ⏭️ Not applicable / Skipped

---

## 1. Infrastructure Prerequisites

### 1.1 Server Requirements
- [ ] Server meets minimum specs (4GB RAM, 2 CPU, 50GB disk)
- [ ] Operating system updated (Ubuntu 22.04+ / RHEL 8+ / macOS)
- [ ] Docker and Docker Compose installed (if using containers)
- [ ] Python 3.11+ installed (if running natively)
- [ ] Network ports available (8001 for web UI, 5432 for PostgreSQL)
- [ ] SSL/TLS certificates configured (production only)
- [ ] Firewall rules configured to allow required ports

### 1.2 Database Server
- [ ] PostgreSQL 15+ installed and running
- [ ] pgvector extension available (optional but recommended)
- [ ] Database user created with appropriate permissions
- [ ] Database `bimcalc` created with UTF-8 encoding
- [ ] Connection string tested and validated
- [ ] Backup directory configured with sufficient storage
- [ ] Database backups scheduled (daily + weekly)

### 1.3 Storage & Directories
- [ ] Application directory created (`/opt/bimcalc` or similar)
- [ ] Log directory created with write permissions (`/var/log/bimcalc`)
- [ ] Backup directory created with retention policy (`/backups/bimcalc`)
- [ ] Data directory for uploads/imports created
- [ ] Sufficient disk space (50GB minimum, 200GB recommended)
- [ ] Disk monitoring alerts configured (90% threshold)

---

## 2. Application Setup

### 2.1 Code Deployment
- [ ] Repository cloned or code deployed to target directory
- [ ] Correct branch/tag checked out (main/production)
- [ ] Git commit hash documented for traceability
- [ ] Virtual environment created (if not using Docker)
- [ ] Dependencies installed from `requirements.txt`
- [ ] Development dependencies excluded in production

### 2.2 Environment Configuration
- [ ] `.env` file created from template
- [ ] `DATABASE_URL` configured correctly
- [ ] `DEFAULT_ORG_ID` set to production organization
- [ ] `CURRENCY` set to EUR (or appropriate)
- [ ] `VAT_INCLUDED` and `VAT_RATE` configured
- [ ] `LOG_LEVEL` set appropriately (INFO for prod, DEBUG for staging)
- [ ] `ARCHON_SERVER` and `ARCHON_TOKEN` configured (if applicable)
- [ ] Alert email/webhook configured
- [ ] All environment variables validated

### 2.3 Database Initialization
- [ ] Database schema initialized (`bimcalc init`)
- [ ] Migrations applied successfully (`alembic upgrade head`)
- [ ] Database connection tested
- [ ] Sample data loaded (staging only)
- [ ] Foreign key constraints verified
- [ ] Indexes created and optimized
- [ ] Database user permissions verified

---

## 3. Feature Validation

### 3.1 Core Matching Features
- [ ] Price ingestion working (CSV, XLSX)
- [ ] Schedule ingestion working (Revit exports)
- [ ] Classification system operational
- [ ] Canonical key generation working
- [ ] Candidate generation with classification blocking operational
- [ ] Confidence scoring working (text, attributes, size, material)
- [ ] Risk flag engine operational (Critical-Veto and Advisory)
- [ ] Escape-hatch matching working for no-match scenarios
- [ ] Auto-routing logic working (High confidence + no flags)

### 3.2 Mapping Memory (SCD2)
- [ ] Mapping creation working
- [ ] SCD2 versioning operational (start_ts, end_ts)
- [ ] No duplicate active mappings per (org_id, canonical_key)
- [ ] Historical queries working (as-of timestamp)
- [ ] Mapping updates close old rows and create new rows
- [ ] Audit trail capturing user, timestamp, reason

### 3.3 Review Workflow
- [ ] Web UI accessible at configured port (8001)
- [ ] Review items displaying with correct data
- [ ] Color coding working (green/yellow/red by confidence)
- [ ] Risk flag badges displaying correctly
- [ ] Accept action creating mappings
- [ ] Reject action recording reasons
- [ ] Remap action allowing price changes
- [ ] Filtering by confidence level working
- [ ] Filtering by risk level working
- [ ] Search functionality operational

### 3.4 Reporting
- [ ] Report generation working
- [ ] As-of timestamp queries working
- [ ] Currency formatting correct (EUR with proper decimals)
- [ ] VAT calculations accurate
- [ ] Report reproducibility verified (same inputs = same output)
- [ ] Export to CSV working
- [ ] Report includes all required fields

---

## 4. Data Pipeline Features

### 4.1 Multi-Source Ingestion
- [ ] CSV file ingestion tested
- [ ] XLSX file ingestion tested
- [ ] JSON file ingestion tested
- [ ] API ingestion configured (if applicable)
- [ ] Validation rules applied during ingestion
- [ ] Error handling for malformed data
- [ ] Batch processing working for large files
- [ ] Success/failure counts logged

### 4.2 Data Quality
- [ ] Classification codes validated against taxonomy
- [ ] Price ranges validated (min/max checks)
- [ ] Currency codes validated (EUR, USD, GBP, etc.)
- [ ] Required fields enforced
- [ ] Duplicate detection working
- [ ] Data normalization working
- [ ] Invalid records rejected with clear errors

### 4.3 Automated Pipelines
- [ ] Pipeline configuration file created (`config/pipeline_sources.yaml`)
- [ ] Configuration validated (`python scripts/validate_config.py`)
- [ ] Scheduled jobs configured (if applicable)
- [ ] Pipeline execution tested end-to-end
- [ ] Pipeline logs being written to `logs/pipeline.log`
- [ ] Error alerts configured for pipeline failures

---

## 5. Performance & Scalability

### 5.1 Performance Benchmarks
- [ ] Test data generated (10K+ prices)
- [ ] Benchmarks executed (`python tests/performance/benchmark.py`)
- [ ] Candidate generation p95 < 1ms ✅
- [ ] End-to-end matching p95 < 2ms ✅
- [ ] Classification blocking achieving ≥6× reduction (test data) ✅
- [ ] Performance results documented
- [ ] Performance monitoring configured

### 5.2 Load Testing
- [ ] Single item matching tested
- [ ] Batch matching tested (100+ items)
- [ ] Large schedule tested (1000+ items)
- [ ] Concurrent user testing (if applicable)
- [ ] Database query performance acceptable
- [ ] Web UI responsiveness acceptable
- [ ] Memory usage within limits
- [ ] No memory leaks detected

### 5.3 Scalability Validation
- [ ] Large price catalog tested (50K+ prices)
- [ ] Multi-organization data tested
- [ ] Historical data queries tested (multiple versions)
- [ ] Disk space projections calculated
- [ ] Database growth projections calculated
- [ ] Scaling plan documented

---

## 6. Security & Access Control

### 6.1 Authentication & Authorization
- [ ] User authentication configured (if applicable)
- [ ] Organization-level data isolation verified
- [ ] Multi-tenant isolation tested
- [ ] API keys/tokens secured in environment variables
- [ ] No credentials in code or logs
- [ ] Session management configured (if applicable)

### 6.2 Data Security
- [ ] Database connections encrypted (SSL/TLS)
- [ ] API connections encrypted (HTTPS)
- [ ] Sensitive data not logged
- [ ] Backup encryption configured
- [ ] File upload validation configured
- [ ] SQL injection prevention verified
- [ ] XSS prevention verified (web UI)

### 6.3 Access Logging
- [ ] User actions logged with timestamps
- [ ] Database queries logged (if needed)
- [ ] Failed login attempts logged (if applicable)
- [ ] Audit trail accessible and queryable
- [ ] Log rotation configured
- [ ] Log retention policy defined

---

## 7. Monitoring & Observability

### 7.1 Health Monitoring
- [ ] Health check script configured (`scripts/health_check.sh`)
- [ ] Database connectivity monitored
- [ ] Disk space monitored (90% alert threshold)
- [ ] Service responsiveness monitored
- [ ] Monitoring dashboard accessible (`scripts/monitoring_dashboard.sh`)
- [ ] Health checks scheduled (every 5 minutes)

### 7.2 Alerting
- [ ] Alert configuration file created (`config/alerts_config.sh`)
- [ ] Email alerts configured (if applicable)
- [ ] Webhook alerts configured (Slack, etc.)
- [ ] Alert script tested (`scripts/send_alert.sh`)
- [ ] Critical alerts defined (DB down, disk full, service crash)
- [ ] Warning alerts defined (high error rate, slow queries)
- [ ] Alert routing tested and validated

### 7.3 Logging
- [ ] Application logs written to `logs/` directory
- [ ] Log level configured appropriately (INFO for prod)
- [ ] Structured logging format used (JSON preferred)
- [ ] Log rotation configured (daily, 7-day retention)
- [ ] Error logs separated from info logs
- [ ] Log aggregation configured (if applicable)

---

## 8. Backup & Recovery

### 8.1 Backup Configuration
- [ ] Backup script configured (`scripts/backup_postgres.sh`)
- [ ] Backup directory created with sufficient space
- [ ] Backup schedule configured (daily + weekly)
- [ ] Backup retention policy configured (7 days + 4 weeks)
- [ ] Backup compression enabled (gzip)
- [ ] Backup encryption configured (production only)
- [ ] Backup monitoring alerts configured

### 8.2 Backup Validation
- [ ] Manual backup executed successfully
- [ ] Backup file integrity verified
- [ ] Backup size reasonable and expected
- [ ] Backup location accessible by ops team
- [ ] Off-site backup configured (production only)
- [ ] Backup automation tested end-to-end

### 8.3 Recovery Testing
- [ ] Restore script configured (`scripts/restore_postgres.sh`)
- [ ] Test database restore performed
- [ ] Restore time documented (RTO)
- [ ] Data integrity verified after restore
- [ ] Point-in-time recovery possible (if needed)
- [ ] Recovery procedure documented
- [ ] Recovery runbook accessible to ops team

---

## 9. Testing

### 9.1 Unit Tests
- [ ] All unit tests passing (`pytest tests/unit/`)
- [ ] Test coverage ≥ 80%
- [ ] No flaky tests
- [ ] Test execution time reasonable
- [ ] Tests documented

### 9.2 Integration Tests
- [ ] Multi-tenant isolation tested
- [ ] SCD2 constraints tested
- [ ] Escape-hatch behavior tested
- [ ] End-to-end workflow tested
- [ ] Database migrations tested
- [ ] All integration tests passing

### 9.3 User Acceptance Testing
- [ ] Sample project run end-to-end
- [ ] Real price catalogs imported successfully
- [ ] Real Revit schedules imported successfully
- [ ] Matching accuracy validated
- [ ] Review workflow validated by users
- [ ] Report accuracy validated
- [ ] User feedback collected and addressed

---

## 10. Documentation

### 10.1 Technical Documentation
- [ ] README.md updated with latest features
- [ ] CLAUDE.md reviewed and current
- [ ] API documentation available (if applicable)
- [ ] Database schema documented
- [ ] Architecture diagrams updated
- [ ] Deployment guide reviewed (STAGING_DEPLOYMENT_GUIDE.md)

### 10.2 Operations Documentation
- [ ] Production operations guide available
- [ ] Backup procedures documented
- [ ] Recovery procedures documented
- [ ] Troubleshooting guide available
- [ ] Monitoring guide available
- [ ] Alerting guide available
- [ ] Runbooks created for common issues

### 10.3 User Documentation
- [ ] User guide available
- [ ] Web UI guide with screenshots
- [ ] Workflow examples documented
- [ ] FAQ document created
- [ ] Training materials prepared (if applicable)
- [ ] Support contact information available

---

## 11. Compliance & Audit

### 11.1 CLAUDE.md Compliance
- [ ] Classification-first blocking enforced
- [ ] Canonical key generation compliant
- [ ] SCD Type-2 mapping implemented correctly
- [ ] Risk flags enforced in UI (Critical-Veto blocks acceptance)
- [ ] EUR currency defaults configured
- [ ] VAT handling explicit and configurable
- [ ] Error handling follows fail-fast policy
- [ ] Deterministic reporting verified

### 11.2 Audit Trail
- [ ] All user actions logged
- [ ] Audit logs immutable
- [ ] Audit logs include required fields (user, timestamp, action, reason)
- [ ] Audit logs queryable
- [ ] Audit log retention policy defined
- [ ] Compliance with data retention requirements

### 11.3 Data Governance
- [ ] Data classification defined
- [ ] PII handling procedures documented (if applicable)
- [ ] Data retention policy documented
- [ ] Data deletion procedures documented
- [ ] GDPR compliance verified (if applicable)
- [ ] Data export capabilities tested

---

## 12. Deployment Execution

### 12.1 Pre-Deployment
- [ ] Deployment window scheduled
- [ ] Stakeholders notified
- [ ] Maintenance page prepared (if applicable)
- [ ] Rollback plan documented
- [ ] Deployment checklist reviewed
- [ ] Team availability confirmed

### 12.2 Deployment Steps
- [ ] Code deployed to server
- [ ] Dependencies installed
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Services started successfully
- [ ] Health checks passing
- [ ] Smoke tests executed
- [ ] User acceptance validation performed

### 12.3 Post-Deployment
- [ ] Services stable for 1 hour
- [ ] Monitoring dashboards reviewed
- [ ] No critical errors in logs
- [ ] Performance metrics within expected range
- [ ] User notifications sent
- [ ] Documentation updated with deployment details
- [ ] Deployment retrospective scheduled

---

## 13. Staging Environment Specific

### 13.1 Staging Setup
- [ ] Staging environment separate from production
- [ ] Staging data isolated from production
- [ ] Staging credentials different from production
- [ ] Sample/test data loaded
- [ ] Staging clearly labeled in UI
- [ ] Staging URL documented

### 13.2 Staging Validation
- [ ] End-to-end workflow tested in staging
- [ ] All features tested in staging before production
- [ ] Performance benchmarks run in staging
- [ ] Load testing performed in staging
- [ ] User acceptance testing in staging
- [ ] No critical issues found in staging

---

## 14. Production Environment Specific

### 14.1 Production Hardening
- [ ] Production secrets rotated
- [ ] Production firewall rules strict
- [ ] Production monitoring more aggressive
- [ ] Production backup frequency increased
- [ ] Production alerts more sensitive
- [ ] Production SSL/TLS enforced

### 14.2 Production Readiness
- [ ] Staging validation completed successfully
- [ ] Production runbooks reviewed
- [ ] On-call team identified
- [ ] Escalation procedures defined
- [ ] Support team trained
- [ ] Production go-live plan approved

---

## Validation Sign-Off

### Technical Lead
- [ ] All critical items verified
- [ ] Performance requirements met
- [ ] Security requirements met
- [ ] Deployment approved

**Name:** ________________
**Date:** ________________
**Signature:** ________________

### Operations Lead
- [ ] Infrastructure ready
- [ ] Monitoring configured
- [ ] Backup/recovery tested
- [ ] Runbooks available
- [ ] Deployment approved

**Name:** ________________
**Date:** ________________
**Signature:** ________________

### Product Owner
- [ ] Features validated
- [ ] User acceptance criteria met
- [ ] Documentation complete
- [ ] Deployment approved

**Name:** ________________
**Date:** ________________
**Signature:** ________________

---

## Appendix: Quick Validation Commands

### Health Check
```bash
./scripts/health_check.sh
```

### Database Connectivity
```bash
docker compose exec app bimcalc --help
# or
psql $DATABASE_URL -c "SELECT 1;"
```

### Run Tests
```bash
pytest -v
pytest --cov=bimcalc --cov-fail-under=80
```

### Performance Benchmarks
```bash
python tests/performance/generate_test_data.py
python tests/performance/benchmark.py
```

### Web UI Access
```bash
# Start web UI
bimcalc web serve --host 0.0.0.0 --port 8001

# Access at http://localhost:8001
curl http://localhost:8001/health
```

### Database Backup
```bash
./scripts/backup_postgres.sh
ls -lh backups/
```

### Check Logs
```bash
tail -f logs/pipeline.log
docker compose logs -f app
journalctl -u bimcalc -f
```

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-14 | BIMCalc Team | Initial deployment checklist |

---

**Notes:**
- This checklist should be completed before every staging and production deployment
- All critical items (marked with blocking) must be completed
- Non-critical items should be completed or documented as skipped with justification
- Keep this checklist in version control and update as deployment procedures evolve
- Use this as a template for deployment documentation and runbooks
