---
sidebar_position: 4
title: LLM Batch Adapter Developer Guide
description: Extending AgentMap's provider-agnostic LLM batch interface
keywords: [LLM batch adapters, BatchAdapterProtocol, AgentMap, developer guide]
---

# LLM Batch Adapter Developer Guide

This guide is for developers extending the batch system. The primary audience
is AI agents making code changes inside AgentMap; human maintainers are the
secondary audience.

For the design decisions behind this implementation, see:

- `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/spec.md` § Canonical Parameter Resolution
- `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/spec.md` § Gemini Result Demux Integrity
- `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/adr-001-batch-optional-deps.md`

## Extension points

The batch system is built around three extension seams:

1. `BatchAdapterProtocol`
2. The reserved-parameter registry in `_param_resolution.py`
3. DI registration in `src/agentmap/di/container_parts/llm.py`

If you are adding a provider, keep changes inside those seams first.

## `BatchAdapterProtocol`

Defined in `src/agentmap/services/protocols/service_protocols.py`.

```python
@runtime_checkable
class BatchAdapterProtocol(Protocol):
    provider_name: str
    supports_cancel: bool

    def submit(
        self,
        requests: List[LLMRequest],
        resolved_params: List[Dict[str, Any]],
    ) -> tuple[str, Dict[str, str], Optional[str]]: ...

    def poll(self, provider_batch_id: str) -> BatchPollResult: ...
    def cancel(self, provider_batch_id: str) -> None: ...
    def fetch_results(
        self,
        provider_batch_id: str,
        request_id_map: Dict[str, str],
        result_ref: Optional[str],
    ) -> List[LLMBatchResult]: ...
```

### Contract summary

- `provider_name` must be the canonical registry key
- `supports_cancel` must reflect real provider capability
- `submit()` returns:
  - provider batch id
  - caller `request_id` -> provider request id map, or an ordered positional map for providers like Gemini inline
  - optional expiry timestamp string
- `poll()` must return a normalized `BatchPollResult`
- `cancel()` performs provider I/O only; the service handles post-cancel re-poll
- `fetch_results()` must return `LLMBatchResult` keyed back to caller `request_id`

The service must not need provider-specific branching once the adapter is registered.

## The `resolved_params` contract

This is the most important developer rule.

`resolved_params[i]` is the only parameter source an adapter is allowed to use
for `requests[i]`.

What is already true when `submit()` is called:

- reserved params are conflict-free
- aliases such as `max_output_tokens` have already been collapsed into the canonical logical param
- pass-through options have already been merged or rejected
- batch-incompatible params have already been rejected
- per-request provider settings have already been rejected

What adapters must not do:

- do not merge per-request direct fields, batch-level direct fields, or either `request_options` dict
- do not apply `setdefault()` to recover a second source of truth
- do not silently prefer canonical over alias values
- do not perform conflict resolution

Allowed adapter work:

- provider-specific field renames after resolution
- payload shaping for the provider SDK
- request id sanitization or positional bookkeeping
- provider status mapping
- provider usage normalization

Example: Gemini renames `max_tokens` to `max_output_tokens` after resolution.
That is correct because it is a transport concern, not a conflict-resolution step.

## Adding a new provider adapter

### 1. Implement the adapter

Create `src/agentmap/services/llm/<provider>_batch_adapter.py`.

Checklist:

- import-gate the SDK in `__init__`
- raise `LLMDependencyError` on missing SDK
- set `provider_name`
- set `supports_cancel`
- return `BatchPollResult` from `poll()`
- normalize usage into `LLMUsage`
- return `LLMBatchResult` keyed by caller `request_id`

Skeleton:

```python
from agentmap.exceptions import LLMDependencyError, LLMServiceError
from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchResult,
    LLMBatchStatus,
    LLMExecutionError,
    LLMUsage,
)


class NewProviderBatchAdapter:
    provider_name = "newprovider"
    supports_cancel = True

    _STATUS_MAP = {
        "queued": LLMBatchStatus.IN_PROGRESS,
        "running": LLMBatchStatus.IN_PROGRESS,
        "completed": LLMBatchStatus.ENDED,
        "cancelled": LLMBatchStatus.CANCELED,
        "expired": LLMBatchStatus.EXPIRED,
        "failed": LLMBatchStatus.FAILED,
    }

    def __init__(self, api_key: str, logger) -> None:
        try:
            import newprovider_sdk
        except ImportError:
            raise LLMDependencyError(
                "The 'newprovider-sdk' package is required for batch execution."
            )
        self._client = newprovider_sdk.Client(api_key=api_key)
        self._logger = logger

    def submit(self, requests, resolved_params):
        ...

    def poll(self, provider_batch_id: str) -> BatchPollResult:
        ...

    def cancel(self, provider_batch_id: str) -> None:
        ...

    def fetch_results(self, provider_batch_id, request_id_map, result_ref):
        ...
```

### 2. Register it in DI

Update `src/agentmap/di/container_parts/llm.py`:

- create a factory method
- catch `LLMDependencyError`
- return `None` when the adapter cannot be built
- add the adapter to the `batch_adapters` dict using the canonical key

Pattern to follow:

- `_create_openai_batch_adapter(...)`
- `_create_gemini_batch_adapter(...)`

### 3. Keep the service untouched

If your provider needs changes in `LLMService` beyond registration, that is a
design smell. The service should stay registry-driven.

Acceptable service changes:

- additive capability metadata in `batch_capabilities()`
- additive tests
- new typed errors only if the existing taxonomy cannot express the outcome

## Reserved param registry

Defined in `src/agentmap/services/llm/_param_resolution.py`.

Current reserved params:

- `model`
- `temperature`
- `max_tokens`

Current alias:

- `max_output_tokens` -> `max_tokens`

### How to add a reserved param

Add one `ReservedParam` row:

```python
ReservedParam(
    logical="top_p",
    options_key="top_p",
    spec_field=None,
    request_field=None,
)
```

Questions to answer before adding it:

1. Is this one logical parameter across multiple surfaces?
2. Which direct fields exist on `LLMRequest` or `LLMBatchSubmitRequest`?
3. Which `request_options` key is canonical?
4. Does any provider alias need to collapse into that canonical key?
5. Is the param valid in batch mode at all?

### How to add an alias

Use `aliases=` on the same `ReservedParam`:

```python
ReservedParam(
    logical="max_tokens",
    options_key="max_tokens",
    spec_field=None,
    request_field="max_tokens",
    aliases=frozenset({"max_output_tokens"}),
)
```

Why this matters:

- aliases are included in `_RESERVED_OPTIONS_KEYS`
- aliases participate in same-surface conflict detection
- aliases participate in cross-surface conflict detection
- aliases are excluded from pass-through merging

Do not add provider aliases in adapter code if the alias represents the same
logical caller parameter. Put that knowledge in the registry once.

## Error taxonomy

Defined primarily in `src/agentmap/services/llm_batch_errors.py`.

| Error | Raise it when |
|---|---|
| `LLMBatchUnsupportedProviderError` | No adapter is registered for the normalized provider |
| `LLMBatchCancelNotSupportedError` | Cancel is requested for a terminal handle, or the provider truly does not support cancel |
| `LLMBatchNotReadyError` | Results are requested before `LLMBatchStatus.ENDED` |
| `LLMBatchExpiredError` | An operation targets an already expired batch |
| `LLMBatchParamConflictError` | The same logical parameter is set with conflicting values |
| `LLMBatchResultIntegrityError` | Provider results cannot be safely correlated back to caller `request_id` values |
| `LLMDependencyError` | The provider SDK is missing |
| `LLMServiceError` | Validation or provider-shape problems that do not fit a more specific type |

### Service vs adapter responsibility

Service raises:

- unsupported provider
- param conflicts
- not ready
- expired handle operations
- terminal cancel attempts

Adapter raises:

- dependency errors
- provider payload shape errors
- result integrity failures that are specific to the provider response format
- malformed SDK response errors that the service cannot interpret generically

## Gemini positional demux integrity contract

This is the main provider-specific correctness constraint in F04.

Gemini inline batch responses are correlated by position, not by per-item key.
AgentMap stores:

```python
{"__ordered__": [request_id_0, request_id_1, ...]}
```

Rules enforced in `GeminiBatchAdapter.fetch_results()`:

- if returned count is greater than submitted count:
  - raise `LLMBatchResultIntegrityError`
  - yield nothing
- if returned count equals submitted count:
  - map strictly by index
- if returned count is less than submitted count:
  - map existing responses by index
  - synthesize missing tail records as errored `missing_result` items
  - never shift positions

What this protects against:

- misattributing one provider response to the wrong caller `request_id`

What it cannot protect against:

- equal-count but provider-reordered inline results, because the Developer API
  does not supply per-item keys in this flow

If you add another positional-only provider, copy this integrity posture.

## Status normalization rules

`poll()` must return `BatchPollResult` with an already normalized status. The
service never performs provider enum lookups.

Current mappings live in adapters:

- `AnthropicBatchAdapter._STATUS_MAP`
- `OpenAIBatchAdapter._STATUS_MAP`
- `GeminiBatchAdapter._STATUS_MAP`

Design rule:

- map provider states to `LLMBatchStatus` in the adapter
- log unexpected provider states
- choose a deterministic fallback status rather than leaking raw provider enums

## Result mapping rules

All adapters must return `LLMBatchResult` keyed by caller `request_id`.

Known patterns:

- Anthropic: provider `custom_id` -> caller `request_id`
- OpenAI: JSONL `custom_id` -> caller `request_id`
- Gemini inline: ordered list index -> caller `request_id`

Normalize usage without fabrication:

- missing fields stay `None`
- do not invent cache token counts
- do not backfill usage from unrelated metadata

## Official provider API references

Use primary sources when implementing adapter I/O:

- OpenAI Batch guide: https://platform.openai.com/docs/guides/batch
- OpenAI Batch API reference: https://platform.openai.com/docs/api-reference/batch
- Gemini Batch API: https://ai.google.dev/gemini-api/docs/batch-api

These are the sources that confirm the current provider-side call shapes used by
the adapters:

- OpenAI: file upload with `purpose="batch"`, then batch creation from `input_file_id`, and result download via `output_file_id`
- Gemini: `client.batches.create(model=..., src=...)`, `client.batches.get(name=...)`, `client.batches.cancel(name=...)`, and inline results under `dest.inlined_responses`

## Tests to update

If you change the batch extension surface, update the relevant tests:

- provider-parametrized lifecycle suite
- adapter-specific unit tests
- service dispatch and helper tests
- DI wiring tests if registration behavior changes

At minimum, cover:

- submit
- poll
- restore
- fetch
- cancel
- normalized status mapping
- usage normalization
- conflict detection
- provider alias normalization
- result reconciliation
