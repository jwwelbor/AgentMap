# AgentMap B102 release candidate review, v21

## A. Executive Summary

V21 changes the HTTP lifespan lease guard to compare both raw `config_file` arguments and adds explicit/default mismatch and same-explicit sharing tests. The candidate still lacks effective configuration identity: equal raw inputs can select different files, and different raw inputs can select the same file.

- **Verdict:** **FAIL**; high configuration risk.
- **Findings:** 1 blocker, 1 non-blocker, 0 nits. Four specialist findings reduce to one production root cause plus its distinct test coverage gap. The three source findings from angles A, B, and C are duplicates. Angle E's blocker-labeled test finding is retained as a non-blocker because the broken acceptance behavior is already counted in B1; its missing counterfactual is a separate test-craft issue.
- **Evidence mode / runner_mode:** `dispatched-six-angle`; **specialists_completed:** `6`; **consolidator_completed:** `true`; **adversarial_model:** `none`; **fallback_reason:** `none`.
- **Base commit:** `dc997387206552533b586c337add8d1b938676c7`; **head:** `39808f7698f3078cba962ca80fb5fe5947b89a00`.
- **Diff path:** `/tmp/agentmap-b102-release-review-v21-20261007/agentmap.diff`; **diff SHA256:** `043e37242930ce9f6ae177c44d54c44feefe857e84da33ef7ccf0dfb71f1bb7b`.
- **Manifest path:** `/tmp/agentmap-b102-release-review-v21-20261007/manifest.txt`; **manifest SHA256:** `4f91c395926d539a5e48f3c532032dec47bf71a5aa756f987198d5d090d9b58c`; **changed path count:** `335`.
- **Coverage and checks:** Each of six JSON artifacts declares completion and matches the exact root/base/head/diff/manifest pins. Each lists precisely all 335 manifest paths. A fresh Git diff reproduces the saved hash, and the manifest exactly matches `git diff --name-only base...head`. The consolidator inspected the cited source, tests, DI discovery, and `claude.md`. No tests were run.
- **Scope sanity:** 335 files, 32,904 insertions and 388 deletions exceed the review guide's 2,000-line split recommendation. The bulk is historical review and verification evidence; the v21 code delta is the B102 lease guard and its tests. A smaller future candidate would ease review. No coverage gap was found.

## B. Findings Table

| id | severity | file:line | rule | diagnosis | evidence | correction |
|---|---|---|---|---|---|---|
| B1 | Blocker; **CONFIRMED** | `src/agentmap/runtime/lifespan_mixin.py:31` | CORRECTNESS | The lease guard compares raw `config_file` values, not the effective file used by DI. Two `None` requests can select different `agentmap_config.yaml` files after a cwd change yet share the first container. Two equal relative strings can likewise resolve differently. Conversely, an explicit path and `None` can select the same file yet be rejected. This is one flawed compatibility rule with both unsafe sharing and false rejection. | `lifespan_mixin.py:31` compares raw values; `runtime_manager.py:191` stores the raw argument; `_initialize_in_transaction` returns on an existing container; `di/__init__.py:47-59,113-122` discovers from `Path.cwd()` for `None`. Angles A, B, C establish unsafe sharing; angle E documents the same-effective false rejection through the test gap. | Resolve and record the effective file identity, including system-default identity, within the serialized bootstrap boundary. Resolve each new lease request under the same rule before comparison. Share only when identities match; reject mismatches or unprovable identity. Cover cwd changes, same-effective default/explicit requests, and equal relative paths in changed cwd. |
| N1 | Non-blocker; **CONFIRMED** | `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py:155` | TESTS | The new default-after-explicit test mocks `initialize_di` and always expects rejection. It cannot prove the legitimate case where default discovery selects the same explicit file. The suite can pass with the false-rejection half of B1. | The test uses `first.yml`, then `None`, with a mocked installer; the same-explicit test uses equal strings. Neither invokes a faithful discovery seam. Angle E. | Use a temporary cwd and the real selection seam, or a faithful discovery stub, to assert same-effective default/explicit requests share the container, while different effective files are rejected. |

## C. Reuse Opportunities

No DRY finding survived. A targeted `rg` search found the existing `discover_config_file` in `src/agentmap/di/__init__.py:47` and its use by `initialize_di` at line 115. Reuse or centralize that selection rule so bootstrap and lease comparison cannot disagree. The v20 mixin extraction remains a defensible small structure for lifecycle ownership; the v21 raw-value guard is not defensible as the final compatibility contract because it changes app behavior under cwd changes.

## E. Tests Review

All six specialists report complete 335-path coverage. Their artifacts include source/test semantic inspection and historical evidence inspection. This read-only consolidation executed no tests and makes no test-pass claim.

The current tests cover different explicit strings, explicit followed by default with unconditional rejection, and equal explicit strings. They do not cover default/default across two cwd values, equal relative paths across two cwd values, or default/explicit requests resolving to the same file. Those are counterfactuals for the required effective-identity contract: a raw-string guard would pass the current tests while failing them. No separate flaky or mock-discipline finding was substantiated beyond N1's unfaithful discovery mock.

## F. Quality Rubric

Scores are 0-5 in order: readability, maintainability, performance, testability, standards. This concise rubric covers the finding-bearing files; the pinned angles provide the full path inspection record. Historical logs are not given synthetic code-quality scores.

| file | readability | maintainability | performance | testability | standards | reason |
|---|---:|---:|---:|---:|---:|---|
| `src/agentmap/runtime/lifespan_mixin.py` | 4 | 3 | 4 | 3 | 4 | The lease flow is compact, but raw argument comparison does not express the DI selection contract. |
| `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py` | 4 | 4 | 5 | 2 | 4 | Focused tests are readable, but mocked installation hides the effective-identity counterfactual. |

No additional quality defect was substantiated by the other angles. The repository standard at `claude.md` requires files no longer than 350 lines and methods no longer than 50; no new size finding was reported at v21.

## G. Risk Hotspots

- **Configuration/security:** a second app may inherit the first app's auth or provider configuration when cwd changes between default leases (B1). The wrong-container assignment is statically established; specific authorization impact depends on deployment.
- **Coupling:** DI configuration discovery and runtime lease compatibility have separate selection rules (B1).
- **Concurrency/I/O:** the serialized lease transaction makes effective identity resolution feasible at one boundary. No new cancellation or owner-loop defect was reported at this pin.

## H. Production Caller Chains

- `FastAPIServer.create_app` → `create_lifespan(config_file: str | None)` → `acquire_runtime_lifespan(config_file)` → `RuntimeLifespanMixin.acquire_lifespan` → raw comparison at line 31 → `_run_initialization_transaction(refresh=False)` → `_initialize_in_transaction`, which reuses an existing container. With `None` in both calls, the comparison passes even if the working directory changed and DI would discover another file.
- `initialize_di(config_file)` → explicit path selection or `discover_config_file()` → `Path.cwd()/agentmap_config.yaml` → `create_container(actual_config_path)`. This is the effective selection rule the lease guard must match.

## I. Triage Summary

**Blocker before QA:**

1. B1: compare resolved effective configuration identities for every lease; cover both unsafe sharing and false rejection.

**Non-blocker to triage:**

1. `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py:155` — `tests/unit/deployment/http/api/test_b102_lifespan_shutdown.py#TESTS#effective-config-discovery-counterfactual` — mocked default selection hides same-effective default/explicit sharing. Add a discovery-faithful positive case and differing-effective negative case.

No nits. The host must disposition N1 under the project's finding triage rule; this read-only report creates no tracker entity.

## J. Verdict

**FAIL**

The six-angle review is complete and pinned to one 335-path candidate. The raw configuration comparison can both share an incompatible runtime and reject a compatible one. Repair effective identity resolution and its boundary tests, then obtain a fresh pinned review before QA or release.
