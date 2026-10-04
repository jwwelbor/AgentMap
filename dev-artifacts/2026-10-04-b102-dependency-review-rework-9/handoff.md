# B102 AgentMap dependency review rework 9 handoff

## Snapshot and outcome

- Pinned clean starting head: `49f486e4e851d6953093153823b59457f57d6472`
- Implementation commit: `6185161897810c54cf9c55e87b3885f28ffd6ae6`
- Scope: AgentMap dependency worktree only; no WWGM, Shark, release, merge, provider, credential, database, or network mutation
- Result: B102-R8-01 is repaired locally across every public `asyncio.to_thread` facade that enters synchronous runtime initialization
- Required disposition: blocked pending a fresh exact-pin review, package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance

## Finding disposition

| Finding | Disposition and proof |
|---|---|
| B102-R8-01 | Async install/startup now runs on one lifecycle-dedicated executor instead of the event loop's shared default executor. Transaction ownership still serializes lifecycle work, ordinary concurrent synchronous initialization still waits and shares one installed container, and `contextvars` propagation preserves the former `asyncio.to_thread` behavior. Deterministic one- and two-worker tests establish the async owner, occupy every default-executor worker with each real public facade, release owner startup, and prove the owner plus every facade terminate successfully in an initialized runtime. |

The pinned review contained one blocker and no non-blockers or nits. No finding was silently deferred.

## Counterfactual and defect-class sweep

Before the production edit, all six combinations of one/two default-executor workers and `list_graphs_async`, `inspect_graph_async`, or `validate_workflow_async` failed deterministically: every facade worker waited for the async transaction while owner startup remained queued behind those same workers. `verification/counterfactual-red.log` retains the six exact failures.

The production sweep found exactly three public `asyncio.to_thread` facade sites in `runtime/workflow_ops.py`, at the list, inspect, and validate entrypoints. The new parameterized test executes all three real facades against offline services at both bounded worker counts. It asserts successful facade results, successful owner completion, and terminal initialized state. The focused set also retains the all-async burst, event-loop synchronous refusal, all six async admin routes and live ASGI contention, refresh, first-start, prerequisite/startup/rollback cancellation and cleanup, credential/cache identity, two-root structural inventory, and the ten-thread ordinary synchronous initialization contract.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Public-facade counterfactual before production edit | Expected RED: 6 failed for list/inspect/validate at 1 and 2 workers | `verification/counterfactual-red.log` |
| All B102-tagged modules plus runtime init/state tests | 324 passed; 0 skipped; 0 warnings | `verification/focused.log`, `verification/focused-collect.log` |
| `make test` at implementation commit | 5,719 passed; 49 skipped; 1 deselected; 5 warnings; 228 subtests passed | `verification/make-test.log` |
| Black check on both task-owned Python files | 2 files unchanged | `verification/black.log` |
| isort check on both task-owned Python files | PASS | `verification/isort.log` |
| `make lint` | PASS across `src/` and `tests/` | `verification/lint.log` |
| Isolated-cache mypy at baseline and candidate | Both 1,638 errors in 248 files and 1,779 diagnostics; normalized added 0, removed 0 | `verification/mypy-normalized-comparison.log` |
| `make type-check` | Non-green inherited TD-052 state: 1,623 errors in 248 files | `verification/mypy-normalized-comparison.log` |
| `git diff --check` and staged evidence check | PASS | performed before each commit |

The 49 full-suite skips and one benchmark deselection remain visible in the full log. The five inherited warnings are unawaited-`AsyncMock` warnings in three `test_suspend_agent_messaging.py` cases, `test_init_command.py::test_init_copies_config_files`, and `test_api_minimal.py::test_execution_endpoint_basic`. The focused run has no skips or warnings.

Mypy remains non-green under TD-052. The only raw diagnostic location change is the inherited missing-return-annotation finding in `runtime_manager.py`, shifted from line 309 to 329 by the inserted method. Normalization strips line and column locations while retaining file, severity, message, and error code; both normalized sets have the same SHA-256 and no semantic delta. Raw transcripts were ephemeral, and their checksums are retained.

## Remaining gates

Run a fresh exact-pin dependency review on the evidence commit. Package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance remain open. No release or host-readiness claim is made by this dependency-only repair.

**RECOMMENDED OUTCOME: blocked because fresh review/release/TD-140/host/product gates remain.**
