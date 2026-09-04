from __future__ import annotations

from typing import Any


class ThesisBreakerRepository:
    def __init__(self):
        # Keyed by breaker_id
        self._store: dict[str, dict[str, Any]] = {}

    def create_or_update(self, analysis_id: str, data: dict[str, Any]) -> dict[str, Any]:
        breaker_id = data.get("id") or f"breaker-{analysis_id}-{len(self._store) + 1}"
        record = {
            "id": breaker_id,
            "analysis_id": analysis_id,
            "condition": data.get("condition", ""),
            "metric": data.get("metric", ""),
            "operator": data.get("operator", "<"),  # <, <=, >, >=, ==
            "threshold": float(data.get("threshold", 0.0)),
            "current_value": float(data.get("current_value", 0.0)) if data.get("current_value") is not None else None,
            "current_status": data.get("current_status", "Not Triggered"),  # Not Triggered, Warning, Triggered
            "notes": data.get("notes", ""),
        }

        # Auto-evaluate status if current_value is supplied
        if record["current_value"] is not None:
            val = record["current_value"]
            thresh = record["threshold"]
            op = record["operator"]
            triggered = False
            if op == "<" and val < thresh:
                triggered = True
            elif op == "<=" and val <= thresh:
                triggered = True
            elif op == ">" and val > thresh:
                triggered = True
            elif op == ">=" and val >= thresh:
                triggered = True
            elif op == "==" and val == thresh:
                triggered = True

            if triggered:
                record["current_status"] = "Triggered"

        self._store[breaker_id] = record
        return record

    def get_by_analysis(self, analysis_id: str) -> list[dict[str, Any]]:
        return [b for b in self._store.values() if b["analysis_id"] == analysis_id]

    def delete(self, breaker_id: str) -> bool:
        if breaker_id in self._store:
            del self._store[breaker_id]
            return True
        return False

    def check_breakers_status(self, analysis_id: str) -> dict[str, Any]:
        breakers = self.get_by_analysis(analysis_id)
        triggered = [b for b in breakers if b["current_status"] == "Triggered"]
        warnings = [b for b in breakers if b["current_status"] == "Warning"]
        return {
            "total": len(breakers),
            "triggered_count": len(triggered),
            "warning_count": len(warnings),
            "has_triggered": len(triggered) > 0,
            "triggered_conditions": [b["condition"] for b in triggered],
        }
