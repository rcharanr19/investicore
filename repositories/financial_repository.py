from __future__ import annotations

from typing import Any

from database.client import get_db_table


class FinancialRepository:
    def __init__(self):
        # Keyed by f"{company_id}_{fiscal_year}"
        self._store: dict[str, dict[str, Any]] = {}

    def create_or_update(self, company_id: str, fiscal_year: int, data: dict[str, Any]) -> dict[str, Any]:
        key = f"{company_id}_{fiscal_year}"
        db_payload = {
            "company_id": company_id,
            "fiscal_year": int(fiscal_year),
            "revenue": float(data.get("revenue", 0.0)),
            "gross_profit": float(data.get("gross_profit", 0.0)),
            "operating_income": float(data.get("operating_income", 0.0)),
            "net_income": float(data.get("net_income", 0.0)),
            "eps": float(data.get("eps", 0.0)),
            "free_cash_flow": float(data.get("free_cash_flow", 0.0)),
            "capex": float(data.get("capex", 0.0)),
            "rnd": float(data.get("rnd", 0.0)),
            "sbc": float(data.get("sbc", 0.0)),
            "cash": float(data.get("cash", 0.0)),
            "debt": float(data.get("debt", 0.0)),
            "shares_outstanding": float(data.get("shares_outstanding", 1.0)),
        }

        table = get_db_table("financials")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.upsert(db_payload, on_conflict="company_id,fiscal_year").execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[key] = rec
                    return rec
            except Exception:
                pass

        record = {
            "id": data.get("id") or f"fin-{key}",
            "company_id": company_id,
            "fiscal_year": int(fiscal_year),
            "revenue": float(data.get("revenue", 0.0)),
            "gross_profit": float(data.get("gross_profit", 0.0)),
            "operating_income": float(data.get("operating_income", 0.0)),
            "net_income": float(data.get("net_income", 0.0)),
            "eps": float(data.get("eps", 0.0)),
            "free_cash_flow": float(data.get("free_cash_flow", 0.0)),
            "capex": float(data.get("capex", 0.0)),
            "rnd": float(data.get("rnd", 0.0)),
            "sbc": float(data.get("sbc", 0.0)),
            "cash": float(data.get("cash", 0.0)),
            "debt": float(data.get("debt", 0.0)),
            "shares_outstanding": float(data.get("shares_outstanding", 1.0)),
            "updated_at": data.get("updated_at", "2026-09-04T00:00:00Z"),
        }
        self._store[key] = record
        return record

    def get_by_company(self, company_id: str) -> list[dict[str, Any]]:
        table = get_db_table("financials")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.select("*").eq("company_id", company_id).order("fiscal_year").execute()
                if res and res.data is not None:
                    for rec in res.data:
                        k = f"{company_id}_{rec['fiscal_year']}"
                        self._store[k] = rec
                    return res.data
            except Exception:
                pass

        records = [rec for rec in self._store.values() if rec["company_id"] == company_id]
        return sorted(records, key=lambda x: x["fiscal_year"])

    def get_latest(self, company_id: str) -> dict[str, Any] | None:
        records = self.get_by_company(company_id)
        return records[-1] if records else None

    def calculate_historical_cagr(self, company_id: str, metric: str = "revenue") -> float | None:
        records = self.get_by_company(company_id)
        if len(records) < 2:
            return None
        first = records[0].get(metric, 0.0)
        last = records[-1].get(metric, 0.0)
        years = records[-1]["fiscal_year"] - records[0]["fiscal_year"]
        if first <= 0 or years <= 0:
            return None
        return (((last / first) ** (1 / years)) - 1) * 100

