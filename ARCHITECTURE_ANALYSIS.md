# InvestiCore V2 — Architecture Analysis & Implementation Plan

**Current Date:** 2026-09-08  
**Scope:** SEC-driven fundamental research platform  
**Document:** Architecture Review + Phase 1 Implementation Plan

---

## EXECUTIVE SUMMARY

InvestiCore V1 is a **production-ready investment research journal** with:
- ✅ Company CRUD and versioned analysis workflow
- ✅ Structured research framework (YAML-driven)
- ✅ Scenario modeling (Bear/Base/Bull)
- ✅ Thesis tracking and risk management
- ✅ Market data integration (yfinance)

**Missing:** SEC filing ingestion, financial statement parsing, NCAV/NNWC calculations, catalyst detection, and cigar-butt screening.

**Approach:** Extend InvestiCore WITH A PARALLEL SEC-DRIVEN WORKFLOW instead of rewriting it. This preserves the existing research journal while adding institutional-grade financial data ingestion.

---

## 1. EXISTING TECHNOLOGY STACK

| Component | Library | Version |
|-----------|---------|---------|
| Framework | Streamlit | >=1.39.0 |
| Language | Python | 3.11+ |
| Database | Supabase/PostgreSQL | — |
| Data | pandas | >=2.2.0 |
| Visualization | plotly | >=5.24.0 |
| Configuration | PyYAML | >=6.0.2 |
| Market Data | yfinance | >=0.2.40 |
| Secrets | python-dotenv | >=1.0.1 |
| Testing | pytest | >=8.3.3 |

**Assessment:** ✅ Appropriate for SEC data work. No unnecessary frameworks. Leverage existing patterns.

---

## 2. EXISTING PAGES (Streamlit Navigation)

| Page | Icon | Purpose | Status |
|------|------|---------|--------|
| Dashboard | 📊 | Overview of portfolio & research | Active |
| Companies | 🏢 | Company CRUD, search | Active |
| New Analysis | 📝 | Create/edit versioned analysis | Active |
| Research | 🔎 | Research workflow (in development) | Active |
| Valuation | 💰 | Scenario modeling, expected returns | Active |
| Thesis Journal | 📒 | Historical thesis tracking | Active |
| Settings | ⚙️ | Configuration | Active |

**Impact:** All pages must remain functional. SEC features should integrate via new pages or existing flow (e.g., "SEC Filings" sub-tab in Research).

---

## 3. EXISTING DATABASE SCHEMA (001_initial_schema.sql)

### Core Tables

#### `companies`
```sql
id (UUID, PK)
ticker (TEXT, UNIQUE) — Primary identifier for market data
name, sector, industry, country, description, website
status (Researching|Watchlist|Owned|Buy Candidate|Avoid|Sold|Archived)
created_at, updated_at
```

**Purpose:** Company master record.  
**Gap:** No CIK. Ticker is volatile (can change). Need SEC CIK as canonical ID.

#### `financials`
```sql
id (UUID, PK)
company_id (FK → companies)
fiscal_year, period_type (Annual|Quarterly), fiscal_quarter
revenue, gross_profit, operating_income, net_income, eps
operating_cash_flow, free_cash_flow, capex, rnd, sbc
cash, debt, shares_outstanding
created_at, updated_at
```

**Issue:** Only 12 line items. Missing:
- Balance sheet details (receivables, inventory, goodwill, intangible assets, current assets breakdown, liabilities breakdown, current ratio, equity)
- Cash equivalents & marketable securities
- Share count distinction (basic vs diluted)
- Period-end date (only fiscal_year/quarter stored)
- Source filing attribution
- Confidence / data quality score

#### `analyses`, `analysis_answers`, `scenarios`, `theses`, `thesis_breakers`
```sql
— Full thesis/risk/catalyst system already exists
— Versioning in place (version_number, change_summary)
— Status tracking (Draft|Completed|Archived)
```

**Assessment:** ✅ Reusable. Do not modify core thesis system.

#### `risks`, `moat_assessments`, `thesis_updates`
```sql
— Risk cataloging already present
— Moat scoring framework in place
— Change tracking infrastructure exists
```

**Assessment:** ✅ Can integrate with SEC-derived data.

### Database Strengths
- ✅ UUID PKs & FKs (good for distributed systems)
- ✅ Versioning infrastructure (version_number, previous_analysis_id)
- ✅ Rich thesis model (risks, thesis_breakers, scenarios)
- ✅ Change tracking (thesis_updates)
- ✅ Soft-delete capability (status field)
- ✅ Timestamps on every record

### Database Gaps (for SEC work)
- ❌ No SEC CIK mapping
- ❌ No filing metadata table
- ❌ No raw document storage
- ❌ No financial metrics source attribution
- ❌ No confidence/data quality scoring
- ❌ No period-end date tracking
- ❌ No full balance sheet line items

---

## 4. EXISTING SERVICES

### `financial_fetcher.py` (yfinance integration)
```python
fetch_company_profile(ticker)  # Retrieves market data
_get_val()  # Helper to extract from DataFrame

# Returns: current_price, shares_outstanding, cash, debt (from yfinance)
```

**Assessment:** ✅ Works for market data. NOT for historical financials. Will need to coexist with SEC fetcher.

### `valuation.py` (calculation engine)
```python
calculate_cagr()
calculate_percentage_change()
calculate_future_revenue()
calculate_future_fcf()
calculate_expected_return()
calculate_valuation()  # Full scenario model
```

**Assessment:** ✅ Core logic sound. Will extend with NCAV, NNWC, liquidation value.

### `scenario_engine.py`, `scoring.py`
```python
— Scenario probability modeling
— Score calculation from framework answers
```

**Assessment:** ✅ Reusable patterns. Will add catalyst/NCAV scoring.

### `framework.py` (YAML loader)
```python
load_investment_framework()  # Loads config/investment_framework.yaml
```

**Assessment:** ✅ Can extend to load SEC concept mappings from YAML.

---

## 5. EXISTING REPOSITORIES (Data Access Layer)

| Repository | Purpose |
|------------|---------|
| `company_repository.py` | Company CRUD |
| `analysis_repository.py` | Analysis versioning |
| `financial_repository.py` | Financial data CRUD |
| `scenario_repository.py` | Scenario persistence |
| `growth_driver_repository.py` | Custom metrics |
| `risk_repository.py` | Risk tracking |
| `thesis_breaker_repository.py` | Thesis killer logic |

**Pattern:** Thin wrappers around Supabase table operations.  
**Assessment:** ✅ Reusable pattern. Will create analogous repositories for SEC data.

---

## 6. EXISTING CONFIGURATION

### `config/investment_framework.yaml`
```yaml
sections:
  - id: business
    name: Business
    questions:
      - id: company_what_it_does
        name: What does the company do?
        type: short_text
      # ... 8 more business questions
  
  - id: industry
    name: Industry
    questions:
      # TAM, competitive intensity, regulation, etc.
  
  # — Additional sections for management, valuation, risks, etc.
```

**Assessment:** ✅ Framework is extensible. Can add SEC concept mapping section.

---

## 7. WHAT CAN BE REUSED

| Component | Reuse Plan |
|-----------|-----------|
| Streamlit pages architecture | ✅ Add new pages; don't modify existing |
| Company CRUD | ✅ Extend with SEC CIK mapping |
| Database pattern | ✅ Add SEC tables following same UX (FKs, timestamps, status) |
| Repository pattern | ✅ Create new repositories for SEC data |
| Valuation logic | ✅ Extend with NCAV/NNWC functions |
| Scenario engine | ✅ Reuse for Bear/Base/Bull |
| YAML framework | ✅ Extend for SEC concept mappings |
| Thesis/risk system | ✅ Integrate with SEC insights |
| Testing framework | ✅ Add unit tests for new functions |

---

## 8. WHAT NEEDS MODIFICATION

| Component | Change |
|-----------|--------|
| `companies` table | Add `cik` (SEC) field, keep `ticker` |
| `financials` table | Add 30+ fields for full BS/IS/CF; add source attribution |
| `company_repository.py` | Add CIK lookup methods |
| `financial_repository.py` | Extend to store per-filing, per-concept data |
| `app.py` | Add new Streamlit pages for SEC workflows |
| `requirements.txt` | Add `requests` (or `httpx`) for SEC API; consider `beautifulsoup4` for parsing |

---

## 9. PROPOSED NEW FILE STRUCTURE (Phase 1 — SEC Foundation)

```
services/
├── sec/
│   ├── __init__.py
│   ├── client.py              # SEC Edgar API client (rate-limited, cached)
│   ├── company.py             # Company/CIK resolver (ticker → CIK)
│   ├── submissions.py         # Filing metadata retrieval
│   ├── filings.py             # Download 10-K, 10-Q, 8-K documents
│   └── parser.py              # Extract text/HTML from raw SEC documents
│
├── financial_fetcher.py        # EXISTING — will coexist with SEC
├── valuation.py                # EXISTING — will extend with NCAV/NNWC
└── ...existing services

repositories/
├── sec_repository.py           # SEC company/filing CRUD
├── financial_repository.py      # EXISTING — will extend schema
└── ...existing repositories

config/
├── investment_framework.yaml   # EXISTING
└── sec_xbrl_mappings.yaml     # NEW — Concept mapping config

database/
├── client.py                   # EXISTING
└── store.py                    # EXISTING

supabase/
└── migrations/
    ├── 001_initial_schema.sql           # EXISTING
    ├── 002_sec_foundation.sql           # NEW — SEC tables
    ├── 003_financial_normalization.sql  # NEW — Full B/S, I/S, C/F
    ├── 004_catalyst_engine.sql          # NEW — 8-K & catalysts
    └── 005_ncav_analysis.sql            # NEW — NCAV/NNWC scoring

pages/
├── dashboard.py                # EXISTING
├── companies.py                # EXISTING
├── research.py                 # EXISTING — will extend
├── sec_research/               # NEW — SEC-specific pages
│   ├── __init__.py
│   ├── filings.py              # View SEC filings
│   ├── financials.py           # View parsed financials
│   ├── ncav.py                 # NCAV/NNWC analysis
│   └── catalysts.py            # 8-K catalyst timeline
└── ...existing pages

analysis/
├── valuation/
│   ├── ncav.py                 # NEW — NCAV/NNWC calcs
│   ├── liquidation.py          # NEW — Liquidation value
│   └── valuation.py            # EXISTING — DCF, scenarios
├── catalysts/
│   ├── detector.py             # NEW — 8-K parsing
│   ├── classifier.py           # NEW — Catalyst categorization
│   └── scoring.py              # NEW — Catalyst scoring
└── ...existing analysis

tests/
├── test_sec_client.py          # NEW — SEC API mocks
├── test_ncav.py                # NEW — NCAV calculation unit tests
├── test_catalyst_detector.py   # NEW — 8-K parsing tests
└── ...existing tests
```

---

## 10. DATABASE MIGRATIONS PLAN

### Migration 002 — SEC Foundation
```sql
CREATE TABLE sec_companies (
  id UUID PRIMARY KEY,
  cik TEXT UNIQUE NOT NULL,
  ticker TEXT,
  company_name TEXT NOT NULL,
  sic TEXT,
  state TEXT,
  exchange TEXT,
  status TEXT DEFAULT 'Active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sec_filings (
  id UUID PRIMARY KEY,
  sec_company_id UUID REFERENCES sec_companies(id),
  accession_number TEXT UNIQUE NOT NULL,
  form_type TEXT NOT NULL,
  filing_date DATE NOT NULL,
  report_date DATE NOT NULL,
  period_start DATE,
  period_end DATE,
  fiscal_year INTEGER,
  fiscal_quarter INTEGER,
  primary_document TEXT,
  filing_url TEXT,
  raw_content_location TEXT,  -- e.g., S3 path or local file path
  parsed_status TEXT DEFAULT 'Pending',  -- Pending|Extracted|Manual_Review|Failed
  confidence TEXT DEFAULT 'LOW',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(sec_company_id, accession_number)
);

CREATE TABLE sec_filing_documents (
  id UUID PRIMARY KEY,
  filing_id UUID REFERENCES sec_filings(id),
  document_name TEXT,
  raw_content TEXT,  -- Full HTML/text
  content_hash TEXT,  -- SHA256 for deduplication
  retrieval_timestamp TIMESTAMPTZ,
  source_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sec_companies_ticker ON sec_companies(ticker);
CREATE INDEX idx_sec_companies_cik ON sec_companies(cik);
CREATE INDEX idx_sec_filings_company ON sec_filings(sec_company_id);
CREATE INDEX idx_sec_filings_date ON sec_filings(filing_date);
CREATE INDEX idx_sec_filings_form ON sec_filings(form_type);
```

### Migration 003 — Financial Normalization
```sql
ALTER TABLE financials ADD COLUMN IF NOT EXISTS filing_id UUID;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS period_end DATE;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS source_concept TEXT;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS confidence TEXT DEFAULT 'UNKNOWN';
ALTER TABLE financials ADD COLUMN IF NOT EXISTS is_derived BOOLEAN DEFAULT FALSE;

-- Expand balance sheet line items
ALTER TABLE financials ADD COLUMN IF NOT EXISTS marketable_securities NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS accounts_receivable NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS inventory NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS other_current_assets NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS total_current_assets NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS property_plant_equipment NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS goodwill NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS intangible_assets NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS other_assets NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS total_assets NUMERIC;

-- Liabilities
ALTER TABLE financials ADD COLUMN IF NOT EXISTS accounts_payable NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS short_term_debt NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS total_current_liabilities NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS long_term_debt NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS lease_liabilities NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS other_liabilities NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS total_liabilities NUMERIC;

-- Equity
ALTER TABLE financials ADD COLUMN IF NOT EXISTS preferred_equity NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS common_equity NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS retained_earnings NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS treasury_stock NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS total_equity NUMERIC;

-- Share data
ALTER TABLE financials ADD COLUMN IF NOT EXISTS basic_shares NUMERIC;
ALTER TABLE financials ADD COLUMN IF NOT EXISTS diluted_shares NUMERIC;
```

### Migration 004 — Catalyst Engine
```sql
CREATE TABLE catalysts (
  id UUID PRIMARY KEY,
  company_id UUID NOT NULL REFERENCES companies(id),
  filing_id UUID REFERENCES sec_filings(id),
  catalyst_type TEXT NOT NULL,  -- Asset Sale, Liquidation, Tender Offer, etc.
  title TEXT NOT NULL,
  description TEXT,
  date_identified DATE NOT NULL,
  expected_date DATE,
  probability INTEGER CHECK (probability >= 0 AND probability <= 100),
  estimated_value_impact NUMERIC,
  status TEXT DEFAULT 'Potential',  -- Potential|Announced|Pending|Completed|Delayed|Failed|Invalidated
  source TEXT,  -- e.g., "8-K Item 1.01"
  confidence TEXT DEFAULT 'MEDIUM',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_catalysts_company ON catalysts(company_id);
CREATE INDEX idx_catalysts_date ON catalysts(expected_date);
CREATE INDEX idx_catalysts_status ON catalysts(status);
```

### Migration 005 — NCAV Analysis
```sql
CREATE TABLE ncav_analysis (
  id UUID PRIMARY KEY,
  company_id UUID NOT NULL REFERENCES companies(id),
  filing_id UUID REFERENCES sec_filings(id),
  analysis_date DATE NOT NULL,
  
  -- Inputs
  total_current_assets NUMERIC,
  total_liabilities NUMERIC,
  
  -- NCAV
  ncav NUMERIC,
  ncav_per_share NUMERIC,
  price_ncav_ratio NUMERIC,
  
  -- NNWC with defaults
  cash_value NUMERIC,
  receivables_value NUMERIC,  -- 75% assumption
  inventory_value NUMERIC,     -- 50% assumption
  current_assets_total NUMERIC,
  nnwc NUMERIC,
  nnwc_per_share NUMERIC,
  
  -- Net cash
  cash NUMERIC,
  short_term_investments NUMERIC,
  total_debt NUMERIC,
  net_cash NUMERIC,
  
  -- Haircut assumptions (user-configurable)
  cash_haircut_pct NUMERIC DEFAULT 100,
  receivables_haircut_pct NUMERIC DEFAULT 75,
  inventory_haircut_pct NUMERIC DEFAULT 50,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(company_id, analysis_date)
);

CREATE TABLE liquidation_assumptions (
  id UUID PRIMARY KEY,
  analysis_id UUID REFERENCES ncav_analysis(id),
  company_id UUID REFERENCES companies(id),
  
  cash_recovery_pct NUMERIC DEFAULT 100,
  receivables_recovery_pct NUMERIC DEFAULT 50,
  inventory_recovery_pct NUMERIC DEFAULT 30,
  ppe_recovery_pct NUMERIC DEFAULT 20,
  other_assets_recovery_pct NUMERIC DEFAULT 0,
  goodwill_recovery_pct NUMERIC DEFAULT 0,
  
  liquidation_value NUMERIC,
  liquidation_value_per_share NUMERIC,
  
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ncav_company ON ncav_analysis(company_id);
CREATE INDEX idx_liquidation_analysis ON liquidation_assumptions(analysis_id);
```

---

## 11. NEW DEPENDENCIES

```txt
# Add to requirements.txt
requests>=2.31.0           # SEC API calls (httpx alternative: httpx>=0.24.0)
beautifulsoup4>=4.12.0     # HTML parsing
lxml>=4.9.0                # XML/HTML fast parsing
```

**Rationale:**
- `requests` — Standard, well-tested HTTP client for SEC Edgar
- `beautifulsoup4` + `lxml` — Robust HTML table extraction from 10-K/10-Q
- Already have `pandas` for data transformation
- Don't add XBRL libraries yet (Phase 2+)

---

## 12. IMPLEMENTATION SEQUENCE — PHASE 1 (SEC Foundation)

### Week 1 — Core Infrastructure
1. ✅ Create `services/sec/client.py` — Edgar API wrapper
   - Rate limiting (1 req/sec)
   - Caching (local file or Redis)
   - User-Agent compliance
   - Error handling
   - Logging

2. ✅ Create `services/sec/company.py` — CIK resolution
   - Ticker → CIK lookup (SEC Edgar endpoint)
   - Company metadata retrieval
   - Cache company list

3. ✅ Create database migration 002 (sec_companies, sec_filings, sec_filing_documents)

4. ✅ Create `repositories/sec_repository.py` — Data access for SEC tables

### Week 1 (cont'd) — Filing Retrieval
5. ✅ Create `services/sec/submissions.py` — Filing list + metadata
   - Call Edgar /submissions endpoint
   - Parse JSON response
   - Store in sec_filings

6. ✅ Create `services/sec/filings.py` — Download 10-K, 10-Q, 8-K
   - Download primary document (HTML)
   - Extract raw text
   - Store in sec_filing_documents
   - Prevent re-downloading (check content_hash)

### Week 2 — UI Integration
7. ✅ Create `pages/sec_research/filings.py` — SEC Filing View page
   - Company search → resolve CIK
   - Fetch available filings
   - Display filing list (date, form type, period)
   - Download + store button
   - View raw filing link

8. ✅ Update `pages/companies.py` — Show SEC CIK on company profile

9. ✅ Update `app.py` — Add SEC Research navigation section

### Week 2 (cont'd) — Testing
10. ✅ Create `tests/test_sec_client.py` — Mock SEC API calls
11. ✅ Create `tests/test_sec_company.py` — CIK resolution tests
12. ✅ Manual testing with a real ticker (e.g., META, AAPL)

### Deliverables (Phase 1)
- ✅ User enters TICKER in Streamlit
- ✅ System resolves CIK
- ✅ User clicks "Fetch SEC Filings"
- ✅ 10-K, 10-Q, 8-K for past 3 years downloaded & stored
- ✅ Filing list displayed with dates, form types
- ✅ Raw content accessible from Streamlit
- ✅ No re-downloading on subsequent runs

---

## 13. PHASE 2 — FINANCIAL ENGINE (Preview)

**Phase 2 deliverable:**
- Parse balance sheet, income statement, cash flow from 10-K/10-Q
- Extract 30+ financial metrics
- Store with source attribution (filing_id, concept)
- Display 5-year financial history
- Manual review + override capability

**Files to create:**
- `services/sec/parser.py` — HTML table extraction
- `services/sec/xbrl.py` — XBRL helper (Phase 2.5+)
- `services/sec/concept_mapper.py` — Map XBRL concepts to canonical metrics
- `pages/sec_research/financials.py` — Financial statement viewer
- `repositories/financial_metrics_repository.py` — Detailed metrics CRUD
- Database migration 003 (financial_normalization)

---

## 14. PHASE 3 — NCAV ENGINE (Preview)

**Phase 3 deliverable:**
- NCAV = Current Assets - Total Liabilities
- NCAV/share calculation
- NNWC with configurable haircuts (cash 100%, receivables 75%, inventory 50%)
- Price/NCAV & Price/NNWC ratios
- Cash burn analysis
- Dilution tracking

**Files to create:**
- `analysis/valuation/ncav.py` — NCAV/NNWC formulas
- `analysis/valuation/liquidation.py` — Liquidation value modeling
- `repositories/ncav_repository.py` — Store NCAV snapshots
- `pages/sec_research/ncav.py` — NCAV dashboard
- Database migration 005 (ncav_analysis, liquidation_assumptions)

---

## 15. PHASE 4 — CATALYST ENGINE (Preview)

**Phase 4 deliverable:**
- 8-K item extraction (Item 1.01, 2.01, 2.05, 5.02, 8.01)
- Catalyst detection (asset sale, spinoff, acquisition, management change)
- Catalyst timeline (sorted by expected resolution date)
- Catalyst scoring (probability × magnitude / time)
- Integration with existing thesis system

**Files to create:**
- `services/sec/parser.py` — 8-K item extraction
- `analysis/catalysts/detector.py` — Item → catalyst mapping
- `analysis/catalysts/classifier.py` — Catalyst categorization
- `analysis/catalysts/scoring.py` — Catalyst scoring logic
- `repositories/catalyst_repository.py` — Catalyst CRUD
- `pages/sec_research/catalysts.py` — Catalyst timeline viewer
- Database migration 004 (catalysts table)

---

## 16. WHAT CAN BE REUSED FROM EXISTING CODEBASE

```python
# From services/valuation.py:
calculate_expected_return(current_price, future_price, years)
calculate_percentage_change(start, end)

# Can wrap for NCAV work:
def ncav_to_expected_return(current_price, ncav_per_share, years):
    return calculate_expected_return(current_price, ncav_per_share, years)

# From services/framework.py:
load_investment_framework()

# Can extend to load SEC mappings:
load_sec_xbrl_mappings()

# From repositories pattern:
# All new repositories follow same init + CRUD pattern

# From database/client.py:
get_supabase_client()
get_db_table(table_name)

# Can use directly for new tables
```

---

## 17. TESTING STRATEGY

### Unit Tests (Phase 1+)
```python
# tests/test_sec_client.py
def test_edgar_rate_limit():
    # Verify 1 req/sec compliance

def test_cik_resolution():
    # Mock CIK lookup

def test_filing_download():
    # Mock filing fetch

def test_duplicate_prevention():
    # Verify content_hash prevents re-download

# tests/test_ncav.py
def test_ncav_calculation():
    ncav = ncav(current_assets=1000, liabilities=600)
    assert ncav == 400

def test_nnwc_with_haircuts():
    nnwc = nnwc(
        cash=100, receivables=50, inventory=100, liabilities=80,
        receivables_pct=0.75, inventory_pct=0.50
    )
    # 100 + (50 * 0.75) + (100 * 0.50) - 80 = 127.5

def test_price_ncav_ratio():
    # Test edge cases: zero NCAV, negative equity

def test_cash_burn():
    # Historical FCF → cash runway
```

### Integration Tests
```python
# tests/test_sec_workflow.py
def test_full_workflow():
    # 1. Resolve ticker → CIK
    # 2. Fetch filings
    # 3. Parse balance sheet
    # 4. Calculate NCAV
    # 5. Check expected return
```

### Manual Testing Checklist
- [ ] Streamlit app launches without errors
- [ ] Company search resolves valid tickers (META, AAPL, GOOGL)
- [ ] SEC filing list displays correctly
- [ ] No duplicate downloads on re-run
- [ ] Existing pages (Dashboard, Valuation, Thesis) still work
- [ ] Existing analyses/scenarios unaffected
- [ ] SEC data properly isolated in new tables

---

## 18. DEPLOYMENT CONSIDERATIONS

### Environment Variables
```env
# Existing
SUPABASE_URL=
SUPABASE_KEY=
APP_ENV=development

# New (optional, if using Redis cache)
SEC_CACHE_TYPE=file  # or 'redis'
SEC_CACHE_DIR=.cache/sec
SEC_RATE_LIMIT=1.0   # requests per second
```

### Database Migration
```bash
# Apply migrations in order
supabase migration up  # 001 already applied

# Phase 1
supabase migration up  # Runs 002

# Phase 2
supabase migration up  # Runs 003

# etc.
```

### Local Development
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env with Supabase credentials
cp .env.example .env

# 3. Apply migrations
# (Done automatically by ensure_database() or manual via Supabase CLI)

# 4. Run app
streamlit run app.py

# 5. Navigate to new "SEC Research" section
```

---

## 19. KNOWN LIMITATIONS (Phase 1)

1. **No real-time:** SEC Edgar data is delayed (only updated after close)
2. **No XBRL yet:** Phase 1 uses HTML table extraction (less accurate)
3. **No earnings calls:** Transcripts require separate data source
4. **No AI summarization:** Phase 1 is pure extraction
5. **No multi-class shares:** Simplifies share count handling
6. **No foreign GAAP:** Only US 10-K/10-Q/8-K (no 20-F/6-K)
7. **No insider trades:** Form 4 parsing deferred to Phase 7+
8. **No activist tracking:** Manual research required

**Impact:** Can still build a functional NCAV/cigar-butt screener in Phase 1.

---

## 20. IMPLEMENTATION RISKS & MITIGATIONS

| Risk | Mitigation |
|------|-----------|
| Breaking existing pages | Parallel development; new tables only; no ALTER on core tables early |
| SEC Edgar rate limit | Implement 1 req/sec + cache; test with mock data |
| Parsing instability | Use BeautifulSoup + manual QA; versioned parser (parse_version field) |
| Data quality issues | Confidence scores + manual_review flag; never auto-save if LOW confidence |
| Database migration failures | Test migrations locally; version migrations; allow rollback |
| Performance (large financials history) | Index on company_id + period_end; pagination in UI |

---

## 21. SUCCESS CRITERIA — PHASE 1

A user can:
1. ✅ Search a ticker (e.g., "META")
2. ✅ See resolved CIK (e.g., "1326801")
3. ✅ Click "Fetch SEC Filings"
4. ✅ View list of 10-K, 10-Q, 8-K (past 3 years)
5. ✅ Click filing → view raw HTML/text in Streamlit
6. ✅ Second run: no redundant downloads (cached)
7. ✅ Add notes to filing in existing thesis system
8. ✅ Existing analyses/valuations unaffected

**Acceptance:** Functional for META, AAPL, GOOGL (real SEC data, no mocking).

---

## 22. NEXT STEPS (For User)

### Immediate
1. Review this architecture document.
2. Confirm Phase 1 scope aligns with goals.
3. Approve new dependencies (requests, beautifulsoup4).

### Then (I will implement)
1. Create database migrations 002-005 (in sequence).
2. Implement services/sec/ layer.
3. Implement repositories/sec_repository.py.
4. Create pages/sec_research/ pages.
5. Update app.py navigation.
6. Write unit + integration tests.
7. Manual QA with real tickers.
8. Document SEC workflow in README.

### Estimated Time
- Phase 1 (SEC Foundation): **6-8 hours**
- Phase 2 (Financial Engine): **8-10 hours**
- Phase 3 (NCAV): **4-6 hours**
- Phase 4 (Catalyst): **4-6 hours**
- Phase 5+ (Screening, Monitoring): **8-12 hours**

---

## 23. DEFINITION OF SUCCESS (Full V2)

A professional investment researcher can:

1. ✅ Enter a ticker
2. ✅ Auto-fetch company profile + CIK
3. ✅ Auto-import SEC filings (10-K, 10-Q, 8-K)
4. ✅ View full financial statements (5 years)
5. ✅ Review NCAV / NNWC / Price-to-NCAV
6. ✅ Analyze cash burn + dilution
7. ✅ Review recent 8-K catalysts
8. ✅ Build Bear/Base/Bull valuation
9. ✅ Calculate expected return
10. ✅ Define thesis + risks + thesis killers
11. ✅ Save investment thesis
12. ✅ Get alerts on new SEC filings
13. ✅ Track thesis changes over time
14. ✅ Access evidence links for every number

**Result:** Professional research dossier, not just a stock quote.

---

## 24. QUESTIONS FOR USER

1. **Scope:** Implement Phase 1 only now, or full v1-5 roadmap?
2. **Parsing:** HTML-first (Phase 1) or wait for XBRL (Phase 2)?
3. **Caching:** File-based cache or Supabase table?
4. **Rate limiting:** Strict 1 req/sec or more lenient?
5. **Test data:** Mock filings or real Edgar calls?

---

## DOCUMENT HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-09-08 | AI Assistant | Initial architecture review & Phase 1 plan |

---

**End of Architecture Analysis Document.**
