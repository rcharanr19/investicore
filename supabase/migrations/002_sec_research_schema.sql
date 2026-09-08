-- Migration 002: SEC Fundamental Research & Special Situations Analysis Schema
-- Adds support for CIK canonical identification, SEC filings, normalized XBRL metrics,
-- NCAV / NNWC analytics, catalysts, valuation snapshots, and research alerts under schema `investicore`.

CREATE SCHEMA IF NOT EXISTS investicore;
SET search_path TO investicore, public;

-- 1. Extend Companies table with canonical SEC identifiers
ALTER TABLE investicore.companies
    ADD COLUMN IF NOT EXISTS cik TEXT,
    ADD COLUMN IF NOT EXISTS sic TEXT,
    ADD COLUMN IF NOT EXISTS sic_description TEXT,
    ADD COLUMN IF NOT EXISTS exchange TEXT,
    ADD COLUMN IF NOT EXISTS fiscal_year_end TEXT,
    ADD COLUMN IF NOT EXISTS state_of_incorporation TEXT;

CREATE INDEX IF NOT EXISTS idx_companies_cik ON investicore.companies(cik);

-- 2. SEC Filings Table (stores raw submissions, accession numbers, and metadata)
CREATE TABLE IF NOT EXISTS investicore.sec_filings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    accession_number TEXT NOT NULL,
    form_type TEXT NOT NULL,
    filing_date DATE NOT NULL,
    report_date DATE,
    period_start DATE,
    period_end DATE,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    primary_document TEXT,
    filing_url TEXT,
    index_url TEXT,
    is_xbrl BOOLEAN NOT NULL DEFAULT FALSE,
    is_inline_xbrl BOOLEAN NOT NULL DEFAULT FALSE,
    items TEXT,
    raw_content_location TEXT,
    content_hash TEXT,
    parsed_status TEXT NOT NULL DEFAULT 'Unparsed' CHECK (parsed_status IN ('Unparsed', 'Parsed', 'Failed', 'NeedsReview')),
    parse_version TEXT,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_company_accession UNIQUE (company_id, accession_number)
);

CREATE INDEX IF NOT EXISTS idx_sec_filings_company ON investicore.sec_filings(company_id);
CREATE INDEX IF NOT EXISTS idx_sec_filings_form_date ON investicore.sec_filings(form_type, filing_date);
CREATE INDEX IF NOT EXISTS idx_sec_filings_accession ON investicore.sec_filings(accession_number);

-- 3. Filing Documents (for raw text / HTML sections & footnotes preservation)
CREATE TABLE IF NOT EXISTS investicore.filing_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id UUID NOT NULL REFERENCES investicore.sec_filings(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    description TEXT,
    content TEXT,
    content_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_filing_docs_filing ON investicore.filing_documents(filing_id);

-- 4. Normalized Financial Periods Table
CREATE TABLE IF NOT EXISTS investicore.financial_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    period_type TEXT NOT NULL CHECK (period_type IN ('Annual', 'Quarterly', 'TTM', 'Other')),
    fiscal_year INTEGER NOT NULL,
    fiscal_period TEXT,
    period_start DATE,
    period_end DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_financial_periods_company_end ON investicore.financial_periods(company_id, period_end);

-- 5. Normalized Financial Metrics Table
CREATE TABLE IF NOT EXISTS investicore.financial_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    financial_period_id UUID REFERENCES investicore.financial_periods(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC,
    currency TEXT NOT NULL DEFAULT 'USD',
    unit TEXT DEFAULT 'USD',
    source_filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    source_concept TEXT,
    source_type TEXT NOT NULL DEFAULT 'XBRL',
    confidence TEXT NOT NULL DEFAULT 'HIGH' CHECK (confidence IN ('HIGH', 'MEDIUM', 'LOW', 'MANUAL_REVIEW')),
    is_derived BOOLEAN NOT NULL DEFAULT FALSE,
    calculation_formula TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_financial_metrics_company_name ON investicore.financial_metrics(company_id, metric_name);

-- 6. NCAV / NNWC and Liquidation Valuation Table
CREATE TABLE IF NOT EXISTS investicore.ncav_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    as_of_date DATE NOT NULL,
    share_price NUMERIC,
    shares_outstanding NUMERIC,
    market_cap NUMERIC,
    current_assets NUMERIC,
    total_liabilities NUMERIC,
    ncav NUMERIC,
    ncav_per_share NUMERIC,
    price_to_ncav NUMERIC,
    nnwc NUMERIC,
    nnwc_per_share NUMERIC,
    price_to_nnwc NUMERIC,
    net_cash NUMERIC,
    cash_recovery_pct NUMERIC NOT NULL DEFAULT 100.0,
    receivables_recovery_pct NUMERIC NOT NULL DEFAULT 75.0,
    inventory_recovery_pct NUMERIC NOT NULL DEFAULT 50.0,
    other_assets_recovery_pct NUMERIC NOT NULL DEFAULT 0.0,
    adjusted_liquidation_value NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ncav_company_date ON investicore.ncav_analysis(company_id, as_of_date);

-- 7. Catalysts Table (for 8-K events, asset sales, tender offers, restructurings)
CREATE TABLE IF NOT EXISTS investicore.catalysts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    thesis_id UUID REFERENCES investicore.theses(id) ON DELETE SET NULL,
    filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    catalyst_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    date_identified DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_date DATE,
    probability INTEGER CHECK (probability >= 0 AND probability <= 100),
    estimated_value_impact NUMERIC,
    status TEXT NOT NULL DEFAULT 'Potential' CHECK (status IN ('Potential', 'Announced', 'Pending', 'Completed', 'Delayed', 'Failed', 'Invalidated')),
    source TEXT,
    confidence TEXT NOT NULL DEFAULT 'HIGH',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_catalysts_company_status ON investicore.catalysts(company_id, status);

-- 8. Valuation Snapshots Table (for versioned historical thesis tracking)
CREATE TABLE IF NOT EXISTS investicore.valuation_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    share_price NUMERIC,
    shares NUMERIC,
    market_cap NUMERIC,
    ncav NUMERIC,
    ncav_per_share NUMERIC,
    price_to_ncav NUMERIC,
    nnwc NUMERIC,
    nnwc_per_share NUMERIC,
    price_to_nnwc NUMERIC,
    net_cash NUMERIC,
    adjusted_liquidation_value NUMERIC,
    catalyst_score NUMERIC,
    expected_value NUMERIC,
    expected_return NUMERIC,
    thesis_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_valuation_snapshots_company_date ON investicore.valuation_snapshots(company_id, snapshot_date);

-- 9. Filing Changes & Research Alerts Table
CREATE TABLE IF NOT EXISTS investicore.research_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    alert_type TEXT NOT NULL,
    headline TEXT NOT NULL,
    description TEXT,
    severity TEXT NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS on new tables
ALTER TABLE investicore.sec_filings ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.filing_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.financial_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.financial_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.ncav_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.catalysts ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.valuation_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.research_alerts ENABLE ROW LEVEL SECURITY;
