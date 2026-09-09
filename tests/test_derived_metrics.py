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