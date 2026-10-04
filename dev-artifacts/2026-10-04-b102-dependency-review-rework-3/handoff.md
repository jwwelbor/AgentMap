# B102 AgentMap dependency review rework 3

Date: 2026-10-04. Branch: `fix/wwgm-b102-physical-attempts`.
Implementation commit: `707973c2f23f2de89088421299d4bbb636579d24`.
Review input: WWGM `dev-artifacts/2026-10-04-0058-b102-dependency-review-b8f4135/REVIEW.md`, pinned AgentMap head `b8f41351a4235c7c21b016fc93b3db191c5b3f40`.
Ownership contract: WWGM `docs/plan/decisions/DB-2026-10-04-b102-observed-client-lifecycle.md`.

## Finding disposition

All seven B102-D4-R1 through R7 findings were fixed in this dependency worktree. No WWGM host code was changed.

| Finding | Repair and regression evidence |
| --- | --- |
| R1 negative usage | The calculator rejects every negative non-`None` count before pricing. Calculator and public lifecycle tests cover all four buckets at zero and positive rates; the known usage remains diagnostic, cost is unknown, and a second physical call is refused. |
| R2 observed-client ownership | OpenAI and Anthropic use separate sync/async observed transports; Google uses a lazy shared adapter. Factory cache construction is serialized; `clear_cache()` refuses governed resources before mutation; awaited factory and service shutdown detach clients and close owned pools once, remain idempotent, and report cleanup failure. Offline real wrappers cover all providers, both modes, cache reuse, credential rotation, direct/fallback calls, concurrent construction, shutdown, and late lazy use. |
| R3 cleanup discriminator | `LLMAttemptOutcome.cleanup_failed` and public `ResponseCaptureFailure.cleanup_failed` carry only a boolean. Public lifecycle tests cover sync/async read failure and cancellation, each with successful/failed cleanup, partial evidence, one settlement, and no raw secret in the outcome or public error. |
| R4 test size | The fallback credential scenario was split into focused transport, setup, and closure helpers. The structural guard now discovers every B102-marked test module and checks every function against the 50-line limit, plus the 350-line module limit. |
| R5 calculator test cohesion | The empty-catalog version assertion now lives in the existing empty-catalog case; the one-test private-import module was removed. |
| R6 cost docs | The public response documentation now states missing-required-count, absent optional-cache-count, and negative-count semantics. |
| R7 mypy evidence | The prior handoff now says 1,767 normalized diagnostics, matching both retained logs. The non-green 1,626-error/248-file result remains explicit. |

## Verification

All provider traffic was offline fake HTTP. Logs are in `verification/`.

| Command | Result | Log |
| --- | --- | --- |
| Focused LLM tests plus client-factory and service tests | Pass | `focused.log` |
| `uv run black --check src tests` | Pass; 783 files unchanged | `black.log` |
| `uv run isort --check-only --sp pyproject.toml src tests` | Pass | `isort.log` |
| `make lint` | Pass | `lint.log` |
| `make test` | Pass: 5,651 passed, 48 skipped, 1 deselected, 6 warnings, 228 subtests passed | `make-test.log` |
| `make type-check` | Non-green inherited TD-052 baseline: 1,626 errors in 248 files | `mypy.log` |

The 1,767 normalized mypy error/note diagnostics match the prior retained log exactly: zero added and zero removed (`mypy-normalized-comparison.log`). The six test warnings are in unrelated suspend-agent and CLI tests and are reported, not hidden. `git diff --cached --check` passed for the implementation commit. No paid provider call, live credential use, package publication, merge, WWGM host edit, or Shark workflow-state mutation occurred.

## Parent control handoff

This is a dependency-local pass, not B102 acceptance. Keep B102 in development. Remaining ordered gates: fresh exact-pin AgentMap review and package release; TD-140 ledger and immutable-payload durability; WWGM host integration and restart reconciliation; terminal/process-death counterfactuals; then WWGM review, QA, CI, release, and product acceptance. The parent loop owns all workflow transitions.

RECOMMENDED OUTCOME: blocked
