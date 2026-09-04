from __future__ import annotations

from typing import Any


class CompanyRepository:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        company_id = data.get("id") or f"company-{len(self._store) + 1}"
        record = {
            "id": company_id,
            "ticker": data["ticker"],
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
        self._store[company_id] = record
        return record

    def get_by_id(self, company_id: str) -> dict[str, Any] | None:
        return self._store.get(company_id)

    def get_by_ticker(self, ticker: str) -> dict[str, Any] | None:
        for company in self._store.values():
            if company.get("ticker") == ticker:
                return company
        return None

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._store.values())

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = (query or "").lower()
        return [
            company for company in self._store.values()
            if needle in company.get("ticker", "").lower() or needle in company.get("name", "").lower()
        ]
