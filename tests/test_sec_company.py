from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.sec.company import SECCompanyService, format_cik


def test_format_cik_zero_padding():
    assert format_cik(320193) == "0000320193"
    assert format_cik("320193") == "0000320193"
    assert format_cik("0000320193") == "0000320193"
    assert format_cik(1326801) == "0001326801"
    assert format_cik("") == "0000000000"


def test_sec_company_service_lookup_by_ticker():
    mock_client = MagicMock()
    mock_client.get_json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 1326801, "ticker": "META", "title": "Meta Platforms, Inc."},
        "2": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
    }

    service = SECCompanyService(client=mock_client)
    res = service.get_company_by_ticker("AAPL")
    assert res is not None
    assert res["cik"] == "0000320193"
    assert res["ticker"] == "AAPL"
    assert res["name"] == "Apple Inc."

    # Test lowercase and alt tickers
    res_lower = service.get_company_by_ticker("meta")
    assert res_lower is not None
    assert res_lower["cik"] == "0001326801"

    res_brk = service.get_company_by_ticker("BRK.B")
    assert res_brk is not None
    assert res_brk["cik"] == "0001067983"


def test_sec_company_service_lookup_by_cik():
    mock_client = MagicMock()
    mock_client.get_json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    }

    service = SECCompanyService(client=mock_client)
    res = service.get_company_by_cik("320193")
    assert res is not None
    assert res["ticker"] == "AAPL"


def test_sec_company_search():
    mock_client = MagicMock()
    mock_client.get_json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 1326801, "ticker": "META", "title": "Meta Platforms, Inc."},
        "2": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    }

    service = SECCompanyService(client=mock_client)
    results = service.search_companies("app")
    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
