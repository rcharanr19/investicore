-- InvestiCore V2 - Phase 1 validation-status compatibility fix.
-- Apply after 002_investicorev2_phase1_hardening.sql.

SET search_path TO investicorev2, public;

ALTER TABLE investicorev2.financial_validation_issues
    DROP CONSTRAINT IF EXISTS financial_validation_issues_validation_status_check;
ALTER TABLE investicorev2.financial_validation_issues
    ADD CONSTRAINT financial_validation_issues_validation_status_check
    CHECK (validation_status IN ('PASS', 'VALID_53_WEEK_YEAR', 'WARNING', 'FAIL', 'REQUIRES_REVIEW', 'NOT_APPLICABLE'));