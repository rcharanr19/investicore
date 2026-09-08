from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class ManagementCompensationRepository:
    """Repository for DEF 14A executive compensation, ownership, and governance records."""

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
            "fiscal_year": int(data.get("fiscal_year", 2025)),
            "executive_name": data.get("executive_name", "Named Executive"),
            "title": data.get("title", "Executive"),
            "base_salary": float(data.get("base_salary", 0.0)),
            "bonus": float(data.get("bonus", 0.0)),
            "stock_awards": float(data.get("stock_awards", 0.0)),
            "option_awards": float(data.get("option_awards", 0.0)),
            "other_compensation": float(data.get("other_compensation", 0.0)),
            "total_compensation": float(data.get("total_compensation", 0.0)),
            "shares_owned": float(data.get("shares_owned", 0.0)),
            "ownership_pct": float(data.get("ownership_pct", 0.0)),
            "incentive_metrics": data.get("incentive_metrics", "TSR, ROIC, FCF"),
            "alignment_score": float(data.get("alignment_score", 70.0)),
            "governance_flags": data.get("governance_flags", []),
            "source_filing": data.get("source_filing", "SEC DEF 14A"),
        }

        table = get_db_table("management_compensation")
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

    def list_by_company(self, company_id: str) -> list[dict[str, Any]]:
        table = get_db_table("management_compensation")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = (
                    table.select("*")
                    .eq("company_id", company_id)
                    .order("total_compensation", desc=True)
                    .execute()
                )
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [m for m in self._store.values() if m.get("company_id") == company_id]
        return sorted(items, key=lambda x: float(x.get("total_compensation", 0.0)), reverse=True)

    def delete(self, record_id: str) -> bool:
        table = get_db_table("management_compensation")
        if table is not None:
            try:
                table.delete().eq("id", record_id).execute()
            except Exception:
                pass
        if record_id in self._store:
            del self._store[record_id]
            return True
        return False
