# B102 AgentMap dependency review rework 2

Date: 2026-10-04. Branch: `fix/wwgm-b102-physical-attempts`.
Implementation commit: `6de01d848707fe288946e3a23822f66d4ec51efb`.
Review input: WWGM `dev-artifacts/2026-10-04-0020-b102-dependency-review-a9bd70b/REVIEW.md`, pinned AgentMap head `a9bd70bb3e4779eff4f4937ed1938746d64d70fa`.

## Disposition

All six surviving review findings were fixed under B102 in the existing isolated AgentMap worktree. The inherited oversized `test_llm_client_factory.py` observation remains no-action for the reason in the pinned review.

| Finding | Repair and counterfactual |
| --- | --- |
| B102-D3-01, missing required count | A missing input or output count is unknown unless its own catalog rate is explicitly zero. Absent, zero and positive rate matrices cover both buckets at calculator and public lifecycle boundaries. Unknown cost retains usage and refuses a second physical call. |
| B102-D3-02, oversized test module | Replaced the mocked fallback credential test with real wire-level tests in a separate module. `test_attempt_lifecycle_boundaries.py` is 331 lines. A structural guard now covers all B102-owned test modules, including the existing calculator test edited for the revised trust rule. |
| B102-D3-03, oversized calculator method | Extracted the required-bucket trust predicate; the structural guard now checks `LLMCostCalculator.calculate`. |
| B102-D3-04, credential isolation | Public direct and real fallback calls send both same-prefix credentials, in both orders, through offline real wrappers for OpenAI, Anthropic and Google. Assertions inspect provider-specific physical-request authentication, exact wire counts, cache-key secrecy and outcome representations. |
| B102-D3-05, interrupted response cleanup | Sync and async observation close/aclose the acquired HTTPX response after failed or cancelled reads. Tests retain partial bytes and the original failure, and expose cleanup failures as the original failure's cause. Transport-level tests prove acquired responses are released. |
| B102-D3-06, timing race | Worker-start and retained-prefix barriers now precede an injected timeout. The wall-clock waits are only deadlock guards, while the original sealed-response assertions remain. |

The existing quantization test now declares `output_tokens=0` so it tests quantization with a complete required-count input. Its former unspecified output count contradicts the accepted unknown-cost rule. The existing calculator test module was split below AgentMap's 350-line file limit, preserving its zero-catalog case in `test_cost_calculator_unconfigured.py`.

## Verification

All commands used this worktree's `uv` environment and offline provider fakes. Logs are in `verification/`.

| Command | Result | Log |
| --- | --- | --- |
| Focused B102/calculator pytest selection | Pass | `focused.log` |
| `uv run black --check src tests` | Pass; 782 files unchanged | `black.log` |
| `uv run isort --check-only --sp pyproject.toml src tests` | Pass | `isort.log` |
| `make lint` | Pass | `lint.log` |
| `make test` | Pass: 5,601 passed, 48 skipped, 1 deselected, 4 warnings, 228 subtests passed | `make-test.log` |
| `make type-check` | Non-green inherited TD-052 baseline: 1,626 errors in 248 files | `mypy.log` |

The 1,763 normalized mypy error/note diagnostics exactly match `dev-artifacts/2026-10-04-b102-dependency-review-rework/verification/mypy.log`: zero added and zero removed. This does not call type checking green. `git diff --cached --check` passed before the implementation commit. No paid provider call, database mutation, publishing, merge, WWGM host edit, or Shark workflow-state command occurred.

## Parent control handoff

This is a dependency repair candidate, not B102 acceptance. Keep B102 in development. The remaining ordered gates are fresh exact-pin AgentMap review and package release; TD-140 ledger and immutable-payload durability; WWGM host integration and terminal/process-death counterfactuals; then WWGM review, QA, quality, and release checks. Do not infer end-to-end managed non-text retry safety from these dependency checks.

RECOMMENDED OUTCOME: blocked
