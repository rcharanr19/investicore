-- Migration 004: Re-enable RLS for SEC research and filing intelligence tables.
-- Keeps current application access explicit through policies instead of disabling RLS.

CREATE SCHEMA IF NOT EXISTS investicore;
SET search_path TO investicore, public;

ALTER TABLE investicore.sec_filings ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.filing_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.financial_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.financial_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.ncav_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.catalysts ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.valuation_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.research_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.management_compensation ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.ownership_filings ENABLE ROW LEVEL SECURITY;
ALTER TABLE investicore.insider_transactions ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA investicore TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA investicore TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA investicore TO anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA investicore TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA investicore GRANT ALL ON TABLES TO anon, authenticated, service_role;

DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'sec_filings',
        'filing_documents',
        'financial_periods',
        'financial_metrics',
        'ncav_analysis',
        'catalysts',
        'valuation_snapshots',
        'research_alerts',
        'management_compensation',
        'ownership_filings',
        'insider_transactions'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "Allow all access" ON investicore.%I', tbl);
        EXECUTE format('CREATE POLICY "Allow all access" ON investicore.%I FOR ALL TO anon, authenticated, service_role USING (true) WITH CHECK (true)', tbl);
    END LOOP;
END $$;