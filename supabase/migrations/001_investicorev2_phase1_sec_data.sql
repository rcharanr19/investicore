-- InvestiCore V2 - Phase 1 SEC data foundation
-- Apply in the Supabase SQL Editor or as a migration.
-- Raw SEC artifacts live in the `sec-filings` Storage bucket. PostgreSQL stores
-- filing/document metadata, normalized facts, provenance, and ingestion state.

CREATE SCHEMA IF NOT EXISTS investicorev2;
SET search_path TO investicorev2, public;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS investicorev2.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL,
    cik TEXT NOT NULL,
    legal_name TEXT,
    sic TEXT,
    sic_description TEXT,
    exchange TEXT,
    fiscal_year_end TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT companies_cik_key UNIQUE (cik),
    CONSTRAINT companies_ticker_key UNIQUE (ticker)
);

CREATE TABLE IF NOT EXISTS investicorev2.sec_filings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    accession_number TEXT NOT NULL,
    form_type TEXT NOT NULL,
    filing_date DATE NOT NULL,
    report_date DATE,
    period_start DATE,
    period_end DATE,
    fiscal_year INTEGER,
    fiscal_period TEXT CHECK (fiscal_period IN ('FY', 'Q1', 'Q2', 'Q3', 'Q4') OR fiscal_period IS NULL),
    primary_document TEXT,
    sec_url TEXT NOT NULL,
    index_url TEXT,
    filing_items TEXT,
    is_xbrl BOOLEAN NOT NULL DEFAULT FALSE,
    is_inline_xbrl BOOLEAN NOT NULL DEFAULT FALSE,
    is_amendment BOOLEAN NOT NULL DEFAULT FALSE,
    amends_filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL,
    ingestion_status TEXT NOT NULL DEFAULT 'DISCOVERED'
        CHECK (ingestion_status IN ('DISCOVERED', 'DOWNLOADING', 'DOWNLOADED', 'PARSED', 'NORMALIZED', 'FAILED', 'REQUIRES_REVIEW')),
    last_error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    last_attempt_at TIMESTAMPTZ,
    downloaded_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT sec_filings_company_accession_key UNIQUE (company_id, accession_number)
);

CREATE INDEX IF NOT EXISTS sec_filings_company_idx ON investicorev2.sec_filings(company_id);
CREATE INDEX IF NOT EXISTS sec_filings_accession_idx ON investicorev2.sec_filings(accession_number);
CREATE INDEX IF NOT EXISTS sec_filings_form_date_idx ON investicorev2.sec_filings(company_id, form_type, filing_date DESC);
CREATE INDEX IF NOT EXISTS sec_filings_report_date_idx ON investicorev2.sec_filings(company_id, report_date DESC);
CREATE INDEX IF NOT EXISTS sec_filings_status_idx ON investicorev2.sec_filings(company_id, ingestion_status);

CREATE TABLE IF NOT EXISTS investicorev2.sec_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id UUID NOT NULL REFERENCES investicorev2.sec_filings(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_url TEXT NOT NULL,
    storage_bucket TEXT NOT NULL DEFAULT 'sec-filings',
    storage_path TEXT NOT NULL,
    content_type TEXT,
    byte_size BIGINT CHECK (byte_size >= 0),
    content_hash TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT sec_documents_storage_path_key UNIQUE (storage_bucket, storage_path),
    CONSTRAINT sec_documents_filing_filename_key UNIQUE (filing_id, filename)
);

CREATE INDEX IF NOT EXISTS sec_documents_filing_idx ON investicorev2.sec_documents(filing_id);
CREATE INDEX IF NOT EXISTS sec_documents_hash_idx ON investicorev2.sec_documents(content_hash);

CREATE TABLE IF NOT EXISTS investicorev2.financial_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    period_type TEXT NOT NULL CHECK (period_type IN ('Annual', 'Quarterly', 'TTM')),
    fiscal_year INTEGER NOT NULL,
    fiscal_period TEXT NOT NULL CHECK (fiscal_period IN ('FY', 'Q1', 'Q2', 'Q3', 'Q4', 'TTM')),
    calendar_year INTEGER,
    period_start DATE,
    period_end DATE NOT NULL,
    duration_days INTEGER CHECK (duration_days IS NULL OR duration_days > 0),
    source_filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT financial_periods_canonical_key UNIQUE (company_id, period_type, fiscal_year, fiscal_period, period_end)
);

CREATE INDEX IF NOT EXISTS financial_periods_company_end_idx ON investicorev2.financial_periods(company_id, period_end DESC);
CREATE INDEX IF NOT EXISTS financial_periods_type_end_idx ON investicorev2.financial_periods(company_id, period_type, period_end DESC);

CREATE TABLE IF NOT EXISTS investicorev2.financial_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    financial_period_id UUID NOT NULL REFERENCES investicorev2.financial_periods(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC,
    currency TEXT NOT NULL DEFAULT 'USD',
    unit TEXT NOT NULL DEFAULT 'USD',
    source_filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL,
    source_document_id UUID REFERENCES investicorev2.sec_documents(id) ON DELETE SET NULL,
    source_accession_number TEXT,
    xbrl_namespace TEXT,
    xbrl_tag TEXT,
    source_period_start DATE,
    source_period_end DATE,
    source_section TEXT,
    source_type TEXT NOT NULL DEFAULT 'XBRL' CHECK (source_type IN ('XBRL', 'DERIVED', 'MANUAL')),
    confidence TEXT NOT NULL DEFAULT 'HIGH' CHECK (confidence IN ('HIGH', 'MEDIUM', 'LOW', 'REQUIRES_REVIEW')),
    is_derived BOOLEAN NOT NULL DEFAULT FALSE,
    calculation_formula TEXT,
    supersedes_metric_id UUID REFERENCES investicorev2.financial_metrics(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT financial_metrics_observation_key UNIQUE NULLS NOT DISTINCT
        (financial_period_id, metric_name, source_filing_id, xbrl_namespace, xbrl_tag)
);

CREATE INDEX IF NOT EXISTS financial_metrics_company_metric_idx ON investicorev2.financial_metrics(company_id, metric_name);
CREATE INDEX IF NOT EXISTS financial_metrics_period_metric_idx ON investicorev2.financial_metrics(financial_period_id, metric_name);
CREATE INDEX IF NOT EXISTS financial_metrics_source_filing_idx ON investicorev2.financial_metrics(source_filing_id);

CREATE TABLE IF NOT EXISTS investicorev2.financial_validation_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    financial_period_id UUID REFERENCES investicorev2.financial_periods(id) ON DELETE CASCADE,
    source_filing_id UUID REFERENCES investicorev2.sec_filings(id) ON DELETE SET NULL,
    check_name TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED', 'DISMISSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS financial_validation_issues_company_idx ON investicorev2.financial_validation_issues(company_id, status);

CREATE TABLE IF NOT EXISTS investicorev2.sec_refresh_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING', 'COMPLETED', 'PARTIAL_FAILURE', 'FAILED')),
    discovered_count INTEGER NOT NULL DEFAULT 0,
    existing_count INTEGER NOT NULL DEFAULT 0,
    new_count INTEGER NOT NULL DEFAULT 0,
    downloaded_count INTEGER NOT NULL DEFAULT 0,
    normalized_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sec_refresh_runs_company_started_idx ON investicorev2.sec_refresh_runs(company_id, started_at DESC);

-- Supabase Storage bucket. Objects must use deterministic paths such as:
-- {cik}/{form_type}/{accession_number}/filing.html
INSERT INTO storage.buckets (id, name, public)
VALUES ('sec-filings', 'sec-filings', FALSE)
ON CONFLICT (id) DO NOTHING;

-- Expose this schema to the Supabase HTTP Data API by adding `investicorev2`
-- to API Settings > Exposed schemas in the Supabase dashboard. The grants below
-- authorize PostgREST once the schema is exposed.
GRANT USAGE ON SCHEMA investicorev2 TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA investicorev2 TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA investicorev2 TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA investicorev2 GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA investicorev2 GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;

ALTER TABLE investicorev2.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.sec_filings ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.sec_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.financial_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.financial_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.financial_validation_issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.sec_refresh_runs ENABLE ROW LEVEL SECURITY;

-- This is a single-user application policy for the anon/authenticated Data API.
-- Replace it with user-ownership policies before allowing multiple users.
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'companies',
        'sec_filings',
        'sec_documents',
        'financial_periods',
        'financial_metrics',
        'financial_validation_issues',
        'sec_refresh_runs'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "InvestiCore V2 HTTP API access" ON investicorev2.%I', tbl);
        EXECUTE format(
            'CREATE POLICY "InvestiCore V2 HTTP API access" ON investicorev2.%I FOR ALL TO anon, authenticated, service_role USING (true) WITH CHECK (true)',
            tbl
        );
    END LOOP;
END $$;

-- Restrict Storage API access to SEC artifacts in this bucket. Service-role
-- requests bypass RLS; anon/authenticated requests are permitted for this app.
DROP POLICY IF EXISTS "InvestiCore V2 SEC Storage select" ON storage.objects;
CREATE POLICY "InvestiCore V2 SEC Storage select"
ON storage.objects FOR SELECT TO anon, authenticated
USING (bucket_id = 'sec-filings');

DROP POLICY IF EXISTS "InvestiCore V2 SEC Storage insert" ON storage.objects;
CREATE POLICY "InvestiCore V2 SEC Storage insert"
ON storage.objects FOR INSERT TO anon, authenticated
WITH CHECK (bucket_id = 'sec-filings');

DROP POLICY IF EXISTS "InvestiCore V2 SEC Storage update" ON storage.objects;
CREATE POLICY "InvestiCore V2 SEC Storage update"
ON storage.objects FOR UPDATE TO anon, authenticated
USING (bucket_id = 'sec-filings')
WITH CHECK (bucket_id = 'sec-filings');

DROP POLICY IF EXISTS "InvestiCore V2 SEC Storage delete" ON storage.objects;
CREATE POLICY "InvestiCore V2 SEC Storage delete"
ON storage.objects FOR DELETE TO anon, authenticated
USING (bucket_id = 'sec-filings');