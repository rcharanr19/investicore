from __future__ import annotations

from typing import Any

from database.client import get_db_table


class AnalysisRepository:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}
        self._answers: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        analysis_id = data.get("id")
        db_payload = {
            "company_id": data["company_id"],
            "framework_version": data.get("framework_version", "1.0"),
            "analysis_date": str(data.get("analysis_date", "2026-09-04")),
            "status": data.get("status", "Draft"),
            "decision": data.get("decision", "Watch"),
            "confidence": int(data.get("confidence", 70)),
            "overall_score": float(data.get("overall_score", 0.0)),
            "notes": data.get("notes", ""),
            "version_number": int(data.get("version_number", 1)),
            "change_summary": data.get("change_summary", ""),
        }
        prev_id = data.get("previous_analysis_id")
        if prev_id and not str(prev_id).startswith("analysis-"):
            db_payload["previous_analysis_id"] = prev_id

        if analysis_id and not str(analysis_id).startswith("analysis-"):
            db_payload["id"] = analysis_id

        table = get_db_table("analyses")
        if table is not None:
            try:
                res = table.insert(db_payload).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        aid = analysis_id or f"analysis-{len(self._store) + 1}"
        record = {
            "id": aid,
            "company_id": data["company_id"],
            "framework_version": data.get("framework_version", "1.0"),
            "analysis_date": data.get("analysis_date", "2026-09-04"),
            "status": data.get("status", "Draft"),
            "decision": data.get("decision", "Watch"),
            "confidence": data.get("confidence", 70),
            "overall_score": data.get("overall_score", 0.0),
            "notes": data.get("notes", ""),
            "version_number": data.get("version_number", 1),
            "previous_analysis_id": data.get("previous_analysis_id"),
            "change_summary": data.get("change_summary", ""),
            "created_at": data.get("created_at", "2026-09-04T00:00:00Z"),
            "updated_at": data.get("updated_at", "2026-09-04T00:00:00Z"),
            "framework": data.get("framework"),
            "company": data.get("company"),
        }
        self._store[aid] = record
        return record

    def create_version(self, company_id: str, previous_analysis_id: str | None, data: dict[str, Any]) -> dict[str, Any]:
        previous = self.get_by_id(previous_analysis_id) if previous_analysis_id else None
        next_version = 1 if previous is None else previous.get("version_number", 1) + 1
        payload = {
            "company_id": company_id,
            "framework_version": data.get("framework_version", previous.get("framework_version", "1.0") if previous else "1.0"),
            "analysis_date": data.get("analysis_date", "2026-09-04"),
            "status": data.get("status", previous.get("status", "Draft") if previous else "Draft"),
            "decision": data.get("decision", previous.get("decision", "Watch") if previous else "Watch"),
            "confidence": data.get("confidence", previous.get("confidence", 70) if previous else 70),
            "overall_score": data.get("overall_score", previous.get("overall_score", 0.0) if previous else 0.0),
            "notes": data.get("notes", previous.get("notes", "") if previous else ""),
            "version_number": next_version,
            "previous_analysis_id": previous_analysis_id,
            "change_summary": data.get("change_summary", "Updated analysis"),
        }
        return self.create(payload)

    def save_answers(self, analysis_id: str, answers: dict[str, Any]) -> dict[str, Any]:
        table = get_db_table("analysis_answers")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                for qid, val in answers.items():
                    payload = {
                        "analysis_id": analysis_id,
                        "section_id": "general",
                        "question_id": str(qid),
                        "answer_value": str(val) if val is not None else None,
                    }
                    table.insert(payload).execute()
            except Exception:
                pass

        current = self._answers.setdefault(analysis_id, {})
        current.update(answers)
        return current

    def get_answers(self, analysis_id: str) -> dict[str, Any]:
        table = get_db_table("analysis_answers")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.select("*").eq("analysis_id", analysis_id).execute()
                if res and res.data:
                    ret = {row["question_id"]: row["answer_value"] for row in res.data}
                    self._answers[analysis_id] = ret
                    return ret
            except Exception:
                pass
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
        table = get_db_table("analyses")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.update(data).eq("id", analysis_id).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        current = self._store.get(analysis_id)
        if current is None:
            return None
        current.update(data)
        current["updated_at"] = data.get("updated_at", "2026-09-04T00:00:00Z")
        self._store[analysis_id] = current
        return current

    def get_by_id(self, analysis_id: str) -> dict[str, Any] | None:
        table = get_db_table("analyses")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.select("*").eq("id", analysis_id).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass
        return self._store.get(analysis_id)

    def get_latest_for_company(self, company_id: str) -> dict[str, Any] | None:
        versions = self.get_versions_for_company(company_id)
        return versions[-1] if versions else None

    def get_versions_for_company(self, company_id: str) -> list[dict[str, Any]]:
        table = get_db_table("analyses")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.select("*").eq("company_id", company_id).order("version_number").execute()
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass

        company_analyses = [
            analysis for analysis in self._store.values() if analysis.get("company_id") == company_id
        ]
        return sorted(company_analyses, key=lambda item: item.get("version_number", 0))

    def list_all(self) -> list[dict[str, Any]]:
        table = get_db_table("analyses")
        if table is not None:
            try:
                res = table.select("*").order("version_number").execute()
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
            except Exception:
                pass
        return list(self._store.values())

