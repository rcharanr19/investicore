from __future__ import annotations

from typing import Any

import pandas as pd

METRIC_GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Income statement": [
        ("revenue", "Revenue", "currency"),
        ("cogs", "Cost of goods sold", "currency"),
        ("gross_profit", "Gross profit", "currency"),
        ("operating_expenses", "Operating expenses", "currency"),
        ("operating_income", "Operating income / EBIT", "currency"),
        ("interest_expense", "Interest expense", "currency"),
        ("pretax_income", "Pre-tax income", "currency"),
        ("income_tax", "Income tax expense", "currency"),
        ("net_income", "Net income", "currency"),
        ("eps_diluted", "Diluted EPS", "per_share"),
        ("eps_basic", "Basic EPS", "per_share"),
    ],
    "Cash flow": [
        ("operating_cash_flow", "Operating cash flow", "currency"),
        ("capex", "Capital expenditures", "currency"),
        ("free_cash_flow", "Free cash flow", "currency"),
        ("cash_flow_investing", "Net cash from investing", "currency"),
        ("cash_flow_financing", "Net cash from financing", "currency"),
        ("sbc", "Stock-based compensation", "currency"),
    ],
    "Balance sheet": [
        ("cash", "Cash & cash equivalents", "currency"),
        ("marketable_securities", "Marketable securities", "currency"),
        ("accounts_receivable", "Accounts receivable", "currency"),
        ("inventory", "Inventory", "currency"),
        ("other_current_assets", "Other current assets", "currency"),
        ("total_current_assets", "Total current assets", "currency"),
        ("ppe", "Property, plant & equipment", "currency"),
        ("goodwill", "Goodwill", "currency"),
        ("intangibles", "Intangible assets", "currency"),
        ("other_assets", "Other non-current assets", "currency"),
        ("total_assets", "Total assets", "currency"),
        ("accounts_payable", "Accounts payable", "currency"),
        ("current_liabilities", "Total current liabilities", "currency"),
        ("short_term_debt", "Short-term debt", "currency"),
        ("long_term_debt", "Long-term debt", "currency"),
        ("lease_liabilities", "Lease liabilities", "currency"),
        ("total_liabilities", "Total liabilities", "currency"),
        ("total_equity", "Shareholders' equity", "currency"),
    ],
    "Per share & capital structure": [
        ("shares_outstanding", "Period-end shares", "shares"),
        ("shares_diluted", "Diluted shares", "shares"),
        ("eps_diluted", "Diluted EPS", "per_share"),
        ("eps_basic", "Basic EPS", "per_share"),
    ],
    "Growth & margins": [
        ("revenue_growth", "Revenue growth", "percentage"),
        ("gross_profit_growth", "Gross profit growth", "percentage"),
        ("operating_income_growth", "EBIT growth", "percentage"),
        ("net_income_growth", "Net income growth", "percentage"),
        ("free_cash_flow_growth", "Free cash flow growth", "percentage"),
        ("gross_margin", "Gross margin", "percentage"),
        ("operating_margin", "Operating margin", "percentage"),
        ("net_margin", "Net margin", "percentage"),
        ("ocf_margin", "Operating cash flow margin", "percentage"),
        ("fcf_margin", "Free cash flow margin", "percentage"),
    ],
    "Profitability & returns": [
        ("roe", "ROE", "percentage"),
        ("roa", "ROA", "percentage"),
        ("roic", "ROIC", "percentage"),
        ("cfo_to_net_income", "CFO / net income", "percentage"),
        ("fcf_to_net_income", "FCF / net income", "percentage"),
    ],
    "Financial strength": [
        ("net_debt", "Net debt", "currency"),
        ("current_ratio", "Current ratio", "multiple"),
        ("debt_to_equity", "Debt / equity", "multiple"),
        ("net_debt_to_equity", "Net debt / equity", "multiple"),
        ("net_debt_to_ebitda", "Net debt / EBITDA", "multiple"),
        ("interest_coverage", "Interest coverage", "multiple"),
        ("shares_yoy_change", "Share dilution", "percentage"),
        ("sbc_to_revenue", "SBC / revenue", "percentage"),
    ],
    "Asset value": [
        ("ncav", "NCAV", "currency"),
        ("nnwc", "NNWC", "currency"),
        ("net_cash", "Net cash", "currency"),
    ],
    "Valuation": [
        ("market_cap", "Market capitalization", "currency"),
        ("enterprise_value", "Enterprise value", "currency"),
        ("price_to_sales", "P / Sales", "multiple"),
        ("price_to_earnings", "P / E", "multiple"),
        ("price_to_ocf", "P / OCF", "multiple"),
        ("price_to_fcf", "P / FCF", "multiple"),
        ("ev_to_ebit", "EV / EBIT", "multiple"),
        ("ev_to_ebitda", "EV / EBITDA", "multiple"),
        ("ev_to_fcf", "EV / FCF", "multiple"),
        ("earnings_yield", "Earnings yield", "percentage"),
        ("fcf_yield", "FCF yield", "percentage"),
    ],
}


def format_metric_value(value: Any, unit: str) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    if unit == "percentage":
        return f"{number * 100:,.1f}%"
    if unit == "multiple":
        return f"{number:,.1f}x"
    if unit == "per_share":
        return f"${number:,.2f}"
    if unit == "shares":
        return f"{number / 1_000_000:,.1f}M"
    absolute = abs(number)
    sign = "-" if number < 0 else ""
    if absolute >= 1_000_000_000:
        return f"{sign}${absolute / 1_000_000_000:,.2f}B"
    return f"{sign}${absolute / 1_000_000:,.1f}M"


def build_historical_matrix(
    periods: list[dict[str, Any]],
    values_by_period: dict[str, dict[str, Any]],
    metric_group: str,
    include_yoy_change: bool = False,
) -> pd.DataFrame:
    """Build a researcher-facing metric-rows/fiscal-period-columns matrix."""
    rows: list[dict[str, str]] = []
    for metric_name, label, unit in METRIC_GROUPS[metric_group]:
        row = {"Metric": label}
        prior_value: float | None = None
        for period in periods:
            header = f"FY{period['fiscal_year']}"
            value = values_by_period.get(period["id"], {}).get(metric_name)
            display = format_metric_value(value, unit)
            if include_yoy_change and value is not None and prior_value is not None and prior_value != 0:
                change = ((float(value) / prior_value) - 1) * 100
                display = f"{display}\n{change:+,.1f}%"
            row[header] = display
            prior_value = float(value) if value is not None else None
        rows.append(row)
    return pd.DataFrame(rows)
