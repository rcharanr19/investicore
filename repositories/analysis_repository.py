from __future__ import annotations

from typing import Any


class AnalysisRepository:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}
        self._answers: dict[str, dict[str, Any]] = {}

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

    def create_version(self, company_id: str, previous_analysis_id: str | None, data: dict[str, Any]) -> dict[str, Any]:
        previous = self.get_by_id(previous_analysis_id) if previous_analysis_id else None
        next_version = 1 if previous is None else previous.get("version_number", 1) + 1
        payload = {
            "company_id": company_id,
            "framework_version": data.get("framework_version", previous.get("framework_version", "1.0") if previous else "1.0"),
            "analysis_date": data.get("analysis_date", "2026-01-01"),
            "status": data.get("status", previous.get("status", "Draft") if previous else "Draft"),
            "decision": data.get("decision", previous.get("decision", "Watch") if previous else "Watch"),
            "confidence": data.get("confidence", previous.get("confidence", 0) if previous else 0),
            "overall_score": data.get("overall_score", previous.get("overall_score", 0.0) if previous else 0.0),
            "notes": data.get("notes", previous.get("notes", "") if previous else ""),
            "version_number": next_version,
            "previous_analysis_id": previous_analysis_id,
            "change_summary": data.get("change_summary", "Updated analysis"),
        }
        return self.create(payload)

    def save_answers(self, analysis_id: str, answers: dict[str, Any]) -> dict[str, Any]:
        current = self._answers.setdefault(analysis_id, {})
        current.update(answers)
        return current

    def get_answers(self, analysis_id: str) -> dict[str, Any]:
        return dict(self._answers.get(analysis_id, {}))

    def compare_versions(self, previous_analysis_id: str, current_analysis_id: str) -> dict[str, Any]:
        previous = self.get_by_id(previous_analysis_id)
        current = self.get_by_id(current_analysis_id)
        if previous is None or current is None:
            return {
                "decision_change": (None, None),
                "score_change": (None, None),
                "notes_change": (None, None),
            }
        return {
            "decision_change": (previous.get("decision"), current.get("decision")),
            "score_change": (previous.get("overall_score"), current.get("overall_score")),
            "notes_change": (previous.get("notes"), current.get("notes")),
        }

    def update(self, analysis_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        current = self._store.get(analysis_id)
        if current is None:
            return None
        current.update(data)
        current["updated_at"] = data.get("updated_at", "2026-01-01T00:00:00Z")
        self._store[analysis_id] = current
        return current

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
