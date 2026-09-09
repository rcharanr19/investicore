-- InvestiCore V2 - Phase 1 completion and hardening.
-- Apply after 001_investicorev2_phase1_sec_data.sql.

SET search_path TO investicorev2, public;

ALTER TABLE investicorev2.sec_filings
    ADD COLUMN IF NOT EXISTS failure_stage TEXT,
    ADD COLUMN IF NOT EXISTS last_error_type TEXT,
    ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_preferred BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS superseded_by_filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL;

ALTER TABLE investicorev2.financial_periods
    ADD COLUMN IF NOT EXISTS is_derived BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS calculation_method TEXT,
    ADD COLUMN IF NOT EXISTS calculation_version TEXT,
    ADD COLUMN IF NOT EXISTS calculated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source_period_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS source_filing_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE investicorev2.financial_metrics
    ADD COLUMN IF NOT EXISTS metric_kind TEXT NOT NULL DEFAULT 'stock' CHECK (metric_kind IN ('flow', 'stock')),
    ADD COLUMN IF NOT EXISTS calculation_method TEXT,
    ADD COLUMN IF NOT EXISTS calculation_version TEXT,
    ADD COLUMN IF NOT EXISTS calculated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source_periods JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS source_fact_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS is_preferred BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE investicorev2.financial_validation_issues
    ADD COLUMN IF NOT EXISTS validation_type TEXT,
    ADD COLUMN IF NOT EXISTS validation_status TEXT NOT NULL DEFAULT 'REQUIRES_REVIEW'
        CHECK (validation_status IN ('PASS', 'WARNING', 'FAIL', 'REQUIRES_REVIEW', 'NOT_APPLICABLE')),
    ADD COLUMN IF NOT EXISTS expected_value NUMERIC,
    ADD COLUMN IF NOT EXISTS actual_value NUMERIC,
    ADD COLUMN IF NOT EXISTS difference NUMERIC,
    ADD COLUMN IF NOT EXISTS tolerance NUMERIC,
    ADD COLUMN IF NOT EXISTS message TEXT;

CREATE TABLE IF NOT EXISTS investicorev2.xbrl_mapping_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL,
    canonical_metric TEXT NOT NULL,
    review_type TEXT NOT NULL CHECK (review_type IN ('MISSING_MAPPING', 'AMBIGUOUS_MAPPING', 'MULTIPLE_CANDIDATES', 'CONFLICTING_FACTS', 'UNSUPPORTED_METRIC')),
    candidate_xbrl_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    selected_tag TEXT,
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'REQUIRES_REVIEW',
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED', 'DISMISSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT xbrl_mapping_reviews_unique UNIQUE NULLS NOT DISTINCT (filing_id, canonical_metric, review_type, selected_tag)
);

CREATE INDEX IF NOT EXISTS xbrl_mapping_reviews_company_status_idx
    ON investicorev2.xbrl_mapping_reviews(company_id, status);

ALTER TABLE investicorev2.xbrl_mapping_reviews ENABLE ROW LEVEL SECURITY;

GRANT ALL ON investicorev2.xbrl_mapping_reviews TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "InvestiCore V2 HTTP API access" ON investicorev2.xbrl_mapping_reviews;
CREATE POLICY "InvestiCore V2 HTTP API access"
ON investicorev2.xbrl_mapping_reviews FOR ALL TO anon, authenticated, service_role
USING (true) WITH CHECK (true);