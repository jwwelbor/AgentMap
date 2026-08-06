"""
Utility functions for serverless event handling.

This module provides small, focused utility functions for parsing
and converting data from different cloud platforms.
"""

import json
from typing import Any, Dict


def safe_json_loads(s: Any) -> Any:
    """
    Safely parse JSON string, returning dict or fallback for invalid JSON.

    Args:
        s: Input to parse (string or other type)

    Returns:
        The value parsed from JSON (dict, list, str, int, float, bool, or
        None — whatever ``json.loads`` yields for the given string), the
        original non-str input, or a fallback dict with raw content if the
        string was not valid JSON. Callers that require a dict must check
        the shape themselves (TD-047) rather than assume this always
        returns one.
    """
    if not isinstance(s, str):
        return s or {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {"raw": s}


def ddb_attr_to_py(value: Any) -> Any:
    """
    Convert a single DynamoDB attribute value to Python type.

    Args:
        value: DynamoDB attribute in format {"S": "string"} or {"N": "123"}

    Returns:
        Python native type value
    """
    if not isinstance(value, dict) or len(value) != 1:
        return value

    k, v = next(iter(value.items()))

    if k == "S":  # String
        return v
    elif k == "N":  # Number
        return float(v) if "." in v else int(v)
    elif k == "BOOL":  # Boolean
        return v
    elif k == "M":  # Map
        return {kk: ddb_attr_to_py(vv) for kk, vv in v.items()}
    elif k == "L":  # List
        return [ddb_attr_to_py(elem) for elem in v]
    else:
        return v


def ddb_image_to_dict(image: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert DynamoDB image (NewImage/OldImage) to Python dict.

    Args:
        image: DynamoDB image with typed attributes

    Returns:
        Python dict with native types
    """
    return {k: ddb_attr_to_py(v) for k, v in (image or {}).items()}
