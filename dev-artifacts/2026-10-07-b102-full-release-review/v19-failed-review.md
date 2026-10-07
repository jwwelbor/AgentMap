# AgentMap B102 release candidate review, v19

## A. Executive Summary

This frozen candidate adds governed physical LLM attempt accounting and lifecycle handling, including provider observation, runtime initialization transactions, HTTP lifespan leases, and supporting tests and review evidence. The implementation direction is defensible: a single runtime coordinator and terminal cleanup helper address a real resource lifetime contract. The current lease API has three release and configuration invariants that are not enforced, and the coordinator breaches the repository's explicit file size limit. These require repair before QA.

- **Verdict:** **FAIL**. Overall risk: high for HTTP runtime ownership and shutdown.
- **Findings:** 4 blockers, 3 non-blockers, 0 nits. Eight specialist findings became seven unique findings; the two cross-loop release findings were merged.
- **Evidence mode:** `dispatched-six-angle`; **specialists completed:** `6`; **consolidator completed:** `true`; **runner_mode:** `dispatched-six-angle`; **adversarial_model:** `none`; **fallback_reason:** `none`.
- **Base commit:** `dc997387206552533b586c337add8d1b938676c7`; **head:** `9e72d88709bea88a4737380da5d1ad5bb5fe9a2c`.
- **Diff path:** `/tmp/agentmap-b102-release-review-v19-20261007/agentmap.diff`; **diff SHA256:** `61d8c4ad6e9dc62dcdddf0cea1d0472b48c7b24a3122bed3fe4012beb62b670c`.
- **Manifest path:** `/tmp/agentmap-b102-release-review-v19-20261007/manifest.txt`; **manifest SHA256:** `3d38af8f0345e92e2bd0c7f3618a12c625ff70c77f9a26a5d5cb0b49ba9552d8`.
- **Changed paths:** 331; **reviewed paths:** 331 in every angle, exact set and count. The manifest matches `git diff --name-only base...head`; the saved diff hash matches a fresh Git diff; the worktree HEAD matches the pin. Each JSON declares complete status and exact root/base/head/diff/manifest pins.
- **Scope sanity:** 331 files, 32,522 insertions and 384 deletions, well above the 2,000-line split threshold. About 260 paths are historical review and verification evidence. This broad evidence history makes review harder, but the changed source, tests, and artifacts match the B102 lifecycle intent. Recommend a narrower future candidate if feasible; this observation does not by itself invalidate the frozen six-angle coverage.
- **Checks performed:** six specialist artifacts plus this consolidator; source and production call chains at each finding; `claude.md` standards; no tests executed in this read-only consolidation.

## B. Findings Table

| id | severity | file:line | rule | diagnosis and verification | evidence | correction |
|---|---|---|---|---|---|---|
| B1 | Blocker; **CONFIRMED** | `src/agentmap/runtime/runtime_manager.py:135` | RISK | Cancellation while `release_lifespan` waits for its transaction exits before the lease is removed. The HTTP `finally` awaits release directly, so a cancelled lifespan can strand a token and prevent shutdown or refresh. Angle A. | `_acquire_async_transaction` awaits a future at line 252; token removal starts at line 139; `server.py:78` is a direct await. | Make the whole lease release a terminal task and preserve caller cancellation after lease and owned cleanup reach a terminal state; add a contended transaction cancellation regression. |
| B2 | Blocker; **CONFIRMED** | `src/agentmap/runtime/runtime_manager.py:118` | ARCHITECTURE | Two overlapping apps with different `config_file` values silently share the first container. The second application's configuration is ignored while startup succeeds. Angle B. | `acquire_lifespan` passes config into non-refresh startup, but `_initialize_in_transaction` returns on an existing container at lines 214-216. `server.py:57` passes each app's config. | Record effective config identity and reject incompatible leases, including on a borrowed runtime; retain same-config sharing and cover both cases. |
| B3 | Blocker; **CONFIRMED** | `src/agentmap/runtime/runtime_manager.py:137` | RISK | A public release can run on a foreign event loop. The last release clears loop ownership and closes loop-bound clients on the caller's loop, potentially losing the lease before cleanup fails. Angles A and B, deduplicated. | Acquisition compares `_lifespan_loop` at lines 112-116; release has no comparable check before removal at lines 137-149. The loop-bound resource in `test_b102_runtime_shutdown.py:39` asserts cleanup on its owner loop. | Reject foreign-loop release before consuming a lease, or marshal final cleanup to the owner loop; add a cross-loop release regression. |
| B4 | Blocker; **CONFIRMED** | `src/agentmap/runtime/runtime_manager.py:26` | CODING-STANDARD | The lifecycle change expands the coordinator to 437 lines, above the project 350-line ceiling. Angle F. | `wc -l` returns 437; `claude.md`, `anti_patterns`, says “no files over 350 lines.” The base version was about 94 lines. | Extract a cohesive lifecycle concern while retaining `RuntimeManager` as coordinator and preserving its transaction boundary. |
| N1 | Non-blocker; **CONFIRMED** | `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py:76` | TESTS | The overlap test uses one event loop and cannot fail if the new different-loop acquisition guard is removed. Angle E. | Both nested `create_lifespan` contexts run in one marked asyncio test; guard is at `runtime_manager.py:113`. | Add a two-loop attempted overlap test and assert no second lease or premature shutdown. |
| N2 | Non-blocker; **CONFIRMED** | `src/agentmap/services/llm/fallback_ladder.py:55` | CODING-STANDARD | `_try_fallback_tier` spans 51 lines, one beyond the stated method ceiling. Angle F. | Definition spans lines 55-105; `claude.md`, `anti_patterns`, says “no methods over 50 lines.” | Extract client resolution or governed limit preparation without changing refusal propagation. |
| N3 | Non-blocker; **CONFIRMED** | `src/agentmap/services/llm_service.py:1889` | CODING-STANDARD | `_attempt_llm_call_async` spans 51 lines, one beyond the stated method ceiling. Angle F. | Definition spans lines 1889-1939; same `claude.md` clause. | Extract description or accounting callback construction without changing admission and settlement order. |

The method overages are only one line and do not independently demonstrate a production failure; they remain standards triage rather than merge blockers. The module size overage is 87 lines and represents a material expansion of the lifecycle coordinator, so it is a blocker under the explicit standard. No candidate was refuted on current-caller reachability grounds: the lease methods are exported through `runtime_api.py`.

## C. Reuse Opportunities

No DRY finding survived. A targeted `rg` search found a single `release_lifespan` implementation in `runtime_manager.py`, a facade in `init_ops.py`, and calls in `server.py`; there is no duplicate lease implementation to consolidate. The existing `await_terminal_task` helper in `src/agentmap/async_lifecycle.py:32` is the reuse point for B1. The two cross-loop specialist reports describe one root cause and are counted once. No structural sibling inventory was triggered by the seven findings.

## D. Standards Crosswalk

| finding id | standards doc | section | quoted clause |
|---|---|---|---|
| B4 | `claude.md` | `anti_patterns` | “no files over 350 lines” |
| N2, N3 | `claude.md` | `anti_patterns` | “no methods over 50 lines” |

The same standards file prescribes `unittest.TestCase`, while the repository's existing and added test modules use pytest functions. Angle F recorded this conflict and followed the established local test convention; it is not counted as a new B102 defect.

## E. Tests Review

The six angles report exact 331-path coverage. Their semantic pass includes 25 production Python paths and 43 test Python paths; historical evidence was checked mainly by metadata, header, and tail. Existing tests cover same-loop lease sharing, borrowed runtime, active-lease refresh rejection, loop-bound async refresh, startup rollback, and transaction wait cancellation. No test run was authorized for this consolidation; test outcomes are not claimed here.

Counterfactual failures: removing the acquisition loop guard would leave the current overlap test green (N1). A foreign-loop final release, differing overlapping app configs, and cancellation while release waits for another transaction lack direct regression cases (B3, B2, B1). Add those before re-review. Existing HTTP lifespan tests use mocked container services; the new risk cases should exercise the real `RuntimeManager` transaction and lease state with a loop-bound resource. No concrete flaky test or mock-discipline defect was substantiated by the angles.

## F. Quality Rubric

Scores are 0-5 in order: readability, maintainability, performance, testability, standards. This rubric focuses on the files with surviving findings; six angle artifacts provide the complete 331-path inspection record. Historical evidence files are assessed for provenance in the scope section rather than assigning synthetic code-quality scores.

| file | readability | maintainability | performance | testability | standards | evidence |
|---|---:|---:|---:|---:|---:|---|
| `src/agentmap/runtime/runtime_manager.py` | 3 | 2 | 4 | 3 | 1 | Transaction flow is traceable, but three lease invariants are unenforced and the file is 437 lines against a 350-line limit. |
| `src/agentmap/services/llm/fallback_ladder.py` | 4 | 3 | 4 | 4 | 3 | The tier flow and refusal propagation are clear; the edited method spans 51 lines. |
| `src/agentmap/services/llm_service.py` | 4 | 3 | 4 | 4 | 3 | Attempt admission and settlement are explicit; the edited method spans 51 lines. |
| `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py` | 4 | 4 | 5 | 3 | 4 | The lifespan tests exercise ownership, but the two-loop guard has no counterfactual. |
| Remaining 67 changed source, test, configuration, and document paths | 4 | 4 | 4 | 4 | 4 | Six specialists reported no further concrete quality defect across these paths; aggregate score, not individual certification. |

The runtime manager scores at or below 2 in maintainability and standards, consistent with B4. No score is used to override a concrete production blocker.

## G. Risk Hotspots

- **Concurrency and I/O:** cancellation before transaction acquisition and foreign-loop cleanup threaten terminal resource release (B1, B3).
- **Configuration and coupling:** a process-wide singleton can attach a second HTTP app to the wrong configuration (B2).
- **Architecture:** the transaction and governed attempt design is defensible for lifecycle correctness, but the missing lease invariants and 437-line coordinator make this implementation incomplete. The provider accounting seam is a reasonable minimal boundary; no additional architecture defect was substantiated by the angles.
- **Security:** B2 can apply the wrong auth configuration to an overlapping app; the static record establishes the configuration mismatch, while actual authorization impact depends on deployment.
- **Performance:** no concrete new bottleneck was substantiated.

## H. Production Caller Chains

- **Lease startup and config:** `FastAPIServer.create_app` → `create_lifespan(config_file)` → `acquire_runtime_lifespan(config_file)` → `RuntimeManager.acquire_lifespan` → `_run_initialization_transaction(..., refresh=False, config_file=...)` → `_initialize_in_transaction`. A second app passes its own string or `None`; an existing container causes the config to be ignored (B2).
- **Lease release and cancellation:** FastAPI lifespan `finally` → `release_runtime_lifespan(lease: object)` → `RuntimeManager.release_lifespan` → `_acquire_async_transaction` → token removal → `_await_shutdown` → `container.llm_service().shutdown()`. Cancellation at the transaction wait prevents token removal (B1); a caller on another loop can close resources on that loop (B3).
- **Governed attempt:** `LLMService._attempt_llm_call_async` constructs description and callbacks → `invoke_governed_attempt` → timed provider invocation and accounting. This path's 51-line method is a small standards issue (N3); no contract defect in this chain was substantiated by the specialist reports.

## I. Triage Summary

**Blockers before QA:**

1. B1: terminal lease release under cancellation.
2. B2: incompatible config rejection for overlapping or borrowed runtime.
3. B3: owner-loop enforcement or marshalled cleanup on release.
4. B4: split the enlarged runtime manager along a cohesive lifecycle boundary.

**Non-blockers to triage:**

1. `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py:76` — `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py#TESTS#cross-loop-acquire-counterfactual` — same-loop overlap test cannot detect a missing cross-loop guard. Add a two-loop rejection regression.
2. `src/agentmap/services/llm/fallback_ladder.py:55` — `src/agentmap/services/llm/fallback_ladder.py#CODING-STANDARD#fallback-tier-method-limit` — 51-line method. Extract client preparation while retaining refusal semantics.
3. `src/agentmap/services/llm_service.py:1889` — `src/agentmap/services/llm_service.py#CODING-STANDARD#physical-attempt-method-limit` — 51-line method. Extract accounting setup while retaining attempt order.

No nits. The host must disposition each non-blocker under the project's finding triage rule; this report is read-only and creates no Shark entities.

## J. Verdict

**FAIL**

The six-angle review is complete and pinned to one candidate, but the current HTTP lifespan implementation can strand an active lease, shut down on a foreign loop, and silently reuse incompatible app configuration. The runtime coordinator also exceeds an explicit project limit. Repair the four blockers and obtain a fresh pinned review of the new candidate before QA or release.
