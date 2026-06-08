"""
Conflict-matrix parametrized tests for the centralized batch parameter resolver
(D-8, spec.md § Canonical Parameter Resolution, N5.1).

The test matrix is generated from RESERVED_PARAMS × all unordered surface pairs
valid for each param × {same-value, different-value}.  Adding a future reserved
key to RESERVED_PARAMS automatically generates its full row of cells — a future
quality gate cannot find an uncovered pair.

Surface labels:
    S1 = LLMRequest direct field
    S2 = LLMRequest.request_options[options_key]
    S3 = LLMBatchSubmitRequest direct field
    S4 = LLMBatchSubmitRequest.request_options[options_key]
"""

from typing import Any, Dict, List, Tuple

import pytest

from agentmap.models.llm_execution import (
    DEFAULT_TOKEN_LIMIT,
    LLMBatchSubmitRequest,
    LLMRequest,
)
from agentmap.services.llm._param_resolution import (
    RESERVED_PARAMS,
    ReservedParam,
    applicable_surfaces,
    resolve_request_params,
    surface_pairs,
)
from agentmap.services.llm_batch_errors import LLMBatchParamConflictError

# ---------------------------------------------------------------------------
# Helpers to build spec / request with a given surface set
# ---------------------------------------------------------------------------


def _base_request(provider="anthropic", model="claude-3-5-haiku", max_tokens=1024):
    return LLMBatchSubmitRequest(
        provider=provider,
        model=model,
        max_tokens=max_tokens,
        requests=[],
    )


def _base_spec(request_id="s1"):
    return LLMRequest(
        request_id=request_id,
        messages=[{"role": "user", "content": "hi"}],
    )


def _apply_surface(
    param: ReservedParam,
    surface: str,
    value: Any,
    spec: LLMRequest,
    request: LLMBatchSubmitRequest,
) -> Tuple[LLMRequest, LLMBatchSubmitRequest]:
    """Return (spec, request) with ``value`` applied on ``surface`` for ``param``."""
    # We return new objects to avoid shared-state bugs between test cells.
    spec_kwargs: Dict[str, Any] = {
        "request_id": spec.request_id,
        "messages": spec.messages,
    }
    req_kwargs: Dict[str, Any] = {
        "provider": request.provider,
        "model": request.model,
        "max_tokens": request.max_tokens,
        "requests": request.requests,
    }

    # Carry over existing options
    spec_req_opts = dict(spec.request_options) if spec.request_options else {}
    req_req_opts = dict(request.request_options) if request.request_options else {}

    # Carry over existing direct fields
    if spec.model is not None:
        spec_kwargs["model"] = spec.model
    if spec.temperature is not None:
        spec_kwargs["temperature"] = spec.temperature

    if surface == "S1":
        assert param.spec_field is not None, f"{param.logical} has no S1 (spec_field)"
        spec_kwargs[param.spec_field] = value
    elif surface == "S2":
        spec_req_opts[param.options_key] = value
    elif surface == "S3":
        assert (
            param.request_field is not None
        ), f"{param.logical} has no S3 (request_field)"
        req_kwargs[param.request_field] = value
    elif surface == "S4":
        req_req_opts[param.options_key] = value
    else:
        raise ValueError(f"Unknown surface {surface!r}")

    if spec_req_opts:
        spec_kwargs["request_options"] = spec_req_opts
    if req_req_opts:
        req_kwargs["request_options"] = req_req_opts

    return LLMRequest(**spec_kwargs), LLMBatchSubmitRequest(**req_kwargs)


def _build_cell(
    param: ReservedParam,
    surfaces: List[str],
    values: List[Any],
) -> Tuple[LLMRequest, LLMBatchSubmitRequest]:
    """
    Build a (spec, request) pair with each surface[i] set to values[i].

    Surfaces NOT being tested are set to a fixed neutral value matching
    values[0] so they do not introduce spurious conflicts.  For ``model``
    this is necessary because ``request.model`` is always required and
    always constitutes an active S3 surface.
    """
    # Determine the "neutral" fill value (same as values[0] so it doesn't conflict).
    fill = values[0]
    # Apply neutral values to all applicable surfaces first.
    spec = _base_spec()
    # For params with mandatory request-envelope fields, we must set those to
    # the fill value so they don't introduce spurious conflicts.
    req_model = fill if param.logical == "model" else "claude-3-5-haiku"
    req_max_tokens = fill if param.logical == "max_tokens" else 1024
    request = _base_request(model=req_model, max_tokens=req_max_tokens)
    for surface, value in zip(surfaces, values):
        spec, request = _apply_surface(param, surface, value, spec, request)
    return spec, request


# ---------------------------------------------------------------------------
# Same-value matrix (N5.1: all pairs, same value → no error)
# ---------------------------------------------------------------------------


def _same_value_for_param(param: ReservedParam) -> Any:
    """A canonical same-value to use for a given param."""
    if param.logical == "model":
        return "my-model-v1"
    if param.logical == "temperature":
        return 0.7
    if param.logical == "max_tokens":
        return 512
    return "test-value"


def _different_values_for_param(param: ReservedParam) -> Tuple[Any, Any]:
    """Two distinct values for a given param."""
    if param.logical == "model":
        return "model-a", "model-b"
    if param.logical == "temperature":
        return 0.2, 0.9
    if param.logical == "max_tokens":
        return 256, 1024
    return "val-a", "val-b"


# Generate parametrize IDs and args for the same-value matrix
def _same_value_cases():
    cases = []
    for param in RESERVED_PARAMS:
        pairs = surface_pairs(param)
        v = _same_value_for_param(param)
        for s1, s2 in pairs:
            case_id = f"{param.logical}_{s1}_vs_{s2}_same"
            cases.append(pytest.param(param, [s1, s2], [v, v], id=case_id))
    return cases


# Generate parametrize IDs and args for the different-value matrix
def _different_value_cases():
    cases = []
    for param in RESERVED_PARAMS:
        pairs = surface_pairs(param)
        va, vb = _different_values_for_param(param)
        for s1, s2 in pairs:
            case_id = f"{param.logical}_{s1}_vs_{s2}_different"
            cases.append(pytest.param(param, [s1, s2], [va, vb], id=case_id))
    return cases


# ---------------------------------------------------------------------------
# Test: same value on two surfaces → allowed, value in resolved dict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("param,surfaces,values", _same_value_cases())
def test_same_value_on_two_surfaces_is_allowed(param, surfaces, values):
    """N5.1: same-value cell — resolve_request_params must NOT raise."""
    spec, request = _build_cell(param, surfaces, values)
    # Must not raise
    resolved = resolve_request_params(spec, request)
    # The resolved dict must carry the single value under options_key
    assert param.options_key in resolved, (
        f"Param {param.logical!r} should be in resolved dict "
        f"when set on surfaces {surfaces}"
    )
    assert (
        resolved[param.options_key] == values[0]
    ), f"Expected {values[0]!r} for {param.logical!r}, got {resolved[param.options_key]!r}"


# ---------------------------------------------------------------------------
# Test: different values on two surfaces → LLMBatchParamConflictError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("param,surfaces,values", _different_value_cases())
def test_different_values_on_two_surfaces_raises_conflict_error(
    param, surfaces, values
):
    """N5.1: different-value cell — resolve_request_params must raise LLMBatchParamConflictError."""
    spec, request = _build_cell(param, surfaces, values)
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    msg = str(exc_info.value)
    # Error must name the param
    assert param.logical in msg, (
        f"Error message for {param.logical!r} conflict must name the parameter. "
        f"Got: {msg!r}"
    )
    # Error must name the request_id
    assert "s1" in msg, f"Error must name request_id. Got: {msg!r}"


# ---------------------------------------------------------------------------
# Test: single surface → value applied, no error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "param", RESERVED_PARAMS, ids=[p.logical for p in RESERVED_PARAMS]
)
@pytest.mark.parametrize("surface", ["S1", "S2", "S3", "S4"])
def test_single_surface_value_is_applied(param, surface):
    """N5.1: one surface set → value in resolved dict, no error."""
    if surface not in applicable_surfaces(param):
        pytest.skip(f"{param.logical} has no {surface}")

    v = _same_value_for_param(param)
    spec, request = _build_cell(param, [surface], [v])
    resolved = resolve_request_params(spec, request)
    assert param.options_key in resolved
    assert resolved[param.options_key] == v


# ---------------------------------------------------------------------------
# Test: zero surfaces set for a non-mandatory param → param absent
# ---------------------------------------------------------------------------


def test_temperature_absent_when_no_surface_set():
    """N5.1: zero-surface cell for temperature → not in resolved dict."""
    spec = _base_spec()
    request = _base_request()
    resolved = resolve_request_params(spec, request)
    assert (
        "temperature" not in resolved
    ), "temperature should be absent from resolved dict when no surface sets it"


def test_model_always_resolved_from_request_envelope():
    """model is always resolved from request.model when no per-spec override."""
    spec = _base_spec()
    request = _base_request(model="base-model")
    resolved = resolve_request_params(spec, request)
    assert resolved["model"] == "base-model"


def test_max_tokens_always_resolved_from_request_envelope():
    """max_tokens is always resolved from request.max_tokens when no per-spec override."""
    spec = _base_spec()
    request = _base_request(max_tokens=2048)
    resolved = resolve_request_params(spec, request)
    assert resolved["max_tokens"] == 2048


def test_spec_level_max_tokens_override_does_not_conflict_when_batch_default_unset():
    """Per-spec max_tokens should resolve cleanly when request.max_tokens is None."""
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        request_options={"max_tokens": 256},
    )
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="claude-3-5-haiku",
        max_tokens=None,
        requests=[],
    )

    resolved = resolve_request_params(spec, request)

    assert resolved["max_tokens"] == 256


def test_max_tokens_falls_back_to_default_token_limit_when_unset_everywhere():
    """Anthropic-compatible fallback must inject DEFAULT_TOKEN_LIMIT when unresolved."""
    spec = _base_spec()
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="claude-3-5-haiku",
        max_tokens=None,
        requests=[],
    )

    resolved = resolve_request_params(spec, request)

    assert resolved["max_tokens"] == DEFAULT_TOKEN_LIMIT


# ---------------------------------------------------------------------------
# Test: pass-through (non-reserved) key conflict detection
# ---------------------------------------------------------------------------


def test_passthrough_same_value_on_both_dicts_is_allowed():
    """Non-reserved key with same value in both option dicts → allowed."""
    spec = _base_spec()
    spec = LLMRequest(
        request_id="s1", messages=spec.messages, request_options={"top_p": 0.9}
    )
    request = _base_request()
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="m",
        max_tokens=100,
        requests=[],
        request_options={"top_p": 0.9},
    )
    resolved = resolve_request_params(spec, request)
    assert resolved["top_p"] == 0.9


def test_passthrough_different_values_raises_conflict_error():
    """Non-reserved key with different values in both option dicts → conflict error."""
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        request_options={"top_p": 0.5},
    )
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="m",
        max_tokens=100,
        requests=[],
        request_options={"top_p": 0.9},
    )
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    assert "top_p" in str(exc_info.value)


def test_passthrough_key_only_in_spec_request_options():
    """Non-reserved key only in spec.request_options → applied."""
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        request_options={"seed": 42},
    )
    request = _base_request()
    resolved = resolve_request_params(spec, request)
    assert resolved["seed"] == 42


def test_passthrough_key_only_in_batch_request_options():
    """Non-reserved key only in request.request_options → applied."""
    spec = _base_spec()
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="m",
        max_tokens=100,
        requests=[],
        request_options={"seed": 99},
    )
    resolved = resolve_request_params(spec, request)
    assert resolved["seed"] == 99


# ---------------------------------------------------------------------------
# Test: batch-incompatible params rejected
# ---------------------------------------------------------------------------


def test_stream_in_spec_request_options_raises():
    """stream param in spec.request_options raises LLMServiceError."""
    from agentmap.exceptions.service_exceptions import LLMServiceError

    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        request_options={"stream": True},
    )
    request = _base_request()
    with pytest.raises(LLMServiceError):
        resolve_request_params(spec, request)


# ---------------------------------------------------------------------------
# Test: max_tokens == 0 rejected
# ---------------------------------------------------------------------------


def test_max_tokens_zero_raises():
    """max_tokens == 0 in request.max_tokens raises LLMServiceError."""
    from agentmap.exceptions.service_exceptions import LLMServiceError

    spec = _base_spec()
    request = _base_request(max_tokens=0)
    with pytest.raises(LLMServiceError):
        resolve_request_params(spec, request)


# ---------------------------------------------------------------------------
# Test: RESERVED_PARAMS registry covers all expected keys
# ---------------------------------------------------------------------------


def test_reserved_params_contains_expected_keys():
    """RESERVED_PARAMS must contain model, temperature, max_tokens."""
    logical_names = {p.logical for p in RESERVED_PARAMS}
    assert "model" in logical_names
    assert "temperature" in logical_names
    assert "max_tokens" in logical_names


def test_surface_pairs_completeness():
    """Every applicable surface pair is tested — verify applicable_surfaces is non-empty."""
    for param in RESERVED_PARAMS:
        surfaces = applicable_surfaces(param)
        assert len(surfaces) >= 2, (
            f"Param {param.logical!r} has fewer than 2 surfaces — "
            "conflict detection would be impossible"
        )
        pairs = surface_pairs(param)
        assert len(pairs) > 0, f"No pairs for {param.logical!r}"


# ---------------------------------------------------------------------------
# N4: Intra-surface (same-dict) canonical+alias conflict detection (AC-8)
# ---------------------------------------------------------------------------


def test_intra_surface_S2_canonical_and_alias_different_values_raises():
    """N4: spec.request_options with canonical + alias at different values → LLMBatchParamConflictError.

    Uses max_tokens=None at the request level to isolate the intra-surface conflict:
    with the old break-on-first-match code, the alias value (200) is silently
    discarded and only max_tokens=100 is seen on S2 — no conflict raised.
    """
    # max_tokens (canonical) and max_output_tokens (Gemini alias) in the SAME dict
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        request_options={"max_tokens": 100, "max_output_tokens": 200},
    )
    # max_tokens=None so request envelope does NOT introduce a second surface;
    # the only surface is S2, which contains the intra-dict conflict.
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="claude-3-5-haiku",
        max_tokens=None,
        requests=[],
    )
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    msg = str(exc_info.value)
    assert "max_tokens" in msg, f"Error must name the param. Got: {msg!r}"
    assert "s1" in msg, f"Error must name request_id. Got: {msg!r}"


def test_intra_surface_S4_canonical_and_alias_different_values_raises():
    """N4: request.request_options with canonical + alias at different values → LLMBatchParamConflictError.

    Uses max_tokens=None at the request direct-field level to isolate the intra-surface
    conflict within request.request_options (S4 alone).
    """
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="claude-3-5-haiku",
        max_tokens=None,
        requests=[],
        request_options={"max_tokens": 100, "max_output_tokens": 200},
    )
    spec = _base_spec()
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    msg = str(exc_info.value)
    assert "max_tokens" in msg, f"Error must name the param. Got: {msg!r}"
    assert "s1" in msg, f"Error must name request_id. Got: {msg!r}"


def test_intra_surface_S2_canonical_and_alias_same_values_allowed():
    """N4: spec.request_options with canonical + alias at SAME value → allowed, single value resolved."""
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        request_options={"max_tokens": 512, "max_output_tokens": 512},
    )
    # max_tokens=None so the only surface is S2 (the intra-dict same-value case).
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="claude-3-5-haiku",
        max_tokens=None,
        requests=[],
    )
    resolved = resolve_request_params(spec, request)
    assert resolved["max_tokens"] == 512


def test_intra_surface_S4_canonical_and_alias_same_values_allowed():
    """N4: request.request_options with canonical + alias at SAME value → allowed."""
    request = LLMBatchSubmitRequest(
        provider="anthropic",
        model="claude-3-5-haiku",
        max_tokens=None,
        requests=[],
        request_options={"max_tokens": 512, "max_output_tokens": 512},
    )
    spec = _base_spec()
    resolved = resolve_request_params(spec, request)
    assert resolved["max_tokens"] == 512


def _intra_surface_alias_cases():
    """
    Registry-driven intra-surface alias conflict cases.

    For every param that HAS aliases, generate a test case where BOTH the
    canonical key and an alias appear in the same options dict with different
    values (S2 = spec.request_options, S4 = request.request_options).
    """
    cases = []
    for param in RESERVED_PARAMS:
        if not param.aliases:
            continue
        va, vb = _different_values_for_param(param)
        for alias in sorted(param.aliases):
            for surface_label in ("S2", "S4"):
                cases.append(
                    pytest.param(
                        param,
                        alias,
                        surface_label,
                        va,
                        vb,
                        id=f"{param.logical}_{alias}_{surface_label}_intra_conflict",
                    )
                )
    return cases


@pytest.mark.parametrize(
    "param,alias,surface_label,canonical_val,alias_val", _intra_surface_alias_cases()
)
def test_intra_surface_alias_conflict_raises(
    param, alias, surface_label, canonical_val, alias_val
):
    """N4 registry-driven: intra-surface canonical+alias with different values → raises."""
    opts = {param.options_key: canonical_val, alias: alias_val}
    if surface_label == "S2":
        spec = LLMRequest(
            request_id="s1",
            messages=[{"role": "user", "content": "hi"}],
            request_options=opts,
        )
        # max_tokens=None isolates the S2 intra-surface conflict; no S3 pollution.
        request = LLMBatchSubmitRequest(
            provider="anthropic",
            model="claude-3-5-haiku",
            max_tokens=None,
            requests=[],
        )
    else:  # S4
        spec = _base_spec()
        # max_tokens=None isolates the S4 intra-surface conflict; no S3 pollution.
        request = LLMBatchSubmitRequest(
            provider="anthropic",
            model="claude-3-5-haiku",
            max_tokens=None,
            requests=[],
            request_options=opts,
        )
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    msg = str(exc_info.value)
    assert (
        param.logical in msg or param.options_key in msg
    ), f"Error must name the param. Got: {msg!r}"


# ---------------------------------------------------------------------------
# Test: same-spec conflict (S1 vs S2 for temperature — the N1 missing cell)
# ---------------------------------------------------------------------------


def test_same_spec_s1_vs_s2_temperature_conflict_raises():
    """
    N1 regression: spec.temperature (S1) vs spec.request_options["temperature"] (S2)
    with different values must raise LLMBatchParamConflictError.

    This is the exact cell that was uncovered by the pair-by-pair implementation
    and that triggered the N1 UAT finding.
    """
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2,
        request_options={"temperature": 0.9},
    )
    request = _base_request()
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    msg = str(exc_info.value)
    assert "temperature" in msg
    assert "s1" in msg


def test_same_spec_s1_vs_s2_temperature_same_value_allowed():
    """Same value on S1 and S2 for temperature → allowed (same-value rule)."""
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7,
        request_options={"temperature": 0.7},
    )
    request = _base_request()
    resolved = resolve_request_params(spec, request)
    assert resolved["temperature"] == 0.7


# ---------------------------------------------------------------------------
# Test: model conflict S1 vs S3 (spec.model vs request.model)
# ---------------------------------------------------------------------------


def test_model_s1_vs_s3_conflict_raises():
    """spec.model (S1) vs request.model (S3) with different values → conflict."""
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        model="model-a",
    )
    request = _base_request(model="model-b")
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    assert "model" in str(exc_info.value)


def test_model_s1_vs_s3_same_value_allowed():
    """spec.model (S1) == request.model (S3) → allowed."""
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        model="shared-model",
    )
    request = _base_request(model="shared-model")
    resolved = resolve_request_params(spec, request)
    assert resolved["model"] == "shared-model"


# ---------------------------------------------------------------------------
# Alias-awareness tests (CR5-1 regression, AC-8 / N1 via Gemini alias)
# ---------------------------------------------------------------------------


def test_alias_different_value_raises_conflict_error():
    """
    CR5-1 regression: max_tokens=1024 (canonical, S3) + request_options
    max_output_tokens=2048 (Gemini alias, S4) → LLMBatchParamConflictError.

    Previously the alias bypassed the resolver as a 'pass-through' key and
    silently overrode the canonical value inside the Gemini adapter.
    """
    spec = _base_spec()
    request = LLMBatchSubmitRequest(
        provider="gemini",
        model="gemini-1.5-flash",
        max_tokens=1024,
        requests=[],
        request_options={"max_output_tokens": 2048},
    )
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    msg = str(exc_info.value)
    assert "max_tokens" in msg
    assert "s1" in msg


def test_alias_same_value_is_allowed():
    """
    max_tokens=512 (S3) + request_options max_output_tokens=512 (S4 alias)
    → allowed; resolved dict carries canonical max_tokens=512.
    """
    spec = _base_spec()
    request = LLMBatchSubmitRequest(
        provider="gemini",
        model="gemini-1.5-flash",
        max_tokens=512,
        requests=[],
        request_options={"max_output_tokens": 512},
    )
    resolved = resolve_request_params(spec, request)
    assert resolved["max_tokens"] == 512
    # The alias must NOT appear in the resolved dict (canonical only)
    assert "max_output_tokens" not in resolved


def test_alias_only_in_spec_request_options():
    """
    max_output_tokens=768 in spec.request_options (S2) with no canonical
    max_tokens set elsewhere → resolves to max_tokens=768.
    """
    spec = LLMRequest(
        request_id="s1",
        messages=[{"role": "user", "content": "hi"}],
        request_options={"max_output_tokens": 768},
    )
    request = LLMBatchSubmitRequest(
        provider="gemini",
        model="gemini-1.5-flash",
        max_tokens=None,
        requests=[],
    )
    resolved = resolve_request_params(spec, request)
    assert resolved["max_tokens"] == 768
    assert "max_output_tokens" not in resolved


def test_alias_not_treated_as_passthrough():
    """
    max_output_tokens must NOT appear as a pass-through key in the resolved
    dict even when only set in one options surface.  It must be collapsed to
    canonical max_tokens.
    """
    spec = _base_spec()
    request = LLMBatchSubmitRequest(
        provider="gemini",
        model="gemini-1.5-flash",
        max_tokens=None,
        requests=[],
        request_options={"max_output_tokens": 300},
    )
    resolved = resolve_request_params(spec, request)
    assert "max_output_tokens" not in resolved
    assert resolved.get("max_tokens") == 300


# Generate alias-vs-canonical conflict-matrix cases:
# For each reserved param that has aliases, generate same/different-value cells
# where one surface uses the canonical key and another uses the alias.
def _alias_same_value_cases():
    cases = []
    for param in RESERVED_PARAMS:
        if not param.aliases:
            continue
        v = _same_value_for_param(param)
        for alias in sorted(param.aliases):
            # S3 (canonical request_field) vs S4 (alias in request.request_options)
            case_id = f"{param.logical}_S3_canonical_vs_S4_alias_{alias}_same"
            cases.append(pytest.param(param, alias, v, v, id=case_id))
    return cases


def _alias_different_value_cases():
    cases = []
    for param in RESERVED_PARAMS:
        if not param.aliases:
            continue
        va, vb = _different_values_for_param(param)
        for alias in sorted(param.aliases):
            case_id = f"{param.logical}_S3_canonical_vs_S4_alias_{alias}_different"
            cases.append(pytest.param(param, alias, va, vb, id=case_id))
    return cases


@pytest.mark.parametrize("param,alias,v_canonical,v_alias", _alias_same_value_cases())
def test_alias_same_value_matrix_allowed(param, alias, v_canonical, v_alias):
    """Matrix: canonical (S3) + alias (S4) with same value → allowed."""
    # Only run for params with a request_field (S3 available)
    if param.request_field is None:
        pytest.skip(f"{param.logical} has no S3")
    req_kwargs = {
        "provider": "gemini",
        "model": "gemini-1.5-flash" if param.logical != "model" else v_canonical,
        "max_tokens": v_canonical if param.logical == "max_tokens" else 1024,
        "requests": [],
        "request_options": {alias: v_alias},
    }
    request = LLMBatchSubmitRequest(**req_kwargs)
    spec = _base_spec()
    resolved = resolve_request_params(spec, request)
    assert resolved[param.options_key] == v_canonical
    assert alias not in resolved


@pytest.mark.parametrize(
    "param,alias,v_canonical,v_alias", _alias_different_value_cases()
)
def test_alias_different_value_matrix_raises(param, alias, v_canonical, v_alias):
    """Matrix: canonical (S3) + alias (S4) with different values → conflict error."""
    if param.request_field is None:
        pytest.skip(f"{param.logical} has no S3")
    req_kwargs = {
        "provider": "gemini",
        "model": "gemini-1.5-flash" if param.logical != "model" else v_canonical,
        "max_tokens": v_canonical if param.logical == "max_tokens" else 1024,
        "requests": [],
        "request_options": {alias: v_alias},
    }
    request = LLMBatchSubmitRequest(**req_kwargs)
    spec = _base_spec()
    with pytest.raises(LLMBatchParamConflictError) as exc_info:
        resolve_request_params(spec, request)
    assert param.logical in str(exc_info.value)
