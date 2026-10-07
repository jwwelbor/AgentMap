# AgentMap B102 release candidate review, v22

## A. Executive Summary

V22 resolves lifespan configuration identity through the same current-directory discovery rule as DI bootstrap and canonicalizes selected paths before sharing a runtime. The new tests cover changed cwd, equal relative names, and default/explicit selection of the same file. The six-angle review found one missing symlink alias counterfactual and no production blocker.

- **Verdict:** **PASS-with-triage**. Overall risk: moderate due to the size of the candidate and unexecuted tests in this read-only consolidation.
- **Findings:** 0 blockers, 1 non-blocker, 0 nits.
- **Evidence mode / runner_mode:** `dispatched-six-angle`; **specialists_completed:** `6`; **consolidator_completed:** `true`; **adversarial_model:** `none`; **fallback_reason:** `none`.
- **Base commit:** `dc997387206552533b586c337add8d1b938676c7`; **head:** `24b098bf1479c65f8074e7c684f53268c1486322`.
- **Diff path:** `/tmp/agentmap-b102-release-review-v22-20261007/agentmap.diff`; **diff SHA256:** `fd4b2d52161858809004b1c02b8d3605df93a086fa1e6fe4a6ce73228b3d3a49`.
- **Manifest path:** `/tmp/agentmap-b102-release-review-v22-20261007/manifest.txt`; **manifest SHA256:** `6293f2c24e99fe16f049998bb6984f3540fd7cf24744a47d0d9c6754db8765e1`; **changed path count:** `337`.
- **Coverage and checks:** All six JSON artifacts declare completion, match exact root/base/head/diff/manifest pins, and each names exactly all 337 manifest paths. A fresh Git diff reproduces the saved diff hash; `git diff --name-only base...head` exactly reproduces the manifest. This consolidator inspected the finding, current source and tests, and `claude.md`. No tests were executed.
- **Scope sanity:** 337 files changed, 33,126 insertions and 387 deletions, above the review guide's 2,000-line split recommendation. Most added lines are historical review and verification evidence. The v22 source/test delta fits B102 runtime configuration ownership; no coverage gap or unrelated production edit was found. A narrower future candidate would ease review.

## B. Findings Table

| id | severity | file:line | rule | diagnosis | evidence | correction |
|---|---|---|---|---|---|---|
| N1 | Non-blocker; **CONFIRMED** | `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py:31` | TESTS | No counterfactual proves a direct config path and a symlink alias share one runtime. The implementation promises equivalent symlink spellings, but replacing `Path.resolve()` with absolute-path normalization would leave current tests green. | `canonical_config_path` at `src/agentmap/runtime/lifespan_mixin.py:12-14` calls `Path.resolve()`. The discovery test uses `agentmap_config.yaml` and `./agentmap_config.yaml`; the sharing test uses direct paths. No changed test creates a symlink. Angle E. | Create a symlink to one temporary config file and acquire overlapping lifespans by real path and alias in both orders; assert one container and install, no first-exit shutdown, and one final shutdown. |

The source's `Path.resolve()` follows symlinks, so N1 is a missing test for an existing behavior, not evidence of a current production failure. No other angle reported a finding, and no deduplication was needed.

## C. Reuse Opportunities

No DRY finding survived. A targeted `rg` search found one `canonical_config_path` in `src/agentmap/runtime/lifespan_mixin.py:12`, with `Path.resolve()` as its existing canonicalization mechanism; the DI discovery function is reused by `effective_config_file` at line 19. The v22 change is architecturally defensible: it brings lease comparison into agreement with DI bootstrap without adding another independent config selector.

## E. Tests Review

The six specialists report 337-path coverage; angle F inspected 27 source Python paths and 44 test Python paths by AST. V22 adds real DI discovery, cwd-change mismatch, equal-relative-name mismatch, and default/explicit same-file sharing cases. The symlink alias counterfactual remains absent (N1). No concrete flaky or mock-discipline problem was substantiated. This consolidation did not run tests and does not claim test success.

## F. Quality Rubric

Scores are 0-5 in order: readability, maintainability, performance, testability, standards. This concise table covers the finding-bearing path and its implementation; six pinned artifacts supply full path coverage. Historical logs are not given synthetic code scores.

| file | readability | maintainability | performance | testability | standards | reason |
|---|---:|---:|---:|---:|---:|---|
| `src/agentmap/runtime/lifespan_mixin.py` | 4 | 4 | 4 | 4 | 4 | A small canonicalization helper shares DI discovery and uses `Path.resolve()` for relative and symlink aliases. |
| `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py` | 4 | 4 | 5 | 3 | 4 | Boundary tests cover discovery and cwd changes but omit the symlink equivalence counterfactual. |

Angle F reports `runtime_manager.py` at exactly 350 lines and changed methods at no more than 50, within `claude.md` limits. No additional quality issue was substantiated.

## G. Risk Hotspots

- **Configuration:** lease compatibility now compares resolved effective identities; the remaining risk is regression of symlink alias equivalence without a test (N1).
- **I/O:** config discovery and path resolution depend on the current working directory at lease time. The new cwd-change tests cover the primary mismatch case.
- **Architecture:** the same discovery rule is used for bootstrap and comparison; this is a defensible minimum change for the v21 blocker.

## H. Production Caller Chains

`FastAPIServer.create_app` → `create_lifespan(config_file)` → `acquire_runtime_lifespan(config_file)` → `RuntimeLifespanMixin.acquire_lifespan` → `effective_config_file(config_file)` → `discover_config_file()` when omitted → `canonical_config_path` → `Path.resolve()`. The resulting identity is compared with `RuntimeManager._runtime_config_file`, which records the installed container's path. Matching identities share the runtime; mismatches fail before a lease is issued.

## I. Triage Summary

**Non-blocker to triage:**

1. `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py:31` — `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py#TESTS#symlink-config-alias-counterfactual` — no direct-versus-symlink sharing test. Add both orderings and assert one install and one final shutdown.

No blockers or nits. The host must disposition N1 under the project's finding triage rule; this read-only report creates no tracker entity.

## J. Verdict

**PASS-with-triage**

The complete six-angle review found no blocker in the pinned v22 candidate. The symlink alias test gap needs a host disposition before the review gate is considered resolved. This verdict reports code review evidence only; it does not establish QA, live product acceptance, CI, or release readiness.
