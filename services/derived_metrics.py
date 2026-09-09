from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return (float(current) / float(prior)) - 1.0


def calculate_period_metrics(
    current: dict[str, float | None],
    prior: dict[str, float | None] | None = None,
    market_price: float | None = None,
) -> dict[str, float | None]:
    """Calculate Phase 2 ratios from normalized preferred values only."""
    result: dict[str, float | None] = {}
    revenue = current.get("revenue")
    operating_income = current.get("operating_income")
    net_income = current.get("net_income")
    cfo = current.get("operating_cash_flow")
    fcf = current.get("free_cash_flow")
    sbc = current.get("sbc")
    debt = current.get("total_debt")
    equity = current.get("total_equity")
    assets = current.get("total_assets")
    cash = current.get("cash")
    securities = current.get("marketable_securities") or 0.0
    shares = current.get("shares_diluted") or current.get("shares_outstanding")
    pretax_income = current.get("pretax_income")
    income_tax = current.get("income_tax")
    gross_profit = current.get("gross_profit")
    depreciation = current.get("depreciation_amortization")
    interest_expense = current.get("interest_expense")
    ebitda = operating_income + depreciation if operating_income is not None and depreciation is not None else None
    net_debt = debt - cash - securities if debt is not None and cash is not None else None

    result["revenue"] = revenue
    result["gross_profit"] = gross_profit
    result["ebit"] = operating_income
    result["ebitda"] = ebitda
    result["net_income"] = net_income
    result["operating_cash_flow"] = cfo
    result["free_cash_flow"] = fcf
    result["stock_based_compensation"] = sbc
    result["diluted_shares"] = shares
    result["cash"] = cash
    result["total_debt"] = debt
    result["net_debt"] = net_debt
    result["gross_margin"] = _ratio(gross_profit, revenue)
    result["operating_margin"] = _ratio(operating_income, revenue)
    result["net_margin"] = _ratio(net_income, revenue)
    result["ocf_margin"] = _ratio(cfo, revenue)
    result["fcf_margin"] = _ratio(fcf, revenue)
    result["capex_to_revenue"] = _ratio(current.get("capex"), revenue)
    result["sbc_to_revenue"] = _ratio(sbc, revenue)
    result["sbc_to_ocf"] = _ratio(sbc, cfo)
    result["sbc_to_fcf"] = _ratio(sbc, fcf)
    result["cfo_to_net_income"] = _ratio(cfo, net_income)
    result["fcf_to_net_income"] = _ratio(fcf, net_income)
    result["debt_to_equity"] = _ratio(debt, equity)
    result["net_debt_to_equity"] = _ratio(net_debt, equity)
    result["net_debt_to_ebitda"] = _ratio(net_debt, ebitda)
    result["current_ratio"] = _ratio(current.get("total_current_assets"), current.get("current_liabilities"))
    result["interest_coverage"] = _ratio(operating_income, interest_expense)

    if prior:
        for metric_name in ("revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "free_cash_flow", "sbc"):
            result[f"{metric_name}_growth"] = _growth(current.get(metric_name), prior.get(metric_name))
        result["shares_yoy_change"] = _ratio(
            (shares - prior.get("shares_diluted", prior.get("shares_outstanding"))) if shares is not None and (prior.get("shares_diluted") or prior.get("shares_outstanding")) is not None else None,
            prior.get("shares_diluted") or prior.get("shares_outstanding"),
        )
        average_equity = ((equity or 0.0) + (prior.get("total_equity") or 0.0)) / 2 if equity is not None and prior.get("total_equity") is not None else None
        average_assets = ((assets or 0.0) + (prior.get("total_assets") or 0.0)) / 2 if assets is not None and prior.get("total_assets") is not None else None
        result["roe"] = _ratio(net_income, average_equity)
        result["roa"] = _ratio(net_income, average_assets)
        tax_rate = _ratio(income_tax, pretax_income)
        invested_capital = (debt or 0.0) + (equity or 0.0) - (cash or 0.0) - securities if debt is not None and equity is not None and cash is not None else None
        prior_invested = (prior.get("total_debt") or 0.0) + (prior.get("total_equity") or 0.0) - (prior.get("cash") or 0.0) - (prior.get("marketable_securities") or 0.0)
        average_invested = (invested_capital + prior_invested) / 2 if invested_capital is not None else None
        result["roic"] = _ratio(operating_income * (1 - tax_rate) if operating_income is not None and tax_rate is not None else None, average_invested)

    if market_price is not None and shares is not None:
        market_cap = float(market_price) * float(shares)
        result["market_cap"] = market_cap
        result["price_to_earnings"] = _ratio(market_cap, net_income)
        result["price_to_fcf"] = _ratio(market_cap, fcf)
        result["price_to_ocf"] = _ratio(market_cap, cfo)
        result["price_to_sales"] = _ratio(market_cap, revenue)
        result["earnings_yield"] = _ratio(net_income, market_cap)
        result["fcf_yield"] = _ratio(fcf, market_cap)
        enterprise_value = market_cap + (debt or 0.0) - (cash or 0.0) - securities if debt is not None and cash is not None else None
        result["enterprise_value"] = enterprise_value
        result["ev_to_ebit"] = _ratio(enterprise_value, operating_income)
        result["ev_to_ebitda"] = _ratio(enterprise_value, ebitda)
        result["ev_to_fcf"] = _ratio(enterprise_value, fcf)
    return result


class DerivedMetricsService:
    """Persists Phase 2 metrics with calculation and normalized-period provenance."""

    def __init__(self, client: Any):
        self.client = client

    def calculate_and_save(self, company_id: str, financial_period_id: str, market_price: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        schema = self.client.schema("investicorev2")
        selected = schema.table("financial_periods").select("id,period_end,period_type,source_filing_id").eq("id", financial_period_id).execute().data or []
        if not selected:
            return []
        current_period = selected[0]
        periods = schema.table("financial_periods").select("id,period_end,period_type,source_filing_id").eq("company_id", company_id).eq("period_type", current_period["period_type"]).order("period_end", desc=True).execute().data or []
        position = next((index for index, period in enumerate(periods) if period["id"] == financial_period_id), None)
        if position is None:
            return []
        comparison_offset = 4 if current_period["period_type"] == "Quarterly" else 1
        prior_period = periods[position + comparison_offset] if position + comparison_offset < len(periods) else None
        ids = [current_period["id"]] + ([prior_period["id"]] if prior_period else [])
        metrics = schema.table("financial_metrics").select("financial_period_id,metric_name,metric_value").in_("financial_period_id", ids).eq("is_preferred", True).execute().data or []
        metric_sets: dict[str, dict[str, float | None]] = {period_id: {} for period_id in ids}
        for metric in metrics:
            metric_sets[metric["financial_period_id"]][metric["metric_name"]] = float(metric["metric_value"]) if metric["metric_value"] is not None else None
        values = calculate_period_metrics(metric_sets[current_period["id"]], metric_sets.get(prior_period["id"]) if prior_period else None, market_price.get("price") if market_price else None)
        now = datetime.now(timezone.utc).isoformat()
        rows = [{
            "company_id": company_id,
            "financial_period_id": financial_period_id,
            "market_price_id": market_price.get("id") if market_price else None,
            "metric_name": name,
            "metric_value": value,
            "unit": "currency" if name in {"revenue", "gross_profit", "ebit", "ebitda", "net_income", "operating_cash_flow", "free_cash_flow", "stock_based_compensation", "cash", "total_debt", "net_debt", "market_cap", "enterprise_value"} else "shares" if name == "diluted_shares" else "percentage" if name.endswith(("_margin", "_growth", "_yield")) or name in {"sbc_to_revenue", "sbc_to_ocf", "sbc_to_fcf", "capex_to_revenue", "cfo_to_net_income", "fcf_to_net_income", "shares_yoy_change", "roe", "roa", "roic"} else "ratio",
            "status": "AVAILABLE" if value is not None else "NOT_APPLICABLE",
            "calculation_method": "phase2_normalized_financials",
            "source_period_ids": ids,
            "source_metric_names": list(metric_sets[current_period["id"]]),
            "source_filing_ids": [item["source_filing_id"] for item in (current_period, prior_period) if item and item.get("source_filing_id")],
            "calculated_at": now,
        } for name, value in values.items()]
        if rows:
            schema.table("derived_metrics").upsert(rows, on_conflict="company_id,financial_period_id,market_price_id,metric_name,calculation_version").execute()
        return rows

    def calculate_all(self, company_id: str, market_price: dict[str, Any] | None = None) -> int:
        """Calculate operating metrics for all annual, quarterly, and TTM periods."""
        periods = (
            self.client.schema("investicorev2").table("financial_periods")
            .select("id,period_type,period_end")
            .eq("company_id", company_id)
            .in_("period_type", ["Annual", "Quarterly", "TTM"])
            .order("period_end", desc=True)
            .execute().data
            or []
        )
        latest_ttm_id = next((item["id"] for item in periods if item["period_type"] == "TTM"), None)
        saved = 0
        for item in periods:
            rows = self.calculate_and_save(
                company_id,
                item["id"],
                market_price if item["id"] == latest_ttm_id else None,
            )
            saved += len(rows)
        return saved

    def save_latest_market_price(self, company_id: str, ticker: str, price: float) -> dict[str, Any]:
        return self.client.schema("investicorev2").table("market_prices").insert({
            "company_id": company_id,
            "ticker": ticker,
            "price": price,
            "source": "Yahoo Finance",
        }).execute().data[0]