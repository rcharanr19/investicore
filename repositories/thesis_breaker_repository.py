from __future__ import annotations

from typing import Any

from database.client import get_db_table


class ThesisBreakerRepository:
    def __init__(self):
        # Keyed by breaker_id
        self._store: dict[str, dict[str, Any]] = {}

    def create_or_update(self, analysis_id: str, data: dict[str, Any]) -> dict[str, Any]:
        breaker_id = data.get("id")
        current_val = float(data.get("current_value", 0.0)) if data.get("current_value") is not None else None
        thresh_val = float(data.get("threshold", 0.0))
        op_val = data.get("operator", "<")
        status_val = data.get("current_status", "Not Triggered")

        if current_val is not None:
            triggered = False
            if op_val == "<" and current_val < thresh_val:
                triggered = True
            elif op_val == "<=" and current_val <= thresh_val:
                triggered = True
            elif op_val == ">" and current_val > thresh_val:
                triggered = True
            elif op_val == ">=" and current_val >= thresh_val:
                triggered = True
            elif op_val == "==" and current_val == thresh_val:
                triggered = True
            if triggered:
                status_val = "Triggered"

        db_payload = {
            "analysis_id": analysis_id,
            "condition": data.get("condition", ""),
            "metric": data.get("metric", ""),
            "operator": op_val,
            "threshold": thresh_val,
            "current_value": current_val,
            "current_status": status_val,
            "notes": data.get("notes", ""),
        }
        if breaker_id and not str(breaker_id).startswith("breaker-"):
            db_payload["id"] = breaker_id

        table = get_db_table("thesis_breakers")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.insert(db_payload).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[rec["id"]] = rec
                    return rec
            except Exception:
                pass

        bid = breaker_id or f"breaker-{analysis_id}-{len(self._store) + 1}"
        record = {
            "id": bid,
            "analysis_id": analysis_id,
            "condition": data.get("condition", ""),
            "metric": data.get("metric", ""),
            "operator": op_val,
            "threshold": thresh_val,
            "current_value": current_val,
            "current_status": status_val,
            "notes": data.get("notes", ""),
        }
        self._store[bid] = record
        return record

    def get_by_analysis(self, analysis_id: str) -> list[dict[str, Any]]:
        table = get_db_table("thesis_breakers")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.select("*").eq("analysis_id", analysis_id).execute()
                if res and res.data is not None:
                    for rec in res.data:
                        self._store[rec["id"]] = rec
                    return res.data
            except Exception:
                pass
        return [b for b in self._store.values() if b["analysis_id"] == analysis_id]

    def delete(self, breaker_id: str) -> bool:
        table = get_db_table("thesis_breakers")
        if table is not None and not str(breaker_id).startswith("breaker-"):
            try:
                table.delete().eq("id", breaker_id).execute()
            except Exception:
                pass
        if breaker_id in self._store:
            del self._store[breaker_id]
            return True
        return False

    def check_breakers_status(self, analysis_id: str) -> dict[str, Any]:
        breakers = self.get_by_analysis(analysis_id)
        triggered = [b for b in breakers if b.get("current_status") == "Triggered"]
        warnings = [b for b in breakers if b.get("current_status") == "Warning"]
        return {
            "total": len(breakers),
            "triggered_count": len(triggered),
            "warning_count": len(warnings),
            "has_triggered": len(triggered) > 0,
            "triggered_conditions": [b.get("condition", "") for b in triggered],
        }

