-- InvestiCore V2 - Phase 1 completion and hardening.
-- Apply after 001_investicorev2_phase1_sec_data.sql.

SET search_path TO investicorev2, public;

ALTER TABLE investicorev2.sec_filings
    ADD COLUMN IF NOT EXISTS failure_stage TEXT,
    ADD COLUMN IF NOT EXISTS last_error_type TEXT,
    ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_preferred BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS superseded_by_filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL;

ALTER TABLE investicorev2.sec_filings
    DROP CONSTRAINT IF EXISTS sec_filings_ingestion_status_check;
ALTER TABLE investicorev2.sec_filings
    ADD CONSTRAINT sec_filings_ingestion_status_check
    CHECK (ingestion_status IN ('DISCOVERED', 'DOWNLOADING', 'DOWNLOADED', 'PARSED', 'NORMALIZED', 'VALIDATED', 'COMPLETED', 'FAILED', 'REQUIRES_REVIEW'));

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

CREATE TABLE IF NOT EXISTS investicorev2.sec_xbrl_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL,
    accession_number TEXT,
    taxonomy TEXT NOT NULL,
    xbrl_tag TEXT NOT NULL,
    fact_value NUMERIC,
    unit TEXT,
    start_date DATE,
    end_date DATE,
    instant_date DATE,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    form_type TEXT,
    filed_date DATE,
    frame TEXT,
    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT sec_xbrl_facts_identity_key UNIQUE NULLS NOT DISTINCT
        (company_id, accession_number, taxonomy, xbrl_tag, unit, start_date, end_date, instant_date, frame)
);

CREATE INDEX IF NOT EXISTS sec_xbrl_facts_company_tag_idx
    ON investicorev2.sec_xbrl_facts(company_id, taxonomy, xbrl_tag);
CREATE INDEX IF NOT EXISTS sec_xbrl_facts_filing_idx
    ON investicorev2.sec_xbrl_facts(filing_id);

ALTER TABLE investicorev2.financial_validation_issues
    ADD COLUMN IF NOT EXISTS validation_type TEXT,
    ADD COLUMN IF NOT EXISTS validation_status TEXT NOT NULL DEFAULT 'REQUIRES_REVIEW'
        CHECK (validation_status IN ('PASS', 'VALID_53_WEEK_YEAR', 'WARNING', 'FAIL', 'REQUIRES_REVIEW', 'NOT_APPLICABLE')),
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
ALTER TABLE investicorev2.sec_xbrl_facts ENABLE ROW LEVEL SECURITY;

GRANT ALL ON investicorev2.xbrl_mapping_reviews TO anon, authenticated, service_role;
GRANT ALL ON investicorev2.sec_xbrl_facts TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "InvestiCore V2 HTTP API access" ON investicorev2.xbrl_mapping_reviews;
CREATE POLICY "InvestiCore V2 HTTP API access"
ON investicorev2.xbrl_mapping_reviews FOR ALL TO anon, authenticated, service_role
USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "InvestiCore V2 HTTP API access" ON investicorev2.sec_xbrl_facts;
CREATE POLICY "InvestiCore V2 HTTP API access"
ON investicorev2.sec_xbrl_facts FOR ALL TO anon, authenticated, service_role
USING (true) WITH CHECK (true);