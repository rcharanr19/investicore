from __future__ import annotations

from typing import Any

from database.client import get_db_table


class GrowthDriverRepository:
    def __init__(self):
        # Keyed by driver_id
        self._store: dict[str, dict[str, Any]] = {}
        # Keyed by driver_id -> dict of fiscal_year -> float
        self._values: dict[str, dict[int, float]] = {}

    def create_or_update(self, company_id: str, data: dict[str, Any]) -> dict[str, Any]:
        driver_id = data.get("id")
        db_payload = {
            "company_id": company_id,
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "unit": data.get("unit", ""),
            "current_value": float(data.get("current_value", 0.0)),
            "confidence": int(data.get("confidence", 70)),
            "notes": data.get("notes", ""),
        }
        if driver_id and not str(driver_id).startswith("gd-"):
            db_payload["id"] = driver_id

        table = get_db_table("growth_drivers")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.insert(db_payload).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        gdid = driver_id or f"gd-{company_id}-{len(self._store) + 1}"
        record = {
            "id": gdid,
            "company_id": company_id,
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "unit": data.get("unit", ""),
            "current_value": float(data.get("current_value", 0.0)),
            "confidence": int(data.get("confidence", 70)),
            "notes": data.get("notes", ""),
        }
        self._store[gdid] = record
        return record

    def set_driver_values(self, driver_id: str, year_values: dict[int, float]) -> None:
        self._values[driver_id] = year_values

    def get_driver_values(self, driver_id: str) -> dict[int, float]:
        return self._values.get(driver_id, {})

    def get_by_company(self, company_id: str) -> list[dict[str, Any]]:
        table = get_db_table("growth_drivers")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.select("*").eq("company_id", company_id).execute()
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass
        return [g for g in self._store.values() if g["company_id"] == company_id]

    def calculate_implied_growth_impact(self, company_id: str) -> float:
        drivers = self.get_by_company(company_id)
        if not drivers:
            return 0.10
        confidence_sum = sum(d.get("confidence", 70) for d in drivers)
        if confidence_sum == 0:
            return 0.10
        weighted_conf = confidence_sum / (len(drivers) * 100.0)
        return round(0.05 + (weighted_conf * 0.15), 4)

