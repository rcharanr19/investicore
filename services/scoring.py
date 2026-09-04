from __future__ import annotations


def calculate_component_score(value: float, minimum: int = 1, maximum: int = 10) -> float:
    if value is None:
        return minimum
    return max(minimum, min(maximum, value))


def calculate_quality_score(component_scores: dict[str, float]) -> float:
    weights = {
        "business": 0.20,
        "moat": 0.20,
        "growth": 0.15,
        "financial_quality": 0.15,
        "management": 0.10,
        "capital_allocation": 0.10,
        "risk": 0.10,
    }

    score = 0.0
    for key, weight in weights.items():
        normalized = calculate_component_score(component_scores.get(key, 0), 1, 10)
        score += normalized * weight
    return round(score, 2)


def validate_probability_mix(probabilities: dict[str, float]) -> bool:
    required = ["bear", "base", "bull"]
    values = {key: float(probabilities.get(key, 0)) for key in required}
    total = sum(values.values())
    if total != 100:
        return False
    return all(0 <= values[key] <= 100 for key in required)
