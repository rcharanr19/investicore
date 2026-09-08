from __future__ import annotations

import logging
from typing import Any

from repositories.catalyst_repository import CatalystRepository
from repositories.sec_filing_repository import SECFilingRepository

logger = logging.getLogger(__name__)

# SEC Form 8-K Item Classification Map
SEC_8K_ITEMS_MAP: dict[str, dict[str, Any]] = {
    "1.01": {
        "type": "Contract / Strategic Agreement",
        "title": "Entry into a Material Definitive Agreement",
        "default_probability": 70,
        "impact_direction": "Positive",
    },
    "1.02": {
        "type": "Contract Termination",
        "title": "Termination of a Material Definitive Agreement",
        "default_probability": 85,
        "impact_direction": "Negative",
    },
    "2.01": {
        "type": "Asset Sale / Acquisition",
        "title": "Completion of Acquisition or Disposition of Assets",
        "default_probability": 90,
        "impact_direction": "Material Catalyst",
    },
    "2.02": {
        "type": "Operational Results",
        "title": "Results of Operations and Financial Condition",
        "default_probability": 60,
        "impact_direction": "Neutral",
    },
    "2.05": {
        "type": "Restructuring / Liquidation",
        "title": "Costs Associated with Exit or Disposal Activities",
        "default_probability": 80,
        "impact_direction": "Restructuring",
    },
    "2.06": {
        "type": "Impairment",
        "title": "Material Impairments",
        "default_probability": 85,
        "impact_direction": "Asset Write-down",
    },
    "3.02": {
        "type": "Equity Financing",
        "title": "Unregistered Sales of Equity Securities",
        "default_probability": 90,
        "impact_direction": "Dilution",
    },
    "5.01": {
        "type": "Activist / Control Change",
        "title": "Changes in Control of Registrant",
        "default_probability": 85,
        "impact_direction": "Activist / Takeover",
    },
    "5.02": {
        "type": "Management Change",
        "title": "Departure / Election of Directors or Principal Officers",
        "default_probability": 75,
        "impact_direction": "Leadership Change",
    },
    "8.01": {
        "type": "Special Situation / Other",
        "title": "Other Events (Special Dividend, Strategic Review, Buybacks)",
        "default_probability": 65,
        "impact_direction": "Corporate Event",
    },
}


class SECCatalystDetector:
    """Detects, classifies, and scores catalysts from SEC Form 8-K filings."""

    @staticmethod
    def classify_8k_items(items_str: str | None) -> list[dict[str, Any]]:
        """Parses comma-separated or space-separated 8-K item codes into structured catalyst definitions."""
        if not items_str:
            return []

        cleaned = items_str.replace("Item", "").replace("item", "").strip()
        tokens = [t.strip() for t in cleaned.replace(";", ",").split(",") if t.strip()]
        matches: list[dict[str, Any]] = []

        for token in tokens:
            for item_key, info in SEC_8K_ITEMS_MAP.items():
                if item_key in token:
                    matches.append({
                        "item_number": f"Item {item_key}",
                        "catalyst_type": info["type"],
                        "title": info["title"],
                        "default_probability": info["default_probability"],
                        "impact_direction": info["impact_direction"],
                    })
                    break

        return matches

    @classmethod
    def extract_catalysts_from_filings(
        cls,
        company_id: str,
        filing_repo: SECFilingRepository,
        catalyst_repo: CatalystRepository,
    ) -> list[dict[str, Any]]:
        """Scans all stored 8-K filings for the company and creates structured catalyst records."""
        filings_8k = filing_repo.list_by_company(company_id, form_types=["8-K"])
        existing_cats = catalyst_repo.list_by_company(company_id)
        existing_filing_ids = {c.get("filing_id") for c in existing_cats if c.get("filing_id")}

        created: list[dict[str, Any]] = []

        for f in filings_8k:
            fid = f.get("id")
            if fid in existing_filing_ids:
                continue

            items_raw = f.get("items") or ""
            parsed_items = cls.classify_8k_items(items_raw)

            if parsed_items:
                for p_item in parsed_items:
                    cat_payload = {
                        "company_id": company_id,
                        "filing_id": fid,
                        "catalyst_type": p_item["catalyst_type"],
                        "title": f"{p_item['title']} ({p_item['item_number']})",
                        "description": f"Form 8-K filed on {f.get('filing_date')}. Reported {p_item['item_number']} ({p_item['impact_direction']}). Accession: {f.get('accession_number')}.",
                        "date_identified": f.get("filing_date", "2026-09-08"),
                        "probability": p_item["default_probability"],
                        "status": "Announced",
                        "source": f"SEC Form 8-K ({f.get('filing_date')})",
                        "confidence": "HIGH",
                    }
                    saved = catalyst_repo.create(cat_payload)
                    created.append(saved)
            else:
                # Generic 8-K event
                cat_payload = {
                    "company_id": company_id,
                    "filing_id": fid,
                    "catalyst_type": "Corporate Event",
                    "title": f"Material Event 8-K ({f.get('filing_date')})",
                    "description": f"Form 8-K event filed on {f.get('filing_date')}. Accession: {f.get('accession_number')}.",
                    "date_identified": f.get("filing_date", "2026-09-08"),
                    "probability": 60,
                    "status": "Announced",
                    "source": f"SEC Form 8-K ({f.get('filing_date')})",
                    "confidence": "HIGH",
                }
                saved = catalyst_repo.create(cat_payload)
                created.append(saved)

        return created

    @staticmethod
    def calculate_catalyst_score(
        probability_pct: float,
        value_impact_per_share: float,
        time_to_realization_years: float = 1.0,
    ) -> dict[str, Any]:
        """Calculates expected catalyst score and annualized value velocity.

        Formula: Score = (Probability * Value Impact) / Time
        """
        prob = max(0.0, min(100.0, float(probability_pct))) / 100.0
        impact = float(value_impact_per_share or 0.0)
        t = max(0.25, float(time_to_realization_years or 1.0))

        expected_impact = prob * impact
        velocity_score = expected_impact / t

        return {
            "expected_value_impact": round(expected_impact, 2),
            "catalyst_velocity_score": round(velocity_score, 2),
            "time_horizon_years": t,
        }


# Global singleton instance
sec_catalyst_detector = SECCatalystDetector()
