---
title: Async Workflow Execution
sidebar_position: 1
description: Concurrent workflow execution with the async runtime API — patterns, FastAPI integration, and cancellation handling.
keywords: [async, asyncio, concurrent, FastAPI, run_workflow_async, performance]
---

# Async Workflow Execution

AgentMap ships a native async runtime API alongside its sync counterpart. The two surfaces have identical argument and return shapes — the async versions simply run without blocking the event loop.

## When to use async vs sync

| | Sync (`run_workflow`) | Async (`run_workflow_async`) |
|---|---|---|
| **Scripts and CLIs** | ✓ Preferred | Unnecessary overhead |
| **AWS Lambda / serverless** | ✓ Simpler | ✓ Works fine |
| **Simple integrations** | ✓ Preferred | Unnecessary overhead |
| **FastAPI / aiohttp handlers** | Blocks the event loop | ✓ Required |
| **Concurrent fan-out** | Requires threads | ✓ `asyncio.gather` |
| **Existing event loops** | Blocks event loop | ✓ Required |
| **Native async I/O agents** | N/A | ✓ Full benefit |
| **Sync-only agents** | ✓ | ✓ Free via executor fallback |

## Concurrent execution with asyncio.gather

The primary reason to reach for the async API is fan-out — running many workflows simultaneously without spawning threads manually.

```python
import asyncio
from agentmap import ensure_initialized, run_workflow_async

ensure_initialized()

DOCUMENTS = ["doc-0", "doc-1", "doc-2", "doc-3", "doc-4"]

async def run_all():
    tasks = [
        run_workflow_async("summarizer", {"doc": doc})
        for doc in DOCUMENTS
    ]
    results = await asyncio.gather(*tasks)
    return results

results = asyncio.run(run_all())
```

Why the speedup: `asyncio.gather` schedules all coroutines concurrently on the event loop. Sync agents inside each workflow run via `loop.run_in_executor`, which offloads them to a thread pool — so multiple sync-only workflows run in parallel threads without any code changes to the agents.

A 5-run concurrent benchmark from `examples/async_demo/run_example.py` shows ~5× wall-clock improvement over sequential awaits when each workflow contains a 0.3 s `time.sleep()` node.

## FastAPI integration

Inside an `async def` endpoint, always use `run_workflow_async` — calling the blocking `run_workflow` inside an async handler stalls the entire event loop.

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from agentmap import ensure_initialized, run_workflow_async

app = FastAPI()

@app.on_event("startup")
async def startup():
    ensure_initialized()

class WorkflowRequest(BaseModel):
    inputs: Dict[str, Any]
    profile: str = None

@app.post("/workflows/{graph_name}")
async def execute_workflow(graph_name: str, request: WorkflowRequest):
    result = await run_workflow_async(
        graph_name=graph_name,
        inputs=request.inputs,
        profile=request.profile,
    )
    if result["success"]:
        return result["outputs"]
    elif result.get("interrupted"):
        return {"status": "interrupted", "thread_id": result["thread_id"]}
    raise HTTPException(status_code=500, detail=result.get("error"))
```

For production FastAPI patterns including middleware, background tasks, and resume endpoints, see the [FastAPI Integration guide](/docs/deployment/fastapi-integration).

## Cancellation handling

`asyncio.CancelledError` propagates cleanly through both `run_workflow_async` and `resume_workflow_async`. For `resume_workflow_async`, the framework also unmarks the checkpoint's `resuming` state on cancellation so the workflow can be safely retried.

```python
import asyncio
from agentmap import run_workflow_async

async def run_with_timeout(graph_name: str, inputs: dict, timeout: float):
    task = asyncio.create_task(
        run_workflow_async(graph_name, inputs)
    )
    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected — task was cancelled
        return None

# Manual cancel pattern
async def run_with_manual_cancel():
    task = asyncio.create_task(
        run_workflow_async("long_running", {"input": "data"})
    )
    # ... some condition
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        raise  # Always re-raise unless you've fully handled shutdown
```

**Do not catch and swallow `CancelledError`** without re-raising. Swallowing it breaks asyncio's cooperative cancellation protocol — parent tasks and `asyncio.gather` will not propagate cancellation correctly. The timeout example above is the one valid exception: it catches `CancelledError` only after explicitly cancelling the task and translating the result to a `None` return.

For full API parameter tables and return shapes, see [API Reference → Async Workflow Operations](/docs/reference/api#async-workflow-operations).
