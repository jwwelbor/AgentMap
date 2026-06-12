# Async Demo

End-to-end demonstration of the AgentMap native async runtime API.

## What this demonstrates

`run_example.py` proves five things in sequence:

1. **Async execution** — `run_workflow_async()` completes and returns the correct output
2. **Sync/async parity** — both paths produce identical final state for the same graph
3. **Concurrent execution** — `asyncio.gather` runs multiple workflows simultaneously with correct, independent results
4. **Cancellation propagation** — `CancelledError` propagates without hanging or deadlocking
5. **Concurrency proof** — `SlowFlow` contains a `time.sleep(0.3)` node; 5 sequential runs take ~1.5 s; 5 concurrent runs take ~0.3 s, proving the event loop is not blocked

## Requirements

```bash
pip install agentmap
```

No LLM API key required — `EchoFlow` uses built-in echo agents; `SlowFlow` uses a local custom agent.

## Running

```bash
cd examples/async_demo
uv run python run_example.py
```

## What to expect

The script prints five numbered sections. Each ends with `PASS` on success:

```
1. Sync execution (run_workflow)                    → PASS
2. Async execution — parity check                   → PASS
3. Concurrent execution (asyncio.gather, 5 runs)    → all 5 correct
4. Cancellation — CancelledError propagates cleanly → PASS
5. Concurrency proof — SlowAgent (time.sleep)       → PASS (≥2× speedup asserted)

All checks passed.
```

Section 5 asserts that concurrent wall-clock time is at least 2× faster than serial. If the assertion fails, the async runner is wrapping sync calls instead of offloading them to threads.

## Key files

| File | Description |
|------|-------------|
| `run_example.py` | Main demo script — runs all five checks |
| `custom_agents/slow_agent.py` | Sync agent with `time.sleep(0.3)` to prove real concurrency |
| `workflows/echo_flow.csv` | CSV defining `EchoFlow` (echo agent) and `SlowFlow` (slow agent) |

---

For usage patterns and best practices, see the [Async Workflows guide](/docs/guides/async-workflows).
For full parameter tables and return shapes, see [API Reference → Async Workflow Operations](/docs/reference/api#async-workflow-operations).
