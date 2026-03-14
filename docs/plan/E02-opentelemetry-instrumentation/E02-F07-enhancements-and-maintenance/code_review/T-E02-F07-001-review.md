# Code Review: T-E02-F07-001 -- TelemetryService Metrics Protocol Extension

**Task**: T-E02-F07-001
**Branch**: `feature/T-E02-F07-001-metrics-protocol-extension`
**Reviewer**: TechLead
**Date**: 2026-03-14
**Verdict**: FAIL -- Changes Required

---

## Summary

The implementation adds the four new protocol methods, NoOp instrument classes with singleton reuse, metric name constants, dimension constants, and re-exports in `__init__.py`. The overall structure is sound and follows established codebase patterns. However, there are two blocking defects and several spec deviations that must be corrected before approval.

---

## Test Results

- **Unit tests**: 67/67 passed (9 new tests added to existing files)
- **Full suite**: 3367 passed, 46 skipped, 0 failures, 0 errors
- **Regressions**: None
- **flake8**: Clean
- **OTEL import isolation**: Confirmed -- `from opentelemetry import metrics` appears only in `otel_telemetry_service.py`

---

## Blocking Issues

### BLOCK-1: OTELTelemetryService does not initialize meter in constructor (AC6 violation)

**File**: `src/agentmap/services/telemetry/otel_telemetry_service.py`

The task spec (AC6) and Architecture Section 5.1 require:

```python
# In __init__()
self._meter = metrics.get_meter("agentmap", version=_agentmap_version)
```

The implementation instead calls `metrics.get_meter("agentmap", version=_agentmap_version)` inside each `create_counter`, `create_histogram`, and `create_up_down_counter` method. This means:

1. A meter object is obtained on every instrument creation call instead of once at init.
2. `get_meter()` returns a fresh meter each call rather than `self._meter`.
3. This deviates from the architectural pattern where the meter parallels the existing tracer init.

**Required fix**: Add `self._meter = metrics.get_meter("agentmap", version=_agentmap_version)` in `__init__()`. Change `create_*` methods to delegate to `self._meter`. Change `get_meter()` to return `self._meter` (ignoring the `name` parameter, as the architecture specifies).

### BLOCK-2: create_* methods return None on failure instead of NoOp instruments (AC3 violation)

**File**: `src/agentmap/services/telemetry/otel_telemetry_service.py`

The task spec (AC3) states: "OTEL service delegates create_* to self._meter; returns NoOp on failure." Architecture Section 5.2 states: "Wraps in try/except, returning a `_NoOpCounter` on failure."

The implementation returns `None` in the except handler:

```python
except Exception as exc:
    logger.warning("Failed to create counter %r: %s", name, exc)
    return None  # BUG: should return _NOOP_COUNTER
```

Returning `None` breaks the duck-typing contract. Downstream code (T-E02-F07-002 in LLMService) will call `.add()` or `.record()` on the result, causing `AttributeError: 'NoneType' object has no attribute 'add'`.

**Required fix**: Import the NoOp singletons from `noop_telemetry_service` and return them as fallbacks:

```python
from agentmap.services.telemetry.noop_telemetry_service import (
    _NOOP_COUNTER, _NOOP_HISTOGRAM, _NOOP_UP_DOWN_COUNTER,
)
```

Then in each except handler, return the corresponding NoOp singleton.

---

## Non-Blocking Issues (Must Fix)

### ISSUE-3: Metric dimension constant names and values deviate from spec

**File**: `src/agentmap/services/telemetry/constants.py`

The task spec (AC7) defines exact constant names and values per Architecture Section 7:

| Spec Constant | Spec Value | Implementation Constant | Implementation Value |
|---|---|---|---|
| `METRIC_DIM_PROVIDER` | `"provider"` | `DIM_PROVIDER` | `"agentmap.llm.provider"` |
| `METRIC_DIM_MODEL` | `"model"` | `DIM_MODEL` | `"agentmap.llm.model"` |
| `METRIC_DIM_ERROR_TYPE` | `"error_type"` | `DIM_ERROR_TYPE` | `"agentmap.llm.error_type"` |
| `METRIC_DIM_TIER` | `"tier"` | `DIM_FALLBACK_REASON` | `"agentmap.llm.fallback_reason"` |

Two problems:
1. **Names**: Constants should use the `METRIC_DIM_` prefix per spec, not `DIM_`.
2. **Values**: Dimension attribute keys should be short strings (`"provider"`, `"model"`, `"error_type"`, `"tier"`), not namespaced strings. OTEL metric dimension keys are conventionally short because they appear in every data point and affect cardinality. The namespaced values add unnecessary verbosity.
3. **METRIC_DIM_TIER vs DIM_FALLBACK_REASON**: The spec calls for `METRIC_DIM_TIER` with value `"tier"`, not `DIM_FALLBACK_REASON` with value `"agentmap.llm.fallback_reason"`.

**Required fix**: Rename constants and correct values to match Architecture Section 7.2 exactly.

### ISSUE-4: METRIC_LLM_DURATION docstring says "milliseconds" but architecture says "seconds"

**File**: `src/agentmap/services/telemetry/constants.py`, line with `METRIC_LLM_DURATION`

The docstring reads:
```python
"""Histogram recording LLM call duration in milliseconds."""
```

Architecture Section 8.1 specifies `unit="s"` and Section 8.3 uses `time.monotonic()` which returns seconds.

**Required fix**: Change docstring to `"""Histogram recording LLM call duration in seconds."""`

### ISSUE-5: get_meter protocol signature deviates from spec

**File**: `src/agentmap/services/telemetry/protocol.py`

The task spec defines: `get_meter(name: str = "agentmap") -> Any`

The implementation defines: `get_meter(name: str, version: Optional[str] = None) -> Any`

Two deviations:
1. `name` parameter has no default value (spec says default `"agentmap"`).
2. Extra `version` parameter not in spec.

The `version` parameter is arguably useful, but adding a parameter not in the spec changes the protocol contract. The missing default on `name` means callers cannot call `get_meter()` without arguments, which the spec allows.

**Required fix**: Add default value `name: str = "agentmap"`. The `version` parameter can stay as an optional addition -- it does not break callers.

---

## Non-Blocking Issues (Should Fix)

### ISSUE-6: Missing test for create_* error fallback to NoOp

Per test plan Section 2.4, there should be tests verifying that `create_counter`, `create_histogram`, and `create_up_down_counter` return usable NoOp instruments when the meter raises an exception. The current test (`test_metrics_methods_handle_errors_gracefully`) only tests `get_meter` error handling.

**Recommended**: Add three tests verifying each create method returns an instrument with a working `.add()` or `.record()` method when the meter raises.

### ISSUE-7: NoOp instrument edge case coverage incomplete

Test plan Section 2.2 specifies testing zero, negative, and float values on NoOp instruments. The current tests cover basic positive integers and positive floats but miss:
- `counter.add(0)` -- zero amount
- `counter.add(-1)` -- negative (OTEL counters reject negatives, but NoOp should accept silently)
- `counter.add(3.14)` -- float amount

**Recommended**: Extend NoOp instrument tests to cover these edge cases.

---

## What Was Done Well

1. **NoOp instrument classes** follow the established `_NoOpSpan` singleton pattern precisely.
2. **Singleton reuse** is correctly implemented with module-level pre-allocated instances and identity-checked in tests.
3. **Zero OTEL imports** in `noop_telemetry_service.py` -- verified by test and source inspection.
4. **Protocol extension** is clean -- all four new methods added with proper docstrings, type hints, and no OTEL imports in the protocol module.
5. **`__init__.py` re-exports** are comprehensive -- all 11 new constants added to both the import block and `__all__`.
6. **Test structure** extends existing test classes cleanly rather than creating parallel test files.
7. **No regressions** -- full test suite passes with 3367 tests.
8. **OTEL import isolation** maintained -- `from opentelemetry import metrics` only in `otel_telemetry_service.py`.

---

## Required Actions Before Approval

1. [BLOCK-1] Initialize `self._meter` in `OTELTelemetryService.__init__()` and delegate create methods to it
2. [BLOCK-2] Return NoOp instrument singletons (not `None`) from create methods on failure
3. [ISSUE-3] Rename dimension constants to `METRIC_DIM_*` prefix and correct values to match Architecture Section 7.2
4. [ISSUE-4] Fix METRIC_LLM_DURATION docstring: "seconds" not "milliseconds"
5. [ISSUE-5] Add default value to `get_meter` name parameter: `name: str = "agentmap"`
6. [ISSUE-6] Add tests for create_* error fallback behavior
7. [ISSUE-7] Add edge case tests for NoOp instruments (zero, negative, float)
8. Update `__init__.py` imports and `__all__` to reflect renamed dimension constants
9. Update test assertions to match corrected constant names and values

---

*Review conducted against task spec T-E02-F07-001.md, Architecture Sections 3-7, and Test Plan Sections 2.1-3.4.*
