-- InvestiCore V2 - Phase 2 derived financial metrics and SEC activity evidence.

SET search_path TO investicorev2, public;

CREATE TABLE IF NOT EXISTS investicorev2.market_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    price NUMERIC NOT NULL CHECK (price >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL DEFAULT 'Yahoo Finance',
    market_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS market_prices_company_timestamp_idx
    ON investicorev2.market_prices(company_id, market_timestamp DESC);

CREATE TABLE IF NOT EXISTS investicorev2.derived_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    financial_period_id UUID REFERENCES investicorev2.financial_periods(id) ON DELETE SET NULL,
    market_price_id UUID REFERENCES investicorev2.market_prices(id) ON DELETE SET NULL,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC,
    unit TEXT NOT NULL DEFAULT 'ratio',
    status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'NOT_APPLICABLE', 'REQUIRES_REVIEW')),
    calculation_method TEXT NOT NULL,
    calculation_version TEXT NOT NULL DEFAULT 'phase2_v1',
    source_period_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_metric_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_filing_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT derived_metrics_unique_observation UNIQUE NULLS NOT DISTINCT (company_id, financial_period_id, market_price_id, metric_name, calculation_version)
);

CREATE INDEX IF NOT EXISTS derived_metrics_company_metric_idx
    ON investicorev2.derived_metrics(company_id, metric_name, calculated_at DESC);

CREATE TABLE IF NOT EXISTS investicorev2.insider_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    filing_id UUID NOT NULL REFERENCES investicorev2.sec_filings(id) ON DELETE CASCADE,
    reporting_person TEXT NOT NULL,
    officer_title TEXT,
    transaction_date DATE,
    transaction_code TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    shares_transacted NUMERIC,
    price_per_share NUMERIC,
    total_value NUMERIC,
    shares_owned_after NUMERIC,
    is_direct BOOLEAN,
    source_document_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT insider_transactions_filing_code_date_value_key UNIQUE NULLS NOT DISTINCT (filing_id, transaction_code, transaction_date, shares_transacted, price_per_share)
);

CREATE INDEX IF NOT EXISTS insider_transactions_company_date_idx
    ON investicorev2.insider_transactions(company_id, transaction_date DESC);

CREATE TABLE IF NOT EXISTS investicorev2.ownership_disclosures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicorev2.companies(id) ON DELETE CASCADE,
    filing_id UUID NOT NULL REFERENCES investicorev2.sec_filings(id) ON DELETE CASCADE,
    holder_name TEXT,
    form_type TEXT NOT NULL,
    filing_date DATE NOT NULL,
    shares_beneficially_owned NUMERIC,
    ownership_pct NUMERIC,
    is_activist BOOLEAN NOT NULL DEFAULT FALSE,
    activity_type TEXT NOT NULL DEFAULT 'OWNERSHIP_DISCLOSURE',
    source_document_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ownership_disclosures_filing_key UNIQUE (filing_id)
);

CREATE INDEX IF NOT EXISTS ownership_disclosures_company_date_idx
    ON investicorev2.ownership_disclosures(company_id, filing_date DESC);

ALTER TABLE investicorev2.market_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.derived_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.insider_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicorev2.ownership_disclosures ENABLE ROW LEVEL SECURITY;

GRANT ALL ON investicorev2.market_prices, investicorev2.derived_metrics, investicorev2.insider_transactions, investicorev2.ownership_disclosures TO anon, authenticated, service_role;

DO $$
DECLARE tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['market_prices', 'derived_metrics', 'insider_transactions', 'ownership_disclosures']
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "InvestiCore V2 HTTP API access" ON investicorev2.%I', tbl);
        EXECUTE format('CREATE POLICY "InvestiCore V2 HTTP API access" ON investicorev2.%I FOR ALL TO anon, authenticated, service_role USING (true) WITH CHECK (true)', tbl);
    END LOOP;
END $$;