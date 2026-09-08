from __future__ import annotations

import logging
from typing import Any

from services.sec.client import SECClient, sec_client
from services.sec.company import format_cik

logger = logging.getLogger(__name__)

SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_COMPANY_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json"


class SECXBRLService:
    """Service to retrieve and parse SEC structured XBRL Company Facts."""

    def __init__(self, client: SECClient | None = None):
        self.client = client or sec_client

    def get_company_facts(self, cik: int | str, use_cache: bool = True) -> dict[str, Any] | None:
        """Fetch all XBRL Company Facts JSON from SEC EDGAR API."""
        cik_str = format_cik(cik)
        url = SEC_COMPANY_FACTS_URL.format(cik=cik_str)
        # Cache company facts for 24 hours
        return self.client.get_json(url, use_cache=use_cache, cache_ttl_seconds=86400)

    def get_concept_units(
        self,
        facts: dict[str, Any],
        concept_names: list[str],
        taxonomy: str = "us-gaap",
    ) -> list[dict[str, Any]]:
        """Find facts for the given concept names in taxonomy (e.g. us-gaap).

        Returns list of fact units sorted by end period date desc.
        """
        if not facts or "facts" not in facts or taxonomy not in facts["facts"]:
            return []

        tax_facts = facts["facts"][taxonomy]
        matched_units: list[dict[str, Any]] = []

        for concept in concept_names:
            if concept in tax_facts:
                concept_data = tax_facts[concept]
                units_dict = concept_data.get("units", {})
                label = concept_data.get("label", concept)
                description = concept_data.get("description", "")

                for unit_name, items in units_dict.items():
                    for item in items:
                        # Extract fact metadata
                        fact_rec = {
                            "concept": concept,
                            "label": label,
                            "description": description,
                            "unit": unit_name,
                            "val": item.get("val"),
                            "fy": item.get("fy"),
                            "fp": item.get("fp"),
                            "form": item.get("form"),
                            "filed": item.get("filed"),
                            "frame": item.get("frame"),
                            "start": item.get("start"),
                            "end": item.get("end"),
                            "accn": item.get("accn"),
                        }
                        matched_units.append(fact_rec)

        return matched_units

    def get_latest_fact_value(
        self,
        facts: dict[str, Any],
        concept_names: list[str],
        form_filter: list[str] | None = None,
        taxonomy: str = "us-gaap",
    ) -> dict[str, Any] | None:
        """Get the latest recorded fact value for a list of candidate concept names.

        Prioritizes by latest 'end' date and filing date.
        """
        items = self.get_concept_units(facts, concept_names, taxonomy=taxonomy)
        if not items:
            return None

        if form_filter:
            allowed = {f.upper() for f in form_filter}
            items = [it for it in items if it.get("form", "").upper() in allowed]
            if not items:
                return None

        # Sort primarily by end date desc, filed date desc
        def sort_key(x: dict[str, Any]) -> tuple[str, str]:
            return (str(x.get("end") or ""), str(x.get("filed") or ""))

        sorted_items = sorted(items, key=sort_key, reverse=True)
        return sorted_items[0] if sorted_items else None


# Global singleton instance
sec_xbrl_service = SECXBRLService()
