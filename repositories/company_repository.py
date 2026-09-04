from __future__ import annotations

from typing import Any

from database.client import get_db_table


class CompanyRepository:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        company_id = data.get("id")
        db_payload = {
            "ticker": data["ticker"].upper(),
            "name": data["name"],
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "country": data.get("country"),
            "description": data.get("description"),
            "website": data.get("website"),
            "status": data.get("status", "Researching"),
        }
        if company_id and not company_id.startswith("company-"):
            db_payload["id"] = company_id

        table = get_db_table("companies")
        if table is not None:
            try:
                res = table.insert(db_payload).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception as e:
                pass

        cid = company_id or f"company-{len(self._store) + 1}"
        record = {
            "id": cid,
            "ticker": data["ticker"].upper(),
            "name": data["name"],
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "country": data.get("country"),
            "description": data.get("description"),
            "website": data.get("website"),
            "status": data.get("status", "Researching"),
            "created_at": data.get("created_at", "2026-01-01T00:00:00Z"),
            "updated_at": data.get("updated_at", "2026-01-01T00:00:00Z"),
        }
        self._store[cid] = record
        return record

    def update(self, company_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        table = get_db_table("companies")
        if table is not None:
            try:
                res = table.update(data).eq("id", company_id).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        current = self._store.get(company_id)
        if current is None:
            return None
        current.update(data)
        current["updated_at"] = data.get("updated_at", "2026-01-01T00:00:00Z")
        self._store[company_id] = current
        return current

    def delete(self, company_id: str) -> bool:
        table = get_db_table("companies")
        if table is not None:
            try:
                table.delete().eq("id", company_id).execute()
            except Exception:
                pass

        if company_id in self._store:
            del self._store[company_id]
            return True
        return False

    def get_by_id(self, company_id: str) -> dict[str, Any] | None:
        table = get_db_table("companies")
        if table is not None:
            try:
                res = table.select("*").eq("id", company_id).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass
        return self._store.get(company_id)

    def get_by_ticker(self, ticker: str) -> dict[str, Any] | None:
        table = get_db_table("companies")
        if table is not None:
            try:
                res = table.select("*").eq("ticker", ticker.upper()).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        for company in self._store.values():
            if company.get("ticker") == ticker.upper():
                return company
        return None

    def list_all(self) -> list[dict[str, Any]]:
        table = get_db_table("companies")
        if table is not None:
            try:
                res = table.select("*").order("ticker").execute()
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
            except Exception:
                pass
        return list(self._store.values())

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = (query or "").lower()
        all_companies = self.list_all()
        return [
            company for company in all_companies
            if needle in company.get("ticker", "").lower() or needle in company.get("name", "").lower()
        ]

