-- Enable UUID generation extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    country TEXT,
    description TEXT,
    website TEXT,
    status TEXT NOT NULL DEFAULT 'Watchlist' CHECK (status IN ('Researching', 'Watchlist', 'Owned', 'Buy Candidate', 'Avoid', 'Sold', 'Archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    framework_version TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Draft', 'Completed', 'Archived')),
    decision TEXT NOT NULL CHECK (decision IN ('Strong Buy', 'Buy', 'Watch', 'Hold', 'Avoid', 'Sell')),
    confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    overall_score NUMERIC(4,2) CHECK (overall_score >= 0 AND overall_score <= 10),
    notes TEXT,
    previous_analysis_id UUID,
    version_number INTEGER NOT NULL DEFAULT 1,
    change_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analysis_answers (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    section_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    answer_value TEXT,
    numeric_value NUMERIC,
    score_value INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS financials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    period_type TEXT NOT NULL DEFAULT 'Annual',
    fiscal_quarter INTEGER,
    period_label TEXT,
    revenue NUMERIC DEFAULT 0.0,
    gross_profit NUMERIC DEFAULT 0.0,
    operating_income NUMERIC DEFAULT 0.0,
    net_income NUMERIC DEFAULT 0.0,
    eps NUMERIC DEFAULT 0.0,
    operating_cash_flow NUMERIC DEFAULT 0.0,
    free_cash_flow NUMERIC DEFAULT 0.0,
    capex NUMERIC DEFAULT 0.0,
    rnd NUMERIC DEFAULT 0.0,
    sbc NUMERIC DEFAULT 0.0,
    cash NUMERIC DEFAULT 0.0,
    debt NUMERIC DEFAULT 0.0,
    shares_outstanding NUMERIC DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS growth_drivers (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    unit TEXT,
    current_value NUMERIC,
    confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS growth_driver_values (
    id UUID PRIMARY KEY,
    growth_driver_id UUID NOT NULL REFERENCES growth_drivers(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    value NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(growth_driver_id, fiscal_year)
);

CREATE TABLE IF NOT EXISTS moat_assessments (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    score INTEGER CHECK (score >= 1 AND score <= 5),
    evidence TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risks (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    risk TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('Competition', 'Regulation', 'Technology', 'Management', 'Financial', 'Macroeconomic', 'Valuation', 'Capital Allocation', 'Execution', 'Other')),
    probability INTEGER CHECK (probability >= 0 AND probability <= 100),
    impact INTEGER CHECK (impact >= 1 AND impact <= 10),
    time_horizon TEXT,
    mitigation TEXT,
    status TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thesis_breakers (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    condition TEXT NOT NULL,
    metric TEXT,
    operator TEXT,
    threshold NUMERIC,
    current_status TEXT CHECK (current_status IN ('Not Triggered', 'Warning', 'Triggered')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scenarios (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    scenario_name TEXT NOT NULL CHECK (scenario_name IN ('Bear', 'Base', 'Bull')),
    probability INTEGER CHECK (probability >= 0 AND probability <= 100),
    revenue_cagr NUMERIC,
    forecast_period INTEGER,
    terminal_revenue NUMERIC,
    operating_margin NUMERIC,
    fcf_margin NUMERIC,
    terminal_multiple NUMERIC,
    future_fcf NUMERIC,
    enterprise_value NUMERIC,
    equity_value NUMERIC,
    implied_share_price NUMERIC,
    expected_annual_return NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS valuations (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    valuation_name TEXT,
    implied_share_price NUMERIC,
    expected_annual_return NUMERIC,
    scenario_probability INTEGER CHECK (scenario_probability >= 0 AND scenario_probability <= 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS theses (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    investment_thesis TEXT,
    variant_perception TEXT,
    key_investment_drivers TEXT,
    catalysts TEXT,
    key_risks TEXT,
    thesis_breakers TEXT,
    decision TEXT,
    confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thesis_updates (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    previous_analysis_id UUID,
    version_number INTEGER,
    change_summary TEXT,
    changed_assumptions TEXT,
    changed_scores TEXT,
    changed_valuation TEXT,
    changed_decision TEXT,
    changed_thesis TEXT,
    new_risks TEXT,
    removed_risks TEXT,
    triggered_thesis_breakers TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies(ticker);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_analyses_company_id ON analyses(company_id);
CREATE INDEX IF NOT EXISTS idx_analyses_date ON analyses(analysis_date);
CREATE INDEX IF NOT EXISTS idx_analysis_answers_analysis ON analysis_answers(analysis_id);
CREATE INDEX IF NOT EXISTS idx_financials_company_year ON financials(company_id, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_growth_drivers_company ON growth_drivers(company_id);
CREATE INDEX IF NOT EXISTS idx_risks_analysis ON risks(analysis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_breakers_analysis ON thesis_breakers(analysis_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_analysis ON scenarios(analysis_id);

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE financials ENABLE ROW LEVEL SECURITY;
ALTER TABLE growth_drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE growth_driver_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE moat_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE risks ENABLE ROW LEVEL SECURITY;
ALTER TABLE thesis_breakers ENABLE ROW LEVEL SECURITY;
ALTER TABLE scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE valuations ENABLE ROW LEVEL SECURITY;
ALTER TABLE theses ENABLE ROW LEVEL SECURITY;
ALTER TABLE thesis_updates ENABLE ROW LEVEL SECURITY;
