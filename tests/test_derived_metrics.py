import pytest
import pandas as pd

from services.financial_fetcher import closes_on_or_before
from services.derived_metrics import calculate_period_metrics
from services.sec.activity import parse_form4_xml


def test_calculate_phase2_profitability_share_and_market_ratios():
    current = {
        "revenue": 100, "operating_income": 20, "net_income": 15, "operating_cash_flow": 25, "free_cash_flow": 18,
        "sbc": 4, "total_debt": 30, "total_equity": 60, "total_assets": 120, "cash": 10, "marketable_securities": 5,
        "shares_diluted": 10, "total_current_assets": 40, "current_liabilities": 20, "pretax_income": 20, "income_tax": 5,
    }
    prior = {"shares_diluted": 8, "total_equity": 50, "total_assets": 100, "total_debt": 25, "cash": 8, "marketable_securities": 2}
    ratios = calculate_period_metrics(current, prior, market_price=100)
    assert ratios["operating_margin"] == 0.2
    assert ratios["shares_yoy_change"] == 0.25
    assert ratios["sbc_to_revenue"] == 0.04
    assert ratios["debt_to_equity"] == 0.5
    assert ratios["price_to_fcf"] == 1000 / 18
    assert ratios["gross_margin"] is None
    assert ratios["net_margin"] == 0.15
    assert ratios["cfo_to_net_income"] == 25 / 15
    assert ratios["revenue_growth"] is None
    assert ratios["ev_to_fcf"] == (1000 + 30 - 10 - 5) / 18


def test_calculate_growth_and_margin_metrics_when_prior_values_exist():
    ratios = calculate_period_metrics(
        {"revenue": 120, "gross_profit": 72, "operating_income": 24, "net_income": 18, "operating_cash_flow": 30, "free_cash_flow": 21, "sbc": 6},
        {"revenue": 100, "gross_profit": 55, "operating_income": 20, "net_income": 15, "operating_cash_flow": 25, "free_cash_flow": 18, "sbc": 4},
    )
    assert ratios["revenue_growth"] == pytest.approx(0.2)
    assert ratios["gross_margin"] == 0.6
    assert ratios["operating_margin"] == 0.2
    assert ratios["free_cash_flow_growth"] == pytest.approx(21 / 18 - 1)
    assert ratios["ocf_margin"] == 0.25
    assert ratios["sbc_to_revenue"] == 0.05


def test_calculate_per_share_working_capital_and_asset_value_metrics():
    current = {"revenue": 100, "free_cash_flow": 20, "total_equity": 50, "goodwill": 5, "intangibles": 5, "shares_diluted": 10, "cash": 15, "marketable_securities": 5, "total_debt": 10, "total_current_assets": 60, "current_liabilities": 30, "accounts_receivable": 20, "inventory": 10, "accounts_payable": 8, "cogs": 40, "ncav": 30, "nnwc": 25}
    prior = {"accounts_receivable": 10, "inventory": 8, "accounts_payable": 6}
    ratios = calculate_period_metrics(current, prior)
    assert ratios["book_value_per_share"] == 5
    assert ratios["tangible_book_value_per_share"] == 4
    assert ratios["fcf_per_share"] == 2
    assert ratios["quick_ratio"] == pytest.approx(4 / 3)
    assert ratios["dso"] == pytest.approx(15 / 100 * 365)
    assert ratios["ncav_per_share"] == 3


def test_negative_earnings_or_cash_flow_do_not_create_price_ratios():
    ratios = calculate_period_metrics({"net_income": -1, "free_cash_flow": 0, "operating_cash_flow": 0, "shares_diluted": 10}, market_price=100)
    assert ratios["price_to_earnings"] is None
    assert ratios["price_to_fcf"] is None
    assert ratios["price_to_ocf"] is None


def test_form4_parser_uses_actual_transaction_code_and_amounts():
    content = """<ownershipDocument><reportingOwner><reportingOwnerId><rptOwnerName>Jane Executive</rptOwnerName></reportingOwnerId><reportingOwnerRelationship><officerTitle>CEO</officerTitle></reportingOwnerRelationship></reportingOwner><nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>2026-09-01</value></transactionDate><transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>25</value></transactionPricePerShare></transactionAmounts><postTransactionAmounts><sharesOwnedFollowingTransaction><value>1000</value></sharesOwnedFollowingTransaction></postTransactionAmounts><ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
    transaction = parse_form4_xml(content)[0]
    assert transaction["reporting_person"] == "Jane Executive"
    assert transaction["transaction_type"] == "Open market purchase"
    assert transaction["total_value"] == 2500


def test_form4_parser_skips_html_or_malformed_primary_documents():
    assert parse_form4_xml("<html><body>SEC filing index</body></html>") == []
    assert parse_form4_xml("not xml") == []


def test_historical_close_uses_period_end_or_previous_trading_day():
    history = pd.DataFrame({"Close": [100.0, 105.0]}, index=pd.to_datetime(["2024-12-27", "2024-12-31"]))
    closes = closes_on_or_before(history, ["2024-12-29", "2024-12-31"])
    assert closes["2024-12-29"] == ("2024-12-27", 100.0)
    assert closes["2024-12-31"] == ("2024-12-31", 105.0)