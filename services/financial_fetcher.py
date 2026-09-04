from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _get_val(df: pd.DataFrame, posibles: list[str], col: Any, is_per_share: bool = False) -> float:
    """Helper to extract a numeric float from DataFrame rows looking through a list of possible row names."""
    if df.empty or col not in df.columns:
        return 0.0
    for name in posibles:
        if name in df.index:
            val = df.loc[name, col]
            if pd.notna(val):
                try:
                    fval = float(val)
                    if is_per_share:
                        return round(fval, 4)
                    # yfinance values are raw numbers (e.g. 100,000,000). Convert to Millions ($M)
                    return float(fval) / 1_000_000.0
                except (ValueError, TypeError):
                    pass
    return 0.0



def fetch_company_profile(ticker: str) -> dict[str, Any] | None:
    """Fetch company profile metadata using yfinance with safe fallback."""
    clean_ticker = (ticker or "").strip().upper()
    if not clean_ticker:
        return None

    try:
        t = yf.Ticker(clean_ticker)
        info = {}
        try:
            info = t.info or {}
        except Exception as ex:
            logger.warning(f"Could not retrieve yfinance info for {clean_ticker}: {ex}")

        name = info.get("longName") or info.get("shortName") or info.get("name") or clean_ticker

        # Convert shares to Millions
        shares_raw = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 0
        shares_m = float(shares_raw) / 1_000_000.0 if shares_raw else 1.0

        # Cash & Debt in Millions
        cash_m = float(info.get("totalCash") or 0) / 1_000_000.0
        debt_m = float(info.get("totalDebt") or 0) / 1_000_000.0

        price = float(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 100.0)

        return {
            "ticker": clean_ticker,
            "name": name,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "United States"),
            "website": info.get("website", ""),
            "description": info.get("longBusinessSummary", ""),
            "status": "Watchlist",
            "current_price": price,
            "shares_outstanding": max(shares_m, 1.0),
            "cash": cash_m,
            "debt": debt_m,
        }
    except Exception as e:
        logger.error(f"Error fetching company profile for {clean_ticker}: {e}")
        return {
            "ticker": clean_ticker,
            "name": clean_ticker,
            "sector": "N/A",
            "industry": "N/A",
            "country": "United States",
            "website": "",
            "description": "",
            "status": "Watchlist",
            "current_price": 100.0,
            "shares_outstanding": 1.0,
            "cash": 0.0,
            "debt": 0.0,
        }


def _parse_statements(
    income_df: pd.DataFrame,
    cashflow_df: pd.DataFrame,
    balance_df: pd.DataFrame,
    period_type: str = "Annual",
) -> list[dict[str, Any]]:
    """Parse yfinance statement DataFrames into Investicore financial records."""
    records = []
    if income_df.empty:
        return records

    columns = list(income_df.columns)
    for col in columns:
        try:
            date_obj = pd.to_datetime(col)
            fiscal_year = int(date_obj.year)
        except Exception:
            continue

        fiscal_quarter = None
        if period_type == "Quarterly":
            # Determine quarter number from date month
            month = date_obj.month
            fiscal_quarter = (month - 1) // 3 + 1

        shares = _get_val(balance_df, ["Ordinary Shares Number", "Share Issued", "Treasury Shares Number"], col)
        if shares <= 0:
            shares = 1.0

        rev = _get_val(income_df, ["Total Revenue", "Operating Revenue", "Revenue"], col)
        gp = _get_val(income_df, ["Gross Profit", "GrossMargin"], col)
        op_inc = _get_val(income_df, ["Operating Income", "Total Operating Income As Reported", "EBIT"], col)
        net_inc = _get_val(income_df, ["Net Income Common Stockholders", "Net Income", "Net Income Continuous Operations"], col)
        eps = _get_val(income_df, ["Diluted EPS", "Basic EPS"], col, is_per_share=True)
        if eps == 0.0 and net_inc != 0 and shares > 0:
            eps = round(net_inc / shares, 2)

        fcf = _get_val(cashflow_df, ["Free Cash Flow"], col)
        capex = abs(_get_val(cashflow_df, ["Capital Expenditure", "Capital Expenditures"], col))
        rnd = _get_val(income_df, ["Research And Development"], col)
        sbc = _get_val(cashflow_df, ["Stock Based Compensation"], col)

        cash = _get_val(balance_df, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial"], col)
        debt = _get_val(balance_df, ["Total Debt", "Net Debt", "Long Term Debt"], col)

        period_label = f"{fiscal_year} Q{fiscal_quarter}" if period_type == "Quarterly" else f"FY{fiscal_year}"

        rec = {
            "fiscal_year": fiscal_year,
            "period_type": period_type,
            "fiscal_quarter": fiscal_quarter,
            "period_label": period_label,
            "revenue": rev,
            "gross_profit": gp,
            "operating_income": op_inc,
            "net_income": net_inc,
            "eps": eps,
            "free_cash_flow": fcf,
            "capex": capex,
            "rnd": rnd,
            "sbc": sbc,
            "cash": cash,
            "debt": debt,
            "shares_outstanding": shares,
        }
        records.append(rec)

    # Sort chronological
    return sorted(records, key=lambda x: (x["fiscal_year"], x.get("fiscal_quarter") or 0))


def fetch_financial_history(ticker: str) -> dict[str, list[dict[str, Any]]]:
    """Fetch annual and quarterly financial statements using yfinance."""
    clean_ticker = (ticker or "").strip().upper()
    result = {"annual": [], "quarterly": []}
    if not clean_ticker:
        return result

    try:
        t = yf.Ticker(clean_ticker)

        annual_income = t.financials
        annual_cashflow = t.cashflow
        annual_balance = t.balance_sheet

        result["annual"] = _parse_statements(annual_income, annual_cashflow, annual_balance, period_type="Annual")

        q_income = t.quarterly_financials
        q_cashflow = t.quarterly_cashflow
        q_balance = t.quarterly_balance_sheet

        result["quarterly"] = _parse_statements(q_income, q_cashflow, q_balance, period_type="Quarterly")

    except Exception as e:
        logger.error(f"Error fetching financial history for {clean_ticker}: {e}")

    return result
