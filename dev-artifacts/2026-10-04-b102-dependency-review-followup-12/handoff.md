# B102 AgentMap dependency review follow-up 12 handoff

## Snapshot and outcome

- Pinned clean starting head: `098d540a14ce4f28743729e670a8af574338343f`
- Test implementation commit: `9852f657b1c17068a6d4e7313b04617d82878d40`
- Scope: one B102 runtime test and this evidence; production source is unchanged
- Result: B102-R11-01 through B102-R11-04 are fixed locally

## Finding disposition

| Finding | Disposition and proof |
|---|---|
| B102-R11-01 | Fixed now. The cancellation/timeout regression owns an independent `finally` boundary that always opens the gate, cancels a pending guard, and terminally gathers owner, facade, completion, and guard tasks. Cleanup outcomes use `return_exceptions=True`, so cleanup cannot replace the primary assertion, and the green path asserts every outcome. A precise mutation that omitted the helper's release failed within the outer bound and the test fallback reaped the work. |
| B102-R11-02 | Fixed now. Timeout cleanup no longer reads or releases `RuntimeManager._transaction_owner`. A controlled gate seam skips lifecycle dispatch only after timeout, allowing `initialize_async()` to return through its own `finally` and release its token. Unexpected task failures are attached to the primary as a `BaseExceptionGroup`; the regression asserts the primary has no cause and all gathered task outcomes match expectations. Omitting the seam produced the retained RED with the secondary failure visible. |
| B102-R11-03 | Fixed now. The guard sets an explicit entry event immediately before its completion wait. The cancellation route awaits that acknowledgement before cancelling; `asyncio.sleep(0)` is gone. |
| B102-R11-04 | Fixed now. The guard accepts a keyword-only `timeout` with the 10-second production-test default, while the timeout regression passes `timeout=0.01` directly. No `__globals__` mutation remains. |

No finding was deferred, and no production source changed.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Independent cleanup mutation | Expected RED; bounded failure when the helper omitted `release.set()` | `verification/independent-cleanup-counterfactual-red.log` |
| Controlled owner-seam mutation | Expected RED; timeout stayed primary and the secondary cleanup failure remained visible as its cause | `verification/owner-seam-counterfactual-red.log` |
| Changed B102 runtime module | 12 passed; 0 skipped; 0 warnings | `verification/changed-module.log` |
| B102-tagged modules plus runtime init/state tests | 330 passed; 0 skipped; 0 warnings | `verification/focused.log`, `verification/focused-collect.log` |
| Black | PASS; one file unchanged | `verification/black.log` |
| isort | PASS | `verification/isort.log` |
| Repository lint | PASS | `verification/lint.log` |
| Full `make test` at the test implementation commit | 5,725 passed; 49 skipped; 1 deselected; 6 warnings; 228 subtests passed | `verification/make-test.log` |
| Production-source diff from pinned starting head | Empty using `git diff BASE..TEST -- src/agentmap` | `verification/production-source-diff.log` |
| `git diff --check` from pinned starting head | PASS | `verification/git-diff-check.log` |

The full-suite skips and benchmark deselection remain visible in the retained log. The six warnings are inherited from unchanged suspend-agent messaging, minimal API, and auth-root tests; all are unawaited-`AsyncMock` warnings outside the changed test. The focused and changed-module runs have no skips or warnings. Mypy was not run because production source did not change and tests are excluded by the repository's mypy configuration.

## Remaining gates

Run a fresh exact-pin dependency review on the evidence commit. Package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance remain open. No release or host-readiness claim is made by this test-only repair.

**RECOMMENDED OUTCOME: blocked pending final review/release/TD-140/host/product gates.**
