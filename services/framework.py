from __future__ import annotations

from pathlib import Path

import yaml


def load_framework() -> dict:
    framework_path = Path(__file__).resolve().parents[1] / "config" / "investment_framework.yaml"
    with framework_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
