# B102 dependency review

| Metadata | Value |
|---|---|
| Entity | `B102` |
| Base commit | `49f486e4e851d6953093153823b59457f57d6472` |
| Head commit | `56b0efabc0340e1c5dcb95b98062d23ad8fe4bc6` |
| Diff path | `candidate.diff` |
| Candidate SHA-256 | `9e7d234655d5e57fe0055657abcaa6531be3734da20e4e93eef0d8b38b2aa648` |
| Runner mode | `dispatched-six-angle` |
| Specialists completed | `6` |
| Consolidator completed | `true` |
| Adversarial model | `none` |
| Fallback reason | `native Workflow unavailable` |
| Scope | 11 changed files; every specialist reported the exact 11/11 manifest; no missing or extra files |

## A. Executive Summary

This diff moves blocking runtime installation and startup from the shared default executor to a dedicated single-worker lifecycle executor, explicitly preserves the caller's `contextvars` context, and adds real public-facade starvation regressions plus retained verification evidence. The production repair is small, architecturally defensible, and directly breaks the previously confirmed circular executor dependency.

- Overall risk: **medium-low**. No production defect survived review, but two gaps in the new regression file weaken proof of context propagation and make the deadlock test more sensitive to host scheduling.
- Verdict: **PASS-with-triage**
- Counts: **0 blockers / 2 non-blockers / 0 nits**
- Scope sanity: 458 insertions and 7 deletions across 11 task-related source, test, handoff, and verification files. No unrelated modification or oversized diff was identified.
- Coverage: six dispatched specialists each reported the exact 11/11 changed-file manifest. Regenerating the pinned diff reproduced the recorded SHA-256.
- Checks performed: six dispatched angles plus this consolidator; static inspection of the lifecycle executor, context propagation, all three public facade cases, counterfactual evidence, and retained focused/full-suite results.

Both findings are confined to the changed test surface, are small and safe to correct, and should be fixed in B102 before QA instead of being deferred as separate debt.

## B. Findings Table

| id | severity | file:line | rule | diagnosis | evidence | correction |
|---|---|---|---|---|---|---|
| B102-R9-01 | Non-blocker | `tests/unit/runtime/test_b102_public_facade_starvation.py:137` | `TESTS` | The production repair explicitly copies the caller context before running lifecycle work, but the new regression suite never sets or observes a `ContextVar`. Removing `contextvars.copy_context()` and `context.run` would leave the changed tests green even though it would regress the former `asyncio.to_thread` context-propagation behavior. **CONFIRMED.** | `RuntimeManager._run_install_and_startup()` copies and runs the context at `src/agentmap/runtime/runtime_manager.py:118-126`. The parameterized public-facade test asserts termination, results, and initialized state only. Repository search found ContextVar tests for LLM task-local behavior, but none for runtime initialization or this lifecycle-executor boundary. | Add a focused counterfactual that sets a sentinel `ContextVar` in the calling task and observes the same value inside `initialize_di`, startup, or cache refresh on the lifecycle executor. Prove that removing either `copy_context()` or `context.run` fails the test. |
| B102-R9-02 | Non-blocker | `tests/unit/runtime/test_b102_public_facade_starvation.py:112` | `TESTS` | Worker readiness is detected with up to 1,000 one-millisecond polling sleeps, and starvation is inferred from a one-second wall-clock timeout. On a loaded CI host, scheduling delay can be misclassified as the deadlock this test is meant to detect. **CONFIRMED.** | `wait_for_thread_event()` polls `threading.Event.is_set()` with `asyncio.sleep(0.001)` at lines 112-118; `complete_tasks_or_break_counterfactual()` uses `asyncio.wait(..., timeout=1)` at lines 121-131. Existing sibling tests use `loop.call_soon_threadsafe(entered.set)` in `test_b102_runtime_coordination.py:158,201` and `test_b102_admin_async_initialization.py:86`. | Signal worker readiness into an `asyncio.Event` with `loop.call_soon_threadsafe`, assert the ordering events that establish the queued-work state, and retain only a generous outer timeout as a test-process safety guard. |

## C. Reuse Opportunities

No production DRY finding survived consolidation. The search `rg -n "ContextVar|copy_context|context\.run|call_soon_threadsafe|wait_for_thread_event|all_workers_active|complete_tasks_or_break_counterfactual" src tests` found no runtime-initialization ContextVar regression to reuse. It did find the deterministic cross-thread notification pattern in `tests/unit/runtime/test_b102_runtime_coordination.py:158,201` and `tests/unit/deployment/http/api/test_b102_admin_async_initialization.py:86`; B102-R9-02 should reuse that pattern rather than retain polling.

## D. Standards Crosswalk

| finding id | standards or contract source | section | controlling clause |
|---|---|---|---|
| B102-R9-01 | `dev-artifacts/2026-10-04-b102-dependency-review-rework-9/handoff.md` | Finding disposition, `B102-R8-01` | The repair claims that explicit `contextvars` propagation preserves the former `asyncio.to_thread` behavior. The changed tests do not establish that part of the claimed contract. |
| B102-R9-02 | `dev-artifacts/2026-10-04-b102-dependency-review-rework-9/handoff.md` | Counterfactual and defect-class sweep | The handoff describes the one- and two-worker cases as deterministic. Millisecond polling plus a one-second completion cutoff makes that claim sensitive to host scheduling. |
| B102-R9-01, B102-R9-02 | `AGENTS.md` | Testing | Unit tests belong under `tests/unit` and should use repository test conventions. The file is correctly placed and uses mocks appropriately; the remaining issues concern counterfactual strength and deterministic synchronization. |

## E. Tests Review

- The retained focused evidence reports 324 passed with zero skips and warnings. The retained full suite reports 5,719 passed, 49 skipped, 1 deselected, 5 warnings, and 228 subtests. Formatting, import order, lint, and normalized mypy comparison are also retained.
- The six public-facade combinations cover list, inspect, and validate at one and two shared-executor workers and prove the dedicated lifecycle executor breaks the prior deadlock cycle.
- Missing counterfactual: delete `contextvars.copy_context()` or `context.run`; the current focused and full suites still pass. B102-R9-01 adds the direct contract check.
- Flaky-risk: readiness polling and a one-second deadlock cutoff couple the test outcome to scheduler speed. B102-R9-02 replaces polling with event-loop notification and ordering assertions.
- Mock discipline is otherwise appropriate: the test drives the real public facades and runtime coordination while mocking offline service dependencies at their boundary.

## F. Quality Rubric

Scores are 0-5. Evidence files are scored for auditability rather than production design.

| file | readability | maintainability | performance | testability | standards | notes |
|---|---:|---:|---:|---:|---:|---|
| `dev-artifacts/2026-10-04-b102-dependency-review-rework-9/handoff.md` | 5 | 5 | 5 | 4 | 5 | Clear disposition and exact evidence; its context-propagation and deterministic-test claims need the two targeted test corrections. |
| `verification/black.log` | 5 | 5 | 5 | 5 | 5 | Exact formatter command and result. |
| `verification/counterfactual-red.log` | 5 | 5 | 5 | 5 | 5 | Retains all six pre-fix deadlock failures. |
| `verification/focused-collect.log` | 5 | 5 | 5 | 5 | 5 | Explicit focused inventory. |
| `verification/focused.log` | 5 | 5 | 5 | 5 | 5 | Concise result with no hidden skip or warning. |
| `verification/isort.log` | 5 | 5 | 5 | 5 | 5 | Exact import-order result. |
| `verification/lint.log` | 5 | 5 | 5 | 5 | 5 | Exact repository lint result. |
| `verification/make-test.log` | 4 | 4 | 4 | 5 | 5 | Preserves full-suite skips, deselection, warnings, and subtest count. |
| `verification/mypy-normalized-comparison.log` | 4 | 4 | 5 | 4 | 4 | Transparently records the inherited non-green baseline and zero semantic delta. |
| `src/agentmap/runtime/runtime_manager.py` | 5 | 4 | 5 | 4 | 5 | Dedicated executor is the smallest direct repair, and explicit context copying preserves prior behavior; lifecycle-executor shutdown remains outside this narrow diff's contract. |
| `tests/unit/runtime/test_b102_public_facade_starvation.py` | 4 | 4 | 4 | 3 | 4 | Strong production-shaped facade coverage; missing context assertion and timing-based synchronization reduce testability to 3 and produce the two non-blockers. |

No rubric dimension averages at or below 3 across the changed-file set, so no additional rubric-only finding is added.

## G. Risk Hotspots

- **Concurrency:** the production cycle is repaired with a dedicated executor, while B102-R9-02 identifies avoidable scheduler sensitivity in the regression proof.
- **Execution context:** explicit `ContextVar` propagation is correct by inspection but lacks a direct counterfactual assertion (B102-R9-01).
- **Resource lifetime:** the process-wide single-worker executor matches the singleton runtime lifecycle and introduces no per-call thread growth. Package release and host integration remain separate gates.
- **Architectural defensibility:** moving only install/startup work to one dedicated executor is a focused response to the confirmed shared-pool dependency cycle. It preserves transaction serialization and avoids a broader runtime rewrite.

## H. Production Caller Chains

- `list_graphs_async()` -> shared-default-executor `list_graphs()` -> `ensure_initialized()` waits for transaction owner, while async owner -> `ensure_initialized_async()` -> `_run_initialization_transaction()` -> `_run_install_and_startup()` uses `RuntimeManager._lifecycle_executor`.
- `inspect_graph_async("graph", csv_file=...)` follows the same synchronous initialization wait while owner startup proceeds independently on the lifecycle executor.
- `validate_workflow_async("workflow::graph")` follows the same path and now terminates under one- and two-worker shared-executor saturation.

## I. Triage Summary

### Non-blockers to triage

1. `tests/unit/runtime/test_b102_public_facade_starvation.py:137` — fingerprint `tests/unit/runtime/test_b102_public_facade_starvation.py#TESTS#lifecycle-context-propagation-counterfactual` — the dedicated-executor test does not prove preservation of caller `ContextVar` state. Fix suggestion: add a sentinel ContextVar assertion through the real async initialization transaction. **Recommended disposition: fix now in B102; this is a small changed-surface test addition.**
2. `tests/unit/runtime/test_b102_public_facade_starvation.py:112` — fingerprint `tests/unit/runtime/test_b102_public_facade_starvation.py#TESTS#starvation-test-wall-clock-polling` — millisecond polling and a one-second cutoff make the deadlock regression scheduler-sensitive. Fix suggestion: bridge worker readiness with `loop.call_soon_threadsafe` and assert ordering, leaving a generous timeout only as an outer guard. **Recommended disposition: fix now in B102; sibling code already provides the pattern.**

## J. Verdict

**PASS-with-triage**

The dedicated lifecycle executor is a narrow, defensible repair for the shared-executor deadlock, and the changed tests cover all six public-facade/worker-count combinations with retained red and green evidence. No production blocker remains. The two changed-surface test gaps should be corrected before QA so context propagation has a real counterfactual and the starvation regression does not depend on millisecond scheduling.
