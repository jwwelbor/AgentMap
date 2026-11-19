"""Shared, deterministic ordering rules for document storage queries."""

import json
import math
from typing import Any, Optional, Tuple


def get_sort_options(field: Any, order: Any) -> Tuple[Optional[str], bool]:
    """Return a valid field and descending flag from untrusted query values."""
    sort_field = field if isinstance(field, str) and field else None
    reverse = isinstance(order, str) and order.lower() == "desc"
    return sort_field, reverse


def stable_sort_key(value: Any) -> Tuple[int, Any]:
    """Order JSON-like values consistently without comparing unlike types.

    Values sort in this order: null, booleans, numbers, strings, then compound
    or unsupported values. Compound values use canonical JSON when possible.
    """
    if value is None:
        return 0, ""
    if isinstance(value, bool):
        return 1, int(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return 2, (1, "nan")
        return 2, (0, value)
    if isinstance(value, str):
        return 3, value

    try:
        stable_value = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError):
        stable_value = repr(value)
    return 4, stable_value
