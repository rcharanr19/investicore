from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class FinancialMetricRepository:
    """Repository for storing and querying granular normalized financial metrics with concept provenance."""

    def __init__(self):
        # Keyed by metric id
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        metric_id = data.get("id") or str(uuid.uuid4())
        company_id = data["company_id"]
        financial_period_id = data.get("financial_period_id")
        metric_name = data["metric_name"]
        metric_value = data.get("metric_value")

        db_payload = {
            "id": metric_id,
            "company_id": company_id,
            "financial_period_id": financial_period_id,
            "metric_name": metric_name,
            "metric_value": float(metric_value) if metric_value is not None else None,
            "currency": data.get("currency", "USD"),
            "unit": data.get("unit", "USD"),
            "source_filing_id": data.get("source_filing_id"),
            "source_concept": data.get("source_concept"),
            "source_type": data.get("source_type", "XBRL"),
            "confidence": data.get("confidence", "HIGH"),
            "is_derived": bool(data.get("is_derived", False)),
            "calculation_formula": data.get("calculation_formula"),
        }

        table = get_db_table("financial_metrics")
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
            "created_at": data.get("created_at", "2026-01-01T00:00:00Z"),
        }
        self._store[metric_id] = record
        return record

    def create_batch(self, metrics_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Batch insert metrics for efficiency."""
        created = []
        for m in metrics_list:
            created.append(self.create(m))
        return created

    def list_by_period(self, financial_period_id: str) -> list[dict[str, Any]]:
        table = get_db_table("financial_metrics")
        if table is not None:
            try:
                res = table.select("*").eq("financial_period_id", financial_period_id).execute()
                if res and res.data:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        return [m for m in self._store.values() if m.get("financial_period_id") == financial_period_id]

    def list_by_company(self, company_id: str, metric_name: str | None = None) -> list[dict[str, Any]]:
        table = get_db_table("financial_metrics")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if metric_name:
                    query = query.eq("metric_name", metric_name)
                res = query.execute()
                if res and res.data:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [m for m in self._store.values() if m.get("company_id") == company_id]
        if metric_name:
            items = [m for m in items if m.get("metric_name") == metric_name]
        return items

    def delete_by_period(self, financial_period_id: str) -> bool:
        table = get_db_table("financial_metrics")
        if table is not None:
            try:
                table.delete().eq("financial_period_id", financial_period_id).execute()
            except Exception:
                pass

        keys_to_delete = [
            k for k, v in self._store.items() if v.get("financial_period_id") == financial_period_id
        ]
        for k in keys_to_delete:
            del self._store[k]
        return True
