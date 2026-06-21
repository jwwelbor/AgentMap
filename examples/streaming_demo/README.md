# Streaming Demo

End-to-end demonstration of streaming through **AgentMap interfaces only** — no
provider SDK is imported. This example is the canonical verification artifact for
epic E06 success criterion **SC-5** ("single boundary; one config path; additive;
**no provider SDK import**").

## What this demonstrates

`run_example.py` exercises the two caller-facing streaming surfaces in sequence:

1. **Graph-progress streaming** (always runs, no API key needed) —
   `agentmap.runtime_api.run_workflow_stream_async()` is iterated with `async for`.
   `StreamFlow` is a 3-node echo graph, so the reader sees one
   `WorkflowProgressEvent` with `event_type="node_progress"` arrive per completed
   node (incremental, not buffered), followed by exactly one terminal event
   (`completed` / `failed` / `suspended`).

2. **Service-level token streaming** (key-gated; **SKIPs cleanly without a key**) —
   `LLMService.call_llm_stream_async()`, reached through the AgentMap DI container,
   yields `LLMStreamChunk` objects. Non-final chunks carry `text_delta` +
   `chunk_index`; the single terminal chunk (`is_final=True`) carries `usage`,
   `finish_reason`, `resolved_provider`, and `resolved_model`. This section runs
   only when an LLM API key is present, so the example stays CI-safe offline.

## Supported provider / mode boundary

| Provider        | Mode                 | Streams?                          |
|-----------------|----------------------|-----------------------------------|
| Anthropic       | Token (text)         | Supported                         |
| OpenAI          | Token (text)         | Supported                         |
| Google / Gemini | Token                | Unsupported — documented error    |
| Any             | Batch (`stream` kwarg) | Unsupported — documented error  |
| Graph (any)     | Graph-progress       | Supported                         |

For the full caller contract, provider caveats, the operational envelope, and the
exact unsupported-mode error strings, see
[`docs/streaming/streaming-caller-contract.md`](../../docs/streaming/streaming-caller-contract.md).

## Requirements

```bash
pip install agentmap
```

No LLM API key is required for the graph-progress section — `StreamFlow` uses
built-in echo agents. The token-streaming section is skipped unless
`ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set.

## Running

```bash
cd examples/streaming_demo
uv run python run_example.py
```

## What to expect

The script prints two numbered sections and a final summary. With **no API key**
set:

```
1. Graph-progress streaming (run_workflow_stream_async)
   ... per-node node_progress events, then a terminal event ...
   PASS — graph-progress streamed ordered per-node events then a terminal.

2. Token streaming (LLMService.call_llm_stream_async)
   SKIP — no LLM API key found in environment (ANTHROPIC_API_KEY / OPENAI_API_KEY).

All checks passed.
```

The process exits `0` in both the no-key and key-present cases. With a key set,
section 2 prints incremental token deltas and ends with `PASS` instead of `SKIP`.

## No-provider-SDK-import constraint (SC-5)

This example imports **zero** provider SDKs (`anthropic`, `openai`,
`google.generativeai`, `google.genai`). All streaming is reached through AgentMap's
runtime API and service container. Verify mechanically — this command must return
**no output** (grep exit status 1):

```bash
grep -nE '^[[:space:]]*(import|from)[[:space:]]+(anthropic|openai|google(\.generativeai|\.genai)?)([[:space:]]|\.|$)' \
  run_example.py
```

## Key files

| File | Description |
|------|-------------|
| `run_example.py` | Main demo — graph-progress streaming (keyless) + token streaming (key-gated) |
| `agentmap_config.yaml` | The single canonical AgentMap config for the example |
| `workflows/stream_flow.csv` | CSV defining `StreamFlow`, a 3-node echo graph (multi-node so per-node ordering is observable) |
