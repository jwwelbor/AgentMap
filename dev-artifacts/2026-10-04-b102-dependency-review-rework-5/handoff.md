# B102 AgentMap dependency review rework 5

Date: 2026-10-04. Branch: `fix/wwgm-b102-physical-attempts`.
Implementation commit: `4e55e178a5cdb605baf52f5bf87ef925bac1d9c4`.
Review input: WWGM `dev-artifacts/2026-10-04-0148-b102-dependency-review-e522c02/REVIEW.md`, pinned AgentMap head `e522c02636b2c72ae0fcb04c9b1f2002ee37f2ea`.
Ownership contract: WWGM `docs/plan/decisions/DB-2026-10-04-b102-observed-client-lifecycle.md`.

## Finding disposition

All four blockers and both non-blockers from the pinned review were fixed in this dependency worktree.

| Finding | Repair and regression evidence |
| --- | --- |
| B102-R4-01 production lifecycle | `LLMServiceProtocol` now exposes awaited shutdown. The public runtime owns an awaited `shutdown_runtime()` boundary, synchronous refresh awaits the old container before replacement, and the FastAPI lifespan always awaits runtime shutdown after successful initialization. The host-shaped test creates a governed resource and proves it closes exactly once while the runtime is detached. |
| B102-R4-02 construction rollback | Governed construction now uses an explicit uncommitted owner. The async construction boundary awaits rollback before re-raising the original typed constructor error, and a cleanup failure is surfaced alongside that error in an `ExceptionGroup`. A failure-after-registration test proves both sync and async resources close, no owner/client is published, and a clean retry succeeds. |
| B102-R4-03 terminal shutdown | The factory marks itself closing before waiting for in-flight acquisitions and rejects ordinary or governed acquisition during and after shutdown with a stable `LLMConfigurationError`. A deterministic barrier test proves shutdown wins against in-flight construction, rolls its owner back, and refuses later construction. |
| B102-R4-04 cancellation ownership | Owner and factory cleanup run in shielded internal tasks. Caller cancellation is re-raised only after all pending resources/owners finish; injected cleanup cancellation cannot skip later entries. Tests cover cancellation at the first async resource and first factory owner, later entries, repeat shutdown, and exact-once close behavior. |
| B102-R4-05 per-key coordination | A short factory map lock selects one lock per cache key. Full wrapper construction runs outside the map lock, same-key callers share one client/owner, distinct keys cross deterministic barriers concurrently, and owner flow is explicit through the factory and all provider builders. The mutable `_constructing_resources` field is gone. |
| B102-R4-06 shared observation helpers | The four duplicate send/admit/observe methods now delegate to one sync and one async module helper while retaining the distinct Google shared, sync-only, and async-only transport ownership classes. Existing offline response-evidence coverage remains green. |

## Defect-class sweep

Class statement: asynchronous resources allocated or cleaned outside a terminal owner transaction can be leaked, detached, or admitted after shutdown.

- Construction surface: one governed factory entry and all three provider builders were enumerated. All four now pass the owner explicitly; no mutable factory construction owner remains.
- Coordination surface: same-key, different-key, in-flight-shutdown, post-shutdown, construction-failure, and clean-retry paths were enumerated and covered with deterministic barriers.
- Cleanup surface: the two cleanup loops (`ObservedResources` resources and factory owners) were enumerated. Both retain a shielded cleanup task through caller cancellation and close later entries exactly once.
- Production lifecycle surface: service protocol, service implementation, runtime replacement, and HTTP lifespan were enumerated. Each now participates in the awaited shutdown chain.
- Observation sibling surface: two sync and two async request methods were enumerated. All four delegate to the corresponding shared helper.
- Structural guards: the new tests fail if owner flow becomes implicit, per-key concurrency regresses, shutdown admits a late client, rollback publishes state, cancellation skips a later close, or the production lifespan stops awaiting runtime shutdown. Nothing was triaged out.

## Verification

All provider traffic used offline fakes or fake HTTP transports. No credentials or paid provider calls were used. Retained logs are under `verification/`.

| Command | Result | Log |
| --- | --- | --- |
| Focused LLM, lifecycle, fallback, and runtime suite | Pass: 334 collected tests | `focused.log` |
| `uv run black --check src tests` | Pass: 787 files unchanged | `black.log` |
| `uv run isort --check-only --sp pyproject.toml src tests` | Pass | `isort.log` |
| `make lint` | Pass | `lint.log` |
| `make test` | Pass: 5,663 passed, 48 skipped, 1 deselected, 6 warnings, 228 subtests passed | `make-test.log` |
| `make type-check` | Non-green inherited TD-052 baseline: 1,624 errors in 248 files | `mypy.log` |

The normalized mypy comparison contains 1,764 current error/note diagnostics versus 1,767 in the retained baseline: zero added and three removed. One removed diagnostic is the factory cache type annotation now supplied by the lifecycle mixin; the other two are an unrelated pandas import error/note pair in `runtime/workflow_ops.py`. The six full-suite warnings remain in unrelated suspend-agent and CLI tests and are reported rather than hidden. `git diff --cached --check` passed before the implementation commit.

## Parent control handoff

This is a dependency-local repair, not B102 acceptance. Keep B102 in development. Remaining ordered gates are a fresh exact-pin AgentMap review and package release; TD-140 ledger and immutable-payload durability; WWGM host integration and restart reconciliation; terminal and process-death counterfactuals; then WWGM review, QA, CI, release, and product acceptance. The parent loop owns all Shark workflow transitions.

RECOMMENDED OUTCOME: blocked
