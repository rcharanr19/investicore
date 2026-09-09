from __future__ import annotations

from typing import Any


def validation_result(
    validation_type: str,
    status: str,
    message: str,
    expected_value: float | None = None,
    actual_value: float | None = None,
    tolerance: float | None = None,
) -> dict[str, Any]:
    difference = actual_value - expected_value if actual_value is not None and expected_value is not None else None
    return {
        "validation_type": validation_type,
        "validation_status": status,
        "message": message,
        "expected_value": expected_value,
        "actual_value": actual_value,
        "difference": difference,
        "tolerance": tolerance,
    }


def validate_balance_sheet(assets: float | None, liabilities: float | None, equity: float | None) -> dict[str, Any]:
    if None in (assets, liabilities, equity):
        return validation_result("balance_sheet_equation", "NOT_APPLICABLE", "Assets, liabilities, or equity is unavailable.")
    expected = float(liabilities) + float(equity)
    tolerance = max(abs(float(assets)) * 0.01, 1.0)
    status = "PASS" if abs(float(assets) - expected) <= tolerance else "WARNING"
    return validation_result("balance_sheet_equation", status, "Assets compared with liabilities plus equity.", expected, float(assets), tolerance)


def validate_cash_flow(beginning_cash: float | None, cfo: float | None, cfi: float | None, cff: float | None, ending_cash: float | None, fx_effect: float | None = 0.0) -> dict[str, Any]:
    values = (beginning_cash, cfo, cfi, cff, ending_cash)
    if any(value is None for value in values):
        return validation_result("cash_flow_reconciliation", "NOT_APPLICABLE", "Required cash-flow components are unavailable.")
    expected = float(beginning_cash) + float(cfo) + float(cfi) + float(cff) + float(fx_effect or 0.0)
    tolerance = max(abs(float(ending_cash)) * 0.01, 1.0)
    status = "PASS" if abs(float(ending_cash) - expected) <= tolerance else "WARNING"
    return validation_result("cash_flow_reconciliation", status, "Ending cash compared with cash-flow reconciliation.", expected, float(ending_cash), tolerance)


def validate_share_change(previous: float | None, current: float | None) -> dict[str, Any]:
    if previous is None or current is None or previous == 0:
        return validation_result("share_discontinuity", "NOT_APPLICABLE", "Comparable share counts are unavailable.")
    ratio = float(current) / float(previous)
    if 1.9 <= ratio <= 2.1 or 0.45 <= ratio <= 0.55:
        return validation_result("share_discontinuity", "REQUIRES_REVIEW", "Possible stock split or reverse split detected.", float(previous), float(current))
    if abs(ratio - 1.0) > 0.20:
        return validation_result("share_discontinuity", "REQUIRES_REVIEW", "Material share-count change requires review.", float(previous), float(current))
    return validation_result("share_discontinuity", "PASS", "No material share-count discontinuity.", float(previous), float(current))