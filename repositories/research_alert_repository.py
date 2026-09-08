from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class ResearchAlertRepository:
    """Repository for managing filing change detections, YoY/QoQ divergences, and research alerts."""

    def __init__(self):
        # Keyed by alert id
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        alert_id = data.get("id") or str(uuid.uuid4())
        company_id = data["company_id"]

        db_payload = {
            "id": alert_id,
            "company_id": company_id,
            "filing_id": data.get("filing_id"),
            "alert_type": data.get("alert_type", "FILING_CHANGE"),
            "headline": data.get("headline", "Material Filing Change Detected"),
            "description": data.get("description", ""),
            "severity": data.get("severity", "INFO"),
        }

        table = get_db_table("research_alerts")
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
        self._store[alert_id] = record
        return record

    def list_by_company(self, company_id: str, severity: str | None = None) -> list[dict[str, Any]]:
        table = get_db_table("research_alerts")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if severity:
                    query = query.eq("severity", severity)
                res = query.order("created_at", desc=True).execute()
                if res and res.data:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [a for a in self._store.values() if a.get("company_id") == company_id]
        if severity:
            items = [a for a in items if a.get("severity") == severity]
        return sorted(items, key=lambda x: str(x.get("created_at") or ""), reverse=True)

    def delete(self, alert_id: str) -> bool:
        table = get_db_table("research_alerts")
        if table is not None:
            try:
                table.delete().eq("id", alert_id).execute()
            except Exception:
                pass
        if alert_id in self._store:
            del self._store[alert_id]
            return True
        return False

    def clear_for_company(self, company_id: str) -> bool:
        to_del = [k for k, v in self._store.items() if v.get("company_id") == company_id]
        for k in to_del:
            del self._store[k]
        return True
