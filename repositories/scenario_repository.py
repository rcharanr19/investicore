from __future__ import annotations

from typing import Any

from database.client import get_db_table
from services.scoring import validate_probability_mix
from services.valuation import calculate_expected_return, calculate_future_fcf, calculate_future_revenue


class ScenarioRepository:
    def __init__(self):
        # Keyed by analysis_id -> dict of scenario_name -> scenario data
        self._store: dict[str, dict[str, dict[str, Any]]] = {}

    def save_scenarios(self, analysis_id: str, scenarios: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        probs = {name.lower(): data.get("probability", 0) for name, data in scenarios.items()}
        if not validate_probability_mix(probs):
            raise ValueError("Scenario probabilities must total exactly 100%.")

        table = get_db_table("scenarios")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                for name, s_data in scenarios.items():
                    payload = {
                        "analysis_id": analysis_id,
                        "scenario_name": name,
                        "probability": int(s_data.get("probability", 33)),
                        "revenue_cagr": float(s_data.get("revenue_cagr", 0.10)),
                        "forecast_period": int(s_data.get("forecast_period", 5)),
                        "fcf_margin": float(s_data.get("fcf_margin", 0.20)),
                        "terminal_multiple": float(s_data.get("terminal_multiple", 15.0)),
                    }
                    table.insert(payload).execute()
            except Exception:
                pass

        self._store[analysis_id] = scenarios
        return self._store[analysis_id]

    def get_scenarios(self, analysis_id: str) -> dict[str, dict[str, Any]]:
        table = get_db_table("scenarios")
        if table is not None and not str(analysis_id).startswith("analysis-"):
            try:
                res = table.select("*").eq("analysis_id", analysis_id).execute()
                if res and res.data:
                    scen_map = {}
                    for row in res.data:
                        scen_map[row["scenario_name"]] = {
                            "probability": row.get("probability", 33),
                            "revenue_cagr": float(row.get("revenue_cagr", 0.10)) if row.get("revenue_cagr") else 0.10,
                            "forecast_period": row.get("forecast_period", 5),
                            "fcf_margin": float(row.get("fcf_margin", 0.20)) if row.get("fcf_margin") else 0.20,
                            "terminal_multiple": float(row.get("terminal_multiple", 15.0)) if row.get("terminal_multiple") else 15.0,
                        }
                    self._store[analysis_id] = scen_map
                    return scen_map
            except Exception:
                pass
        return self._store.get(analysis_id, {})

    def calculate_scenario_outputs(
        self,
        analysis_id: str,
        current_revenue: float,
        current_share_price: float,
        cash: float = 0.0,
        debt: float = 0.0,
        shares_outstanding: float = 1.0,
    ) -> dict[str, Any]:
        scenarios = self.get_scenarios(analysis_id)
        if not scenarios:
            return {"scenarios": {}, "weighted_implied_share_price": 0.0, "weighted_expected_return": 0.0}

        outputs = {}
        weighted_price = 0.0
        shares = max(shares_outstanding, 1.0)
        default_years = 5

        for name, params in scenarios.items():
            prob = params.get("probability", 0)
            cagr = params.get("revenue_cagr", 0.10)
            cagr_decimal = cagr / 100.0 if cagr > 1.0 else cagr
            years = int(params.get("forecast_period", default_years))
            fcf_margin = float(params.get("fcf_margin", 0.10))
            multiple = float(params.get("terminal_multiple", 15.0))

            future_rev = calculate_future_revenue(current_revenue, cagr_decimal, years)
            future_fcf = calculate_future_fcf(future_rev, fcf_margin)
            equity_val = (future_fcf * multiple) + cash - debt
            implied_price = equity_val / shares
            annual_return = calculate_expected_return(current_share_price, max(implied_price, 0.01), years)

            weighted_price += (prob / 100.0) * implied_price

            outputs[name] = {
                "probability": prob,
                "cagr_decimal": cagr_decimal,
                "years": years,
                "fcf_margin": fcf_margin,
                "terminal_multiple": multiple,
                "future_revenue": future_rev,
                "future_fcf": future_fcf,
                "equity_value": equity_val,
                "implied_share_price": implied_price,
                "expected_annual_return": annual_return,
            }

            default_years = years

        weighted_return = calculate_expected_return(current_share_price, max(weighted_price, 0.01), default_years)

        return {
            "scenarios": outputs,
            "weighted_implied_share_price": weighted_price,
            "weighted_expected_return": weighted_return,
        }
