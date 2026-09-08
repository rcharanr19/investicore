from __future__ import annotations

import uuid
from typing import Any

from database.client import get_db_table


class ValuationSnapshotRepository:
    """Repository for time-stamped valuation snapshots supporting historical thesis tracking."""

    def __init__(self):
        # Keyed by snapshot id
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        snap_id = data.get("id") or str(uuid.uuid4())
        company_id = data["company_id"]

        db_payload = {
            "id": snap_id,
            "company_id": company_id,
            "snapshot_date": data.get("snapshot_date", "2026-09-08"),
            "share_price": float(data["share_price"]) if data.get("share_price") is not None else None,
            "shares": float(data["shares"]) if data.get("shares") is not None else None,
            "market_cap": float(data["market_cap"]) if data.get("market_cap") is not None else None,
            "ncav": float(data["ncav"]) if data.get("ncav") is not None else None,
            "ncav_per_share": float(data["ncav_per_share"]) if data.get("ncav_per_share") is not None else None,
            "price_to_ncav": float(data["price_to_ncav"]) if data.get("price_to_ncav") is not None else None,
            "nnwc": float(data["nnwc"]) if data.get("nnwc") is not None else None,
            "nnwc_per_share": float(data["nnwc_per_share"]) if data.get("nnwc_per_share") is not None else None,
            "price_to_nnwc": float(data["price_to_nnwc"]) if data.get("price_to_nnwc") is not None else None,
            "net_cash": float(data["net_cash"]) if data.get("net_cash") is not None else None,
            "adjusted_liquidation_value": float(data["adjusted_liquidation_value"]) if data.get("adjusted_liquidation_value") is not None else None,
            "catalyst_score": float(data["catalyst_score"]) if data.get("catalyst_score") is not None else None,
            "expected_value": float(data["expected_value"]) if data.get("expected_value") is not None else None,
            "expected_return": float(data["expected_return"]) if data.get("expected_return") is not None else None,
            "thesis_status": data.get("thesis_status", "INVEST"),
        }

        table = get_db_table("valuation_snapshots")
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
        self._store[snap_id] = record
        return record

    def list_by_company(self, company_id: str) -> list[dict[str, Any]]:
        table = get_db_table("valuation_snapshots")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = (
                    table.select("*")
                    .eq("company_id", company_id)
                    .order("snapshot_date", desc=True)
                    .execute()
                )
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        items = [s for s in self._store.values() if s.get("company_id") == company_id]
        return sorted(items, key=lambda x: str(x.get("snapshot_date") or ""), reverse=True)

    def get_by_id(self, snapshot_id: str) -> dict[str, Any] | None:
        return self._store.get(snapshot_id)

    def delete(self, snapshot_id: str) -> bool:
        table = get_db_table("valuation_snapshots")
        if table is not None:
            try:
                table.delete().eq("id", snapshot_id).execute()
            except Exception:
                pass
        if snapshot_id in self._store:
            del self._store[snapshot_id]
            return True
        return False
