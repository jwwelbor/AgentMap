"""Shared helpers for HTTP route modules (execute, workflows, stream)."""


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
