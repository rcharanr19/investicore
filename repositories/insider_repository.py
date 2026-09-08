from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class InsiderTransactionsRepository:
    """Repository for Form 4 insider transactions (open-market purchases, sales, awards, option exercises)."""

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
            "reporting_person": data.get("reporting_person", "Insider"),
            "officer_title": data.get("officer_title", "Director / Officer"),
            "transaction_date": data.get("transaction_date", "2026-09-08"),
            "transaction_code": data.get("transaction_code", "P"),
            "transaction_type": data.get("transaction_type", "Open Market Purchase"),
            "shares_transacted": float(data.get("shares_transacted", 0.0)),
            "price_per_share": float(data["price_per_share"]) if data.get("price_per_share") is not None else None,
            "total_value": float(data.get("total_value", 0.0)),
            "shares_owned_after": float(data.get("shares_owned_after", 0.0)),
            "is_direct": bool(data.get("is_direct", True)),
            "is_open_market_purchase": bool(data.get("is_open_market_purchase", False)),
            "source_filing_url": data.get("source_filing_url"),
        }

        table = get_db_table("insider_transactions")
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

    def list_by_company(self, company_id: str, open_market_only: bool = False) -> list[dict[str, Any]]:
        table = get_db_table("insider_transactions")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if open_market_only:
                    query = query.eq("is_open_market_purchase", True)
                res = query.order("transaction_date", desc=True).execute()
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [i for i in self._store.values() if i.get("company_id") == company_id]
        if open_market_only:
            items = [i for i in items if i.get("is_open_market_purchase")]
        return sorted(items, key=lambda x: str(x.get("transaction_date") or ""), reverse=True)

    def delete(self, record_id: str) -> bool:
        table = get_db_table("insider_transactions")
        if table is not None:
            try:
                table.delete().eq("id", record_id).execute()
            except Exception:
                pass
        if record_id in self._store:
            del self._store[record_id]
            return True
        return False
