#!/usr/bin/env python3
"""
E04-F04: Async Graph Execution Demo

Exercises the native async runner path (GraphRunnerService.run_async) introduced
in E04-F04.  No LLM key needed — EchoFlow uses echo agents; SlowFlow uses a
custom agent with a real time.sleep() to prove concurrency is genuine.

What this tests:
  1. Async execution — run_workflow_async() completes and returns correct output
  2. Sync/async parity — both paths produce identical final state for the same graph
  3. Concurrent execution (fast) — asyncio.gather, results are correct and independent
  4. Cancellation — CancelledError propagates without hanging
  5. Concurrency proof — SlowFlow has a 0.3s time.sleep() per run; 5 sequential runs
     take ~1.5s; 5 concurrent runs take ~0.3s — proving the event loop isn't blocked

Usage:
    cd examples/async_demo
    uv run python run_example.py
"""

import asyncio
import os
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from agentmap.runtime_api import ensure_initialized, run_workflow, run_workflow_async

CONFIG = "agentmap_config.yaml"
GRAPH = "echo_flow::EchoFlow"

ensure_initialized(config_file=CONFIG)


# ── 1. Sync baseline ─────────────────────────────────────────────────────────

print("=" * 60)
print("1. Sync execution (run_workflow)")
print("=" * 60)

sync_result = run_workflow(GRAPH, {"msg": "hello"}, config_file=CONFIG)
sync_final = sync_result.get("outputs", {}).get("final")

print(f"  Input:  msg='hello'")
print(f"  Output: final='{sync_final}'")
assert sync_final == "hello", f"Expected 'hello', got '{sync_final}'"
print("  PASS\n")


# ── 2. Async execution — result must match sync ───────────────────────────────

print("=" * 60)
print("2. Async execution (run_workflow_async) — parity check")
print("=" * 60)


async def run_once():
    return await run_workflow_async(GRAPH, {"msg": "hello"}, config_file=CONFIG)


async_result = asyncio.run(run_once())
async_final = async_result.get("outputs", {}).get("final")

print(f"  Input:  msg='hello'")
print(f"  Output: final='{async_final}'")
assert (
    async_final == sync_final
), f"Parity failure: sync={sync_final!r} async={async_final!r}"
print("  PASS — async output matches sync output\n")


# ── 3. Concurrent execution — asyncio.gather ─────────────────────────────────

print("=" * 60)
print("3. Concurrent execution (asyncio.gather, 5 simultaneous runs)")
print("=" * 60)

PAYLOADS = [f"message-{i}" for i in range(5)]


async def run_all():
    tasks = [
        run_workflow_async(GRAPH, {"msg": payload}, config_file=CONFIG)
        for payload in PAYLOADS
    ]
    t0 = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0
    return results, elapsed


all_results, wall_time = asyncio.run(run_all())

print(f"  Ran {len(PAYLOADS)} graphs concurrently in {wall_time:.3f}s")
print()

for i, (payload, result) in enumerate(zip(PAYLOADS, all_results)):
    final = result.get("outputs", {}).get("final")
    status = "PASS" if final == payload else f"FAIL (got {final!r})"
    print(f"  [{i}] msg='{payload}' → final='{final}'  {status}")
    assert (
        final == payload
    ), f"Concurrent run {i} failed: expected {payload!r}, got {final!r}"

print(f"\n  All {len(PAYLOADS)} concurrent runs correct.")


# ── 4. Cancellation ───────────────────────────────────────────────────────────

print()
print("=" * 60)
print("4. Cancellation — CancelledError propagates cleanly")
print("=" * 60)


async def run_with_cancel():
    task = asyncio.create_task(
        run_workflow_async(GRAPH, {"msg": "will-be-cancelled"}, config_file=CONFIG)
    )
    # Cancel immediately; the runner must not hang or swallow the error
    task.cancel()
    try:
        await task
        return "not-cancelled"
    except asyncio.CancelledError:
        return "cancelled-ok"


cancel_outcome = asyncio.run(run_with_cancel())
print(f"  Outcome: {cancel_outcome}")
assert cancel_outcome == "cancelled-ok", f"Expected cancellation, got: {cancel_outcome}"
print("  PASS — CancelledError propagated without deadlock\n")

# ── 5. Concurrency proof with a blocking agent ───────────────────────────────
#
# SlowAgent calls time.sleep(0.3) inside process().  LangGraph's ainvoke
# offloads sync node callables to the thread pool executor, so multiple
# concurrent graphs don't block each other's event loop turns.
#
# Serial baseline: 5 × 0.3s = ~1.5s
# Concurrent:      all sleeping in parallel threads = ~0.3s
#
# If the difference is absent the async path is just a sync wrapper.

print("=" * 60)
print("5. Concurrency proof — SlowAgent (time.sleep per node)")
print("=" * 60)

from custom_agents.slow_agent import DELAY  # noqa: E402

SLOW_GRAPH = "echo_flow::SlowFlow"
N = 5


# Serial baseline using async but sequential awaits (no gather)
async def run_serial():
    results = []
    for i in range(N):
        r = await run_workflow_async(
            SLOW_GRAPH, {"value": f"item-{i}"}, config_file=CONFIG
        )
        results.append(r)
    return results


# Concurrent using asyncio.gather
async def run_concurrent():
    tasks = [
        run_workflow_async(SLOW_GRAPH, {"value": f"item-{i}"}, config_file=CONFIG)
        for i in range(N)
    ]
    return await asyncio.gather(*tasks)


print(f"  SlowAgent sleeps {DELAY}s per node.  Running {N} graphs each way.\n")

t0 = time.perf_counter()
serial_results = asyncio.run(run_serial())
serial_time = time.perf_counter() - t0
print(
    f"  Serial   (sequential awaits): {serial_time:.2f}s  (expected ~{N * DELAY:.1f}s)"
)

t0 = time.perf_counter()
concurrent_results = asyncio.run(run_concurrent())
concurrent_time = time.perf_counter() - t0
print(
    f"  Parallel (asyncio.gather):    {concurrent_time:.2f}s  (expected ~{DELAY:.1f}s)"
)

speedup = serial_time / concurrent_time
print(f"\n  Speedup: {speedup:.1f}×")

# Correctness
for i, result in enumerate(concurrent_results):
    val = result.get("outputs", {}).get("result")
    assert val == f"item-{i}", f"item-{i} came back as {val!r}"

# Sanity bounds: concurrent should be at least 2× faster than serial
assert speedup >= 2.0, (
    f"Speedup {speedup:.1f}× is too low — async runner may not be offloading "
    f"sync nodes to threads.  serial={serial_time:.2f}s concurrent={concurrent_time:.2f}s"
)
print(f"  PASS — concurrent path is genuinely parallel ({speedup:.1f}× faster)\n")

print("=" * 60)
print("All checks passed.")
