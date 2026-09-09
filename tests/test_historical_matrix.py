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


def test_historical_matrix_displays_previous_year_change_in_the_same_cell():
    periods = [{"id": "fy2023", "fiscal_year": 2023}, {"id": "fy2024", "fiscal_year": 2024}]
    values = {"fy2023": {"revenue": 100}, "fy2024": {"revenue": 125}}
    matrix = build_historical_matrix(periods, values, "Income statement", include_yoy_change=True)
    revenue = matrix[matrix["Metric"] == "Revenue"].iloc[0]
    assert revenue["FY2023"] == "$0.0M"
    assert revenue["FY2024"] == "$0.0M\n+25.0%"