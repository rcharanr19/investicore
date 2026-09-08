from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.sec.submissions import SECSubmissionsService


def test_get_company_details_from_submissions():
    mock_client = MagicMock()
    mock_client.get_json.return_value = {
        "cik": "0000320193",
        "entityType": "operating",
        "sic": "3571",
        "sicDescription": "ELECTRONIC COMPUTERS",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "exchanges": ["Nasdaq"],
        "category": "Large accelerated filer",
        "fiscalYearEnd": "0930",
        "stateOfIncorporation": "CA",
        "addresses": {
            "business": {
                "street1": "ONE APPLE PARK WAY",
                "city": "CUPERTINO",
                "stateOrCountry": "CA",
                "zipCode": "95014",
            }
        },
    }

    service = SECSubmissionsService(client=mock_client)
    details = service.get_company_details("0000320193")
    assert details is not None
    assert details["name"] == "Apple Inc."
    assert details["ticker"] == "AAPL"
    assert details["sic"] == "3571"
    assert details["sic_description"] == "ELECTRONIC COMPUTERS"
    assert "CUPERTINO" in details["business_address"]


def test_get_recent_filings_filtering():
    mock_client = MagicMock()
    mock_client.get_json.return_value = {
        "cik": "0000320193",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-24-000100", "0000320193-24-000050", "0000320193-24-000010"],
                "form": ["10-K", "10-Q", "8-K"],
                "filingDate": ["2024-11-01", "2024-08-02", "2024-05-03"],
                "reportDate": ["2024-09-30", "2024-06-29", "2024-05-02"],
                "primaryDocument": ["aapl-20240930.htm", "aapl-20240629.htm", "aapl-8k.htm"],
                "isXBRL": [1, 1, 0],
                "items": ["", "", "5.02"],
            }
        },
    }

    service = SECSubmissionsService(client=mock_client)
    all_filings = service.get_recent_filings("320193")
    assert len(all_filings) == 3

    # Filter for 10-K only
    ten_k_only = service.get_recent_filings("320193", form_types=["10-K"])
    assert len(ten_k_only) == 1
    assert ten_k_only[0]["form_type"] == "10-K"
    assert ten_k_only[0]["accession_number"] == "0000320193-24-000100"
    assert "https://www.sec.gov/Archives/edgar/data/320193/000032019324000100/aapl-20240930.htm" == ten_k_only[0]["filing_url"]
