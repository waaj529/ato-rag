# Rollback Runbook

## Code and Migration Rollback

1. **Application Deployment Rollback**:
   - Revert container image tag to previous stable digest.
   - Run `pytest` to confirm backward compatibility.
2. **Database Migration Rollback**:
   - If a schema change causes regression, execute corresponding down-migration.
   - For `0006_phase6_security_rls.sql`:
     ```sql
     DROP TABLE IF EXISTS matter_documents CASCADE;
     DROP TABLE IF EXISTS customer_matters CASCADE;
     DROP TABLE IF EXISTS dead_letter_queue CASCADE;
     ```
3. **Retrieval Index Rebuild**:
   - If vector or FTS indexes are corrupted:
     ```bash
     python3 scripts/populate_phase4_parents.py
     python3 scripts/verify_phase3_exit.py
     python3 scripts/verify_phase4_e2e.py
     python3 scripts/verify_phase5_exit.py
     ```
