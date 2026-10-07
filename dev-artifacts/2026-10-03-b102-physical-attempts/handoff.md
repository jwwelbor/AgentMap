# B102 dependency implementation handoff

The AgentMap dependency slice is implemented on `fix/wwgm-b102-physical-attempts`, based on `dc997387206552533b586c337add8d1b938676c7`. Return control to the parent for dependency review and TD-140 dispatch. **Keep WWGM B102 in development.** These results do not establish B102's host accounting, journal, plan-item binding, database durability, release, or product acceptance gates.

The implementation follows the accepted WWGM decision at `/home/jwwel/projects/wwgm/docs/plan/decisions/DB-2026-10-03-s010-physical-attempt-accounting.md`. No alternate platform, retry policy, or reservation was introduced. The dependency's older team instructions were superseded by the dispatch's single-worker ownership contract. No subagents, external AI CLIs, Shark transitions, publish, merge, or paid provider probes were run.

The public call is `LLMService.call_llm_async(..., attempt_lifecycle=host_lifecycle)`. `LLMServiceProtocol` exposes the same keyword. Import `LLMAttemptLifecycleProtocol` from `agentmap.services.protocols`; import its data-only `LLMAttemptDescription` and `LLMAttemptOutcome` from `agentmap.models.llm_attempt`.

The host implements:

```python
async def before_attempt(description: LLMAttemptDescription) -> str: ...
async def after_attempt(attempt_id: str, outcome: LLMAttemptOutcome) -> None: ...
```

`before_attempt` runs after local client/message/tool preparation and immediately before provider I/O, outside its timeout. The host returns its durably committed local attempt ID. The description contains `resolved_provider`, `resolved_model`, `attempt_kind` (`primary` or `fallback`), one-based `retry_ordinal` within that tier, `rates`, `catalog_version`, and that tier's `max_output_tokens`. The lifecycle is invocation-local through a ContextVar, explicitly bound to None for plain calls and reset in `finally`; the service stores no host repository or mutable job callback.

`after_attempt` receives a frozen outcome with independently nullable `usage`, `cost_usd`, and returned `provider_request_id`. It also carries `classification` and optional `error_type`, never raw response content or exception messages. Classifications emitted by the attempt runner are `text`, `empty`, `non_text`, `provider_error`, `timeout`, `cancelled`, `receipt_error`, and `normalization_error`. Usage and configured-catalog USD cost are collected independently before content normalization, so billed malformed results retain their evidence. Missing fields remain None; non-USD cost is unavailable in `cost_usd`. The host remains responsible for deciding whether that evidence is trustworthy and whether another call may be admitted.

Either hook can refuse with a host exception. AgentMap preserves that exact exception object at the public boundary and prevents retry, direct/routed fallback, tier fallback, and telemetry re-dispatch from treating it as a provider error. Telemetry records a fresh generic marker without the host exception chain. Completion is attempted once, including provider errors, timeout and cancellation. Cancellation during completion leaves the host's pending intent; it does not launch detached cleanup or authorize another attempt.

Governed clients have separate cache entries. OpenAI and Anthropic use SDK `max_retries=0`; Google uses total attempts `1`. Governed calls reject legacy/community wrapper substitutions. Google requires its 4.x wrapper generation, whose `max_retries` feeds `google-genai` total attempts; other generations fail closed pending qualification. The real installed wrappers were exercised with fake HTTP 429 and 500 responses. No ungoverned cached client's defaults are changed. AgentMap retry/backoff, the existing budget guard/receipt observer, and tool-bound fallback suppression remain in place. Sync, streaming, batch, and fan-out request-option surfaces reject the lifecycle option rather than silently forwarding or ignoring it.

The fake-HTTP evidence used `langchain-openai 1.1.14`, `openai 2.32.0`, `langchain-anthropic 0.3.21`, `anthropic 0.75.0`, `langchain-google-genai 4.0.0`, and `google-genai 1.55.0`, under Python 3.11.14. This qualifies the retained dependency environment, not every possible future dependency version.

The defect class is: an internal retry, fallback, or SDK retry can dispatch without fresh host admission and settlement of its predecessor. The sweep covered three SDK builders; the primary and fallback client creation paths; the provider retry loop; direct, routed, fallback-tier and telemetry exception boundaries; both lifecycle hooks; and sync/streaming/batch/fan-out entry surfaces. The shared attempt runner and isolated SDK retry policy are the structural guard. All findings in this dependency surface were fixed. Existing WWGM owners B102 and TD-140 retain the unfinished host and database work; no duplicate tracker item was created.

The 37 new regression cases exercise the public service entrypoint or real SDK wrappers. They cover JSON/tools non-text cap refusal, known billed normalization failure above/below cap, unknown provider outcomes, timeout and cancellation, exactly-once completion failure, fallback admission and tier limits, tool fallback suppression, routed host refusal, concurrent lifecycles, nested and later plain calls, receipt-calculation failure, malformed returned identity, interrupted settlement, unsupported entry surfaces, both cache-creation orders, and one HTTP request per governed SDK invocation. The new tests use synthetic providers and in-memory host policy, not WWGM repositories or a fake managed LLMService.

Validation is retained beside this report:

| Command/evidence | Result |
|---|---|
| `uv run --frozen pytest -o addopts= -q tests/fresh_suite/unit/services/llm/test_attempt_lifecycle.py` before production edits | 9 failed, 1 existing-behavior control passed; `red-lifecycle.log` |
| Governed client cache tests before implementation | 6 failed; `red-clients.log` |
| Added fallback/unsupported-entry regressions before their fixes | 3 failed, 6 passed; `red-boundaries.log` |
| Batch/returned-identity regressions before their fixes | 3 failed, 11 passed; `red-options.log` |
| Google generation rejection before its fix | 1 failed, 26 passed; `red-google-version.log` |
| Initial dependency focused selection plus first regressions | 211 passed, 6 subtests passed; `green-focused-1.log` |
| Expanded new regression selection | 37 passed; `green-expanded.log` |
| `uv run --frozen pytest --cov=agentmap --cov-report=xml -ra` on final code | 5,453 passed, 48 skipped, 1 benchmark deselected, 5 warnings, 228 subtests passed; `gate-pytest-final.log` |
| `uv run --frozen black --check src/ tests/` | Exit 0, 769 files unchanged; `gate-black-final.log` |
| `uv run --frozen isort --check-only src/ tests/` | Exit 0; `gate-isort-final.log` |
| `uv run --frozen flake8` on all 11 changed Python files | Exit 0; `gate-flake8-changed.log` |
| `git diff --check` | Exit 0 |
| `uv run --frozen mypy src` | **Non-green:** 1,626 errors in 248 files; `gate-mypy-final.log` |

Commands ran with `env -u VIRTUAL_ENV` to use the prepared worktree environment rather than WWGM's active environment. The documented AgentMap CI commands (pytest, Black, isort) passed locally. Live CI, its Python matrix, the `--all-extras` CI environment, dependency review/QA, package build/release, and WWGM gates have not been run by this worker. Full-suite skips include deliberately disabled live-provider and manual tests; exact reasons are in the `-ra` log. The five warnings are unawaited AsyncMock warnings in the existing suspend/messaging suite. This is not an all-tests-ran or warning-free claim.

Mypy is an additional repository-guidance check, not part of `.github/workflows/ci.yml`. A retained source export of the exact base produced 1,642 errors in the same 248 files (`baseline-mypy.log`). Two new argument-type diagnostics found during development were fixed. The final comparison has one changed diagnostic wording: the existing three provider-builder `Any | None` model-argument errors now occur at their shared builder call. Other decreases concern imported stubs/caching and are not claimed as typing repairs. The runtime patch introduces no new diagnostic category; global mypy remains failed. Disposition: no repository-wide typing repair in this dispatch, consistent with the already retained `/home/jwwel/projects/agentmap/dev-artifacts/2026-09-11-mypy-remediation/plan.md` and historical E06-F02 typing acceptance. The parent must retain this caveat and must not report a zero-error type gate. Raw comparison: `mypy-comparison.json`.

For the next parent steps:

1. Record the exact dependency commit returned with this handoff and link this report to WWGM B102/TD-140. Review the whole enumerated defect class, including lifecycle exceptions on fallback and telemetry paths.
2. Route TD-140 through its own workflow. Implement pending/reconciled/unknown/legacy ledger states, write-ahead visibility, admission state, idempotent exact-ID reconciliation, migration compatibility, caller rollback and abandoned-intent tests. This dependency slice implements none of that schema or SQL.
3. Resume B102 host integration against this exact isolated dependency candidate. Build the per-operation host lifecycle, remove duplicate managed receipt inserts, union unique attempt IDs across B041/B099, and carry accounting through errors, fragments, fsynced journals and terminal plan-item bindings. Run every counterfactual in the accepted decision, including real database durability.
4. Ship AgentMap only after review and required checks through its existing merge/PyPI workflow. Then update WWGM's minimum released version and lock and verify live CI. A local editable path is not release evidence. Keep paid extraction gated until the integrated B102/TD-140 gates pass.

The shared AgentMap checkout remains unchanged except for its pre-existing untracked `.worktrees/`; its `llm_service.py` SHA-256 remains `bc24e553436dbfb6b987463683abca85705bda6e43fcf76f4cbca36d8d98ee28`. The WWGM root gained a concurrent edit to `docs/council/escalations/e-s010-physical-attempt-accounting-20261003.yaml` during this dispatch; this worker did not alter it. Logs and the baseline export remain in this worktree's ignored artifact directory. The commit includes only the 11 task-owned Python paths plus this handoff.
