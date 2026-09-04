from __future__ import annotations

from typing import Any


class AnalysisRepository:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        analysis_id = data.get("id") or f"analysis-{len(self._store) + 1}"
        record = {
            "id": analysis_id,
            "company_id": data["company_id"],
            "framework_version": data.get("framework_version", "1.0"),
            "analysis_date": data.get("analysis_date", "2026-01-01"),
            "status": data.get("status", "Draft"),
            "decision": data.get("decision", "Watch"),
            "confidence": data.get("confidence", 0),
            "overall_score": data.get("overall_score", 0.0),
            "notes": data.get("notes", ""),
            "version_number": data.get("version_number", 1),
            "previous_analysis_id": data.get("previous_analysis_id"),
            "change_summary": data.get("change_summary", ""),
            "created_at": data.get("created_at", "2026-01-01T00:00:00Z"),
            "updated_at": data.get("updated_at", "2026-01-01T00:00:00Z"),
            "framework": data.get("framework"),
            "company": data.get("company"),
        }
        self._store[analysis_id] = record
        return record

    def get_by_id(self, analysis_id: str) -> dict[str, Any] | None:
        return self._store.get(analysis_id)

    def get_latest_for_company(self, company_id: str) -> dict[str, Any] | None:
        company_analyses = [
            analysis for analysis in self._store.values() if analysis.get("company_id") == company_id
        ]
        if not company_analyses:
            return None
        return sorted(company_analyses, key=lambda item: item.get("version_number", 0), reverse=True)[0]

    def get_versions_for_company(self, company_id: str) -> list[dict[str, Any]]:
        company_analyses = [
            analysis for analysis in self._store.values() if analysis.get("company_id") == company_id
        ]
        return sorted(company_analyses, key=lambda item: item.get("version_number", 0))

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._store.values())
