from __future__ import annotations

import pytest

from services.sec.mapper import SECConceptMapper
from services.sec.xbrl import SECXBRLService


def test_sec_xbrl_get_concept_units():
    sample_facts = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {
                    "label": "Cash and Cash Equivalents",
                    "description": "Cash and cash equivalents",
                    "units": {
                        "USD": [
                            {"val": 29965000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "end": "2024-09-30", "accn": "0000320193-24-000100"},
                            {"val": 28840000000, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2023-11-03", "end": "2023-09-30", "accn": "0000320193-23-000106"},
                        ]
                    },
                }
            }
        }
    }

    service = SECXBRLService()
    units = service.get_concept_units(sample_facts, ["CashAndCashEquivalentsAtCarryingValue"])
    assert len(units) == 2
    assert units[0]["val"] == 29965000000


def test_sec_concept_mapper_confidence():
    sample_facts = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {
                    "label": "Cash and Cash Equivalents",
                    "units": {
                        "USD": [
                            {"val": 50000000, "fy": 2025, "fp": "Q3", "form": "10-Q", "filed": "2025-08-01", "end": "2025-06-30", "accn": "0001-25-001"}
                        ]
                    },
                }
            }
        }
    }

    metric = SECConceptMapper.map_metric_from_facts(sample_facts, "cash")
    assert metric is not None
    assert metric["metric_name"] == "cash"
    assert metric["value"] == 50000000
    assert metric["confidence"] == "HIGH"
    assert metric["source_concept"] == "CashAndCashEquivalentsAtCarryingValue"
