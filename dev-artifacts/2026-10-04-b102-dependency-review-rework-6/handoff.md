# B102 AgentMap dependency review rework 6

Date: 2026-10-04. Branch: `fix/wwgm-b102-physical-attempts`.
Implementation commit: `8aa527447b7ebfed1b154739a54ae59d235d99d5`.
Review input: WWGM `dev-artifacts/2026-10-04-0218-b102-dependency-review-353b1b9/REVIEW.md`, pinned AgentMap head `353b1b9`.
Ownership contract: WWGM `docs/plan/decisions/DB-2026-10-04-b102-observed-client-lifecycle.md`.

## Finding disposition

The six blockers and four focused non-blockers from the pinned review were fixed in this dependency worktree. B102-R5-11 is no-action for this increment: the retained rework-5 mypy log remains unchanged as required provenance, and the new review can pin the incremental code/test/evidence diff without duplicating that inherited log.

| Finding | Repair and regression evidence |
| --- | --- |
| B102-R5-01 async refresh loop ownership | `ensure_initialized_async()` now awaits old-runtime shutdown on its caller loop and offloads only synchronous DI/cache work. A real governed owner asserts exact caller-loop cleanup during public async refresh. |
| B102-R5-02 repeated cancellation | `_active_governed` now stores the build/finalization task through publication or rollback. The acquisition waiter drains that task through repeated cancellation, and a double-cancel barrier proves later shutdown still finds and closes the allocated resource exactly once. |
| B102-R5-03 synchronous clear race | `clear_cache()` refuses before mutation when either committed owners or active governed lifecycle tasks exist. A barrier holds an allocated unpublished owner, proves ordinary cache state is retained, then proves awaited shutdown closes it. |
| B102-R5-04 partial startup rollback | Async initialization is one transaction. Failed or cancelled post-installation cache work detaches and awaits the newly installed runtime; startup plus cleanup failures remain together. FastAPI lifespan now awaits this public async transaction before publishing `app.state.container`. |
| B102-R5-05 mixed terminal outcomes | `TerminalTaskOutcome` separates caller cancellation from the terminal task result. Caller cancellation is re-raised with cleanup failure as its cause; resource and owner cancellation mixed with ordinary failure is reported in a `BaseExceptionGroup`; nested mixed owner failures cannot skip later owners. |
| B102-R5-06 factory method size | Provider-builder selection moved to `_client_builder`; `_create_langchain_client` is 45 lines. The AST guard now covers it. All changed production methods remain at or below 50 lines, and the factory remains below 350 lines. |
| B102-R5-07 construction plus rollback failure | A deterministic constructor failure after allocation plus rollback failure test asserts both errors and no published owner/client. The rollback boundary accepts mixed cancellation groups without losing the original construction failure. |
| B102-R5-08 deterministic shutdown ordering | The shutdown-wins regression uses an explicit entry event around `_finish_shutdown`; wall-clock scheduling is only the existing five-second deadlock ceiling around worker barriers. |
| B102-R5-09 shared terminal waiter | `await_terminal_task()` is the single repeated-cancellation-safe primitive used by both `ObservedResources.aclose()` and factory shutdown/acquisition ownership. |
| B102-R5-10 documented unit layout | The three review-added unit modules moved from `tests/fresh_suite/unit` into matching `tests/unit` paths. The B102 structural guard now discovers task-owned modules under both established roots. |

## Defect-class sweep

Class statement: a lifecycle operation is unsafe when cancellation, a nested mixed failure, or a synchronous cache mutation can make allocated governed resources undiscoverable before publication or terminal cleanup.

- Initialization surface: synchronous DI/cache work, public async refresh, FastAPI startup, partial installation, startup cancellation, rollback success, and rollback failure were enumerated. The async caller loop owns all awaited cleanup.
- Construction surface: same-key/different-key builds, unpublished allocated owners, repeated caller cancellation, shutdown during construction, post-shutdown acquisition, constructor failure, and rollback failure were enumerated. The build/finalization task is the authoritative tracked object.
- Cache surface: ordinary clear, committed governed owners, and active unpublished owners were enumerated. Governed state now refuses before ordinary cache mutation.
- Cleanup surface: sync resources, async resources, factory owners, caller cancellation, cleanup cancellation, ordinary failure, mixed/nested groups, later entries, repeated shutdown, and exact-once closure were enumerated. The shared terminal waiter and aggregate helper cover both owner layers.
- Structural surface: every B102-owned test module under both supported roots and every changed production function were measured. No changed function exceeds 50 lines and no B102-owned test module exceeds 350 lines.
- Provider behavior: no provider construction, response observation, retry, usage, cost, credential, proxy, or public cleanup-discriminator semantics changed. Verification used only existing offline fakes.

## Verification

All provider traffic used offline fakes or fake HTTP transports. No credentials, paid provider calls, database operations, package publication, merge, WWGM implementation edit, or Shark state command occurred. Exact logs are retained under `verification/`.

| Command | Result | Log |
| --- | --- | --- |
| Focused B102 LLM/lifecycle/runtime suite | Pass: 331 collected tests | `focused.log`, `focused-collect.log` |
| `uv run black --check src tests` | Pass: 790 files unchanged | `black.log` |
| `uv run isort --check-only --sp pyproject.toml src tests` | Pass | `isort.log` |
| `make lint` | Pass | `lint.log` |
| `make test` | Pass: 5,679 passed, 49 skipped, 1 deselected, 6 warnings, 228 subtests passed | `make-test.log` |
| `make type-check` | Non-green inherited TD-052 baseline: 1,623 errors in 248 files | `mypy.log` |

The normalized mypy comparison contains 1,763 current error/note diagnostics versus 1,764 at rework 5: zero added and one removed. The removed diagnostic was the prior `Any | None` provider-builder argument mismatch; this increment adds no type-check diagnostic. The six full-suite warnings remain in unrelated suspend-agent and CLI tests and are retained in the log. `git diff --cached --check` passed before the implementation commit.

## Parent control handoff

This is a dependency-local repair, not B102 acceptance. Keep B102 in development. Remaining ordered gates are fresh exact-pin six-angle review, AgentMap package release, TD-140 ledger/payload durability, WWGM host integration and restart reconciliation, terminal/process-death counterfactuals, then WWGM review, QA, CI, release, and product acceptance. The parent loop owns the Shark lease and every workflow transition.

RECOMMENDED OUTCOME: blocked
