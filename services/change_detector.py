from __future__ import annotations

import logging
from typing import Any

from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository
from repositories.research_alert_repository import ResearchAlertRepository

logger = logging.getLogger(__name__)


class SECChangeDetector:
    """Analyzes sequential SEC filings (10-K vs prior 10-K, 10-Q vs prior 10-Q)

    and generates structured research alerts for material financial and operational shifts.
    """

    def __init__(
        self,
        period_repo: FinancialPeriodRepository,
        metric_repo: FinancialMetricRepository,
        alert_repo: ResearchAlertRepository,
    ):
        self.period_repo = period_repo
        self.metric_repo = metric_repo
        self.alert_repo = alert_repo

    def run_change_detection(self, company_id: str) -> list[dict[str, Any]]:
        """Compares the latest two annual and latest two quarterly periods to detect material shifts."""
        periods = self.period_repo.list_by_company(company_id)
        annuals = [p for p in periods if p.get("period_type") == "Annual"]
        quarterlies = [p for p in periods if p.get("period_type") == "Quarterly"]

        # Clear prior alerts for fresh scan
        self.alert_repo.clear_for_company(company_id)
        generated_alerts: list[dict[str, Any]] = []

        # 1. Compare Annual YoY (Latest 10-K vs Prior 10-K)
        if len(annuals) >= 2:
            latest_a, prior_a = annuals[0], annuals[1]
            alerts_yoy = self._compare_periods(company_id, latest_a, prior_a, timeframe_label="YoY (Annual)")
            for a in alerts_yoy:
                saved = self.alert_repo.create(a)
                generated_alerts.append(saved)

        # 2. Compare Quarterly QoQ (Latest 10-Q vs Prior 10-Q)
        if len(quarterlies) >= 2:
            latest_q, prior_q = quarterlies[0], quarterlies[1]
            alerts_qoq = self._compare_periods(company_id, latest_q, prior_q, timeframe_label="QoQ (Quarterly)")
            for a in alerts_qoq:
                saved = self.alert_repo.create(a)
                generated_alerts.append(saved)

        return generated_alerts

    def _compare_periods(
        self,
        company_id: str,
        current_period: dict[str, Any],
        prior_period: dict[str, Any],
        timeframe_label: str,
    ) -> list[dict[str, Any]]:
        curr_metrics = {m["metric_name"]: float(m["metric_value"]) for m in self.metric_repo.list_by_period(current_period["id"]) if m.get("metric_value") is not None}
        prior_metrics = {m["metric_name"]: float(m["metric_value"]) for m in self.metric_repo.list_by_period(prior_period["id"]) if m.get("metric_value") is not None}

        alerts: list[dict[str, Any]] = []

        def _pct_change(curr: float | None, prev: float | None) -> float | None:
            if curr is None or prev is None or prev == 0:
                return None
            return ((curr - prev) / abs(prev)) * 100.0

        # Check 1: Cash & Liquidity Decline
        c_curr = curr_metrics.get("cash", 0.0) + curr_metrics.get("marketable_securities", 0.0)
        c_prev = prior_metrics.get("cash", 0.0) + prior_metrics.get("marketable_securities", 0.0)
        cash_chg = _pct_change(c_curr, c_prev)
        if cash_chg is not None and cash_chg < -20.0:
            alerts.append({
                "company_id": company_id,
                "alert_type": "CASH_DECLINE",
                "severity": "CRITICAL" if cash_chg < -35.0 else "WARNING",
                "headline": f"Cash & Securities Declined {abs(cash_chg):.1f}% {timeframe_label}",
                "description": f"Liquid cash reserves dropped from ${c_prev/1e6:,.1f}M to ${c_curr/1e6:,.1f}M ({cash_chg:+.1f}%). Affects net cash downside protection.",
            })

        # Check 2: Share Dilution Expansion
        s_curr = curr_metrics.get("shares_diluted") or curr_metrics.get("shares_outstanding")
        s_prev = prior_metrics.get("shares_diluted") or prior_metrics.get("shares_outstanding")
        share_chg = _pct_change(s_curr, s_prev)
        if share_chg is not None and share_chg > 5.0:
            alerts.append({
                "company_id": company_id,
                "alert_type": "SHARE_DILUTION",
                "severity": "WARNING",
                "headline": f"Share Count Expanded {share_chg:+.1f}% {timeframe_label}",
                "description": f"Diluted shares increased from {s_prev/1e6:,.1f}M to {s_curr/1e6:,.1f}M. Dilutes per-share NCAV/NNWC.",
            })

        # Check 3: Inventory Divergence vs Revenue
        inv_chg = _pct_change(curr_metrics.get("inventory"), prior_metrics.get("inventory"))
        rev_chg = _pct_change(curr_metrics.get("revenue"), prior_metrics.get("revenue"))
        if inv_chg is not None and rev_chg is not None:
            if inv_chg > 20.0 and rev_chg < 5.0:
                alerts.append({
                    "company_id": company_id,
                    "alert_type": "INVENTORY_DIVERGENCE",
                    "severity": "CRITICAL" if rev_chg < 0 else "WARNING",
                    "headline": f"Inventory Build-Up ({inv_chg:+.1f}%) Outpacing Revenue ({rev_chg:+.1f}%) {timeframe_label}",
                    "description": f"Inventory grew {inv_chg:+.1f}% while Revenue changed {rev_chg:+.1f}%. High risk of inventory obsolescence or future gross margin compression.",
                })

        # Check 4: Receivables Divergence vs Revenue
        rec_chg = _pct_change(curr_metrics.get("accounts_receivable"), prior_metrics.get("accounts_receivable"))
        if rec_chg is not None and rev_chg is not None:
            if rec_chg > 25.0 and rev_chg < 5.0:
                alerts.append({
                    "company_id": company_id,
                    "alert_type": "RECEIVABLES_DIVERGENCE",
                    "severity": "WARNING",
                    "headline": f"Accounts Receivable Surge ({rec_chg:+.1f}%) vs Revenue ({rev_chg:+.1f}%) {timeframe_label}",
                    "description": f"Receivables grew significantly faster than revenue. Inspect customer payment collections and allowance for doubtful accounts.",
                })

        # Check 5: NCAV Shift
        ncav_curr = curr_metrics.get("ncav")
        ncav_prev = prior_metrics.get("ncav")
        ncav_chg = _pct_change(ncav_curr, ncav_prev)
        if ncav_chg is not None and abs(ncav_chg) > 15.0:
            alerts.append({
                "company_id": company_id,
                "alert_type": "NCAV_SHIFT",
                "severity": "CRITICAL" if ncav_chg < -20.0 else "INFO",
                "headline": f"NCAV Changed {ncav_chg:+.1f}% {timeframe_label}",
                "description": f"Reported Net Current Asset Value moved from ${ncav_prev/1e6:,.1f}M to ${ncav_curr/1e6:,.1f}M.",
            })

        # Check 6: Debt Increase
        debt_curr = curr_metrics.get("total_debt", 0.0)
        debt_prev = prior_metrics.get("total_debt", 0.0)
        debt_chg = _pct_change(debt_curr, debt_prev)
        if debt_chg is not None and debt_chg > 25.0 and debt_curr > 5e6:
            alerts.append({
                "company_id": company_id,
                "alert_type": "DEBT_INCREASE",
                "severity": "WARNING",
                "headline": f"Total Debt Increased {debt_chg:+.1f}% {timeframe_label}",
                "description": f"Total debt increased from ${debt_prev/1e6:,.1f}M to ${debt_curr/1e6:,.1f}M.",
            })

        return alerts
