from __future__ import annotations

from collections import defaultdict
from typing import Any

from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository


FLOW_METRICS = {
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "free_cash_flow",
    "capex",
    "rnd",
    "sbc",
}

BALANCE_SHEET_METRICS = {"cash", "debt", "shares_outstanding"}

METRIC_ALIASES = {
    "revenue": ("revenue",),
    "gross_profit": ("gross_profit",),
    "operating_income": ("operating_income",),
    "net_income": ("net_income",),
    "eps": ("eps_diluted", "eps_basic", "eps"),
    "operating_cash_flow": ("operating_cash_flow",),
    "free_cash_flow": ("free_cash_flow",),
    "capex": ("capex",),
    "rnd": ("rnd",),
    "sbc": ("sbc",),
    "cash": ("cash",),
    "debt": ("total_debt", "debt"),
    "shares_outstanding": ("shares_diluted", "shares_outstanding"),
}


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _quarter_from_period(fiscal_period: Any) -> int | None:
    text = str(fiscal_period or "").strip().upper()
    if text.startswith("Q") and text[1:].isdigit():
        return int(text[1:])
    if text.isdigit():
        return int(text)
    return None


def _metric_value_millions(metric: dict[str, Any] | None, output_name: str) -> float:
    if not metric:
        return 0.0
    value = _to_float(metric.get("metric_value"))
    if output_name == "eps":
        return value
    if output_name == "shares_outstanding":
        return value / 1_000_000.0 if abs(value) > 1_000_000 else value
    return value / 1_000_000.0


def _pick_metric(metrics_by_name: dict[str, list[dict[str, Any]]], aliases: tuple[str, ...]) -> dict[str, Any] | None:
    for alias in aliases:
        candidates = [m for m in metrics_by_name.get(alias, []) if m.get("metric_value") is not None]
        if candidates:
            return sorted(candidates, key=lambda m: str(m.get("created_at") or ""))[-1]
    return None


def get_normalized_financial_records(
    company_id: str,
    period_repository: FinancialPeriodRepository,
    metric_repository: FinancialMetricRepository,
    period_type: str | None = None,
) -> list[dict[str, Any]]:
    """Return SEC-normalized financial rows in the page's legacy $M shape."""
    periods = period_repository.list_by_company(company_id, period_type=period_type)
    if not periods:
        return []

    all_metrics = metric_repository.list_by_company(company_id)
    metrics_by_period: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for metric in all_metrics:
        period_id = metric.get("financial_period_id")
        if period_id:
            metrics_by_period[period_id][metric.get("metric_name", "")].append(metric)

    records: list[dict[str, Any]] = []
    for period in periods:
        fiscal_year = int(period.get("fiscal_year") or 0)
        p_type = period.get("period_type") or "Annual"
        fiscal_period = period.get("fiscal_period")
        fiscal_quarter = _quarter_from_period(fiscal_period)
        if p_type == "Quarterly" and fiscal_quarter is None:
            fiscal_quarter = len([r for r in records if r.get("fiscal_year") == fiscal_year and r.get("period_type") == "Quarterly"]) + 1

        record: dict[str, Any] = {
            "company_id": company_id,
            "financial_period_id": period.get("id"),
            "period_type": p_type,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "period_end": period.get("period_end"),
            "period_label": f"{fiscal_year} Q{fiscal_quarter}" if p_type == "Quarterly" and fiscal_quarter else f"FY{fiscal_year}",
        }

        metric_map = metrics_by_period.get(period.get("id"), {})
        for output_name, aliases in METRIC_ALIASES.items():
            record[output_name] = _metric_value_millions(_pick_metric(metric_map, aliases), output_name)

        records.append(record)

    return sorted(records, key=lambda r: (r.get("fiscal_year", 0), r.get("fiscal_quarter") or 0, str(r.get("period_end") or "")))


def get_latest_normalized_financial(
    company_id: str,
    period_repository: FinancialPeriodRepository,
    metric_repository: FinancialMetricRepository,
    period_type: str | None = None,
) -> dict[str, Any] | None:
    records = get_normalized_financial_records(company_id, period_repository, metric_repository, period_type=period_type)
    return records[-1] if records else None


def calculate_normalized_ttm(
    company_id: str,
    period_repository: FinancialPeriodRepository,
    metric_repository: FinancialMetricRepository,
) -> dict[str, Any] | None:
    quarters = get_normalized_financial_records(company_id, period_repository, metric_repository, period_type="Quarterly")
    if len(quarters) >= 4:
        last_4 = quarters[-4:]
        latest_q = last_4[-1]
        result = {
            "company_id": company_id,
            "period_type": "TTM",
            "period_label": f"TTM ({last_4[0]['period_label']} - {latest_q['period_label']})",
            "fiscal_year": latest_q["fiscal_year"],
        }
        for metric in FLOW_METRICS:
            result[metric] = sum(_to_float(q.get(metric)) for q in last_4)
        for metric in BALANCE_SHEET_METRICS:
            result[metric] = _to_float(latest_q.get(metric), 1.0 if metric == "shares_outstanding" else 0.0)
        result["eps"] = sum(_to_float(q.get("eps")) for q in last_4)
        return result

    return None


def calculate_normalized_cagr(
    company_id: str,
    metric: str,
    period_repository: FinancialPeriodRepository,
    metric_repository: FinancialMetricRepository,
    period_type: str = "Annual",
) -> float | None:
    records = get_normalized_financial_records(company_id, period_repository, metric_repository, period_type=period_type)
    if len(records) < 2:
        return None

    first = _to_float(records[0].get(metric))
    last = _to_float(records[-1].get(metric))
    if first <= 0 or last <= 0:
        return None

    if period_type == "Quarterly":
        span = max((len(records) - 1) / 4.0, 0.25)
    else:
        span = max(float(records[-1].get("fiscal_year", 0) - records[0].get("fiscal_year", 0)), 1.0)
    return (((last / first) ** (1.0 / span)) - 1.0) * 100.0