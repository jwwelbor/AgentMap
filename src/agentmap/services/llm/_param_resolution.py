"""
Centralized batch request parameter resolution (E05-F04, AC-8 / REQ-F-008).

A single ``resolve_spec_params`` function runs at the service boundary, before
any adapter dispatch.  It reads a ``RESERVED_PARAMS`` registry that is the
*only* place the "these are the same logical parameter" mapping lives, applies
one deterministic rule:

- Two or more surfaces with *different* values → ``LLMBatchParamConflictError``
- Two or more surfaces with the *same* value → allow; emit the single value
- Exactly one surface set → apply that value
- No surface set → param absent (let the provider default apply)

Adapters receive the already-resolved, conflict-free dict and perform no
merging of their own.  Provider-specific key renames (e.g. Gemini
``max_output_tokens``) happen inside the adapter *after* resolution.

Decision: D-8 (spec.md § Canonical Parameter Resolution).
"""

import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from agentmap.models.llm_execution import LLMBatchSubmitRequest, LLMCallSpec
from agentmap.services.llm_batch_errors import LLMBatchParamConflictError


@dataclass(frozen=True)
class ReservedParam:
    """Describes how one logical parameter maps across the four param surfaces.

    ``aliases`` lists provider-specific keys that are logically equivalent to
    ``options_key``.  Any alias found in an options dict is treated as if it
    were the canonical ``options_key`` — so a conflict between ``max_tokens``
    and ``max_output_tokens`` (a Gemini alias) across surfaces is detected and
    raises ``LLMBatchParamConflictError``, rather than silently overwriting the
    canonical value (AC-8 / N1, CR5-1).
    """

    logical: str  # canonical name, e.g. "temperature"
    options_key: str  # key used in request_options dicts, e.g. "temperature"
    spec_field: Optional[str]  # LLMCallSpec direct attr, or None
    request_field: Optional[str]  # LLMBatchSubmitRequest direct attr, or None
    aliases: FrozenSet[str] = field(
        default_factory=frozenset
    )  # provider-specific aliases


# Single source of truth for reserved-parameter surface mapping.
#
# Each row = one logical parameter.  To add a future key (e.g. top_p, top_k),
# add exactly one row here — the conflict-matrix test covers it automatically.
#
# Surface availability per param:
#   temperature:  S1 (spec.temperature) | S2 (spec.request_options["temperature"])
#                 | S4 (request.request_options["temperature"])
#                 (no batch-level direct field for temperature)
#   model:        S1 (spec.model) | S2 (spec.request_options["model"])
#                 | S3 (request.model) | S4 (request.request_options["model"])
#   max_tokens:   S2 (spec.request_options["max_tokens"])
#                 | S3 (request.max_tokens) | S4 (request.request_options["max_tokens"])
#                 (no per-spec direct field for max_tokens on LLMCallSpec)
#
# Aliases:
#   max_tokens aliases max_output_tokens (Gemini provider-specific rename).
#   A caller supplying max_output_tokens in any options dict is treated as
#   supplying max_tokens — conflict-detection applies across the combined set.
RESERVED_PARAMS: Tuple[ReservedParam, ...] = (
    ReservedParam(
        logical="model",
        options_key="model",
        spec_field="model",
        request_field="model",
    ),
    ReservedParam(
        logical="temperature",
        options_key="temperature",
        spec_field="temperature",
        request_field=None,  # no batch-level direct temperature field
    ),
    ReservedParam(
        logical="max_tokens",
        options_key="max_tokens",
        spec_field=None,  # no per-spec direct max_tokens on LLMCallSpec
        request_field="max_tokens",
        aliases=frozenset({"max_output_tokens"}),  # Gemini provider alias
    ),
)

# All keys that are "owned" by the reserved-param system (canonical + aliases).
# Used to filter pass-through keys — aliases must NOT slip through as pass-through.
_RESERVED_OPTIONS_KEYS: FrozenSet[str] = frozenset(
    key for p in RESERVED_PARAMS for key in ({p.options_key} | p.aliases)
)

# Map alias → canonical options_key, for use in _collect_surfaces and error messages.
_ALIAS_TO_CANONICAL: Dict[str, str] = {
    alias: p.options_key for p in RESERVED_PARAMS for alias in p.aliases
}

# Surface labels used in error messages
_SURFACE_LABELS = {
    "S1": "spec direct field",
    "S2": "spec.request_options",
    "S3": "request direct field",
    "S4": "request.request_options",
}

# Params that are incompatible with batch submission.
_BATCH_INCOMPATIBLE_PARAMS = frozenset({"stream"})


def _collect_surfaces(
    param: ReservedParam,
    spec: LLMCallSpec,
    request: LLMBatchSubmitRequest,
) -> List[Tuple[str, Any]]:
    """
    Return a list of ``(surface_label, value)`` for every surface that is set
    for this ``param`` on this ``(spec, request)`` pair.

    A value is "set" when:
    - The direct field is not ``None``, or
    - The ``options_key`` is present in the request_options dict.

    S1 = spec direct field; S2 = spec.request_options; S3 = request direct
    field; S4 = request.request_options.
    """
    surfaces: List[Tuple[str, Any]] = []

    # S1 — per-spec direct field
    if param.spec_field is not None:
        val = getattr(spec, param.spec_field, None)
        if val is not None:
            surfaces.append(("S1", val))

    # S2 — per-spec request_options (canonical key or any alias)
    if spec.request_options:
        _keys_to_check = [param.options_key] + sorted(param.aliases)
        for _k in _keys_to_check:
            if _k in spec.request_options:
                surfaces.append(("S2", spec.request_options[_k]))
                break  # only one entry per surface, first key wins

    # S3 — batch-level direct field
    if param.request_field is not None:
        val = getattr(request, param.request_field, None)
        if val is not None:
            surfaces.append(("S3", val))

    # S4 — batch-level request_options (canonical key or any alias)
    if request.request_options:
        _keys_to_check = [param.options_key] + sorted(param.aliases)
        for _k in _keys_to_check:
            if _k in request.request_options:
                surfaces.append(("S4", request.request_options[_k]))
                break  # only one entry per surface, first key wins

    return surfaces


def resolve_spec_params(
    spec: LLMCallSpec,
    request: LLMBatchSubmitRequest,
) -> Dict[str, Any]:
    """
    Resolve all reserved and pass-through params for one spec into a single,
    conflict-free dict keyed by ``options_key``.

    Resolution rule (per ``ReservedParam`` and per pass-through key):
    - Zero surfaces set → param absent; not included in result dict.
    - One or more surfaces set, all equal → allow; emit the single value.
    - Two or more surfaces set with ≥2 distinct values → raise
      ``LLMBatchParamConflictError`` naming the spec_id, logical param, and
      each conflicting surface with its value.

    Pass-through keys (keys in either ``request_options`` dict that are NOT
    in ``RESERVED_PARAMS``) are merged with the same conflict rule applied to
    any key that appears in both dicts.

    Batch-incompatible params (``stream``) and ``max_tokens == 0`` are also
    rejected here — centralizing all validation in one chokepoint.

    Args:
        spec: One ``LLMCallSpec`` from the batch request.
        request: The enclosing ``LLMBatchSubmitRequest``.

    Returns:
        Conflict-free ``Dict[str, Any]`` of resolved param values.  ``model``
        and ``max_tokens`` are always present (they have well-defined defaults
        from the request envelope).

    Raises:
        LLMBatchParamConflictError: if any logical parameter is set on two
            surfaces with different values.
        LLMServiceError: for batch-incompatible params (stream) or
            max_tokens == 0 on any surface.
    """
    from agentmap.exceptions.service_exceptions import LLMServiceError

    resolved: Dict[str, Any] = {}

    # --- Reserved parameters ---
    for param in RESERVED_PARAMS:
        surfaces = _collect_surfaces(param, spec, request)

        if not surfaces:
            continue

        # CR5-3: unhashable values (e.g. dict/list option values) must not raise
        # a raw TypeError from set() — use list-equality instead and re-raise typed.
        try:
            distinct_values = list({v for _, v in surfaces})
        except TypeError:
            # At least two values; check equality sequentially to find conflicts.
            first = surfaces[0][1]
            if any(v != first for _, v in surfaces[1:]):
                surface_detail = ", ".join(
                    f"{_SURFACE_LABELS.get(s, s)}={v!r}" for s, v in surfaces
                )
                raise LLMBatchParamConflictError(
                    f"spec_id={spec.spec_id!r}: conflicting values for "
                    f"parameter {param.logical!r} — {surface_detail}. "
                    "Set this parameter on exactly one surface."
                ) from None
            distinct_values = [first]
        if len(distinct_values) > 1:
            surface_detail = ", ".join(
                f"{_SURFACE_LABELS.get(s, s)}={v!r}" for s, v in surfaces
            )
            raise LLMBatchParamConflictError(
                f"spec_id={spec.spec_id!r}: conflicting values for "
                f"parameter {param.logical!r} — {surface_detail}. "
                "Set this parameter on exactly one surface."
            )

        resolved[param.options_key] = distinct_values[0]

    # Ensure model and max_tokens always have a resolved value (they have
    # envelope-level defaults that are the fallback).
    if "model" not in resolved and request.model is not None:
        resolved["model"] = request.model
    if "max_tokens" not in resolved and request.max_tokens is not None:
        resolved["max_tokens"] = request.max_tokens

    # --- Batch-incompatible param check (centralized) ---
    for bad_key in _BATCH_INCOMPATIBLE_PARAMS:
        if (
            bad_key in resolved
            or (spec.request_options and bad_key in spec.request_options)
            or (request.request_options and bad_key in request.request_options)
        ):
            raise LLMServiceError(
                f"spec_id={spec.spec_id!r}: request_options contains "
                f"batch-incompatible parameter {bad_key!r}. "
                "Batch submissions do not support streaming."
            )

    # --- max_tokens == 0 check (centralized) ---
    if resolved.get("max_tokens") == 0:
        raise LLMServiceError(
            f"spec_id={spec.spec_id!r}: max_tokens=0 is not supported in batch "
            "submissions. Cache pre-warm is incompatible with batch mode."
        )

    # --- Pass-through (non-reserved) keys ---
    # Collect pass-through keys from both option dicts, apply same conflict rule.
    passthrough_keys: set = set()
    if spec.request_options:
        passthrough_keys.update(
            k for k in spec.request_options if k not in _RESERVED_OPTIONS_KEYS
        )
    if request.request_options:
        passthrough_keys.update(
            k for k in request.request_options if k not in _RESERVED_OPTIONS_KEYS
        )

    for key in sorted(passthrough_keys):  # sorted for deterministic error messages
        spec_val = (
            spec.request_options.get(key)
            if spec.request_options and key in spec.request_options
            else _MISSING
        )
        req_val = (
            request.request_options.get(key)
            if request.request_options and key in request.request_options
            else _MISSING
        )

        if spec_val is _MISSING and req_val is _MISSING:
            continue  # should not happen given the key collection above
        elif spec_val is _MISSING:
            resolved[key] = req_val
        elif req_val is _MISSING:
            resolved[key] = spec_val
        elif spec_val == req_val:
            resolved[key] = spec_val
        else:
            raise LLMBatchParamConflictError(
                f"spec_id={spec.spec_id!r}: conflicting values for "
                f"pass-through parameter {key!r} — "
                f"spec.request_options={spec_val!r} vs "
                f"request.request_options={req_val!r}. "
                "Set this parameter on exactly one surface."
            )

    return resolved


# Sentinel — never equal to any real value
class _MissingSentinel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "<MISSING>"


_MISSING = _MissingSentinel()


def build_resolved_params_list(
    request: LLMBatchSubmitRequest,
) -> List[Dict[str, Any]]:
    """
    Build the full list of resolved param dicts, one per spec.

    Raises ``LLMBatchParamConflictError`` on the first conflicting spec.
    The returned list is index-aligned with ``request.call_specs``.
    """
    return [resolve_spec_params(spec, request) for spec in request.call_specs]


# ---------------------------------------------------------------------------
# Surface-pair enumeration (used by conflict-matrix tests — N5.1)
# ---------------------------------------------------------------------------


def applicable_surfaces(param: ReservedParam) -> List[str]:
    """Return the surface labels applicable for ``param`` (in S1→S4 order)."""
    surfaces = []
    if param.spec_field is not None:
        surfaces.append("S1")
    surfaces.append("S2")  # options_key always applies via request_options
    if param.request_field is not None:
        surfaces.append("S3")
    surfaces.append("S4")  # options_key always applies via request.request_options
    return surfaces


def surface_pairs(param: ReservedParam) -> List[Tuple[str, str]]:
    """Return all unordered surface pairs for ``param``."""
    return list(itertools.combinations(applicable_surfaces(param), 2))
