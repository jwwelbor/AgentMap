# B102 dependency review

| Metadata | Value |
|---|---|
| Entity | `B102` |
| Base commit | `f8a37400a2a56b51a305dad78e7a491027f1a5f5` |
| Head commit | `7c22ba61a8a685400c5f9826d3fc9adfe6ebeace` |
| Candidate diff | `candidate.diff` |
| Candidate SHA-256 | `c73121f2fe52e68db59999b089695bc0034e86003e0aa2d483d77b07fae45138` |
| Runner mode | `dispatched-six-angle` |
| Specialists completed | `6` |
| Consolidator completed | `true` |
| Adversarial review | `none` |
| Fallback reason | `native Workflow unavailable` |
| Scope | 17 changed files; every specialist reported the exact 17/17 manifest; no missing or extra files |

## A. Executive Summary

This diff replaces executor-backed lifecycle-lock acquisition with condition ownership and loop futures, moves HTTP admin initialization to the async API, strengthens cancellation and refresh handling, and adds retained evidence and regression coverage. The async-waiter design is a focused and defensible change, but the transaction owner still submits startup to the same bounded default executor in which synchronous public facade callers can wait for that owner. That circular dependency means the implementation does not yet satisfy the executor-starvation contract it claims to repair.

- Overall risk: **high** because the surviving failure can indefinitely stall public workflow operations and runtime initialization.
- Verdict: **FAIL**
- Counts: **1 blocker / 0 non-blockers / 0 nits**
- Scope sanity: 722 additions and 93 deletions across 17 task-related source, test, handoff, and verification files; the size is plausible for the lifecycle rework and retained full-suite evidence, and no unrelated change was identified.
- Coverage: six specialists each reported the exact 17/17 changed-file manifest; candidate diff regeneration from the pinned commits reproduced the recorded SHA-256.
- Checks performed: six dispatched angles plus this consolidator; static verification of the runtime owner/waiter path, all three public `asyncio.to_thread` facade chains, the new bounded-executor tests, the handoff contract, and retained test evidence.

## B. Findings Table

| id | severity | file:line | rule | diagnosis | evidence | correction |
|---|---|---|---|---|---|---|
| B102-R8-01 | Blocker | `src/agentmap/runtime/runtime_manager.py:94`, `src/agentmap/runtime/runtime_manager.py:185`, `tests/unit/runtime/test_b102_runtime_coordination.py:142` | `CONTRACT` | A synchronous facade call running in the loop's default executor may block in `_acquire_sync_transaction()` while an async transaction owns the runtime. The owner then queues `_install_and_startup()` to that same executor. If synchronous facade waiters occupy all one or two workers, the owner cannot start and the waiters cannot be released. The new test covers only async waiters, while the sync-refusal test calls from the event-loop thread and therefore cannot exercise this production shape. **CONFIRMED** from the static wait-for cycle and the public caller chain. Angles C and E independently reported the same root cause. | `_run_initialization_transaction()` submits owner work through `asyncio.to_thread` at lines 94-102. Non-event-loop sync callers wait on the condition at lines 177-186. `list_graphs_async`, `inspect_graph_async`, and `validate_workflow_async` submit their synchronous siblings to the shared default executor at `workflow_ops.py:1182-1223`; those siblings call `ensure_initialized()` at lines 218, 407, and 529. The new bounded-executor test at lines 142-185 queues only `ensure_initialized_async()` callers, and the sync test at lines 188-214 invokes `ensure_initialized()` directly on the loop thread. | Remove the circular executor dependency: use a lifecycle-dedicated execution resource for owner startup, or make synchronous acquisition fail with the typed initialization error whenever another transaction owns the runtime rather than waiting in a shared executor worker. Add deterministic one- and two-worker tests using the public `list_graphs_async`/`inspect_graph_async`/`validate_workflow_async` facade shape concurrently with an async owner; prove termination and the intended terminal runtime state. |

## C. Reuse Opportunities

No DRY finding survived consolidation. A repository search with `rg -n "transaction_condition|_acquire_sync_transaction|ensure_initialized_async|asyncio\\.to_thread\\(" src/agentmap/runtime tests/unit/runtime tests/unit/deployment/http/api` found the existing transaction primitive in `runtime_manager.py` and the three public synchronous-facade wrappers in `workflow_ops.py`; it found no alternate lifecycle executor or existing mixed sync/async bounded-executor regression to reuse.

## D. Standards Crosswalk

| finding id | standards or contract source | section | controlling clause |
|---|---|---|---|
| B102-R8-01 | `dev-artifacts/2026-10-04-b102-dependency-review-rework-8/handoff.md` | Finding disposition, `B102-R7-01`; Defect-class sweep | The repair claims that queued callers add zero default-executor submissions and complete under one- and two-worker bounds. The defect-class sweep requires sync-versus-async ownership coverage. The public mixed-facade path violates the first contract and is absent from the second. |
| B102-R8-01 | `AGENTS.md` | Testing | Service-contract changes require regression coverage. The changed lifecycle coordination contract lacks coverage for the production public caller shape that can still deadlock. |

## E. Tests Review

- The retained focused evidence reports 316 passing tests with no skips or warnings. The retained full suite reports 5,711 passed, 49 skipped, 1 deselected, 5 warnings, and 228 subtests. Those checks do not exercise the surviving mixed sync/async executor cycle.
- Missing boundary case: under a one- and two-worker default executor, let `ensure_initialized_async()` own the transaction, then start enough public async facade calls to fill the pool with their synchronous `ensure_initialized()` path. Assert bounded completion, terminal state, and typed behavior.
- Counterfactual: on the current candidate, every default-executor worker can wait at `_transaction_condition.wait()` while the owner startup is queued behind those workers. The expected test verdict is timeout/deadlock; therefore the claimed starvation repair is incomplete.
- The current `test_bounded_executor_burst_cannot_starve_transaction_owner__b102` is deterministic for all-async waiters, but its caller shape cannot fail for the identified sync-facade cycle.
- No flaky-risk or mock-discipline defect was identified in the changed tests beyond this missing production-shape regression.

## F. Quality Rubric

Scores are 0-5. The verification artifacts are scored for clarity and auditability rather than runtime design.

| file | readability | maintainability | performance | testability | standards | notes |
|---|---:|---:|---:|---:|---:|---|
| `dev-artifacts/2026-10-04-b102-dependency-review-rework-8/handoff.md` | 5 | 4 | 5 | 4 | 4 | Clear dispositions and exact retained evidence, but the starvation claim exceeds the tested caller shapes. |
| `verification/black.log` | 5 | 5 | 5 | 5 | 5 | Small, exact formatter result. |
| `verification/counterfactual-red-summary.log` | 4 | 4 | 5 | 4 | 4 | Records expected-red probes but omits the mixed facade counterfactual. |
| `verification/focused-collect.log` | 5 | 5 | 5 | 5 | 5 | Exact focused inventory. |
| `verification/focused.log` | 5 | 5 | 5 | 5 | 5 | Concise focused result with no hidden skip. |
| `verification/isort.log` | 5 | 5 | 5 | 5 | 5 | Exact import-order result. |
| `verification/lint.log` | 5 | 5 | 5 | 5 | 5 | Exact lint result. |
| `verification/make-test.log` | 4 | 4 | 4 | 5 | 5 | Full result preserves skips, deselection, warnings, and duration. |
| `verification/mypy-normalized-comparison.log` | 4 | 4 | 5 | 4 | 4 | Records inherited non-green state and zero candidate delta. |
| `src/agentmap/deployment/http/api/routes/admin.py` | 5 | 5 | 5 | 5 | 5 | Six initializing routes consistently await the async entrypoint. |
| `src/agentmap/runtime/runtime_manager.py` | 4 | 3 | 2 | 3 | 2 | Ownership is explicit, but shared-executor startup plus blocking sync waiters creates a production deadlock cycle. |
| `tests/fresh_suite/unit/services/test_llm_client_factory.py` | 5 | 5 | 5 | 5 | 5 | Task-owned credential test moved out cleanly. |
| `tests/unit/deployment/http/api/test_b102_admin_async_initialization.py` | 4 | 4 | 5 | 4 | 5 | Covers all admin routes and live-loop contention. |
| `tests/unit/runtime/test_b102_runtime_coordination.py` | 4 | 3 | 4 | 2 | 3 | Strong async coordination cases, but the central executor test omits synchronous facade waiters. |
| `tests/unit/runtime/test_b102_runtime_shutdown.py` | 4 | 4 | 5 | 5 | 5 | Exact outcome assertions follow the richer rollback result. |
| `tests/unit/services/llm/test_b102_credential_cache_identity.py` | 5 | 5 | 5 | 5 | 5 | Focused identity-preservation regression. |
| `tests/unit/services/llm/test_b102_review_size.py` | 4 | 4 | 5 | 4 | 5 | Structural inventory covers both retained unit roots. |

Dimension averages remain above 3 across the 17-file diff; no separate rubric-only finding is added. The low runtime performance and standards scores describe B102-R8-01 itself.

## G. Risk Hotspots

- **Concurrency:** shared bounded default-executor workers can wait for an owner whose startup is queued behind those same workers.
- **I/O and availability:** `list_graphs_async`, `inspect_graph_async`, and `validate_workflow_async` can stop making progress under initialization contention.
- **Architectural defensibility:** condition ownership plus loop futures is a small and defensible replacement for executor-backed async waiting. Keeping blocking synchronous transaction waiters in the same execution resource needed by the async owner is not defensible because it leaves a circular resource dependency in the production caller chain.

## H. Production Caller Chains

- `GET /workflows` -> `list_graphs_async(profile=None, config_file=None)` -> default-executor `list_graphs(...)` -> `ensure_initialized(config_file=None)` -> `RuntimeManager.initialize(...)` -> `_acquire_sync_transaction()` -> condition wait while async owner queues `_install_and_startup(...)` to the same default executor.
- Workflow inspection -> `inspect_graph_async(graph_name, csv_file=None, node=None, config_file=None)` -> default-executor `inspect_graph(...)` -> the same synchronous transaction wait.
- Workflow validation/CLI -> `validate_workflow_async(graph_name, config_file=None)` -> default-executor `validate_workflow(...)` -> the same synchronous transaction wait.

## I. Triage Summary

### Blockers

1. **B102-R8-01:** remove the mixed sync/async shared-executor deadlock and add deterministic one- and two-worker public-facade counterfactuals before QA.

## J. Verdict

**FAIL**

The diff materially improves async waiter coordination, admin wiring, cancellation priority, refresh propagation, and structural test coverage. It still permits synchronous public facade callers to consume every default-executor worker while waiting for an async transaction owner whose startup requires that executor. B102 must return to development for this blocker; the existing green test evidence does not establish the required mixed-caller progress guarantee.
