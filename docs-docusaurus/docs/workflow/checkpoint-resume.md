---
title: Checkpoint and Resume
sidebar_position: 2
description: Pattern for suspending workflows at human-in-the-loop points and resuming them with user responses.
keywords: [checkpoint, resume, suspend, human-in-the-loop, thread_id, response_action]
---

# Checkpoint and Resume

AgentMap supports suspending a workflow mid-execution and resuming it later with a user response. This enables approval gates, multi-turn interactions, and human-in-the-loop review steps without holding server resources between turns.

## How it works

1. A workflow runs until it hits a [SuspendAgent](../agents/suspend-agent-features) node.
2. The agent raises `GraphInterrupt`, which causes the graph to checkpoint its state and stop.
3. The `run_workflow` / `run_workflow_async` call returns an interrupted result envelope with a `thread_id`.
4. The caller stores the `thread_id` and prompts the user.
5. When the user responds, the caller calls `resume_workflow` / `resume_workflow_async` with the `thread_id` and action.
6. The graph restores from the checkpoint and continues from the point of interruption.

## Full suspend → resume pattern

```python
import json
from agentmap import ensure_initialized, run_workflow_async, resume_workflow_async

ensure_initialized()

# --- Step 1: Run until interrupted ---
result = await run_workflow_async("approval_flow", {"draft": "Content to review"})

if result.get("interrupted"):
    thread_id = result["thread_id"]
    print(result["interrupt_message"])  # "Approve the draft?"

    # Store thread_id (database, queue, session, etc.)
    save_pending(thread_id)

# --- Step 2: Resume when the user responds ---
thread_id = load_pending()

resume_token = json.dumps({
    "thread_id": thread_id,
    "response_action": "approve",
    "response_data": {"comment": "Looks good"},
})

result = await resume_workflow_async(resume_token=resume_token)

if result["success"]:
    print("Workflow completed:", result["outputs"])
```

## Resume token format

`resume_token` accepts two forms:

| Form | When to use |
|---|---|
| Plain thread ID string | `"thread-uuid-12345"` — simple continue with no action |
| JSON token | `'{"thread_id": "...", "response_action": "approve", "response_data": {...}}'` |

### Valid response actions

The `response_action` field must be one of:

| Action | Typical use |
|---|---|
| `approve` | Approve a draft or proposal |
| `reject` | Reject and stop the workflow |
| `choose` | Select from multiple options |
| `respond` | Provide a free-text response |
| `edit` | Submit an edited version of content |
| `continue` | Continue without a specific action (default when omitted) |
| `stop` | Stop the workflow |
| `retry` | Retry the suspended step |
| `skip` | Skip the current step |
| `submit` | Submit a form or data |
| `cancel` | Cancel the interaction |
| `text_input` | Provide text input |
| `save` | Save and continue |
| `reply` | Reply in a conversation |
| `end` | End a conversation thread |

Unknown actions are rejected with a validation error before the workflow is invoked.

### Payload size limit

The serialised `resume_token` / `response_data` payload is limited to **64 KiB**. Requests exceeding this limit are rejected at the parsing and HTTP validation layers.

## CLI resume

```bash
# Resume with just a thread ID (continue action)
agentmap resume <thread_id>

# Resume with an action
agentmap resume <thread_id> approve

# Resume with structured data
agentmap resume <thread_id> respond --data '{"message": "Approved with conditions"}'

# Resume with data from a file
agentmap resume <thread_id> edit --data-file /path/to/edited_content.json
```

Options:
- `thread_id` (positional, required): Thread ID from the interrupted workflow
- `response` (positional, optional): Response action (e.g., `approve`, `reject`, `respond`)
- `--data` / `-d`: Additional response data as a JSON string
- `--data-file` / `-f`: Path to a JSON file with response data
- `--config` / `-c`: Path to a custom config file

## Cancellation and safety

`asyncio.CancelledError` propagates cleanly through `resume_workflow_async`. If a resume task is cancelled mid-execution, the framework unmarks the checkpoint's `resuming` state so the same `thread_id` can be resumed again without manual cleanup.

```python
import asyncio
from agentmap import resume_workflow_async

async def resume_with_timeout(thread_id: str, timeout: float = 30.0):
    task = asyncio.create_task(
        resume_workflow_async(resume_token=thread_id)
    )
    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # State is clean — safe to retry resume
        return None
```

**Do not swallow `CancelledError`** outside of a timeout-then-retry pattern. Swallowing it breaks asyncio's cooperative cancellation protocol.

## Storing thread IDs

The `thread_id` returned from an interrupted workflow must be persisted by the caller. It is not stored by AgentMap beyond the checkpoint. Use whatever persistence layer fits your application:

```python
# FastAPI + database pattern
@app.post("/workflows/{graph_name}")
async def run_workflow_endpoint(graph_name: str, request: WorkflowRequest):
    result = await run_workflow_async(graph_name, request.inputs)

    if result.get("interrupted"):
        # Persist so the /resume endpoint can look it up
        await db.save_pending_workflow(
            thread_id=result["thread_id"],
            user_id=request.user_id,
            message=result.get("interrupt_message"),
        )
        return {"status": "pending", "thread_id": result["thread_id"]}

    return result["outputs"]

@app.post("/workflows/resume/{thread_id}")
async def resume_endpoint(thread_id: str, body: ResumeRequest):
    token = json.dumps({
        "thread_id": thread_id,
        "response_action": body.action,
        "response_data": body.data,
    })
    result = await resume_workflow_async(resume_token=token)
    return result["outputs"] if result["success"] else {"error": result.get("error")}
```

## Related

- [Suspend Agent Features](../agents/suspend-agent-features) — configuring the SuspendAgent node
- [Async Workflow Execution](../guides/async-workflows) — concurrent patterns and FastAPI integration
- [API Reference → Async Workflow Operations](../reference/api#async-workflow-operations) — full parameter and return shapes
