# ADR-001: Add openai and google-genai as import-gated optional extras

**Date:** 2026-06-07
**Status:** Accepted

## Context

F03 (provider-native batch contract, Anthropic implementation) established
REQ-NF-003: "no new third-party dependencies added at the core level."
The `anthropic` SDK was already a transitive dependency via `langchain-anthropic`
and was therefore not counted.

F04 extends the batch interface to OpenAI Batch API and Gemini Developer API.
There is no library that unifies native batch execution across these three
providers (confirmed via buy-vs-build spike in feature.md).  Each provider
requires its own SDK:

- OpenAI Batch API → `openai` Python SDK
- Gemini Developer API → `google-genai` SDK (the `google-generativeai` package
  was deprecated by Google in November 2025 and must not be used)

Neither `openai` nor `google-genai` is currently a transitive dependency of the
core `agentmap` install.  Adding them to `[project.dependencies]` (core) would
force every `agentmap` user to install two large SDKs regardless of whether they
use multi-provider batch execution.

## Decision

Reverse F03 REQ-NF-003 for the `openai` and `google-genai` packages:

1. Add a new optional-extras group `batch` in `pyproject.toml`:
   ```
   [project.optional-dependencies]
   batch = [
       "anthropic>=0.40.0",
       "openai>=1.0.0",
       "google-genai>=1.0.0",
   ]
   ```
2. Fold `openai` and `google-genai` into the existing `all` extras group so
   `pip install agentmap[all]` installs them automatically.
3. Gate each adapter's SDK import inside `__init__` with
   `try/except ImportError → raise LLMDependencyError(...)`, mirroring the
   existing pattern in `anthropic_batch_adapter.py`.
4. The DI container wraps each adapter factory in `try/except LLMDependencyError`
   and returns `None` (log + skip) when the SDK is absent, so the container
   builds successfully even without the optional SDKs installed.
5. `google-generativeai` is explicitly excluded from all dependency tables
   (deprecated November 2025).

## Rationale

**Why optional extras, not core?**
Core dependencies are installed by every `agentmap` user.  `openai` (~10 MB) and
`google-genai` (~5 MB) add non-trivial install weight and introduce transitive
conflicts unrelated to the realtime LLM path, which already uses the
`langchain-*` wrappers.  Optional extras follow the established pattern for
`storage`, `telemetry`, and `llm` in `pyproject.toml`.

**Why import-gating at adapter `__init__` rather than module level?**
Module-level imports would cause `ImportError` at container-build time, breaking
the entire `agentmap` DI graph for users who have not installed the batch extras.
Deferring to `__init__` and converting to `LLMDependencyError` (a subclass of
`LLMServiceError`) gives callers a typed, catchable exception at the point of
actual use.

**Why not a buy-side solution (unified batch library)?**
No library abstracts Anthropic Message Batches, OpenAI Batch API, and Gemini
batch submission behind a single interface.  Thin per-provider adapter classes
totaling ~300 LOC each are cheaper than a hypothetical wrapper library with its
own versioning and maintenance risk.

**Alternatives considered:**

| Alternative | Rejected because |
|---|---|
| Add to core deps | Forces all users to install openai + google-genai |
| Plugin architecture (separate packages) | Disproportionate overhead for three known providers |
| Vendor-copy SDK calls (no dep) | Fragile; re-implements provider API client maintenance |

## Consequences

**Positive:**
- Core `pip install agentmap` remains lightweight; no new mandatory dependencies.
- `pip install agentmap[batch]` or `agentmap[all]` installs all three SDKs at once.
- Each adapter's availability is determined at runtime; missing SDK → log warning,
  provider silently absent from registry.  Existing Anthropic batch path is unaffected.
- Typed `LLMDependencyError` at adapter `__init__` gives callers a catchable,
  descriptive error instead of a bare `ImportError`.

**Negative:**
- Users who want OpenAI or Gemini batch execution must install the `[batch]` extra
  explicitly; the error message at runtime (LLMDependencyError) must be clear enough
  to guide them.
- CI must install `[batch]` extras to test all three adapters end-to-end.

## References

- F03 spec REQ-NF-003 (rule being reversed): `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F03-provider-native-batch-llm-contract-and-anthropic-f/spec.md`
- F04 spec REQ-NF-001 (this decision): `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/spec.md §D-2`
- Epic ADR-5 (batch adapter separation), ADR-6 (file-backed persistence), ADR-7 (additive usage)
- Google deprecation notice: `google-generativeai` deprecated November 2025; replacement is `google-genai`
