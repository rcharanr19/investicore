from components.historical_matrix import build_historical_matrix, format_metric_value


def test_historical_matrix_places_metrics_in_rows_and_years_in_columns():
    periods = [{"id": "fy2023", "fiscal_year": 2023}, {"id": "fy2024", "fiscal_year": 2024}]
    values = {"fy2023": {"revenue": 2_500_000_000, "cogs": 0}, "fy2024": {"revenue": 975_300_000}}
    matrix = build_historical_matrix(periods, values, "Income statement")
    revenue = matrix[matrix["Metric"] == "Revenue"].iloc[0]
    cogs = matrix[matrix["Metric"] == "Cost of goods sold"].iloc[0]
    assert list(matrix.columns) == ["Metric", "FY2023", "FY2024"]
    assert revenue["FY2023"] == "$2.50B"
    assert revenue["FY2024"] == "$975.3M"
    assert cogs["FY2023"] == "$0.0M"
    assert cogs["FY2024"] == "-"


def test_historical_matrix_formats_percentages_multiples_and_negative_values():
    assert format_metric_value(0.142, "percentage") == "14.2%"
    assert format_metric_value(15.25, "multiple") == "15.2x"
    assert format_metric_value(-250_000_000, "currency") == "-$250.0M"
    assert format_metric_value(None, "currency") == "-"
    assert format_metric_value([100], "currency") == "-"


def test_historical_matrix_displays_previous_year_change_in_the_same_cell():
    periods = [{"id": "fy2023", "fiscal_year": 2023}, {"id": "fy2024", "fiscal_year": 2024}]
    values = {"fy2023": {"revenue": 100}, "fy2024": {"revenue": 125}}
    matrix = build_historical_matrix(periods, values, "Income statement", include_yoy_change=True)
    revenue = matrix[matrix["Metric"] == "Revenue"].iloc[0]
    assert revenue["FY2023"] == "$0.0M"
    assert revenue["FY2024"] == "$0.0M\n(+25.0%)"


def test_historical_matrix_does_not_add_yoy_to_existing_percentage_metrics():
    periods = [{"id": "fy2023", "fiscal_year": 2023}, {"id": "fy2024", "fiscal_year": 2024}]
    values = {"fy2023": {"revenue_growth": 0.10}, "fy2024": {"revenue_growth": 0.20}}
    matrix = build_historical_matrix(periods, values, "Growth & margins", include_yoy_change=True)
    growth = matrix[matrix["Metric"] == "Revenue growth"].iloc[0]
    assert growth["FY2023"] == "10.0%"
    assert growth["FY2024"] == "20.0%"


def test_historical_matrix_does_not_add_yoy_to_multiple_metrics():
    periods = [{"id": "fy2023", "fiscal_year": 2023}, {"id": "fy2024", "fiscal_year": 2024}]
    values = {"fy2023": {"current_ratio": 1.2}, "fy2024": {"current_ratio": 1.5}}
    matrix = build_historical_matrix(periods, values, "Financial strength", include_yoy_change=True)
    ratio = matrix[matrix["Metric"] == "Current ratio"].iloc[0]
    assert ratio["FY2023"] == "1.2x"
    assert ratio["FY2024"] == "1.5x"