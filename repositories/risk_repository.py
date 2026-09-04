from __future__ import annotations

from typing import Any

from database.client import get_db_table


class RiskRepository:
    def __init__(self):
        # Keyed by risk_id
        self._store: dict[str, dict[str, Any]] = {}

    def create_or_update(self, analysis_id: str, data: dict[str, Any]) -> dict[str, Any]:
        risk_id = data.get("id")
        db_payload = {
            "analysis_id": analysis_id,
            "risk": data.get("risk", ""),
            "category": data.get("category", "Other"),
            "probability": int(data.get("probability", 50)),
            "impact": int(data.get("impact", 5)),
            "time_horizon": data.get("time_horizon", "Medium term"),
            "mitigation": data.get("mitigation", ""),
            "status": data.get("status", "Active"),
            "notes": data.get("notes", ""),
        }
        if risk_id and not str(risk_id).startswith("risk-"):
            db_payload["id"] = risk_id

        table = get_db_table("risks")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.insert(db_payload).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        rid = risk_id or f"risk-{analysis_id}-{len(self._store) + 1}"
        record = {
            "id": rid,
            "analysis_id": analysis_id,
            "risk": data.get("risk", ""),
            "category": data.get("category", "Other"),
            "probability": int(data.get("probability", 50)),
            "impact": int(data.get("impact", 5)),
            "time_horizon": data.get("time_horizon", "Medium term"),
            "mitigation": data.get("mitigation", ""),
            "status": data.get("status", "Active"),
            "notes": data.get("notes", ""),
        }
        self._store[rid] = record
        return record

    def get_by_analysis(self, analysis_id: str) -> list[dict[str, Any]]:
        table = get_db_table("risks")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.select("*").eq("analysis_id", analysis_id).execute()
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass
        return [r for r in self._store.values() if r["analysis_id"] == analysis_id]

    def delete(self, risk_id: str) -> bool:
        table = get_db_table("risks")
        if table is not None and not str(risk_id).startswith("risk-"):
            try:
                table.delete().eq("id", risk_id).execute()
            except Exception:
                pass
        if risk_id in self._store:
            del self._store[risk_id]
            return True
        return False

    def calculate_aggregate_risk_score(self, analysis_id: str) -> float:
        risks = self.get_by_analysis(analysis_id)
        if not risks:
            return 5.0
        scores = [(r.get("probability", 50) / 100.0) * r.get("impact", 5) for r in risks]
        avg_risk_severity = sum(scores) / len(scores)
        quality_risk_component = max(1.0, min(10.0, 10.0 - avg_risk_severity))
        return round(quality_risk_component, 2)

