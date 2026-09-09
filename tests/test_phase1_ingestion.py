from datetime import date, timedelta
import inspect

from services.sec.phase1_ingestion import (
    Phase1SECIngestionService,
    all_company_facts,
    annual_filing_accessions,
    calculate_ttm_from_quarterly_records,
    company_facts_for_filing,
    filing_storage_path,
    facts_for_new_accessions,
)
from services.sec.financial_interpretation import reconstruct_discrete_quarter
from services.sec.financial_validation import validate_balance_sheet, validate_cash_flow, validate_share_change


def test_filing_storage_path_is_deterministic_and_provenance_readable():
    path = filing_storage_path("1326801", "10-K/A", "0001326801-26-000123", "meta-20251231.htm")
    assert path == "0001326801/10-K-A/000132680126000123/meta-20251231.htm"


def test_selected_filings_targets_history_quarters_and_recent_events():
    today = date.today()
    annuals = [
        {"accession_number": f"annual-{year}", "form_type": "10-K", "filing_date": f"{year + 1}-02-01"}
        for year in range(2000, 2017)
    ]
    quarters = [
        {"accession_number": f"quarter-{number}", "form_type": "10-Q", "filing_date": f"2026-0{number}-01"}
        for number in range(1, 10)
    ]
    recent_event = {"accession_number": "recent-event", "form_type": "8-K", "filing_date": today.isoformat()}
    old_event = {"accession_number": "old-event", "form_type": "8-K", "filing_date": (today - timedelta(days=800)).isoformat()}

    selected = Phase1SECIngestionService._selected_filings(annuals + quarters + [recent_event, old_event])
    accessions = {filing["accession_number"] for filing in selected}
    assert len([filing for filing in selected if filing["form_type"] == "10-K"]) == 17
    assert len([filing for filing in selected if filing["form_type"] == "10-Q"]) == 8
    assert "recent-event" in accessions
    assert "old-event" not in accessions


def test_annual_selection_uses_distinct_reporting_periods_and_prefers_amendment():
    filings = [
        {"accession_number": "original", "form_type": "10-K", "filing_date": "2025-01-30", "report_date": "2024-12-31"},
        {"accession_number": "amendment", "form_type": "10-K/A", "filing_date": "2025-02-10", "report_date": "2024-12-31"},
        {"accession_number": "oldest", "form_type": "10-K", "filing_date": "2014-01-30", "report_date": "2013-12-31"},
    ]
    selected = Phase1SECIngestionService._selected_filings(filings)
    assert {filing["accession_number"] for filing in selected} == {"amendment", "oldest"}
    assert annual_filing_accessions(filings) == {"amendment", "oldest"}


def test_ttm_requires_four_quarters_and_preserves_unknown_values():
    three_quarters = [{"period_end": f"2026-0{month}-30", "metrics": {"revenue": 100}} for month in range(1, 4)]
    assert calculate_ttm_from_quarterly_records(three_quarters) is None

    records = three_quarters + [{"period_end": "2026-04-30", "metrics": {"revenue": 125, "cash": 40}}]
    result = calculate_ttm_from_quarterly_records(records)
    assert result is not None
    assert result["revenue"] == 425.0
    assert result["cash"] == 40


def test_ytd_facts_are_reconstructed_as_discrete_quarters():
    facts = [
        {"start": "2026-01-01", "end": "2026-03-31", "val": 100, "filed": "2026-05-01"},
        {"start": "2026-01-01", "end": "2026-06-30", "val": 230, "filed": "2026-08-01"},
        {"start": "2026-01-01", "end": "2026-09-30", "val": 360, "filed": "2026-11-01"},
        {"start": "2026-01-01", "end": "2026-12-31", "val": 500, "filed": "2027-02-01"},
    ]
    results = [
        reconstruct_discrete_quarter("revenue", period, end, facts)
        for period, end in (("Q1", "2026-03-31"), ("Q2", "2026-06-30"), ("Q3", "2026-09-30"), ("Q4", "2026-12-31"))
    ]
    assert [result["value"] for result in results] == [100.0, 130.0, 130.0, 140.0]
    assert [result["method"] for result in results] == ["direct_quarter", "ytd_minus_prior_ytd", "ytd_minus_prior_ytd", "annual_minus_q3_ytd"]


def test_normalized_period_uses_the_actual_period_end_year():
    period = {"period_type": "Annual", "fiscal_year": 2016, "fiscal_period": "FY", "period_end": "2014-12-31"}
    assert int(period["period_end"][:4]) == 2014


def test_structured_financial_validations_cover_balances_cash_and_shares():
    assert validate_balance_sheet(100, 60, 40)["validation_status"] == "PASS"
    assert validate_balance_sheet(100, 50, 40)["validation_status"] == "WARNING"
    assert validate_cash_flow(10, 5, -2, 3, 16)["validation_status"] == "PASS"
    assert validate_cash_flow(10, 5, -2, 3, 20)["validation_status"] == "WARNING"
    assert validate_share_change(100, 200)["validation_status"] == "REQUIRES_REVIEW"


def test_company_facts_are_preserved_unchanged_for_the_matching_accession():
    facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"accn": "target", "val": 230, "start": "2026-01-01", "end": "2026-06-30", "fy": 2026, "fp": "Q2", "form": "10-Q", "filed": "2026-08-01"},
        {"accn": "other", "val": 99, "end": "2026-06-30"},
    ]}}}}}
    rows = company_facts_for_filing("company", "filing", "target", "320193", facts)
    assert len(rows) == 1
    assert rows[0]["fact_value"] == 230
    assert rows[0]["taxonomy"] == "us-gaap"
    assert rows[0]["xbrl_tag"] == "Revenues"
    assert rows[0]["instant_date"] is None


def test_all_company_facts_preserves_available_facts_beyond_selected_window():
    facts = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"accn": "selected", "val": 200, "end": "2025-12-31"},
        {"accn": "historic", "val": 100, "end": "2010-12-31"},
    ]}}}}}
    rows = all_company_facts("company", "320193", facts, {"selected": "filing-id"})
    assert len(rows) == 2
    assert rows[0]["filing_id"] == "filing-id"
    assert rows[1]["filing_id"] is None


def test_raw_fact_incremental_refresh_only_persists_new_accessions():
    rows = [
        {"accession_number": "existing", "fact_value": 100},
        {"accession_number": "new", "fact_value": 120},
        {"accession_number": None, "fact_value": 50},
    ]
    assert facts_for_new_accessions(rows, {"existing"}) == [{"accession_number": "new", "fact_value": 120}]


def test_primary_html_download_is_opt_in_for_refreshes():
    parameter = inspect.signature(Phase1SECIngestionService.refresh_company_sec_data).parameters["download_primary_documents"]
    assert parameter.default is False


def test_background_primary_html_worker_deduplicates_by_company(monkeypatch):
    started = []

    class ImmediateThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            started.append(True)

    monkeypatch.setattr("services.sec.phase1_ingestion.threading.Thread", ImmediateThread)
    assert Phase1SECIngestionService.start_primary_html_download("company-background-test", "320193") is True
    assert Phase1SECIngestionService.start_primary_html_download("company-background-test", "320193") is False
    from services.sec.phase1_ingestion import _BACKGROUND_PRIMARY_DOWNLOADS
    _BACKGROUND_PRIMARY_DOWNLOADS.discard("company-background-test")
    assert len(started) == 1