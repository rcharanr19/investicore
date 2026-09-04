from __future__ import annotations

from typing import Any


class RiskRepository:
    def __init__(self):
        # Keyed by risk_id
        self._store: dict[str, dict[str, Any]] = {}

    def create_or_update(self, analysis_id: str, data: dict[str, Any]) -> dict[str, Any]:
        risk_id = data.get("id") or f"risk-{analysis_id}-{len(self._store) + 1}"
        record = {
            "id": risk_id,
            "analysis_id": analysis_id,
            "risk": data.get("risk", ""),
            "category": data.get("category", "Other"),
            "probability": int(data.get("probability", 50)),  # 0 to 100
            "impact": int(data.get("impact", 5)),            # 1 to 10
            "time_horizon": data.get("time_horizon", "Medium term"),
            "mitigation": data.get("mitigation", ""),
            "status": data.get("status", "Active"),
            "notes": data.get("notes", ""),
        }
        self._store[risk_id] = record
        return record

    def get_by_analysis(self, analysis_id: str) -> list[dict[str, Any]]:
        return [r for r in self._store.values() if r["analysis_id"] == analysis_id]

    def delete(self, risk_id: str) -> bool:
        if risk_id in self._store:
            del self._store[risk_id]
            return True
        return False

    def calculate_aggregate_risk_score(self, analysis_id: str) -> float:
        risks = self.get_by_analysis(analysis_id)
        if not risks:
            return 5.0  # Neutral risk score (1-10)
        # Risk score = Average of (probability / 100 * impact) mapped to 1-10 scale
        scores = [(r["probability"] / 100.0) * r["impact"] for r in risks]
        avg_risk_severity = sum(scores) / len(scores)
        # Invert for Quality Score (lower severity = higher quality score, 10 - severity)
        quality_risk_component = max(1.0, min(10.0, 10.0 - avg_risk_severity))
        return round(quality_risk_component, 2)
