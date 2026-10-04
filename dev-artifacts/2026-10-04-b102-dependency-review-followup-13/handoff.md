# B102 AgentMap dependency review follow-up 13 handoff

## Snapshot and outcome

- Pinned clean starting head: `802676098d1a573c188a452b918ed684fe07ccde`
- Test implementation commit: `de9ed08268d72c001d7bf401b9a9c5b81853906a`
- Scope: one B102 runtime test and this evidence; production source is unchanged
- Result: B102-R12-01 through B102-R12-03 are fixed locally

## Finding disposition

| Finding | Disposition and proof |
|---|---|
| B102-R12-01 | Fixed now. A bounded 10 ms timeout uses `install_owner_gate()` and a real `ensure_initialized_async()` task while that task owns the runtime transaction. The controlled timeout seam skips lifecycle dispatch only after the timeout, then the guard opens the owner gate and terminally reaps the owner. The test asserts the exact timeout remains primary with no cause, the owner succeeds, and the owner's own `finally` clears transaction ownership. A precise mutation that steals the live owner's token produces the retained RED: the timeout remains outer primary while the resulting owner-mismatch failure becomes its cleanup cause. |
| B102-R12-02 | Fixed now. The cancellation/timeout route test asserts the exact exception payload: `offline caller cancellation` for cancellation and `public facades starved the runtime lifecycle` for timeout. Both routes also retain their no-cause and terminal cleanup assertions. |
| B102-R12-03 | Fixed now. The retained isort log records the exact command, `result: PASS`, and `exit-code: 0` from the pinned test commit. |

No finding was deferred, and no production source changed.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Live-owner token theft mutation | Expected RED; exact timeout remained outer primary and `Runtime transaction owner mismatch` appeared as its cleanup cause | `verification/live-owner-token-counterfactual-red.log` |
| Changed B102 runtime module | 13 passed; 0 skipped; 0 warnings | `verification/changed-module.log` |
| B102-tagged modules plus runtime init/state tests | 331 passed; 0 skipped; 0 warnings | `verification/focused.log`, `verification/focused-collect.log` |
| Black | PASS; one file unchanged | `verification/black.log` |
| isort | PASS; exit code 0 explicitly retained | `verification/isort.log` |
| Repository lint | PASS | `verification/lint.log` |
| Full `make test` at the test implementation commit | 5,726 passed; 49 skipped; 1 deselected; 6 warnings; 228 subtests passed | `verification/make-test.log` |
| Production-source diff from pinned starting head | Empty using `git diff BASE..TEST -- src/agentmap` | `verification/production-source-diff.log` |
| `git diff --check` from pinned starting head | PASS | `verification/git-diff-check.log` |

The full-suite skips and benchmark deselection remain visible in the retained log. The six warnings are inherited from unchanged suspend-agent messaging, minimal API, and auth-root tests; all are unawaited-`AsyncMock` warnings outside the changed test. The focused and changed-module runs have no skips or warnings. The changed module remains exactly 350 lines and the structural review-size test passes. Mypy was not run because production source did not change and tests are excluded by the repository's mypy configuration.

## Remaining gates

Run a fresh exact-pin dependency review on the evidence commit. Package release, TD-140, WWGM host integration, restart reconciliation, terminal/process-death acceptance, and product acceptance remain open. No release or host-readiness claim is made by this test-only repair.

**RECOMMENDED OUTCOME: blocked pending final review/release/TD-140/host/product gates.**
