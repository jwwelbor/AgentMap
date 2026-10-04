# B102 AgentMap dependency review rework 7

Date: 2026-10-04. Branch: `fix/wwgm-b102-physical-attempts`.
Implementation commit: `e31df8b0a5fa43b504415174aeb1bc8686eb9849`.
Review input: WWGM `dev-artifacts/2026-10-04-0305-b102-dependency-review-d308bc5/REVIEW.md`, pinned AgentMap head `d308bc5363842e67e850b1792a1095ec38f114c2`.
Ownership contract: WWGM `docs/plan/decisions/DB-2026-10-04-b102-observed-client-lifecycle.md`.

## Finding disposition

All B102-R6 fix-now findings are repaired in the dependency worktree. The inherited HTTP server complexity remains TD-588 and was not changed. The prior raw mypy transcript remains canonical evidence and was not duplicated.

| Finding | Repair and counterfactual evidence |
| --- | --- |
| B102-R6-01 concurrent runtime ownership | `RuntimeManager` now serializes the complete async initialize, refresh, cache validation, rollback, and detach transaction. Rollback detaches only the candidate identity installed by that transaction. Deterministic first-start failure versus peer success and concurrent refresh tests prove that one caller cannot detach another caller's installed runtime. |
| B102-R6-02 typed public failure | Startup failure stays top-level `AgentMapNotInitialized`; rollback failure is retained as its cause. A real FastAPI exception-handler request proves the double-failure path still returns HTTP 503 with type `AgentMapNotInitialized`. |
| B102-R6-03 complete sync cleanup | Synchronous `CancelledError` and `BaseExceptionGroup` join ordinary sync failures in the shared aggregate. Later sync and async resources still close, ownership clears once, and repeated close does not retry. |
| B102-R6-04 cancelled startup | Deterministic barriers cover cancellation before installation completes, after runtime installation, and during rollback failure. Original cancellation stays primary, task or rollback failure remains inspectable as its cause, shutdown is exact-once, and runtime state is detached. |
| B102-R6-05 cancellation origin | The terminal waiter records the caller's cancellation-count baseline for each wait and classifies only a later increment as caller cancellation. A handled earlier cancellation no longer relabels independent child cancellation. |
| B102-R6-06 neutral lifecycle seam | `terminal_task.py` moved from the LLM package to neutral `agentmap.async_lifecycle`; runtime, observed-resource, and factory owners share it while retaining owner-specific aggregate messages. |
| B102-R6-09 deterministic ordering | Repeated cancellation now waits for observed delivery of each cancellation. Shutdown-wins coverage waits for `_finish_shutdown` entry. The former `call_soon` and `sleep(0)` lifecycle assumptions are gone. |
| B102-R6-10 documented test layout | The structural guard moved from `tests/fresh_suite/unit` to `tests/unit` and recursively discovers B102-owned modules under the documented unit root. |
| B102-R6-11 redundant tuple | The terminal waiter no longer repeats `CancelledError` after its exhaustive dedicated branch. |
| B102-R6-07 inherited server size | No action in this dependency repair; WWGM TD-588 owns the unchanged HTTP server and route-registration complexity. |
| B102-R6-08 raw mypy transcript | No action on the retained rework-6 raw transcript. Its canonical SHA-256 is `ceaf54afb4c67c3358e4508d412852eddeba776608b7ed7ef74f2047bce52f63`; this increment retains only checksums and the normalized comparison. |

## Test-first repair and defect-class sweep

The initial counterfactual run failed at the intended boundaries: double failure surfaced an `ExceptionGroup`; the HTTP handler did not map it to 503; a lingering caller cancellation count contaminated child cancellation; and synchronous cancellation skipped later resources. Those same probes pass after the repair.

The sweep covered concurrent first start and refresh, cancellation while waiting for transaction ownership, cancellation before and after installation, startup failure with rollback success and failure, identity-scoped detach, caller-loop refresh cleanup, sync and async cancellation/group positions, lingering and repeated caller cancellation, every shared terminal-waiter consumer, shutdown during unpublished construction, and all remaining lifecycle ordering tests. Tests use deterministic events, offline fakes, and fake HTTP only.

No provider construction, response observation, retry, usage, cost, credential, proxy, or public cleanup-marker behavior changed. No provider or network call, credential use, database operation, package publication, merge, WWGM edit, or Shark command occurred.

## Verification

Exact logs are under `verification/`.

| Command | Result | Log |
| --- | --- | --- |
| Every `__b102` test file plus `test_init_ops.py` and `test_runtime_state.py` | 298 passed, 1 inherited TD-025a history-guard skip | `focused.log`, `focused-collect.log` |
| `uv run black --check src tests` | Pass: 791 files unchanged | `black.log` |
| `uv run isort --check-only --sp pyproject.toml src tests` | Pass | `isort.log` |
| `make lint` | Pass | `lint.log` |
| `make test` | Pass: 5,665 passed, 49 skipped, 1 deselected, 4 warnings, 228 subtests passed | `make-test.log` |
| `make type-check` | Non-green inherited TD-052 state: 1,637 cached-run errors in 248 files | summarized below |
| Isolated-cache mypy at baseline and candidate | Both: 1,638 errors in 248 files; 1,779 error/note diagnostics; normalized added 0, removed 0 | `mypy-normalized-comparison.log` |

The full-suite total is 14 lower than rework 6 because moving the structural guard to the documented root removed 24 duplicate size-check parametrizations over legacy `fresh_suite` modules while this repair added 10 behavioral counterfactuals. No behavioral test was deleted. The focused skip is the pre-existing TD-025a diff-scope guard for unavailable commit `68e1141`.

The four full-suite warnings are inherited unawaited-`AsyncMock` warnings in three suspend-agent tests and one minimal-API integration test. The type-check remains non-green under TD-052. To control incremental-cache drift, the candidate and exact `d308bc5` baseline were also run through the same interpreter with independent empty mypy caches: both produced 1,638 errors in 248 files and identical normalized diagnostics. The new evidence references the retained canonical raw transcript by checksum rather than adding another raw log.

## Parent control handoff

This is dependency-local repair, not B102 acceptance. Keep B102 in development. Remaining gates are fresh exact-pin review, AgentMap package release, TD-140 ledger/payload durability, WWGM host integration and restart reconciliation, terminal/process-death counterfactuals, then WWGM review, QA, CI, release, and product acceptance. The parent loop owns the Shark lease and every workflow transition.

RECOMMENDED OUTCOME: blocked
