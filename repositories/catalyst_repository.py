from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class CatalystRepository:
    """Repository for managing investment catalysts (8-K events, asset sales, tender offers, etc.)."""

    def __init__(self):
        # Keyed by catalyst id
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        cat_id = data.get("id") or str(uuid.uuid4())
        company_id = data["company_id"]

        db_payload = {
            "id": cat_id,
            "company_id": company_id,
            "thesis_id": data.get("thesis_id"),
            "filing_id": data.get("filing_id"),
            "catalyst_type": data.get("catalyst_type", "Other"),
            "title": data.get("title", "Untitled Catalyst"),
            "description": data.get("description", ""),
            "date_identified": data.get("date_identified", "2026-09-08"),
            "expected_date": data.get("expected_date"),
            "probability": int(data["probability"]) if data.get("probability") is not None else 50,
            "estimated_value_impact": float(data["estimated_value_impact"]) if data.get("estimated_value_impact") is not None else None,
            "status": data.get("status", "Potential"),
            "source": data.get("source", "SEC 8-K"),
            "confidence": data.get("confidence", "HIGH"),
            "notes": data.get("notes", ""),
        }

        table = get_db_table("catalysts")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.insert(db_payload).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        record = {
            **db_payload,
            "created_at": data.get("created_at", "2026-09-08T00:00:00Z"),
            "updated_at": data.get("updated_at", "2026-09-08T00:00:00Z"),
        }
        self._store[cat_id] = record
        return record

    def update(self, catalyst_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        table = get_db_table("catalysts")
        if table is not None:
            try:
                res = table.update(data).eq("id", catalyst_id).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        current = self._store.get(catalyst_id)
        if current is None:
            return None
        current.update(data)
        self._store[catalyst_id] = current
        return current

    def get_by_id(self, catalyst_id: str) -> dict[str, Any] | None:
        return self._store.get(catalyst_id)

    def list_by_company(self, company_id: str, status: str | None = None) -> list[dict[str, Any]]:
        table = get_db_table("catalysts")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if status:
                    query = query.eq("status", status)
                res = query.order("date_identified", desc=True).execute()
                if res and res.data:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [c for c in self._store.values() if c.get("company_id") == company_id]
        if status:
            items = [c for c in items if c.get("status") == status]
        return sorted(items, key=lambda x: str(x.get("date_identified") or ""), reverse=True)

    def delete(self, catalyst_id: str) -> bool:
        table = get_db_table("catalysts")
        if table is not None:
            try:
                table.delete().eq("id", catalyst_id).execute()
            except Exception:
                pass

        if catalyst_id in self._store:
            del self._store[catalyst_id]
            return True
        return False
