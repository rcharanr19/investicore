from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class OwnershipFilingsRepository:
    """Repository for Schedule 13D (Activist) and 13G (Passive) significant ownership records."""

    def __init__(self):
        # Keyed by id
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        rec_id = data.get("id") or str(uuid.uuid4())
        company_id = data["company_id"]

        db_payload = {
            "id": rec_id,
            "company_id": company_id,
            "filing_id": data.get("filing_id"),
            "holder_name": data.get("holder_name", "Unknown Holder"),
            "schedule_type": data.get("schedule_type", "13D"),
            "ownership_pct": float(data.get("ownership_pct", 5.0)),
            "shares_owned": float(data.get("shares_owned", 0.0)),
            "filing_date": data.get("filing_date", "2026-09-08"),
            "is_activist": bool(data.get("is_activist", False)),
            "purpose_of_transaction": data.get("purpose_of_transaction", "Investment purposes"),
            "activist_campaign_demands": data.get("activist_campaign_demands", []),
            "source_filing_url": data.get("source_filing_url"),
        }

        table = get_db_table("ownership_filings")
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
        }
        self._store[rec_id] = record
        return record

    def list_by_company(self, company_id: str, activist_only: bool = False) -> list[dict[str, Any]]:
        table = get_db_table("ownership_filings")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if activist_only:
                    query = query.eq("is_activist", True)
                res = query.order("ownership_pct", desc=True).execute()
                if res and res.data:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [o for o in self._store.values() if o.get("company_id") == company_id]
        if activist_only:
            items = [o for o in items if o.get("is_activist")]
        return sorted(items, key=lambda x: float(x.get("ownership_pct", 0.0)), reverse=True)

    def delete(self, record_id: str) -> bool:
        table = get_db_table("ownership_filings")
        if table is not None:
            try:
                table.delete().eq("id", record_id).execute()
            except Exception:
                pass
        if record_id in self._store:
            del self._store[record_id]
            return True
        return False
