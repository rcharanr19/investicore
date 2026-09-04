import pandas as pd
from unittest.mock import MagicMock, patch
from services.financial_fetcher import fetch_company_profile, fetch_financial_history, _parse_statements, _get_val


def test_get_val_helper():
    df = pd.DataFrame(
        {"2025-09-30": [100_000_000.0, 5.5]},
        index=["Total Revenue", "Diluted EPS"],
    )
    val = _get_val(df, ["Total Revenue"], "2025-09-30")
    assert val == 100.0  # $100M

    eps = _get_val(df, ["Diluted EPS"], "2025-09-30", is_per_share=True)
    assert eps == 5.5


def test_parse_statements():
    income_df = pd.DataFrame(
        {
            "2025-09-30": [500_000_000.0, 300_000_000.0, 150_000_000.0, 120_000_000.0, 4.5],
        },
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "Diluted EPS"],
    )
    cashflow_df = pd.DataFrame(
        {
            "2025-09-30": [110_000_000.0, -30_000_000.0],
        },
        index=["Free Cash Flow", "Capital Expenditure"],
    )
    balance_df = pd.DataFrame(
        {
            "2025-09-30": [50_000_000.0, 20_000_000.0, 100_000_000.0],
        },
        index=["Cash And Cash Equivalents", "Total Debt", "Ordinary Shares Number"],
    )

    annual_recs = _parse_statements(income_df, cashflow_df, balance_df, period_type="Annual")
    assert len(annual_recs) == 1
    rec = annual_recs[0]
    assert rec["fiscal_year"] == 2025
    assert rec["period_type"] == "Annual"
    assert rec["revenue"] == 500.0
    assert rec["gross_profit"] == 300.0
    assert rec["operating_income"] == 150.0
    assert rec["net_income"] == 120.0
    assert rec["eps"] == 4.5
    assert rec["free_cash_flow"] == 110.0
    assert rec["capex"] == 30.0
    assert rec["cash"] == 50.0
    assert rec["debt"] == 20.0


@patch("yfinance.Ticker")
def test_fetch_company_profile_mocked(mock_ticker):
    mock_inst = MagicMock()
    mock_inst.info = {
        "longName": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "United States",
        "website": "https://www.nvidia.com",
        "longBusinessSummary": "NVIDIA GPU pioneer",
        "currentPrice": 125.50,
        "sharesOutstanding": 24_000_000_000,
        "totalCash": 30_000_000_000,
        "totalDebt": 10_000_000_000,
    }
    mock_ticker.return_value = mock_inst

    prof = fetch_company_profile("NVDA")
    assert prof is not None
    assert prof["ticker"] == "NVDA"
    assert prof["name"] == "NVIDIA Corporation"
    assert prof["sector"] == "Technology"
    assert prof["current_price"] == 125.50
    assert prof["cash"] == 30000.0
    assert prof["debt"] == 10000.0


def test_fetch_company_profile_empty():
    assert fetch_company_profile("") is None
