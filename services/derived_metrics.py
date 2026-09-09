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


def _cagr(current: float | None, prior: float | None, years: int) -> float | None:
    if current is None or prior is None or current <= 0 or prior <= 0 or years <= 0:
        return None
    return (float(current) / float(prior)) ** (1 / years) - 1.0


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
    receivables = current.get("accounts_receivable")
    inventory = current.get("inventory")
    payables = current.get("accounts_payable")
    cogs = current.get("cogs")
    goodwill = current.get("goodwill") or 0.0
    intangibles = current.get("intangibles") or 0.0
    ncav = current.get("ncav")
    nnwc = current.get("nnwc")
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
    result["working_capital"] = (current.get("total_current_assets") - current.get("current_liabilities")) if current.get("total_current_assets") is not None and current.get("current_liabilities") is not None else None
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
    result["quick_ratio"] = _ratio((cash or 0.0) + securities + (receivables or 0.0), current.get("current_liabilities")) if cash is not None and receivables is not None else None
    result["debt_to_assets"] = _ratio(debt, assets)
    result["debt_to_ebitda"] = _ratio(debt, ebitda)
    result["interest_coverage"] = _ratio(operating_income, interest_expense)
    result["book_value_per_share"] = _ratio(equity, shares)
    result["tangible_book_value_per_share"] = _ratio((equity - goodwill - intangibles) if equity is not None else None, shares)
    result["revenue_per_share"] = _ratio(revenue, shares)
    result["fcf_per_share"] = _ratio(fcf, shares)
    result["net_cash_per_share"] = _ratio((-net_debt) if net_debt is not None else None, shares)
    result["ncav_per_share"] = _ratio(ncav, shares)
    result["nnwc_per_share"] = _ratio(nnwc, shares)
    result["working_capital_to_revenue"] = _ratio(result["working_capital"], revenue)

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
        average_receivables = ((receivables or 0.0) + (prior.get("accounts_receivable") or 0.0)) / 2 if receivables is not None and prior.get("accounts_receivable") is not None else None
        average_inventory = ((inventory or 0.0) + (prior.get("inventory") or 0.0)) / 2 if inventory is not None and prior.get("inventory") is not None else None
        average_payables = ((payables or 0.0) + (prior.get("accounts_payable") or 0.0)) / 2 if payables is not None and prior.get("accounts_payable") is not None else None
        result["dso"] = _ratio(average_receivables * 365 if average_receivables is not None else None, revenue)
        result["dio"] = _ratio(average_inventory * 365 if average_inventory is not None else None, cogs)
        result["dpo"] = _ratio(average_payables * 365 if average_payables is not None else None, cogs)
        result["cash_conversion_cycle"] = result["dso"] + result["dio"] - result["dpo"] if None not in (result["dso"], result["dio"], result["dpo"]) else None

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
        result["ev_to_sales"] = _ratio(enterprise_value, revenue)
        result["price_to_book"] = _ratio(market_cap, equity)
        result["price_to_tangible_book"] = _ratio(market_cap, (equity - goodwill - intangibles) if equity is not None else None)
        result["price_to_ncav"] = _ratio(market_cap, ncav)
        result["price_to_nnwc"] = _ratio(market_cap, nnwc)
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
            "unit": "currency" if name in {"revenue", "gross_profit", "ebit", "ebitda", "net_income", "operating_cash_flow", "free_cash_flow", "stock_based_compensation", "cash", "total_debt", "net_debt", "working_capital", "market_cap", "enterprise_value"} else "shares" if name == "diluted_shares" else "per_share" if name.endswith("_per_share") else "percentage" if name.endswith(("_margin", "_growth", "_yield", "_cagr")) or name in {"sbc_to_revenue", "sbc_to_ocf", "sbc_to_fcf", "capex_to_revenue", "cfo_to_net_income", "fcf_to_net_income", "shares_yoy_change", "roe", "roa", "roic", "working_capital_to_revenue"} else "days" if name in {"dso", "dio", "dpo", "cash_conversion_cycle"} else "ratio",
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

    def _calculate_cagrs(self, company_id: str) -> int:
        schema = self.client.schema("investicorev2")
        periods = schema.table("financial_periods").select("id,fiscal_year,source_filing_id").eq("company_id", company_id).eq("period_type", "Annual").order("period_end").execute().data or []
        if len(periods) < 2:
            return 0
        period_ids = [period["id"] for period in periods]
        source_metrics = schema.table("financial_metrics").select("financial_period_id,metric_name,metric_value").in_("financial_period_id", period_ids).eq("is_preferred", True).execute().data or []
        values: dict[str, dict[str, float | None]] = {period_id: {} for period_id in period_ids}
        for metric in source_metrics:
            values[metric["financial_period_id"]][metric["metric_name"]] = float(metric["metric_value"]) if metric["metric_value"] is not None else None
        rows = []
        for index, current_period in enumerate(periods):
            for target_years in (3, 5, 10):
                prior_index = next((candidate for candidate in range(index - 1, -1, -1) if current_period["fiscal_year"] - periods[candidate]["fiscal_year"] >= target_years), None)
                if prior_index is None:
                    continue
                prior_period = periods[prior_index]
                span = current_period["fiscal_year"] - prior_period["fiscal_year"]
                for metric_name in ("revenue", "operating_income", "net_income", "eps_diluted", "free_cash_flow"):
                    value = _cagr(values[current_period["id"]].get(metric_name), values[prior_period["id"]].get(metric_name), span)
                    rows.append({
                        "company_id": company_id,
                        "financial_period_id": current_period["id"],
                        "metric_name": f"{metric_name}_{target_years}y_cagr",
                        "metric_value": value,
                        "unit": "percentage",
                        "status": "AVAILABLE" if value is not None else "NOT_APPLICABLE",
                        "calculation_method": f"annual_cagr_{span}y",
                        "source_period_ids": [prior_period["id"], current_period["id"]],
                        "source_metric_names": [metric_name],
                        "source_filing_ids": [item["source_filing_id"] for item in (prior_period, current_period) if item.get("source_filing_id")],
                    })
        if rows:
            schema.table("derived_metrics").upsert(rows, on_conflict="company_id,financial_period_id,market_price_id,metric_name,calculation_version").execute()
        return len(rows)

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
        return saved + self._calculate_cagrs(company_id)

    def save_historical_prices(self, company_id: str, ticker: str, closes: dict[str, tuple[str, float]]) -> dict[str, dict[str, Any]]:
        """Persist fiscal-period close snapshots keyed by financial period-end date."""
        rows = []
        for period_end, (market_date, price) in closes.items():
            rows.append({
                "company_id": company_id,
                "ticker": ticker,
                "price": price,
                "source": "Yahoo Finance close",
                "market_timestamp": f"{market_date}T00:00:00+00:00",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            })
        saved = []
        for row in rows:
            saved.append(self.client.schema("investicorev2").table("market_prices").insert(row).execute().data[0])
        return {period_end: price for period_end, price in zip(closes, saved)}

    def calculate_historical_valuations(self, company_id: str, ticker: str, closes: dict[str, tuple[str, float]]) -> int:
        """Calculate annual valuation metrics using each annual fiscal-period close."""
        schema = self.client.schema("investicorev2")
        periods = schema.table("financial_periods").select("id,period_end").eq("company_id", company_id).eq("period_type", "Annual").execute().data or []
        prices = self.save_historical_prices(company_id, ticker, closes)
        saved = 0
        for period in periods:
            snapshot = prices.get(period["period_end"])
            if snapshot:
                saved += len(self.calculate_and_save(company_id, period["id"], snapshot))
        return saved

    def save_latest_market_price(self, company_id: str, ticker: str, price: float) -> dict[str, Any]:
        return self.client.schema("investicorev2").table("market_prices").insert({
            "company_id": company_id,
            "ticker": ticker,
            "price": price,
            "source": "Yahoo Finance",
        }).execute().data[0]