# B102 dependency final review 13

## Executive summary

This test-only diff adds a real runtime-owner timeout counterfactual, restores
exact cancellation and timeout diagnostics, and records complete validation
evidence. Production source is unchanged.

- Verdict: **PASS-with-triage**
- Counts: **0 blockers / 2 non-blockers / 0 nits**
- `runner_mode`: `dispatched-six-angle`
- `specialists_completed`: `6`
- `consolidator_completed`: `true`
- `adversarial_model`: `none`
- `fallback_reason`: `native Workflow unavailable`
- `base_commit`: `802676098d1a573c188a452b918ed684fe07ccde`
- `implementation_commit`: `de9ed08268d72c001d7bf401b9a9c5b81853906a`
- `evidence_commit`: `a05d7dce04f77a826c6d0cdf6510271584732a8f`
- `diff_sha256`: `d420e3c42ad6d857da5c3ad010cd21c38373cac3a0595db71bd9af5311aa69a8`
- Scope: 14 files, 290 insertions, 43 deletions; all task-owned tests or evidence
- Coverage: every specialist reported the exact 14/14 changed-file manifest

The controlled private lifecycle seam is architecturally defensible for
transaction-ordering regression coverage and does not establish a parallel
production path. The implementation is appropriately narrow, although its
acquisition wait and cancellation-route negative proof need strengthening.

## Findings

| ID | Severity | Location | Diagnosis | Required correction |
|---|---|---|---|---|
| B102-R13-01 | Non-blocker | `tests/unit/runtime/test_b102_public_facade_starvation.py:284` | Both real-owner regressions wait for gate acquisition before entering cleanup. A regression can hang the suite, and cancellation there can leak transaction ownership. | Enter cleanup immediately after creating the owner, bound acquisition with `asyncio.wait_for`, and always open both gates and terminally reap the owner in `finally`. |
| B102-R13-02 | Non-blocker | `tests/unit/runtime/test_b102_public_facade_starvation.py:247` | The cancellation route does not prove that the timeout-only callback remains inactive, so an always-call mutation survives. | Assert `timeout_cleanup.is_set() is (route == "timeout")`, or add the equivalent explicit cancellation proof. |

Angles A and E independently reported the unbounded-acquisition root cause.

## Test review

- The new live-owner test uses a real `ensure_initialized_async()` owner, a
  short timeout, successful owner termination, exact timeout diagnostics, no
  cleanup cause, and owner-controlled token release.
- The token-theft mutation is a valid counterfactual: stealing the token makes
  the owner's `finally` raise `Runtime transaction owner mismatch`, retained as
  the timeout cleanup cause.
- Exact cancellation and timeout exception payloads are asserted.
- Gate acquisition itself is unbounded and begins before cleanup protection.
- Cancellation lacks the negative proof for timeout-only cleanup.
- No random data, network access, wall-clock comparison, or sleep-based
  readiness was added.
- Retained validation reports 13 changed-module cases and 331 focused cases
  passing without skips or warnings. Full `make test` reports 5,726 passed, 49
  skipped, 1 deselected, 6 inherited warnings, and 228 subtests.

## Risk hotspots

- Gate acquisition can hang before cleanup and can leak the real owner on
  cancellation.
- The cancellation route does not prove that timeout-only cleanup is inactive.
- Private runtime transaction state is inspected only in this narrow regression
  test because no public ownership-introspection API exists.
- The pinned diff contains no production change under `src/agentmap`.

## Verdict

**PASS-with-triage.** The candidate is production-safe and its live-owner token
counterfactual is meaningful. The two test-design findings are safe, local
fix-now work before the final release gate.
