# B102 AgentMap dependency review follow-up 10 handoff

## Snapshot and outcome

- Pinned clean starting head: `8b12f714f041d6162dfb40eb1b8851291a5dfe26`
- Test implementation commit: `529393acb6facf2482184ef4b22e22bbadd9f995`
- Scope: one AgentMap B102 runtime test plus this evidence; production source is unchanged
- Result: B102-R9-01 and B102-R9-02 are fixed locally without changing runtime behavior

## Finding disposition

| Finding | Disposition and proof |
|---|---|
| B102-R9-01 | Fixed now. A caller-task `ContextVar` sentinel is observed by exact identity during DI installation, the startup cache probe, and cache refresh on the lifecycle executor. Replacing `copy_context()` with a fresh context fails, and bypassing `context.run` fails; both RED transcripts are retained. |
| B102-R9-02 | Fixed now. Default-executor workers notify an `asyncio.Event` with `loop.call_soon_threadsafe`; the test explicitly orders async transaction ownership, occupancy of every one/two-worker executor slot by each list/inspect/validate facade, lifecycle release, and lifecycle execution. Millisecond polling and the one-second starvation inference are gone. One ten-second outer guard exists only to recover and report the deliberately deadlocked counterfactual. |

All six public-facade combinations remain parameterized: list, inspect, and validate with one and two shared-executor workers. No finding was deferred.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Fresh-context mutation | Expected RED: direct ContextVar test failed | `verification/context-copy-counterfactual-red.log` |
| Bypassed-`context.run` mutation | Expected RED: direct ContextVar test failed | `verification/context-run-counterfactual-red.log` |
| B102-tagged modules plus runtime init/state tests | 325 passed; 0 skipped; 0 warnings | `verification/focused.log`, `verification/focused-collect.log` |
| Black | 1 file unchanged | `verification/black.log` |
| isort | PASS | `verification/isort.log` |
| Repository lint | PASS | `verification/lint.log` |
| `make test` at the test implementation commit | 5,720 passed; 49 skipped; 1 deselected; 5 warnings; 228 subtests passed | `verification/make-test.log` |
| Production-source diff from pinned head | Empty; only the B102 test changed before this evidence commit | `verification/production-source-diff.log` |
| `git diff --check` | PASS | `verification/git-diff-check.log` |

The first focused command used Bash-only `mapfile` under zsh, so it expanded to a broader run. That run exited successfully but did not retain a final count and is not used as evidence. The zsh-safe exact inventory was rerun and is the 325-pass result above.

The 49 full-suite skips and one benchmark deselection remain visible in the full log. The five inherited unawaited-`AsyncMock` warnings occurred in three `test_suspend_agent_messaging.py` cases, `test_init_command.py::test_init_copies_config_files`, and `test_api_minimal.py::test_execution_endpoint_basic`. The focused run has no skips or warnings. Mypy comparison was not run because production source did not change and tests are excluded by the repository's mypy configuration.

## Remaining gates

Run a fresh exact-pin dependency review on the evidence commit. Package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance remain open. No release or host-readiness claim is made by this test-only repair.

**RECOMMENDED OUTCOME: blocked pending fresh review/release/TD-140/host/product gates.**
