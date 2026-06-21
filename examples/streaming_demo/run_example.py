#!/usr/bin/env python3
"""
E06-F07: Streaming Demo

Demonstrates streaming through AgentMap using ONLY AgentMap interfaces and
configuration.  This is the canonical SC-5 verification artifact for epic E06:
the file imports NO provider SDK (`anthropic`, `openai`, `google.generativeai`,
`google.genai`) — all streaming is reached through AgentMap's runtime API and
service container.

Two streaming surfaces are exercised:

  1. Graph-progress streaming (always runs, no API key needed)
     `agentmap.runtime_api.run_workflow_stream_async(graph, inputs, config_file=...)`
     yields one `WorkflowProgressEvent` per completed node (`event_type=
     "node_progress"`), then exactly one terminal event (`completed` / `failed`
     / `suspended`).  StreamFlow is a 3-node echo graph, so the reader sees
     incremental per-node events arrive before the terminal result.

  2. Service-level token streaming (key-gated; SKIPs cleanly without a key)
     `LLMService.call_llm_stream_async(messages, ...)` — reached through the
     AgentMap DI container — yields `LLMStreamChunk` objects: non-final chunks
     carry `text_delta` + `chunk_index`; the single terminal chunk
     (`is_final=True`) carries `usage`, `finish_reason`, `resolved_provider`,
     and `resolved_model`.  This section runs only when an LLM API key is
     present so the example stays CI-safe offline.

Provider/mode boundary (see docs/streaming/streaming-caller-contract.md):
  Supported token streaming: Anthropic (text), OpenAI (text).
  Unsupported (documented error): Google/Gemini token streaming, batch streaming.

Usage:
    cd examples/streaming_demo
    uv run python run_example.py

No-SDK-import verification (must return zero matches):
    grep -nE '^[[:space:]]*(import|from)[[:space:]]+(anthropic|openai|google(\\.generativeai|\\.genai)?)([[:space:]]|\\.|$)' \\
      run_example.py
"""

import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from agentmap.runtime_api import (  # noqa: E402
    ensure_initialized,
    get_container,
    run_workflow_stream_async,
)

CONFIG = "agentmap_config.yaml"
GRAPH = "stream_flow::StreamFlow"

# Token-streaming section runs only when one of these is set in the environment.
LLM_KEY_ENV_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")

ensure_initialized(config_file=CONFIG)


# ── 1. Graph-progress streaming (no API key required) ─────────────────────────

print("=" * 64)
print("1. Graph-progress streaming (run_workflow_stream_async)")
print("=" * 64)


async def stream_graph_progress():
    """Iterate WorkflowProgressEvents from a 3-node echo graph.

    Returns (node_event_count, terminal_event) so the caller can assert the
    SC-3 contract: ordered node_progress events then exactly one terminal.
    """
    node_events = 0
    terminal = None

    print("  Streaming events as they arrive:\n")
    async for event in run_workflow_stream_async(
        GRAPH, {"msg": "hello-streaming"}, config_file=CONFIG
    ):
        if event.is_terminal:
            terminal = event
            print(
                f"    [seq {event.sequence}] TERMINAL  event_type={event.event_type!r}"
            )
        else:
            node_events += 1
            print(
                f"    [seq {event.sequence}] node_progress  "
                f"node={event.node_name!r}  state_delta={event.state_delta!r}"
            )

    return node_events, terminal


node_count, terminal_event = asyncio.run(stream_graph_progress())

print()
print(f"  Observed {node_count} node_progress event(s) before the terminal event.")
assert node_count >= 1, (
    "Expected at least one node_progress event from a multi-node graph; "
    f"got {node_count}.  The graph must have >= 2 nodes (SC-3 ordering)."
)
assert terminal_event is not None, "Stream ended without a terminal event."
assert terminal_event.event_type == "completed", (
    f"Expected terminal event_type 'completed', got "
    f"{terminal_event.event_type!r} (error={terminal_event.error!r})."
)

final_output = (terminal_event.result or {}).get("outputs", {}).get("final")
print(f"  Terminal result outputs.final = {final_output!r}")
assert (
    final_output == "hello-streaming"
), f"Expected final output 'hello-streaming', got {final_output!r}."
print("  PASS — graph-progress streamed ordered per-node events then a terminal.\n")


# ── 2. Service-level token streaming (key-gated; SKIPs without a key) ──────────

print("=" * 64)
print("2. Token streaming (LLMService.call_llm_stream_async)")
print("=" * 64)

present_key = next((name for name in LLM_KEY_ENV_VARS if os.environ.get(name)), None)

if present_key is None:
    print(
        "  SKIP — no LLM API key found in environment "
        f"({' / '.join(LLM_KEY_ENV_VARS)})."
    )
    print("  Set ANTHROPIC_API_KEY or OPENAI_API_KEY to exercise live token streaming.")
    print("  (The graph-progress section above needs no key and ran successfully.)\n")
else:
    # Resolve the provider from the key that is present.  Anthropic and OpenAI
    # text token streaming are the supported combinations (see the contract doc).
    provider = "anthropic" if present_key == "ANTHROPIC_API_KEY" else "openai"
    print(f"  Found {present_key} → streaming via provider {provider!r}.\n")

    async def stream_tokens():
        """Reach call_llm_stream_async through the AgentMap container.

        No provider SDK is imported here — the LLMService is obtained from the
        DI container and the streaming entry point is an AgentMap interface.
        """
        container = get_container()
        llm_service = container.llm_service()

        # LLMMessage is a plain dict (agentmap.models.llm_execution.LLMMessage).
        messages = [{"role": "user", "content": "Say hello in exactly five words."}]

        print("  Streaming tokens as they arrive:\n    ", end="", flush=True)
        chunk_count = 0
        terminal_chunk = None
        async for chunk in llm_service.call_llm_stream_async(
            messages, provider=provider
        ):
            if chunk.is_final:
                terminal_chunk = chunk
            else:
                chunk_count += 1
                print(chunk.text_delta, end="", flush=True)
        print("\n")
        return chunk_count, terminal_chunk

    delta_count, final_chunk = asyncio.run(stream_tokens())

    print(f"  Received {delta_count} incremental text chunk(s).")
    assert final_chunk is not None, "Token stream ended without a terminal chunk."
    assert final_chunk.is_final, "Terminal chunk did not have is_final=True."
    print(
        f"  Terminal chunk: resolved_provider={final_chunk.resolved_provider!r} "
        f"resolved_model={final_chunk.resolved_model!r} "
        f"finish_reason={final_chunk.finish_reason!r}"
    )
    print("  PASS — token streaming delivered deltas then a terminal chunk.\n")


# ── Summary ───────────────────────────────────────────────────────────────────

print("=" * 64)
print("All checks passed.")
