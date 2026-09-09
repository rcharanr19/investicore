from __future__ import annotations

import hashlib
import logging
from typing import Any

from services.sec.client import SECClient, sec_client
from services.sec.company import format_cik
from services.sec.submissions import SECSubmissionsService, sec_submissions_service

logger = logging.getLogger(__name__)


class SECFilingService:
    """Service for retrieving, storing, and managing SEC raw filings."""

    def __init__(
        self,
        client: SECClient | None = None,
        submissions_service: SECSubmissionsService | None = None,
    ):
        self.client = client or sec_client
        self.submissions = submissions_service or sec_submissions_service

    def fetch_filing_document(
        self,
        cik: int | str,
        accession_number: str,
        primary_document: str,
    ) -> tuple[str | None, str | None]:
        """Fetch raw HTML/text content for a specific filing document and return (content, sha256_hash)."""
        cik_str = format_cik(cik)
        acc_clean = accession_number.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik_str)}/{acc_clean}/{primary_document}"

        text = self.client.get_text(url)
        if text is None:
            return None, None

        content_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        return text, content_hash

    def get_filing_artifacts(self, cik: int | str, accession_number: str) -> list[dict[str, str]]:
        """List downloadable primary, exhibit, and XBRL artifacts from the SEC filing index."""
        cik_str = format_cik(cik)
        acc_clean = accession_number.replace("-", "")
        base_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik_str)}/{acc_clean}"
        index = self.client.get_json(f"{base_url}/index.json") or {}
        items = index.get("directory", {}).get("item", [])
        artifacts = []
        for item in items:
            name = str(item.get("name") or "")
            lowered = name.lower()
            if not name or lowered in {"index.json", "indexheaders.html"}:
                continue
            if lowered.endswith((".htm", ".html", ".xml", ".xsd", ".txt", ".pdf")):
                document_type = "XBRL" if lowered.endswith((".xml", ".xsd")) else "EXHIBIT"
                artifacts.append({"filename": name, "source_url": f"{base_url}/{name}", "document_type": document_type})
        return artifacts

    def fetch_document_url(self, url: str) -> tuple[str | None, str | None]:
        """Fetch an indexed SEC artifact and return content with its SHA-256 hash."""
        text = self.client.get_text(url)
        if text is None:
            return None, None
        return text, hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    def sync_company_filings(
        self,
        company_id: str,
        cik: int | str,
        filing_repository: Any,
        form_types: list[str] | None = None,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        """Fetch latest SEC filings metadata and upsert into the filing repository."""
        if form_types is None:
            form_types = ["10-K", "10-Q", "8-K", "DEF 14A", "4", "20-F", "6-K"]

        raw_filings = self.submissions.get_recent_filings(cik, form_types=form_types, limit=limit)
        saved_filings: list[dict[str, Any]] = []

        for item in raw_filings:
            acc = item["accession_number"]
            # Deduplication: check if already exists
            existing = filing_repository.get_by_accession(company_id, acc)
            if existing:
                saved_filings.append(existing)
                continue

            record = {
                "company_id": company_id,
                "accession_number": acc,
                "form_type": item["form_type"],
                "filing_date": item["filing_date"],
                "report_date": item.get("report_date"),
                "primary_document": item.get("primary_document"),
                "filing_url": item.get("filing_url"),
                "index_url": item.get("index_url"),
                "is_xbrl": item.get("is_xbrl", False),
                "is_inline_xbrl": item.get("is_inline_xbrl", False),
                "items": item.get("items"),
                "parsed_status": "Unparsed",
                "parse_version": "1.0",
            }
            saved = filing_repository.create(record)
            saved_filings.append(saved)

        return saved_filings


# Global singleton instance
sec_filing_service = SECFilingService()
