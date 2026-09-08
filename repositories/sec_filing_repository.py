from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class SECFilingRepository:
    def __init__(self):
        # Keyed by filing_id
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        filing_id = data.get("id") or str(uuid.uuid4())
        company_id = data["company_id"]
        accession_number = data["accession_number"]

        db_payload = {
            "id": filing_id,
            "company_id": company_id,
            "accession_number": accession_number,
            "form_type": data["form_type"],
            "filing_date": data["filing_date"],
            "report_date": data.get("report_date"),
            "period_start": data.get("period_start"),
            "period_end": data.get("period_end"),
            "fiscal_year": data.get("fiscal_year"),
            "fiscal_period": data.get("fiscal_period"),
            "primary_document": data.get("primary_document"),
            "filing_url": data.get("filing_url"),
            "index_url": data.get("index_url"),
            "is_xbrl": data.get("is_xbrl", False),
            "is_inline_xbrl": data.get("is_inline_xbrl", False),
            "items": data.get("items"),
            "raw_content_location": data.get("raw_content_location"),
            "content_hash": data.get("content_hash"),
            "parsed_status": data.get("parsed_status", "Unparsed"),
            "parse_version": data.get("parse_version", "1.0"),
        }

        table = get_db_table("sec_filings")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.upsert(db_payload, on_conflict="company_id,accession_number").execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        record = {
            **db_payload,
            "id": filing_id,
            "created_at": data.get("created_at", "2026-01-01T00:00:00Z"),
            "updated_at": data.get("updated_at", "2026-01-01T00:00:00Z"),
        }
        self._store[filing_id] = record
        return record

    def update(self, filing_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        table = get_db_table("sec_filings")
        if table is not None:
            try:
                res = table.update(data).eq("id", filing_id).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        current = self._store.get(filing_id)
        if current is None:
            return None
        current.update(data)
        self._store[filing_id] = current
        return current

    def get_by_id(self, filing_id: str) -> dict[str, Any] | None:
        table = get_db_table("sec_filings")
        if table is not None:
            try:
                res = table.select("*").eq("id", filing_id).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass
        return self._store.get(filing_id)

    def get_by_accession(self, company_id: str, accession_number: str) -> dict[str, Any] | None:
        table = get_db_table("sec_filings")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = (
                    table.select("*")
                    .eq("company_id", company_id)
                    .eq("accession_number", accession_number)
                    .execute()
                )
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        for filing in self._store.values():
            if filing.get("company_id") == company_id and filing.get("accession_number") == accession_number:
                return filing
        return None

    def list_by_company(
        self,
        company_id: str,
        form_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        table = get_db_table("sec_filings")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if form_types:
                    query = query.in_("form_type", form_types)
                res = query.order("filing_date", desc=True).limit(limit).execute()
                if res and res.data:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [f for f in self._store.values() if f.get("company_id") == company_id]
        if form_types:
            forms_set = {ft.upper() for ft in form_types}
            items = [f for f in items if f.get("form_type", "").upper() in forms_set]

        # Sort by filing_date desc
        items = sorted(items, key=lambda x: str(x.get("filing_date") or ""), reverse=True)
        return items[:limit]

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._store.values())

    def delete(self, filing_id: str) -> bool:
        table = get_db_table("sec_filings")
        if table is not None:
            try:
                table.delete().eq("id", filing_id).execute()
            except Exception:
                pass
        if filing_id in self._store:
            del self._store[filing_id]
            return True
        return False
