# Incident Response Runbook

## Severity Levels

- **SEV-1 (Critical)**: Cross-tenant data leakage, total service outage, or unauthorized data modification.
  - SLA: 15-minute response, hourly executive updates.
- **SEV-2 (Major)**: Primary provider outage (e.g. Isaacus/Jev), elevated error rate (>5%), or severe latency degradation (p95 > 5s).
  - SLA: 30-minute response.
- **SEV-3 (Moderate)**: Degraded non-blocking background workers or transient DLQ backlog.
  - SLA: 4-hour response.

## Immediate Containment Actions

1. **Suspected Cross-Tenant Breach**:
   - Immediately invoke `reset_tenant_session()` across all connection pools.
   - Restrict access to `PUBLIC_OFFICIAL` data classifications only.
   - Rotate database credentials.
2. **Adversarial Prompt-Injection Outbreak**:
   - Verify all retrieved corpus documents pass `wrap_untrusted_evidence()`.
   - Block attacking IP/tenant via `RateLimiter` quota zeroing.
3. **Database Corruption / Data Loss**:
   - Execute restore procedure via `scripts/backup_restore_ops.py`.
   - Restore database from PITR snapshot.
