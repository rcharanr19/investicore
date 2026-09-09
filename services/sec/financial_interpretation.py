from __future__ import annotations

from datetime import date
from typing import Any

FLOW_METRICS = {
    "revenue", "cogs", "gross_profit", "operating_expenses", "operating_income",
    "interest_expense", "pretax_income", "income_tax", "net_income",
    "operating_cash_flow", "capex", "sbc", "depreciation_amortization",
    "cash_flow_investing", "cash_flow_financing", "eps_basic", "eps_diluted",
}


def metric_kind(metric_name: str) -> str:
    return "flow" if metric_name in FLOW_METRICS else "stock"


def duration_days(fact: dict[str, Any]) -> int | None:
    start, end = fact.get("start"), fact.get("end")
    if not start or not end:
        return None
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def fiscal_year_duration_status(days: int | None) -> str:
    if days is None:
        return "NOT_APPLICABLE"
    if 350 <= days <= 371:
        return "VALID_53_WEEK_YEAR" if days >= 366 else "PASS"
    return "REQUIRES_REVIEW"


def reconstruct_discrete_quarter(
    metric_name: str,
    fiscal_period: str,
    period_end: str,
    facts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Interpret raw SEC facts as a discrete quarter without altering stock facts.

    Facts must already refer to one canonical metric and fiscal year. The result
    includes every fact used so the derived interpretation remains auditable.
    """
    matching = [fact for fact in facts if fact.get("end") == period_end and fact.get("val") is not None]
    if not matching:
        return None
    if metric_kind(metric_name) == "stock":
        fact = sorted(matching, key=lambda item: str(item.get("filed") or ""), reverse=True)[0]
        return {"value": float(fact["val"]), "method": "instant", "source_facts": [fact]}

    direct = [fact for fact in matching if (duration_days(fact) or 999) <= 110]
    if direct:
        fact = sorted(direct, key=lambda item: str(item.get("filed") or ""), reverse=True)[0]
        return {"value": float(fact["val"]), "method": "direct_quarter", "source_facts": [fact]}

    current = sorted(matching, key=lambda item: str(item.get("filed") or ""), reverse=True)[0]
    quarter = fiscal_period.upper()
    if quarter == "Q1":
        return {"value": float(current["val"]), "method": "q1_ytd", "source_facts": [current]}

    duration_limit = {"Q2": 230, "Q3": 320}.get(quarter)
    if duration_limit:
        previous = [
            fact for fact in facts
            if fact.get("end") < period_end and (duration_days(fact) or 999) <= duration_limit
        ]
        if previous:
            prior = sorted(previous, key=lambda item: item["end"], reverse=True)[0]
            return {
                "value": float(current["val"]) - float(prior["val"]),
                "method": "ytd_minus_prior_ytd",
                "source_facts": [current, prior],
            }

    if quarter == "Q4":
        prior = [fact for fact in facts if fact.get("end") < period_end and 200 < (duration_days(fact) or 0) <= 320]
        if prior:
            q3_ytd = sorted(prior, key=lambda item: item["end"], reverse=True)[0]
            return {
                "value": float(current["val"]) - float(q3_ytd["val"]),
                "method": "annual_minus_q3_ytd",
                "source_facts": [current, q3_ytd],
            }
    return None