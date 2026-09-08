-- Migration 003: SEC Filing Intelligence Enhancement Schema
-- Adds support for DEF 14A Proxy Governance, Schedule 13D/13G Beneficial Ownership,
-- and Form 4 Insider Transactions under the `investicore` schema.

CREATE SCHEMA IF NOT EXISTS investicore;
SET search_path TO investicore, public;

-- 1. Management Compensation & Proxy Governance Table (DEF 14A)
CREATE TABLE IF NOT EXISTS investicore.management_compensation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    fiscal_year INTEGER NOT NULL DEFAULT 2025,
    executive_name TEXT NOT NULL,
    title TEXT NOT NULL,
    base_salary NUMERIC DEFAULT 0.0,
    bonus NUMERIC DEFAULT 0.0,
    stock_awards NUMERIC DEFAULT 0.0,
    option_awards NUMERIC DEFAULT 0.0,
    other_compensation NUMERIC DEFAULT 0.0,
    total_compensation NUMERIC DEFAULT 0.0,
    shares_owned NUMERIC DEFAULT 0.0,
    ownership_pct NUMERIC DEFAULT 0.0,
    incentive_metrics TEXT,
    alignment_score NUMERIC DEFAULT 70.0,
    governance_flags JSONB DEFAULT '[]'::jsonb,
    source_filing TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mgmt_comp_company ON investicore.management_compensation(company_id);

-- 2. Significant Ownership & Activist Filings Table (Schedule 13D / 13G)
CREATE TABLE IF NOT EXISTS investicore.ownership_filings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    holder_name TEXT NOT NULL,
    schedule_type TEXT NOT NULL DEFAULT '13D',
    ownership_pct NUMERIC NOT NULL DEFAULT 5.0,
    shares_owned NUMERIC DEFAULT 0.0,
    filing_date DATE NOT NULL DEFAULT CURRENT_DATE,
    is_activist BOOLEAN NOT NULL DEFAULT FALSE,
    purpose_of_transaction TEXT,
    activist_campaign_demands JSONB DEFAULT '[]'::jsonb,
    source_filing_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ownership_company ON investicore.ownership_filings(company_id);
CREATE INDEX IF NOT EXISTS idx_ownership_activist ON investicore.ownership_filings(company_id, is_activist);

-- 3. Form 4 Insider Transactions Table
CREATE TABLE IF NOT EXISTS investicore.insider_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES investicore.companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES investicore.sec_filings(id) ON DELETE SET NULL,
    reporting_person TEXT NOT NULL,
    officer_title TEXT,
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    transaction_code TEXT NOT NULL DEFAULT 'P',
    transaction_type TEXT NOT NULL DEFAULT 'Open Market Purchase',
    shares_transacted NUMERIC DEFAULT 0.0,
    price_per_share NUMERIC,
    total_value NUMERIC DEFAULT 0.0,
    shares_owned_after NUMERIC DEFAULT 0.0,
    is_direct BOOLEAN NOT NULL DEFAULT TRUE,
    is_open_market_purchase BOOLEAN NOT NULL DEFAULT FALSE,
    source_filing_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_insider_tx_company ON investicore.insider_transactions(company_id);
CREATE INDEX IF NOT EXISTS idx_insider_tx_open_market ON investicore.insider_transactions(company_id, is_open_market_purchase);

-- Enable RLS on new tables
ALTER TABLE investicore.management_compensation ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.ownership_filings ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.insider_transactions ENABLE ROW LEVEL SECURITY;

-- Grants for Supabase API access
GRANT USAGE ON SCHEMA investicore TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA investicore TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA investicore TO anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA investicore TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA investicore GRANT ALL ON TABLES TO anon, authenticated, service_role;

-- Permissive RLS policies for application access
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN
        SELECT tablename FROM pg_tables WHERE schemaname = 'investicore'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "Allow all access" ON investicore.%I', tbl);
        EXECUTE format('CREATE POLICY "Allow all access" ON investicore.%I FOR ALL TO anon, authenticated, service_role USING (true) WITH CHECK (true)', tbl);
    END LOOP;
END $$;
