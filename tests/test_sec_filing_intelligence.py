from __future__ import annotations

import pytest

from repositories.catalyst_repository import CatalystRepository
from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository
from repositories.insider_repository import InsiderTransactionsRepository
from repositories.management_repository import ManagementCompensationRepository
from repositories.ownership_repository import OwnershipFilingsRepository
from repositories.sec_filing_repository import SECFilingRepository
from services.sec.cross_filing import SECCrossFilingEngine
from services.sec.insiders import SECInsiderService
from services.sec.management import SECManagementService
from services.sec.ownership import SECOwnershipService
from services.sec.taxonomy import SECFilingTaxonomyService


def test_sec_taxonomy_classification():
    service = SECFilingTaxonomyService()

    # 10-K -> annual_financial
    meta_10k = service.get_metadata("10-K")
    assert meta_10k.category == "annual_financial"
    assert meta_10k.financial_relevance == "HIGH"
    assert "What does the company own?" in meta_10k.key_questions

    # 10-Q -> quarterly_financial
    meta_10q = service.get_metadata("10-Q")
    assert meta_10q.category == "quarterly_financial"
    assert meta_10q.financial_relevance == "HIGH"

    # 8-K -> material_event
    meta_8k = service.get_metadata("8-K")
    assert meta_8k.category == "material_event"
    assert meta_8k.catalyst_relevance == "HIGH"

    # DEF 14A -> management_governance
    meta_proxy = service.get_metadata("DEF 14A")
    assert meta_proxy.category == "management_governance"
    assert meta_proxy.management_relevance == "HIGH"

    # 13D -> ownership_activist
    meta_13d = service.get_metadata("13D")
    assert meta_13d.category == "ownership_activist"
    assert meta_13d.catalyst_relevance == "HIGH"

    # Form 4 -> insider_transaction
    meta_f4 = service.get_metadata("4")
    assert meta_f4.category == "insider_transaction"


def test_management_alignment_score_and_repository():
    service = SECManagementService()
    repo = ManagementCompensationRepository()

    # High alignment case: 15% ownership, 80% equity comp, TSR/ROIC metrics, separated chair
    res = service.calculate_alignment_score(
        insider_ownership_pct=15.0,
        equity_comp_ratio=0.80,
        has_per_share_metrics=True,
        ceo_chair_separated=True,
        has_golden_parachute=False,
    )
    assert res["management_alignment_score"] == 100.0
    assert "Strong Shareholder Alignment" in res["rating"]

    # Poor alignment: 0.5% ownership, cash comp, combined CEO/Chair, golden parachute
    poor_res = service.calculate_alignment_score(
        insider_ownership_pct=0.2,
        equity_comp_ratio=0.10,
        has_per_share_metrics=False,
        ceo_chair_separated=False,
        has_golden_parachute=True,
    )
    assert poor_res["management_alignment_score"] < 30.0

    # Repo CRUD
    rec = repo.create({
        "company_id": "comp-mgmt-1",
        "executive_name": "Jane Doe",
        "title": "CEO",
        "total_compensation": 5000000.0,
        "ownership_pct": 5.5,
    })
    assert rec["id"] is not None
    listed = repo.list_by_company("comp-mgmt-1")
    assert len(listed) == 1
    assert listed[0]["executive_name"] == "Jane Doe"


def test_ownership_13d_and_activist_extraction():
    filing_repo = SECFilingRepository()
    own_repo = OwnershipFilingsRepository()
    cat_repo = CatalystRepository()

    filing_repo.create({
        "company_id": "comp-own-1",
        "accession_number": "0001-13d-001",
        "form_type": "13D",
        "filing_date": "2026-08-20",
    })

    service = SECOwnershipService()
    extracted = service.extract_ownership_from_filings(
        company_id="comp-own-1",
        filing_repo=filing_repo,
        ownership_repo=own_repo,
        catalyst_repo=cat_repo,
    )

    assert len(extracted) == 1
    assert extracted[0]["is_activist"] is True

    # Check catalyst was created
    cats = cat_repo.list_by_company("comp-own-1")
    assert len(cats) == 1
    assert "Activist" in cats[0]["catalyst_type"]


def test_insider_transactions_and_sentiment():
    filing_repo = SECFilingRepository()
    ins_repo = InsiderTransactionsRepository()
    service = SECInsiderService()

    # Create Form 4 filing
    filing_repo.create({
        "company_id": "comp-ins-1",
        "accession_number": "0001-f4-001",
        "form_type": "4",
        "filing_date": "2026-08-25",
    })

    extracted = service.extract_insider_transactions_from_filings(
        company_id="comp-ins-1",
        filing_repo=filing_repo,
        insider_repo=ins_repo,
    )
    assert len(extracted) == 1
    assert extracted[0]["is_open_market_purchase"] is True

    # Sentiment calculation
    sentiment = service.calculate_insider_sentiment(ins_repo.list_by_company("comp-ins-1"))
    assert "Buying" in sentiment["sentiment"]
    assert sentiment["open_market_buys_count"] == 1


def test_cross_filing_engine_timeline_and_synthesis():
    filing_repo = SECFilingRepository()
    period_repo = FinancialPeriodRepository()
    metric_repo = FinancialMetricRepository()
    cat_repo = CatalystRepository()
    mgmt_repo = ManagementCompensationRepository()
    own_repo = OwnershipFilingsRepository()
    ins_repo = InsiderTransactionsRepository()

    cid = "comp-cross-1"

    # Seed 10-K, 10-Q, 8-K, 13D, 4
    filing_repo.create({"company_id": cid, "accession_number": "acc-10k", "form_type": "10-K", "filing_date": "2026-03-01"})
    filing_repo.create({"company_id": cid, "accession_number": "acc-10q", "form_type": "10-Q", "filing_date": "2026-06-01"})
    filing_repo.create({"company_id": cid, "accession_number": "acc-8k", "form_type": "8-K", "filing_date": "2026-07-01", "items": "2.01"})
    filing_repo.create({"company_id": cid, "accession_number": "acc-13d", "form_type": "13D", "filing_date": "2026-07-15"})
    filing_repo.create({"company_id": cid, "accession_number": "acc-f4", "form_type": "4", "filing_date": "2026-08-01"})

    # Seed activist & asset sale catalyst
    cat_repo.create({"company_id": cid, "catalyst_type": "Asset Sale / Divestiture", "title": "Item 2.01 Asset Sale", "source": "8-K"})
    cat_repo.create({"company_id": cid, "catalyst_type": "Activist Campaign", "title": "13D Campaign", "source": "Schedule 13D"})

    # Seed insider buying
    ins_repo.create({"company_id": cid, "reporting_person": "CEO", "transaction_code": "P", "is_open_market_purchase": True, "total_value": 500000.0})

    # Seed management ownership
    mgmt_repo.create({"company_id": cid, "executive_name": "CEO", "title": "CEO", "ownership_pct": 5.0, "total_compensation": 3000000.0})

    engine = SECCrossFilingEngine(
        filing_repo=filing_repo,
        period_repo=period_repo,
        metric_repo=metric_repo,
        catalyst_repo=cat_repo,
        management_repo=mgmt_repo,
        ownership_repo=own_repo,
        insider_repo=ins_repo,
    )

    timeline = engine.build_unified_timeline(cid, filter_category="all")
    assert len(timeline) == 5

    synthesis = engine.generate_cross_filing_synthesis(cid)
    assert len(synthesis) >= 2
    types = {s["type"] for s in synthesis}
    assert "HIGH_CONVICTION_CATALYST" in types
    assert "INSIDER_CONVICTION" in types
    assert "EXECUTIVE_ALIGNMENT" in types
