from services.scoring import calculate_quality_score, calculate_component_score, validate_probability_mix


def test_quality_score_calculations():
    components = {
        "business": 8,
        "moat": 7,
        "growth": 9,
        "financial_quality": 8,
        "management": 6,
        "capital_allocation": 7,
        "risk": 5,
    }

    score = calculate_quality_score(components)
    assert score == 7.35


def test_component_score_bounds():
    assert calculate_component_score(8, 1, 10) == 8
    assert calculate_component_score(11, 1, 10) == 10
    assert calculate_component_score(-1, 1, 10) == 1


def test_probability_validation():
    assert validate_probability_mix({"bear": 25, "base": 50, "bull": 25}) is True
    assert validate_probability_mix({"bear": 30, "base": 50, "bull": 15}) is False
    assert validate_probability_mix({"bear": 0, "base": 50, "bull": 50}) is True


def test_cagr_calculation():
    from services.valuation import calculate_cagr

    assert round(calculate_cagr(100, 200, 5), 4) == 14.8698
