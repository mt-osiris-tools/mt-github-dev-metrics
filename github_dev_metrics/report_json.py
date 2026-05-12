from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from .models import DeveloperMetrics


def _default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def render_json_report(data: DeveloperMetrics) -> str:
    return json.dumps(data.to_dict(), indent=2, sort_keys=True, default=_default)

