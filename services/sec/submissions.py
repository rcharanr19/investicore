from __future__ import annotations

import logging
from typing import Any

from services.sec.client import SECClient, sec_client
from services.sec.company import format_cik

logger = logging.getLogger(__name__)

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


class SECSubmissionsService:
    """Service to retrieve SEC Submissions metadata and filings history."""

    def __init__(self, client: SECClient | None = None):
        self.client = client or sec_client

    def get_submissions(self, cik: int | str, use_cache: bool = True) -> dict[str, Any] | None:
        """Fetch raw SEC submissions payload for a CIK."""
        cik_str = format_cik(cik)
        url = SEC_SUBMISSIONS_URL.format(cik=cik_str)
        # Submissions change when new filings are submitted; cache for 6 hours
        return self.client.get_json(url, use_cache=use_cache, cache_ttl_seconds=21600)

    def get_company_details(self, cik: int | str) -> dict[str, Any] | None:
        """Extract structured SEC company profile from submissions."""
        sub = self.get_submissions(cik)
        if not sub:
            return None

        cik_str = format_cik(cik)
        tickers = sub.get("tickers", [])
        primary_ticker = tickers[0] if tickers else ""
        exchanges = sub.get("exchanges", [])
        primary_exchange = exchanges[0] if exchanges else ""

        addresses = sub.get("addresses", {})
        business_addr = addresses.get("business", {})

        return {
            "cik": cik_str,
            "name": sub.get("name", ""),
            "ticker": primary_ticker,
            "exchange": primary_exchange,
            "sic": sub.get("sic", ""),
            "sic_description": sub.get("sicDescription", ""),
            "category": sub.get("category", ""),
            "fiscal_year_end": sub.get("fiscalYearEnd", ""),
            "state_of_incorporation": sub.get("stateOfIncorporation", ""),
            "state_of_incorporation_description": sub.get("stateOfIncorporationDescription", ""),
            "entity_type": sub.get("entityType", ""),
            "description": sub.get("description", ""),
            "website": sub.get("website", ""),
            "phone": sub.get("phone", ""),
            "business_address": f"{business_addr.get('street1', '')} {business_addr.get('city', '')}, {business_addr.get('stateOrCountry', '')} {business_addr.get('zipCode', '')}".strip(),
            "former_names": sub.get("formerNames", []),
        }

    def get_recent_filings(
        self,
        cik: int | str,
        form_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Extract structured filings list for a given company CIK.

        Supports filtering by form types (e.g. 10-K, 10-Q, 8-K, DEF 14A, 4).
        """
        sub = self.get_submissions(cik)
        if not sub or "filings" not in sub or "recent" not in sub["filings"]:
            return []

        cik_str = format_cik(cik)
        recent = sub["filings"]["recent"]
        length = len(recent.get("accessionNumber", []))

        target_forms = {f.upper() for f in form_types} if form_types else None
        filings: list[dict[str, Any]] = []

        for i in range(length):
            form = recent["form"][i]
            if target_forms and form.upper() not in target_forms:
                continue

            acc_raw = recent["accessionNumber"][i]
            acc_clean = acc_raw.replace("-", "")
            primary_doc = recent["primaryDocument"][i] or ""

            # EDGAR Document direct URL
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik_str)}/{acc_clean}/{primary_doc}"
            index_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik_str)}/{acc_clean}/{acc_raw}-index.htm"

            record = {
                "cik": cik_str,
                "accession_number": acc_raw,
                "accession_number_clean": acc_clean,
                "form_type": form,
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i] or None,
                "acceptance_date_time": recent["acceptanceDateTime"][i] if "acceptanceDateTime" in recent else None,
                "act": recent["act"][i] if "act" in recent else None,
                "file_number": recent["fileNumber"][i] if "fileNumber" in recent else None,
                "film_number": recent["filmNumber"][i] if "filmNumber" in recent else None,
                "items": recent["items"][i] if "items" in recent else None,
                "size": recent["size"][i] if "size" in recent else None,
                "is_xbrl": bool(recent["isXBRL"][i]) if "isXBRL" in recent else False,
                "is_inline_xbrl": bool(recent["isInlineXBRL"][i]) if "isInlineXBRL" in recent else False,
                "primary_document": primary_doc,
                "primary_doc_description": recent["primaryDocDescription"][i] if "primaryDocDescription" in recent else "",
                "filing_url": filing_url,
                "index_url": index_url,
            }
            filings.append(record)
            if len(filings) >= limit:
                break

        return filings


# Global singleton instance
sec_submissions_service = SECSubmissionsService()
