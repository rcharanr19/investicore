from __future__ import annotations

import logging
from typing import Any

from repositories.catalyst_repository import CatalystRepository
from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository
from repositories.insider_repository import InsiderTransactionsRepository
from repositories.management_repository import ManagementCompensationRepository
from repositories.ownership_repository import OwnershipFilingsRepository
from repositories.sec_filing_repository import SECFilingRepository
from services.sec.taxonomy import sec_taxonomy_service

logger = logging.getLogger(__name__)


class SECCrossFilingEngine:
    """Connects information and signals across diverse SEC filing types (10-K, 10-Q, 8-K, DEF 14A, 13D, Form 4)

    to construct a comprehensive evidence timeline and surface multi-filing investment insights.
    """

    def __init__(
        self,
        filing_repo: SECFilingRepository,
        period_repo: FinancialPeriodRepository,
        metric_repo: FinancialMetricRepository,
        catalyst_repo: CatalystRepository,
        management_repo: ManagementCompensationRepository,
        ownership_repo: OwnershipFilingsRepository,
        insider_repo: InsiderTransactionsRepository,
    ):
        self.filing_repo = filing_repo
        self.period_repo = period_repo
        self.metric_repo = metric_repo
        self.catalyst_repo = catalyst_repo
        self.management_repo = management_repo
        self.ownership_repo = ownership_repo
        self.insider_repo = insider_repo

    def build_unified_timeline(
        self,
        company_id: str,
        filter_category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Constructs a chronological company filing and corporate actions timeline."""
        filings = self.filing_repo.list_by_company(company_id, limit=100)
        timeline: list[dict[str, Any]] = []

        for f in filings:
            classified = sec_taxonomy_service.classify_filing(f)
            cat = classified["category"]

            # Apply category filter if specified
            if filter_category and filter_category.lower() != "all":
                filter_norm = filter_category.lower().replace(" ", "_")
                if filter_norm not in cat:
                    continue

            # Build narrative headline and analytical context
            form = f.get("form_type", "")
            fdate = f.get("filing_date", "")
            items = f.get("items") or ""

            if form in ("10-K", "10-K/A", "20-F"):
                headline = f"Annual Financial Baseline Filed ({form})"
                detail = f"Established fiscal annual balance sheet, liabilities, and risk baseline. Report Date: {f.get('report_date') or fdate}."
            elif form in ("10-Q", "10-Q/A", "6-K"):
                headline = f"Quarterly Financial Update ({form})"
                detail = f"Updated working capital and liquidity. Report Date: {f.get('report_date') or fdate}."
            elif "8-K" in form:
                headline = f"Material Event / 8-K Filing ({items or 'General Disclosure'})"
                detail = f"Disclosed unscheduled corporate action or catalyst event. Items: {items or 'General'}."
            elif "14A" in form:
                headline = f"Proxy Statement Filed ({form})"
                detail = "Disclosed executive compensation, insider ownership, board elections, and voting matters."
            elif "13D" in form:
                headline = f"Schedule 13D Activist / Beneficial Ownership"
                detail = "Significant shareholder disclosure (>5%) with active / catalyst intent."
            elif "13G" in form:
                headline = f"Schedule 13G Passive Institutional Ownership"
                detail = "Institutional beneficial ownership disclosure (>5%)."
            elif form in ("4", "4/A"):
                headline = "Form 4 Insider Transaction Report"
                detail = "Director or executive officer changes in beneficial ownership."
            else:
                headline = f"SEC Submission ({form})"
                detail = f"Regulatory filing submitted on {fdate}."

            timeline.append({
                "filing_id": f.get("id"),
                "date": fdate,
                "form_type": form,
                "category": cat,
                "category_label": classified["category_label"],
                "headline": headline,
                "detail": detail,
                "accession_number": f.get("accession_number"),
                "filing_url": f.get("filing_url"),
                "catalyst_relevance": classified["catalyst_relevance"],
                "financial_relevance": classified["financial_relevance"],
                "management_relevance": classified["management_relevance"],
            })

        return sorted(timeline, key=lambda x: str(x.get("date") or ""), reverse=True)

    def generate_cross_filing_synthesis(self, company_id: str) -> list[dict[str, Any]]:
        """Synthesizes cross-filing evidence across 10-K + 10-Q + 8-K + DEF 14A + Form 4 + 13D."""
        observations: list[dict[str, Any]] = []

        # 1. Check for Activist + NCAV Discount alignment
        catalysts = self.catalyst_repo.list_by_company(company_id)
        has_activist = any("13D" in c.get("source", "") or "Activist" in c.get("catalyst_type", "") for c in catalysts)
        has_asset_sale = any("Asset Sale" in c.get("catalyst_type", "") or "2.01" in c.get("title", "") for c in catalysts)

        insider_txs = self.insider_repo.list_by_company(company_id, open_market_only=True)
        has_insider_buying = len(insider_txs) > 0

        if has_activist and has_asset_sale:
            observations.append({
                "type": "HIGH_CONVICTION_CATALYST",
                "severity": "POSITIVE",
                "headline": "Activist Pressure Concurrently Aligned with Asset Monetization",
                "evidence_sources": ["Schedule 13D", "Form 8-K (Item 2.01)"],
                "detail": "An activist investor is actively engaged while the company has announced or completed asset divestitures. High probability of value-unlocking capital return.",
            })

        if has_insider_buying:
            tot_bought = sum(float(t.get("total_value", 0.0)) for t in insider_txs)
            observations.append({
                "type": "INSIDER_CONVICTION",
                "severity": "POSITIVE",
                "headline": f"Discretionary Open-Market Insider Buying (${tot_bought:,.0f} Total)",
                "evidence_sources": ["Form 4"],
                "detail": "Executives or directors purchased shares directly on the open market using personal capital, signalling internal confidence.",
            })

        # 2. Check Management proxy compensation
        mgmt_recs = self.management_repo.list_by_company(company_id)
        if mgmt_recs:
            ceo_rec = next((m for m in mgmt_recs if "CEO" in m.get("title", "")), mgmt_recs[0])
            own_pct = ceo_rec.get("ownership_pct", 0.0)
            if own_pct >= 3.0:
                observations.append({
                    "type": "EXECUTIVE_ALIGNMENT",
                    "severity": "POSITIVE",
                    "headline": f"Meaningful Executive Skin-in-the-Game ({own_pct:.1f}% Ownership)",
                    "evidence_sources": ["DEF 14A"],
                    "detail": "CEO maintains substantial equity ownership, aligning leadership with shareholder per-share value creation.",
                })

        return observations
