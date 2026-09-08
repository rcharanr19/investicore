from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository
from repositories.financial_repository import FinancialRepository
from services.sec.statements import SECStatementReconstructor


@pytest.fixture
def sample_xbrl_facts():
    return {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "units": {
                        "USD": [
                            {"val": 100000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "start": "2024-01-01", "accn": "0001-25-001"},
                            {"val": 90000000, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01", "end": "2023-12-31", "start": "2023-01-01", "accn": "0001-24-001"},
                            {"val": 80000000, "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-01", "end": "2022-12-31", "start": "2022-01-01", "accn": "0001-23-001"},
                            {"val": 28000000, "fy": 2024, "fp": "Q3", "form": "10-Q", "filed": "2024-11-01", "end": "2024-09-30", "start": "2024-07-01", "accn": "0001-24-003"},
                            {"val": 26000000, "fy": 2024, "fp": "Q2", "form": "10-Q", "filed": "2024-08-01", "end": "2024-06-30", "start": "2024-04-01", "accn": "0001-24-002"},
                        ]
                    },
                },
                "CostOfGoodsAndServicesSold": {
                    "label": "Cost of Goods Sold",
                    "units": {
                        "USD": [
                            {"val": 40000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "start": "2024-01-01", "accn": "0001-25-001"},
                        ]
                    },
                },
                "AssetsCurrent": {
                    "label": "Current Assets",
                    "units": {
                        "USD": [
                            {"val": 60000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "accn": "0001-25-001"},
                        ]
                    },
                },
                "Liabilities": {
                    "label": "Total Liabilities",
                    "units": {
                        "USD": [
                            {"val": 25000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "accn": "0001-25-001"},
                        ]
                    },
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "label": "Cash",
                    "units": {
                        "USD": [
                            {"val": 20000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "accn": "0001-25-001"},
                        ]
                    },
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "label": "Operating Cash Flow",
                    "units": {
                        "USD": [
                            {"val": 30000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "start": "2024-01-01", "accn": "0001-25-001"},
                        ]
                    },
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "label": "CapEx",
                    "units": {
                        "USD": [
                            {"val": 8000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "start": "2024-01-01", "accn": "0001-25-001"},
                        ]
                    },
                },
            }
        }
    }


def test_discover_periods(sample_xbrl_facts):
    reconstructor = SECStatementReconstructor()
    annuals, quarterlies = reconstructor._discover_periods(sample_xbrl_facts)

    assert len(annuals) == 3
    assert annuals[0]["fiscal_year"] == 2024
    assert annuals[1]["fiscal_year"] == 2023
    assert annuals[2]["fiscal_year"] == 2022

    assert len(quarterlies) == 2
    assert quarterlies[0]["fiscal_period"] == "Q3"
    assert quarterlies[1]["fiscal_period"] == "Q2"


def test_reconstruct_statements_for_period(sample_xbrl_facts):
    reconstructor = SECStatementReconstructor()
    period = {
        "period_type": "Annual",
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "period_end": "2024-12-31",
        "period_start": "2024-01-01",
    }

    metrics = reconstructor.reconstruct_statements_for_period(sample_xbrl_facts, period)

    # Core reported
    assert metrics["revenue"]["value"] == 100000000
    assert metrics["cogs"]["value"] == 40000000
    assert metrics["cash"]["value"] == 20000000

    # Derived safeguards
    assert metrics["gross_profit"]["value"] == 60000000  # 100M - 40M
    assert metrics["gross_profit"]["is_derived"] is True
    assert metrics["free_cash_flow"]["value"] == 22000000  # 30M OCF - 8M CapEx
    assert metrics["ncav"]["value"] == 35000000  # 60M Current Assets - 25M Liabilities


def test_ingest_and_save_full_history(sample_xbrl_facts):
    mock_xbrl = MagicMock()
    mock_xbrl.get_company_facts.return_value = sample_xbrl_facts

    reconstructor = SECStatementReconstructor(xbrl_service=mock_xbrl)
    period_repo = FinancialPeriodRepository()
    metric_repo = FinancialMetricRepository()
    fin_repo = FinancialRepository()

    result = reconstructor.ingest_and_save_full_history(
        company_id="comp-100",
        cik="0001000000",
        period_repository=period_repo,
        metric_repository=metric_repo,
        financial_repository=fin_repo,
        annual_limit=5,
        quarterly_limit=8,
    )

    assert result["status"] == "success"
    assert result["annual_periods_count"] == 3
    assert result["quarterly_periods_count"] == 2
    assert result["total_metrics_saved"] > 0

    # Verify period repo
    periods = period_repo.list_by_company("comp-100")
    assert len(periods) == 5

    # Verify core financial repo was populated with $M values
    ann_fin = fin_repo.get_by_company("comp-100", period_type="Annual")
    assert len(ann_fin) == 3
    # 2024 revenue in millions = 100.0
    fy24 = next(f for f in ann_fin if f["fiscal_year"] == 2024)
    assert fy24["revenue"] == 100.0
    assert fy24["free_cash_flow"] == 22.0
    assert fy24["gross_profit"] == 60.0
