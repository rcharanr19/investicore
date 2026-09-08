from __future__ import annotations

from typing import Any


class SECEvidence:
    """Helper class for constructing audit-ready SEC evidence records."""

    @staticmethod
    def build_edgar_url(cik: int | str, accession_number: str, primary_document: str = "") -> str:
        clean_cik = int(str(cik).strip().lstrip("0") or "0")
        clean_acc = accession_number.replace("-", "")
        if primary_document:
            return f"https://www.sec.gov/Archives/edgar/data/{clean_cik}/{clean_acc}/{primary_document}"
        return f"https://www.sec.gov/Archives/edgar/data/{clean_cik}/{clean_acc}/{accession_number}-index.htm"

    @staticmethod
    def format_evidence_badge(
        metric_label: str,
        value: Any,
        form: str,
        filing_date: str,
        period_end: str | None,
        concept: str,
        confidence: str = "HIGH",
        edgar_url: str | None = None,
    ) -> dict[str, Any]:
        """Format an evidence record suitable for UI rendering and database storage."""
        return {
            "metric_label": metric_label,
            "value": value,
            "form": form,
            "filing_date": filing_date,
            "period_end": period_end,
            "concept": concept,
            "confidence": confidence,
            "edgar_url": edgar_url,
            "provenance_text": f"Source: SEC Form {form} (Filed: {filing_date}, Period: {period_end or 'N/A'}, Concept: {concept}, Confidence: {confidence})",
        }
