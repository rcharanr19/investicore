from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class FinancialPeriodRepository:
    """Repository for managing normalized financial periods (Annual, Quarterly, TTM)."""

    def __init__(self):
        # Keyed by id
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        period_id = data.get("id") or str(uuid.uuid4())
        company_id = data["company_id"]
        period_type = data.get("period_type", "Annual")
        fiscal_year = int(data["fiscal_year"])
        fiscal_period = data.get("fiscal_period")
        period_end = data["period_end"]

        db_payload = {
            "id": period_id,
            "company_id": company_id,
            "filing_id": data.get("filing_id"),
            "period_type": period_type,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "period_start": data.get("period_start"),
            "period_end": period_end,
        }

        table = get_db_table("financial_periods")
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
        self._store[period_id] = record
        return record

    def get_or_create(
        self,
        company_id: str,
        fiscal_year: int,
        period_type: str,
        period_end: str,
        fiscal_period: str | None = None,
        filing_id: str | None = None,
        period_start: str | None = None,
    ) -> dict[str, Any]:
        """Find existing period matching company, fiscal_year, period_type, and fiscal_period/period_end or create one."""
        table = get_db_table("financial_periods")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = (
                    table.select("*")
                    .eq("company_id", company_id)
                    .eq("fiscal_year", fiscal_year)
                    .eq("period_type", period_type)
                )
                if fiscal_period:
                    query = query.eq("fiscal_period", fiscal_period)
                else:
                    query = query.eq("period_end", period_end)
                res = query.execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        for p in self._store.values():
            if (
                p.get("company_id") == company_id
                and p.get("fiscal_year") == fiscal_year
                and p.get("period_type") == period_type
            ):
                if fiscal_period and p.get("fiscal_period") == fiscal_period:
                    return p
                if p.get("period_end") == period_end:
                    return p

        return self.create(
            {
                "company_id": company_id,
                "fiscal_year": fiscal_year,
                "period_type": period_type,
                "fiscal_period": fiscal_period,
                "period_end": period_end,
                "period_start": period_start,
                "filing_id": filing_id,
            }
        )

    def list_by_company(
        self,
        company_id: str,
        period_type: str | None = None,
    ) -> list[dict[str, Any]]:
        table = get_db_table("financial_periods")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if period_type:
                    query = query.eq("period_type", period_type)
                res = query.order("period_end", desc=True).execute()
                if res and res.data:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [p for p in self._store.values() if p.get("company_id") == company_id]
        if period_type:
            items = [p for p in items if p.get("period_type") == period_type]
        return sorted(items, key=lambda x: str(x.get("period_end") or ""), reverse=True)

    def get_by_id(self, period_id: str) -> dict[str, Any] | None:
        return self._store.get(period_id)
