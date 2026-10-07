# B102 AgentMap dependency review follow-up 11 handoff

## Snapshot and outcome

- Pinned clean starting head: `7938579e30f71c9c207693845d18c52df7a27649`
- Test implementation commit: `2c253384f74e066c1086a79614fa2ddfb600c935`
- Scope: one AgentMap B102 runtime test plus this evidence; production source is unchanged
- Result: B102-R10-01 through B102-R10-03 are fixed locally

## Finding disposition

| Finding | Disposition and proof |
|---|---|
| B102-R10-01 | Fixed now. The ordered-startup guard catches `BaseException`, unconditionally opens the transaction gate, and waits through caller cancellation until the owner, every facade, and the completion task reach a terminal state. Assertion, ordinary exception, custom `BaseException`, caller cancellation, and timeout paths preserve the primary failure. The early-lifecycle counterfactual first failed 3/3 before this cleanup was added; the final parameterized regressions are green and bounded. |
| B102-R10-02 | Fixed now. `verification/production-source-diff.log` records and executes `git diff 7938579e30f71c9c207693845d18c52df7a27649..2c253384f74e066c1086a79614fa2ddfb600c935 -- src/agentmap`; its result is empty. |
| B102-R10-03 | Fixed now. The context regression records the event-loop thread and the thread used by DI initialization, cache startup, and cache refresh. All three callbacks preserve the caller's exact `ContextVar` identity and run on a different lifecycle thread. A direct-loop source mutation retains context identity but fails the new thread assertion; the expected RED transcript is retained and the mutation was reverted. |

No finding was deferred, and no production source changed.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Early-lifecycle cleanup counterfactual before repair | Expected RED: 3/3 assertion, exception, and `BaseException` cases failed because the gate remained closed | `verification/cleanup-counterfactual-red.log` |
| Direct-loop lifecycle mutation | Expected RED: callback thread assertion failed while exact context identity remained green | `verification/direct-loop-counterfactual-red.log` |
| Changed B102 runtime module | 12 passed; 0 skipped; 0 warnings | `verification/changed-module.log` |
| B102-tagged modules plus runtime init/state tests | 330 passed; 0 skipped; 0 warnings | `verification/focused.log`, `verification/focused-collect.log`, `verification/focused-command.log` |
| Black | PASS; one file unchanged | `verification/black.log` |
| isort | PASS | `verification/isort.log` |
| Repository lint | PASS | `verification/lint.log` |
| Full `make test` at the test implementation commit | 5,725 passed; 49 skipped; 1 deselected; 6 warnings; 228 subtests passed | `verification/make-test.log` |
| Production-source diff from pinned starting head | Empty using the revision range before `--` | `verification/production-source-diff.log` |
| `git diff --check` from pinned starting head | PASS | `verification/git-diff-check.log` |

The full-suite skips and benchmark deselection remain visible in the retained log. The six warnings are inherited from unchanged suspend-agent messaging, minimal API, and auth-root tests; all are unawaited-`AsyncMock` warnings outside the changed test. The focused run has no skips or warnings. Mypy was not run because production source did not change and tests are excluded by the repository's mypy configuration.

## Remaining gates

Run a fresh exact-pin dependency review on the evidence commit. Package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance remain open. No release or host-readiness claim is made by this test-only repair.

**RECOMMENDED OUTCOME: blocked pending final review/release/TD-140/host/product gates.**
