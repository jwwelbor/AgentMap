# B102 AgentMap dependency review rework 8 handoff

## Snapshot and outcome

- Pinned clean starting head: `f8a37400a2a56b51a305dad78e7a491027f1a5f5`
- Implementation commit: `4a14ade4a80142f07dbc779919871e36359f6974`
- Scope: AgentMap dependency worktree only; no WWGM, Shark, release, merge, provider, credential, database, or network mutation
- Result: all six B102-R7 blockers are repaired locally and covered by the requested defect-class sweep
- Required disposition: **blocked** pending a fresh exact-pin review, package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance

The inherited HTTP server complexity remains tracked as TD-588 and was not changed. The prior raw mypy transcript remains canonical evidence and was not duplicated.

## Finding disposition

| Finding | Disposition and proof |
|---|---|
| B102-R7-01 | Replaced executor-backed lock acquisition with `RuntimeManager` condition ownership and loop-Future async waiters. Identity tokens guard release. The 1- and 2-worker test queues more callers than workers, proves queued callers add zero executor submissions, and completes every caller. |
| B102-R7-02 | All six initializing async admin handlers await `ensure_initialized_async()`. A synchronous initializer on an active event loop raises typed `AgentMapNotInitialized` when an async transaction owns the runtime. A real ASGI `GET /admin/health` contention test proves the loop remains responsive and the request completes. |
| B102-R7-03 | Rollback now returns the complete `TerminalTaskOutcome`. Cancellation from startup or rollback is selected before ordinary failures, with startup and cleanup failures retained as the cause or a `BaseExceptionGroup`. |
| B102-R7-04 | Runtime replacement and provider-cache refresh use separate flags. `refresh=True` reaches cache validation after an existing runtime is shut down and replaced, including when the replacement cache already reports initialized. |
| B102-R7-05 | Deterministic shutdown-entry/release barriers cover cancellation during prerequisite old-runtime shutdown, both with successful cleanup and with cleanup failure. Both variants prove exact-once shutdown, no replacement install, detached state, and primary cancellation. |
| B102-R7-06 | The documented `tests/unit` structural guard scans and deduplicates B102 modules from both `tests/unit` and `tests/fresh_suite/unit`. Its inventory test requires both roots. The one B102 credential-identity test in the inherited oversized legacy module moved to a focused 31-line `tests/unit` module without changing its behavior. |

There were no non-blockers or nits in the pinned review. No finding was silently deferred.

## Defect-class sweep

The focused set covers bounded default executors with one and two workers; more waiters than workers; sync-versus-async transaction ownership; every async admin initializer and an actual HTTP route under contention; first start and refresh; cancellation while waiting for the transaction, during prerequisite shutdown, during post-install startup, and during rollback; successful and failing cleanup; an already initialized replacement provider cache; and structural enforcement across both retained test roots. All tests use offline fakes and deterministic events.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Counterfactual probes before production edits | Expected RED for refresh propagation, rollback cancellation priority, admin async wiring, and two-root inventory; prerequisite cancellation probes already passed | `verification/counterfactual-red-summary.log` |
| All B102-tagged modules plus runtime init/state tests | 316 passed; 0 skipped; 0 warnings | `verification/focused.log`, `verification/focused-collect.log` |
| `make test` at implementation commit | 5,711 passed; 49 skipped; 1 deselected; 5 warnings; 228 subtests passed | `verification/make-test.log` |
| isort check on eight task-owned Python files | PASS | `verification/isort.log` |
| Black check on eight task-owned Python files | 8 files unchanged | `verification/black.log` |
| `make lint` | PASS across `src/` and `tests/` | `verification/lint.log` |
| `make type-check` | Non-green inherited TD-052 state: cached run reported 1,623 errors in 248 files | `verification/mypy-normalized-comparison.log` |
| Isolated-cache mypy at baseline and candidate | Both 1,638 errors in 248 files; both 1,779 normalized diagnostics; added 0, removed 0 | `verification/mypy-normalized-comparison.log` |
| `git diff --check` / staged evidence check | PASS | recorded before each commit |

The 49 full-suite skips and one deselection are reported by pytest and remain visible in the retained full log. The five warnings are all unawaited-`AsyncMock` warnings in unrelated retained tests: three `test_suspend_agent_messaging.py` cases (`graph_message_raises_when_service_not_configured`, `resume_message_includes_duration`, and `returns_none_when_resume_value_is_none`), `test_init_command.py::test_init_copies_config_files`, and `test_api_minimal.py::test_execution_endpoint_basic`. The warning count varied between full-suite runs because the inherited warnings are nondeterministic; the table reports the final exact-commit run.

TD-052 remains non-green. The isolated-cache comparison controls incremental cache drift and shows no diagnostic delta from exact baseline `f8a3740`. This increment retains only checksums and the normalized comparison, and references the prior canonical raw transcript at SHA-256 `ceaf54afb4c67c3358e4508d412852eddeba776608b7ed7ef74f2047bce52f63`.

## Remaining gates

Run a fresh exact-pin dependency review on the evidence commit. Package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance remain open. No release or host-readiness claim is made by this dependency-only repair.

**RECOMMENDED OUTCOME: blocked**
