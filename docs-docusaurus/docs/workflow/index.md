---
title: Workflow Execution
sidebar_position: 1
description: How AgentMap executes workflows — sync and async execution models, checkpoints, and resume patterns.
keywords: [workflow execution, async, checkpoint, resume, suspend, AgentMap runtime]
---

# Workflow Execution

AgentMap executes workflows as LangGraph graphs compiled from CSV definitions. The runtime supports both sync and async execution with native checkpoint/resume for human-in-the-loop workflows.

## Execution paths

| Path | Entry point | Use when |
|---|---|---|
| **Sync** | `run_workflow()` | Scripts, CLIs, Lambda, simple integrations |
| **Async** | `run_workflow_async()` | FastAPI endpoints, `asyncio.gather` fan-out, existing event loops |
| **CLI run** | `agentmap run` | Development, automation scripts, CI/CD |

The async path uses native `ainvoke` for graph execution. Sync-only agents run in a thread pool executor so they never block the event loop — no code changes needed in existing agents.

For async patterns and concurrency examples, see [Async Workflow Execution](../guides/async-workflows).

## Execution envelope

Every `run_workflow()` / `run_workflow_async()` call returns the same envelope:

```python
{
    "success": True,                     # False on error or unhandled interrupt
    "outputs": { ... },                  # Final state fields
    "metadata": {
        "graph_name": "CustomerSupport",
        "execution_time": 1.23,
    },
    # Present only when an agent raised a suspend/interrupt:
    "interrupted": True,
    "thread_id": "thread-uuid-12345",
    "interrupt_message": "Approve the draft?",
}
```

Check `result["interrupted"]` before assuming completion. An interrupted result contains a `thread_id` that you pass to `resume_workflow()` or `resume_workflow_async()` later.

## Checkpoint and resume

Workflows that reach a [SuspendAgent](../agents/suspend-agent-features) node pause execution and checkpoint their state. The response envelope contains a `thread_id`; the caller stores it and resumes when ready.

See the [Checkpoint and Resume Guide](./checkpoint-resume) for the full pattern including valid resume actions, token format, and error handling.

## Graph naming

Workflows are identified by a graph name that maps to a CSV file in the configured `csv_repository`:

```python
# Simple name — resolves to <repository>/customer_support.csv, graph "customer_support"
run_workflow("customer_support", inputs)

# Explicit graph inside a multi-graph CSV
run_workflow("workflows::CustomerSupport", inputs)
run_workflow("workflows/CustomerSupport", inputs)  # alternate syntax
```

The same naming syntax works for CLI commands and HTTP API endpoints.
