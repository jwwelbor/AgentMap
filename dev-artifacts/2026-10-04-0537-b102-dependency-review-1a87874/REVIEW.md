# B102 dependency review

| Metadata | Value |
|---|---|
| Entity | `B102` |
| Base commit | `8b12f714f041d6162dfb40eb1b8851291a5dfe26` |
| Head commit | `1a87874f22b6842dfe3ec0bd170ad1ac6dfaa1dc` |
| Diff path | `candidate.diff` |
| Candidate SHA-256 | `604055ea43a4c806eb160b54a33f5855905978a3370989408ef7baea9a625d7c` |
| Runner mode | `dispatched-six-angle` |
| Specialists completed | `6` |
| Consolidator completed | `true` |
| Adversarial review | `none` |
| Fallback reason | `native Workflow unavailable` |
| Scope | 12 changed files; every specialist reported the exact 12/12 manifest; no missing or extra files |

## A. Executive Summary

This test-and-evidence diff strengthens B102's dedicated-lifecycle-executor proof with exact-identity `ContextVar` counterfactuals and ordered one/two-worker public-facade regressions. Production source is unchanged. The intended coverage is valuable, but the ordered-startup helper does not release and reap its gated tasks when an assertion fails before `release.set()`. That is the exact regression path the test exists to expose, so a failure can leak blocked tasks and hang teardown instead of terminating with a bounded diagnostic.

- Overall risk: **medium**. The surviving blocker is confined to test cleanup, but it can turn a valid regression signal into an unbounded suite failure.
- Verdict: **FAIL**
- Counts: **1 blocker / 2 non-blockers / 0 nits**
- Scope sanity: 465 additions and 25 deletions across one B102 regression module plus handoff and retained verification evidence. No unrelated production change was identified.
- Coverage: six dispatched specialists each reported the exact 12/12 changed-file manifest. The pinned candidate diff reproduced the recorded SHA-256.
- Checks performed: six dispatched angles plus this consolidation; static inspection of the ordered-startup failure paths, lifecycle context assertions, retained RED transcripts, focused/full-suite logs, and the production-source proof command.

Angles A and C reported the same malformed evidence-command defect; it appears once below as B102-R10-02.

## B. Findings Table

| id | severity | file:line | rule | diagnosis | evidence | correction |
|---|---|---|---|---|---|---|
| B102-R10-01 | Blocker | `tests/unit/runtime/test_b102_public_facade_starvation.py:203` | `IDIOM` | The ordered-startup counterfactual releases and gathers its gated tasks only after its pre-release assertions succeed. If the behavior regresses and lifecycle startup occurs early, the assertion at line 206 raises before `release.set()`. `complete_before_deadlock_guard()` handles only `TimeoutError`, so the assertion escapes while the transaction owner remains gated and facade tasks can remain blocked. The test may then hang executor or event-loop teardown instead of producing a bounded deterministic failure. **CONFIRMED.** | `exercise_ordered_startup()` asserts `not lifecycle_started.is_set()` before `release.set()` at lines 203-209. `complete_before_deadlock_guard()` catches only `TimeoutError` at lines 157-167. The existing recovery pattern in `tests/unit/runtime/test_b102_runtime_coordination.py:175-182` releases the gate and gathers tasks before reraising. | Put release and task reaping in an unconditional `finally`/`BaseException` cleanup path that covers assertion failure, cancellation, and timeout. Preserve the special timeout diagnostic, but always release the transaction gate and gather or cancel the owner, facade, and completion tasks before propagating the primary failure. Add or retain a counterfactual that makes lifecycle startup occur before release and proves bounded cleanup. |
| B102-R10-02 | Non-blocker | `dev-artifacts/2026-10-04-b102-dependency-review-followup-10/verification/production-source-diff.log:1` | `CONTRACT` | The retained command places both revisions after `--`, where Git interprets them as pathspecs. Its empty output therefore does not prove the pinned no-production-source-change claim consumed by the handoff. A correctly ordered independent comparison confirms the underlying claim is true. **CONFIRMED; deduplicated from angles A and C.** | The log records `git diff -- src/agentmap 8b12f714f041d6162dfb40eb1b8851291a5dfe26..529393acb6facf2482184ef4b22e22bbadd9f995`. The required form is `git diff 8b12f714f041d6162dfb40eb1b8851291a5dfe26..529393acb6facf2482184ef4b22e22bbadd9f995 -- src/agentmap`, which independently returns empty output. | Regenerate the retained log with the revision range before `--`, preserve the corrected command and empty result, and keep the handoff reference to that corrected proof. |
| B102-R10-03 | Non-blocker | `tests/unit/runtime/test_b102_public_facade_starvation.py:107` | `TESTS` | The new regressions establish `ContextVar` propagation and freedom from shared-executor starvation, but they do not establish that blocking lifecycle callbacks execute off the event-loop thread. Replacing executor submission with a direct `context.run(_install_and_startup, ...)` call on the loop thread would preserve the observed context identities, satisfy the startup-order assertions, and leave the changed tests green while reintroducing event-loop blocking. **CONFIRMED.** | The callbacks at lines 116-126 record only `ContextVar` values. `observed_initialize_di()` at lines 185-187 records only that startup began. No assertion compares callback thread identity with the calling event-loop thread. | Record the event-loop thread identity before initialization and assert that DI installation and cache startup/refresh execute on a different thread, alongside the existing exact-identity context assertions. Retain a RED counterfactual that runs lifecycle work directly on the event-loop thread. |

## C. Reuse Opportunities

No DRY finding survived consolidation. B102-R10-01 should reuse the repository's existing release-and-gather failure cleanup pattern in `tests/unit/runtime/test_b102_runtime_coordination.py:175-182`. B102-R10-03 can extend the existing callback observations in the changed test rather than introducing another test harness.

## D. Standards Crosswalk

| finding id | contract source | section | controlling clause |
|---|---|---|---|
| B102-R10-01 | `dev-artifacts/2026-10-04-b102-dependency-review-followup-10/handoff.md` | Finding disposition, B102-R9-02 | The test claims deterministic ordering with one generous outer guard. A pre-release assertion failure must still terminate and clean up all deliberately blocked work. |
| B102-R10-02 | `dev-artifacts/2026-10-04-b102-dependency-review-followup-10/handoff.md` | Verification, Production-source diff | The handoff consumes the retained log as proof of an empty pinned source diff; the producer command must actually compare those revisions. |
| B102-R10-03 | `dev-artifacts/2026-10-04-b102-dependency-review-followup-10/handoff.md` | Finding disposition, B102-R9-01 | The lifecycle contract is a dedicated executor that preserves caller context. The test proves context preservation but not execution off the event-loop thread. |

## E. Tests Review

- Retained focused evidence reports 325 passed with no skips or warnings. The retained full suite reports 5,720 passed, 49 skipped, 1 deselected, 5 inherited warnings, and 228 subtests.
- The exact-identity `ContextVar` regression has two retained expected-RED mutations: removing context copying and bypassing `context.run`.
- All six list/inspect/validate and one/two-worker combinations remain parameterized and use explicit ordering events rather than millisecond polling.
- Missing cleanup counterfactual: force `lifecycle_started` before the release assertion and prove that every owner/facade/completion task is released and reaped while the assertion remains primary.
- Missing execution-boundary counterfactual: invoke blocking lifecycle work directly on the loop thread and prove the test fails on thread identity even though context identity remains correct.
- The malformed production-source command weakens retained evidence only; a correctly ordered comparison confirms no production source changed.

## F. Quality Rubric

Scores are 0-5. Evidence files are scored for auditability rather than runtime design.

| file | readability | maintainability | performance | testability | standards | notes |
|---|---:|---:|---:|---:|---:|---|
| `dev-artifacts/2026-10-04-b102-dependency-review-followup-10/handoff.md` | 5 | 5 | 5 | 4 | 4 | Clear disposition and results; its no-source-change proof points to a malformed command. |
| `verification/black.log` | 5 | 5 | 5 | 5 | 5 | Exact formatter result. |
| `verification/context-copy-counterfactual-red.log` | 5 | 5 | 5 | 5 | 5 | Retains the expected failure when context copying is removed. |
| `verification/context-run-counterfactual-red.log` | 5 | 5 | 5 | 5 | 5 | Retains the expected failure when `context.run` is bypassed. |
| `verification/focused-collect.log` | 5 | 5 | 5 | 5 | 5 | Exact focused inventory. |
| `verification/focused.log` | 5 | 5 | 5 | 5 | 5 | Concise green result without skips or warnings. |
| `verification/git-diff-check.log` | 5 | 5 | 5 | 5 | 5 | Exact whitespace check. |
| `verification/isort.log` | 5 | 5 | 5 | 5 | 5 | Exact import-order result. |
| `verification/lint.log` | 5 | 5 | 5 | 5 | 5 | Exact lint result. |
| `verification/make-test.log` | 4 | 4 | 4 | 5 | 5 | Preserves suite counts, skips, deselection, warnings, and subtests. |
| `verification/production-source-diff.log` | 4 | 3 | 5 | 2 | 2 | Human-readable claim, but the command does not perform the claimed comparison. |
| `tests/unit/runtime/test_b102_public_facade_starvation.py` | 4 | 3 | 4 | 2 | 3 | Strong context and starvation cases; exceptional cleanup is incomplete and the executor boundary is not asserted. |

The testability score of 2 for the changed test corresponds to B102-R10-01 and B102-R10-03. The evidence standards score of 2 corresponds to B102-R10-02; no additional rubric-only finding is added.

## G. Risk Hotspots

- **Exceptional test cleanup:** the deliberate transaction gate and occupied executor workers require total cleanup on every exit path.
- **Execution boundary:** exact `ContextVar` identity does not by itself prove blocking callbacks remain off the event loop.
- **Evidence lineage:** retained commands must execute the pinned comparison their consumers claim.
- **Production behavior:** no production source changed in this candidate, and independent inspection found no new runtime defect in scope.

## H. Production Caller Chains

- `ensure_initialized_async()` -> lifecycle transaction -> caller context copied -> blocking install/startup submitted to the dedicated lifecycle executor. The changed context test observes exact identity at DI installation, startup readiness, and refresh.
- `list_graphs_async()` / `inspect_graph_async()` / `validate_workflow_async()` -> default-executor synchronous facade -> transaction wait while async owner startup proceeds on the dedicated lifecycle executor. The changed parameterized test covers each facade with one and two default-executor workers.
- Review 10 changes only the tests and evidence for these chains; the production implementation remains the previously reviewed B102 runtime code.

## I. Triage Summary

### Blocker

1. **B102-R10-01:** make deliberately gated task cleanup unconditional for assertion, cancellation, and timeout exits before rerunning review.

### Non-blockers to triage

1. **B102-R10-02:** regenerate the malformed production-source proof command. Recommended disposition: fix now in the task-owned evidence.
2. **B102-R10-03:** assert lifecycle callback thread identity and retain the direct-loop counterfactual. Recommended disposition: fix now in the changed regression module.

## J. Verdict

**FAIL**

The diff closes the previous context-propagation and scheduler-sensitive synchronization gaps, but its principal ordered-startup regression can leak deliberately blocked work on the assertion path that represents the target defect. B102 must return to development for B102-R10-01. The two small changed-surface non-blockers should be corrected in the same pass before another exact-pin review.
