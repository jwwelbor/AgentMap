# AgentMap B102 release candidate review, v20

## A. Executive Summary

The candidate implements governed LLM attempt accounting and runtime lifecycle ownership. The v20 repair moves HTTP lifespan and cleanup behavior into small mixins, protects release through terminal cleanup, rejects foreign-loop release, and rejects two unequal explicit configuration paths. One configuration case remains unsafe: an app using the default `None` selection can borrow a runtime built from an explicit file.

- **Verdict:** **FAIL**. Risk is high because a second HTTP app may run with the first app's auth and provider configuration while startup reports success.
- **Findings:** 1 blocker, 1 non-blocker, 0 nits. Four specialist findings became two unique findings; the same configuration defect was reported by angles A, B, and D.
- **Evidence mode / runner_mode:** `dispatched-six-angle`; **specialists_completed:** `6`; **consolidator_completed:** `true`; **adversarial_model:** `none`; **fallback_reason:** `none`.
- **Base commit:** `dc997387206552533b586c337add8d1b938676c7`; **head:** `b246af36d2f57bfda93264200aeb34fb4ab3a9ff`.
- **Diff path:** `/tmp/agentmap-b102-release-review-v20-20261007/agentmap.diff`; **diff SHA256:** `fd7d9fa02b418cea3df66ffb89ce6e8192942d2c2f39855d679e7043b90537d5`.
- **Manifest path:** `/tmp/agentmap-b102-release-review-v20-20261007/manifest.txt`; **manifest SHA256:** `562940fba8b4369cb9ed5471e3ebc7ef17a2525ade89fcaa59841dc05a2fd4b0`; **changed path count:** `334`.
- **Coverage and checks:** All six JSON artifacts declare completion and match the exact root, base, head, diff hash, and manifest hash. Each lists exactly the 334 manifest paths with no missing or extra path. The manifest matches `git diff --name-only base...head`; a fresh Git diff reproduces the saved hash. This consolidator checked each finding against the current source and the `claude.md` standards path. No tests were run.
- **Scope sanity:** 334 files changed, 32,788 insertions and 388 deletions, exceeding the review guide's 2,000-line split threshold. Roughly 261 paths are historical evidence; the executable delta and new v20 mixins fit the B102 lifecycle goal. A smaller future candidate would be easier to review. No coverage gap or clearly unrelated production change was identified.

## B. Findings Table

| id | severity | file:line | rule | diagnosis | evidence | correction |
|---|---|---|---|---|---|---|
| B1 | Blocker; **CONFIRMED** | `src/agentmap/runtime/lifespan_mixin.py:33` | CORRECTNESS | The mismatch guard skips the comparison when the new app requests `config_file=None`. `None` invokes config discovery or system defaults at bootstrap. If an explicit-file app starts first, a default-config app silently receives its existing container. | The condition requires `config_file is not None` at lines 31-35; non-refresh initialization returns on an existing container at `runtime_manager.py:174-176`. `create_lifespan()` defaults to `None` and passes it through. `di/__init__.py:99-122` gives `None` real discovery/default behavior. Angles A, B, D. | Compare effective configuration identity for every lease, including `None`, before returning the shared container. Reject mismatches or unprovable identity. Add explicit-first/default-second and default-first/explicit-second regressions, including a same-effective-config case. |
| N1 | Non-blocker; **CONFIRMED** | `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py:129` | TESTS | No test proves two overlapping apps using the same explicit file still share one runtime. A guard that rejects every second explicit request would pass the current tests. | The new mismatch test uses `first.yml` then `second.yml`; the existing sharing test uses `None` for both apps. Angle E. | Nest two `create_lifespan("first.yml")` contexts and assert one container, one install, no shutdown on first exit, and one shutdown on final exit. |

The three B1 reports have the same file, guard, and root cause and are counted once. B1 is a broken production configuration contract, so it blocks QA. N1 is a missing positive counterfactual and does not itself prove a current production failure.

## C. Reuse Opportunities

No DRY finding survived. `rg` found one `discover_config_file` implementation at `src/agentmap/di/__init__.py:47`, with its bootstrap use at line 115. That existing discovery logic is the relevant reuse point for resolving `None`; there is no duplicate config resolver to remove. The v20 mixin extraction is architecturally defensible and keeps `runtime_manager.py` at 342 lines, below the explicit 350-line ceiling. The raw `_runtime_config_file` field still needs an effective-identity contract for B1.

## E. Tests Review

Six pinned angles cover all 334 changed paths. Their evidence describes semantic inspection of the source and test paths, with metadata/header/tail inspection of historical evidence. No test outcome is claimed from this read-only consolidation.

The negative explicit-config case (`first.yml` versus `second.yml`) is covered; the explicit-versus-default case is not (B1). The same explicit-config sharing case is not covered (N1). A test that only exercises two different strings cannot distinguish a correct compatibility guard from one that rejects all second explicit leases. No concrete flaky or mock-discipline problem was reported. Existing `unittest.TestCase` wording in `claude.md` conflicts with established pytest usage; the angles treated that as a pre-existing convention conflict, not a new B102 finding.

## F. Quality Rubric

Scores are 0-5 in order: readability, maintainability, performance, testability, standards. This concise rubric covers the finding-bearing files; the six artifacts are the full path inspection record, and historical logs are not assigned synthetic code scores.

| file | readability | maintainability | performance | testability | standards | reason |
|---|---:|---:|---:|---:|---:|---|
| `src/agentmap/runtime/lifespan_mixin.py` | 4 | 3 | 4 | 3 | 4 | Lease flow is short and traceable, but effective config identity is not enforced or tested at the default boundary. |
| `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py` | 4 | 4 | 5 | 3 | 4 | Negative lifecycle cases are clear; positive same-explicit-config sharing has no counterfactual. |

No additional quality issue was substantiated by the other specialist angles. The existing method-size and runtime-file-size findings from v19 are repaired in this snapshot: `runtime_manager.py` is 342 lines and angle F measured the edited methods at no more than 50 lines.

## G. Risk Hotspots

- **Configuration and security:** a default-config app can inherit another app's auth/provider configuration (B1). The static source proves the wrong container assignment; deployment-specific authorization impact remains conditional.
- **Coupling:** process-wide singleton sharing needs an explicit effective configuration identity. Raw argument equality is insufficient when `None` triggers discovery.
- **Concurrency and I/O:** v20 now protects release with `await_terminal_task` and checks the owner loop before consuming a token. Those earlier risks were rechecked at source, with no new finding from the six angles.

## H. Production Caller Chains

- `FastAPIServer.create_app` → `create_lifespan(config_file: str | None = None)` → `acquire_runtime_lifespan(config_file)` → `RuntimeLifespanMixin.acquire_lifespan` → `RuntimeManager._run_initialization_transaction(refresh=False, config_file)` → `_initialize_in_transaction`. With an existing container, the last method returns without installing the second app's default configuration; the `None` guard in the mixin admits the lease (B1).
- `initialize_di(config_file)` → explicit file selection or `discover_config_file()` → `create_container(actual_config_path)`. This establishes that `None` is a configuration selection, not an identity wildcard.

## I. Triage Summary

**Blocker before QA:**

1. B1: enforce effective configuration compatibility for default and explicit lifespan requests; cover both ordering directions.

**Non-blocker to triage:**

1. `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py:129` — `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py#TESTS#same-explicit-config-sharing` — no positive test for same explicit config sharing. Add a nested same-file lifespan regression with install and shutdown counts.

No nits. The host must disposition N1 under the project's finding triage rule; this report creates no tracker entity.

## J. Verdict

**FAIL**

The v20 six-angle review is complete and tied to one 334-path candidate. The remaining `None` compatibility hole can start an HTTP app with the wrong runtime configuration. Repair B1, add its boundary regressions, and obtain a fresh pinned review before QA or release.
