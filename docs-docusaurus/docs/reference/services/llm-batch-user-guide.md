---
sidebar_position: 3
title: LLM Batch User Guide
description: Provider-agnostic batch usage for Anthropic, OpenAI, and Gemini
keywords: [LLM batch, Anthropic, OpenAI, Gemini, AgentMap, ai agents]
---

# LLM Batch User Guide

This guide is for callers using `LLMService` batch execution as a stable,
provider-agnostic interface. The primary audience is AI agents that need a
repeatable contract; human operators are the secondary audience.

For the feature design details, see:

- `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/spec.md` § Canonical Parameter Resolution
- `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/spec.md` § Gemini Result Demux Integrity
- `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/adr-001-batch-optional-deps.md`

## What you get

One caller contract across three providers:

- Anthropic
- OpenAI
- Gemini Developer API via `google-genai`

The service owns provider normalization, adapter lookup, persistence-safe batch
handles, centralized parameter validation, sync and async lifecycle helpers, and
result re-keying back to your original `request_id`.

## Install and provider availability

Install the optional batch SDKs:

```bash
pip install "agentmap[batch]"
```

Or install everything:

```bash
pip install "agentmap[all]"
```

The `batch` extra includes:

- `anthropic`
- `openai`
- `google-genai`

Registration behavior:

- If an SDK is installed and the provider API key is configured, its adapter is registered.
- If an SDK is missing, adapter construction raises `LLMDependencyError`.
- The DI container catches that error, logs it, and skips that provider.
- Submitting to an unregistered provider raises `LLMBatchUnsupportedProviderError` before any network call.

## Provider selection and registry behavior

The registry uses canonical provider keys:

- `anthropic`
- `openai`
- `google`

`LLMService` normalizes common aliases before lookup:

- `claude` -> `anthropic`
- `gpt` -> `openai`
- `gemini` -> `google`

That means these are equivalent at submission time:

```python
provider="google"
provider="gemini"
```

The handle always stores the canonical provider name after submission.

## Capability matrix

| Capability | Anthropic | OpenAI | Gemini Developer API |
|---|---|---|---|
| Canonical provider key | `anthropic` | `openai` | `google` |
| Submit / poll / fetch | Yes | Yes | Yes |
| Cancel | Yes | Yes | Yes |
| Async surface | Yes | Yes | Yes |
| `batch_capabilities()["completion_window"]` | `24h` | `24h` | `24h` |
| `batch_capabilities()["partial_fetch"]` | `False` | `False` | `False` |
| Result transport used by AgentMap | Provider results stream | `output_file_id` download | Inline responses only |
| `result_ref` on handle | Usually `None` | `output_file_id` after poll | `None` |

Gemini note: this feature documents the Developer API path only. Vertex AI,
GCS, BigQuery, and file-backed Gemini result flows are out of scope here.

## Status lifecycle

All providers are normalized to the same `LLMBatchStatus` values:

| Status | Meaning |
|---|---|
| `submitted` | Batch accepted locally; provider work not yet observed |
| `in_progress` | Provider is processing |
| `canceling` | Cancel requested; provider has not reached terminal state yet |
| `canceled` | Provider canceled the batch |
| `ended` | Provider completed processing; results can be fetched |
| `expired` | Provider expired the batch |
| `failed` | Provider reported failure, or the adapter mapped an unknown terminal state to failure |

Terminal states for caller logic:

- `ended`
- `canceled`
- `expired`
- `failed`

`restore_batch()` does not poll. Treat a restored handle as stale until you call
`poll_batch()` or `apoll_batch()`.

## Sync lifecycle

### Submit

```python
from agentmap.models.llm_execution import LLMBatchSubmitRequest, LLMRequest

request = LLMBatchSubmitRequest(
    provider="openai",
    model="gpt-4o-mini",
    max_tokens=256,
    requests=[
        LLMRequest(
            request_id="summary",
            messages=[{"role": "user", "content": "Summarize this release note."}],
        ),
        LLMRequest(
            request_id="risks",
            messages=[{"role": "user", "content": "List rollout risks."}],
        ),
    ],
)

handle = llm_service.submit_batch(request)
print(handle.agentmap_batch_id)
print(handle.provider)  # canonical provider key
print(handle.status.value)
```

### Poll until terminal

```python
import time

while handle.status not in {
    "ended",
    "canceled",
    "expired",
    "failed",
}:
    time.sleep(10)
    handle = llm_service.poll_batch(handle)
```

Use the enum values if you already imported `LLMBatchStatus`; the example above
stays string-oriented because many agent runtimes serialize status checks.

### Fetch results

```python
records = llm_service.fetch_batch_results(handle)

for record in records:
    if record.status == "succeeded":
        print(record.request_id, record.text)
    else:
        print(record.request_id, record.status, record.error.message if record.error else None)
```

### Cancel

```python
handle = llm_service.cancel_batch(handle)
print(handle.status.value)
```

Cancel outcomes:

- Non-terminal active batch -> adapter cancel request -> service re-polls
- Terminal batch -> `LLMBatchCancelNotSupportedError`
- Unregistered provider -> `LLMBatchUnsupportedProviderError`

The service checks terminal state before checking adapter capabilities, so a
terminal handle gets the more accurate terminal-state error.

### Submit and wait

```python
handle = llm_service.submit_and_wait(
    request,
    poll_interval=10.0,
    timeout=900,
)
records = llm_service.fetch_batch_results(handle)
```

## Async lifecycle

```python
import asyncio

async def run_batch(llm_service, request):
    handle = await llm_service.asubmit_batch(request)
    handle = await llm_service.wait_for_batch(
        handle,
        poll_interval=10.0,
        timeout=900,
    )
    return await llm_service.afetch_batch_results(handle)

records = asyncio.run(run_batch(llm_service, request))
```

Async notes:

- The adapter protocol is synchronous.
- `LLMService` exposes async methods by wrapping the sync lifecycle in `asyncio.to_thread(...)`.
- `wait_for_batch()` uses capped exponential backoff.
- `timeout=None` means wait indefinitely.

## Restore and continue after restart

```python
# writer process
handle = llm_service.submit_batch(request)
persisted = handle.to_dict()
save_somewhere(handle.agentmap_batch_id, persisted)

# reader process
handle_data = load_somewhere(handle.agentmap_batch_id)
handle = llm_service.restore_batch(handle_data)
handle = llm_service.poll_batch(handle)
records = llm_service.fetch_batch_results(handle) if handle.status.value == "ended" else []
```

Persistence guarantees:

- `LLMBatchHandle.to_dict()` contains AgentMap-owned metadata only
- No provider SDK object is stored
- No API key is stored
- No raw message payload is stored
- Existing Anthropic F03 handles still load through `LLMBatchHandle.from_dict()`

## Canonical parameter rules

The service resolves parameters once, before adapter dispatch, in
`src/agentmap/services/llm/_param_resolution.py`.

### Reserved logical parameters

- `model`
- `temperature`
- `max_tokens`

Provider alias handling:

- `max_output_tokens` is treated as an alias of `max_tokens`

### Parameter surfaces

| Surface | Example | Scope |
|---|---|---|
| `S1` | `request.model`, `request.temperature` | per request |
| `S2` | `request.request_options["temperature"]` | per request |
| `S3` | `request.model`, `request.max_tokens` | whole batch |
| `S4` | `request.request_options["temperature"]` | whole batch |

### Resolution rule

- Parameter set on exactly one surface: accepted
- Same parameter set on multiple surfaces with the same value: accepted
- Same parameter set on multiple surfaces with different values: `LLMBatchParamConflictError`
- Batch-incompatible values such as `stream=True` or `max_tokens=0`: `LLMServiceError`
- `LLMRequest.provider` set at all: `LLMServiceError` because provider is batch-level only

### Happy path example

```python
request = LLMBatchSubmitRequest(
    provider="anthropic",
    model="claude-sonnet-4-6",  # batch default model
    max_tokens=512,             # batch default token limit
    requests=[
        LLMRequest(
            request_id="default-model",
            messages=[{"role": "user", "content": "Summarize this RFC."}],
        ),
        LLMRequest(
            request_id="cooler-temp",
            messages=[{"role": "user", "content": "Rewrite as release notes."}],
            temperature=0.2,  # per-request override, one surface only
        ),
    ],
)
```

### Conflict example

```python
from agentmap.services.llm_batch_errors import LLMBatchParamConflictError

request = LLMBatchSubmitRequest(
    provider="openai",
    model="gpt-4o-mini",
    max_tokens=256,
    request_options={"temperature": 0.8},
    requests=[
        LLMRequest(
            request_id="q1",
            messages=[{"role": "user", "content": "Explain the diff."}],
            temperature=0.2,
        ),
    ],
)

try:
    llm_service.submit_batch(request)
except LLMBatchParamConflictError as exc:
    print(type(exc).__name__)
    print(exc)
```

Expected outcome: the service rejects the batch before any provider call, naming
the conflicting logical parameter, the `request_id`, and the conflicting surfaces.

### Alias conflict example

```python
request = LLMBatchSubmitRequest(
    provider="google",
    model="models/gemini-2.5-flash",
    max_tokens=256,
    request_options={
        "max_tokens": 256,
        "max_output_tokens": 1024,
    },
    requests=[
        LLMRequest(
            request_id="q1",
            messages=[{"role": "user", "content": "Generate a changelog."}],
        ),
    ],
)

llm_service.submit_batch(request)
```

Expected outcome: `LLMBatchParamConflictError`. AgentMap treats
`max_output_tokens` as the same logical parameter as `max_tokens`; it does not
silently pick one.

## Result helpers

### Index by `request_id`

```python
records = llm_service.fetch_batch_results(handle)
by_id = llm_service.results_by_request_id(records)
print(by_id["summary"].text)
```

### Reconcile missing results

```python
submitted_request_ids = [request_item.request_id for request_item in request.requests]
reconciled = llm_service.reconcile_batch_results(submitted_request_ids, records)

for request_id, record in reconciled.items():
    if record is None:
        print(f"missing result for {request_id}")
```

Use reconciliation whenever missing results would be operationally important.

## Typed error paths

```python
from agentmap.exceptions import LLMDependencyError, LLMServiceError
from agentmap.services.llm_batch_errors import (
    LLMBatchCancelNotSupportedError,
    LLMBatchExpiredError,
    LLMBatchNotReadyError,
    LLMBatchParamConflictError,
    LLMBatchUnsupportedProviderError,
)

try:
    handle = llm_service.submit_batch(request)
except LLMBatchUnsupportedProviderError:
    ...
except LLMBatchParamConflictError:
    ...
except LLMDependencyError:
    ...
except LLMServiceError:
    ...
```

Key outcomes:

| Error | Typical trigger |
|---|---|
| `LLMBatchUnsupportedProviderError` | Provider has no registered adapter |
| `LLMBatchParamConflictError` | Reserved param conflict across surfaces or aliases |
| `LLMBatchCancelNotSupportedError` | Cancel requested on terminal handle or non-cancelable adapter |
| `LLMBatchNotReadyError` | `fetch_batch_results()` called before `ended` |
| `LLMBatchExpiredError` | Poll or fetch attempted on expired handle |
| `LLMBatchResultIntegrityError` | Gemini inline result counts make positional demux unsafe |

## Provider-specific behavior that matters to callers

### Anthropic

- Results are fetched from the provider batch results stream
- `result_ref` is not required for fetch
- Usage may include cache token fields

### OpenAI

- Submit hides the JSONL staging step
- Poll captures `output_file_id` into `handle.result_ref`
- Fetch downloads the output file and demuxes by `custom_id`

### Gemini

- Uses the Developer API through `google-genai`
- Submit uses inline requests
- Fetch reads `dest.inlined_responses`
- Correlation is positional, not key-based
- Gemini inline delivery means `result_ref` stays `None`

## Official provider API references

- OpenAI Batch API: https://platform.openai.com/docs/guides/batch
- OpenAI Batch API reference: https://platform.openai.com/docs/api-reference/batch
- Gemini Batch API: https://ai.google.dev/gemini-api/docs/batch-api

Those links are the authoritative external references for the provider-side API
shapes that AgentMap wraps.
