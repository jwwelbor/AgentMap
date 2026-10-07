# AgentMap B102 release candidate review, v23

## A. Executive Summary

V23 adds a symlink alias parameter to HTTP lifespan configuration sharing tests. The six-angle review found one narrow gap: the symlink test uses a mock installed container and therefore does not exercise canonicalization of the path returned by a real DI container.

- **Verdict:** **PASS-with-triage**. Overall risk: moderate for the broad candidate; no production defect was substantiated.
- **Findings:** 0 blockers, 1 non-blocker, 0 nits.
- **Evidence mode / runner_mode:** `dispatched-six-angle`; **specialists_completed:** `6`; **consolidator_completed:** `true`; **adversarial_model:** `none`; **fallback_reason:** `none`.
- **Base commit:** `dc997387206552533b586c337add8d1b938676c7`; **head:** `7ba0daa3a09895b348fc4d6b76eda0530be69d6f`.
- **Diff path:** `/tmp/agentmap-b102-release-review-v23-20261007/agentmap.diff`; **diff SHA256:** `6e84e71f5f930bf87bb41b9a52182383dda5aaa3fdec55f2e3fee29bc5efa61a`.
- **Manifest path:** `/tmp/agentmap-b102-release-review-v23-20261007/manifest.txt`; **manifest SHA256:** `9810cf543a78e69a5526a7e482eed8c886c0159e94c6955acfa95cd292324495`; **changed path count:** `338`.
- **Coverage and checks:** All six JSON artifacts declare completion, match the exact root/base/head/diff/manifest pins, and each lists precisely all 338 manifest paths. A fresh Git diff reproduces the saved hash, and `git diff --name-only base...head` reproduces the manifest. This consolidator inspected the finding against the current source and test assertions, including the real-DI `./agentmap_config.yaml` parameter. No tests were executed.
- **Scope sanity:** 338 files, 33,195 insertions and 387 deletions exceed the review guide's 2,000-line split recommendation. Most added lines are historical review and verification evidence; the v23 executable delta is the symlink test parameter. No coverage gap or unrelated production edit was found.

## B. Findings Table

| id | severity | file:line | rule | diagnosis | evidence | correction |
|---|---|---|---|---|---|---|
| N1 | Non-blocker; **CONFIRMED, narrowed** | `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py:87` | TESTS | The symlink-first sharing case uses a mocked installed container with no `config.path()`, so `RuntimeManager._install` takes its `AttributeError` fallback. A symlink-specific regression in the primary real-DI installed-path branch could pass the current suite. | `runtime_setup` returns `SimpleNamespace` without `config` at lines 17-27; the symlink test at lines 87-106 uses it. `_install` calls `canonical_config_path(container.config.path())` at `runtime_manager.py:187`, then falls back to `effective_config_file(config_file)` on `AttributeError` at lines 188-189. The real-DI test at lines 46-58 parametrizes `None` and `./agentmap_config.yaml`, but no symlink. Angle E. | Add a real-DI `RuntimeManager.initialize(config_file=str(alias))` case, assert the stored identity is the target's resolved path, and assert a default lifespan discovering the target shares the runtime. Cover the reverse ordering if it exercises a distinct installation path. |

**Counterfactual limit:** Removing installed-path canonicalization entirely would already fail the existing real-DI `./agentmap_config.yaml` parameter: the DI container returns a relative path, while the assertion expects an absolute resolved path. A narrower change that converts the installed path to an absolute path without resolving symlinks would pass that parameter but fail symlink-first sharing; the current symlink test follows the fallback branch and would not detect it. This is the verified reason N1 survives. The production code currently uses `Path.resolve()` and no production failure was shown.

## C. Reuse Opportunities

No DRY finding survived. A targeted `rg` search found one `canonical_config_path` helper at `src/agentmap/runtime/lifespan_mixin.py:12`; `RuntimeManager._install` uses it for real container paths and the fallback delegates to `effective_config_file`, which also uses it. The current architecture is defensible because the two identity paths share one resolver. The suggested test exercises both paths without a new production abstraction.

## E. Tests Review

All six angles report exact 338-path coverage. Existing tests cover real-DI stored identity for default and relative explicit paths, plus symlink sharing through a mock container. The combined real-DI/symlink-first case is absent (N1). That is a useful regression test, not a demonstrated implementation failure. No concrete flaky or other mock-discipline defect was substantiated. This read-only consolidation did not execute tests.

## F. Quality Rubric

Scores are 0-5 in order: readability, maintainability, performance, testability, standards. This concise rubric covers the finding-bearing test and its production seam; historical logs are not given synthetic code-quality scores.

| file | readability | maintainability | performance | testability | standards | reason |
|---|---:|---:|---:|---:|---:|---|
| `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py` | 4 | 4 | 5 | 3 | 4 | The symlink matrix is clear, but mock installation bypasses the real-DI canonicalization branch. |
| `src/agentmap/runtime/runtime_manager.py` | 4 | 4 | 4 | 4 | 4 | The primary and fallback identity branches are explicit and share the canonical resolver; no code defect was found. |

No additional quality issue was substantiated. The cited project standard is `/home/jwwel/projects/agentmap/.worktrees/s010-b102-v16/claude.md`; no new standards violation was reported.

## G. Risk Hotspots

- **Configuration:** the untested real-DI symlink-first combination could allow a future alias regression (N1).
- **I/O:** path identity depends on symlink resolution; current `Path.resolve()` handles the production behavior.
- **Architecture:** one canonical resolver serves bootstrap identity and lease comparison, a defensible minimum design for this contract.

## H. Production Caller Chains

`RuntimeManager.initialize(config_file=alias)` → `_install` → real `initialize_di(alias)` → `container.config.path()` → `canonical_config_path` → stored `_runtime_config_file`. A subsequent `create_lifespan()` → `acquire_runtime_lifespan(None)` → `effective_config_file(None)` discovers and resolves the target path → compares with the stored identity. The new symlink test covers this comparison after mock installation, while N1 asks for the real installed-container branch.

## I. Triage Summary

**Non-blocker to triage:**

1. `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py:87` — `tests/unit/deployment/http/api/test_b102_lifespan_config_identity.py#TESTS#real-di-symlink-identity-counterfactual` — symlink sharing test bypasses the real installed-container identity branch. Add a real-DI symlink-first stored-path and default-lease sharing regression.

No blockers or nits. The host must disposition N1 under the project's finding triage rule; this read-only report creates no tracker entity.

## J. Verdict

**PASS-with-triage**

The complete six-angle review found no blocker in the pinned v23 candidate. N1 is a confirmed, narrow test gap after accounting for the existing real-DI relative-path assertion. This verdict reports code review evidence only; it does not establish QA, CI, live product acceptance, or release readiness.
