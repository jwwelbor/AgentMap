"""Shared helpers for HTTP route modules (execute, workflows, stream)."""

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any


def normalize_graph_identifier(identifier: str) -> str:
    """Normalize graph identifier to standard "workflow::graph" format.

    TD-015: blanket-replacing every "/" with "::" turns a nested workflow
    path like "sub/folder/graph" (or an already-"::"-form identifier that
    happens to contain a "/" inside the workflow segment) into multiple
    "::" tokens and trips downstream ``count("::") > 1`` validation. Only
    the *last* path separator is converted, matching
    ``_resolve_csv_path``'s ``identifier.rsplit("/", 1)`` convention for
    splitting workflow/graph on "/"-style identifiers; identifiers already
    in "::" form are left untouched.
    """
    identifier = identifier.replace("%3A%3A", "::")
    if "::" not in identifier and "/" in identifier:
        workflow_part, graph_part = identifier.rsplit("/", 1)
        identifier = f"{workflow_part}::{graph_part}"
    return identifier


def to_serializable(value: Any) -> Any:
    """Convert dataclasses, datetimes, and nested structures into JSON-friendly values.

    TD-036: canonical implementation. Previously duplicated as
    ``execute.py:_to_serializable`` (private) and ``sse.py:to_serializable``
    (public); both response-building paths now import this single definition
    so the recursive serialization logic has one place to update.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return to_serializable(asdict(value))
    if isinstance(value, dict):
        return {key: to_serializable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_serializable(item) for item in value]
    return value
