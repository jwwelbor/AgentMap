# B102 response-evidence dependency handoff

Return control to the parent for dependency review and WWGM host integration. **Keep B102 in development; this slice does not establish B102 pass.**

Code commit: **`a625d16a578b295dde44566af6a8f83770419f61`**, branch `fix/wwgm-b102-physical-attempts`, worktree `/home/jwwel/projects/agentmap/.worktrees/s010-physical-attempts`. This commit preserves the earlier lifecycle commit `f34562f2eaf50ed2881d1c199b878eac17da8820` and documentation commit `c899c5d`.

The accepted contract is WWGM's `docs/plan/decisions/DB-2026-10-03-s010-physical-attempt-accounting.md`, including its raw-response supplement. The active B102 dispatch authorizes AgentMap response evidence only. No WWGM implementation, editable-dependency reference, schema, release, merge, Shark lease or workflow state was changed. No subagents or external AI CLIs were used.

## Interface for the next worker

Continue to pass `attempt_lifecycle=host_lifecycle` to `LLMService.call_llm_async`. The existing callback receives `after_attempt(attempt_id, outcome)`. Import `LLMResponseEvidence` from `agentmap.models.llm_attempt`; every `LLMAttemptOutcome` now includes `response_evidence`.

The frozen envelope contains `status` (`available`, `unavailable`, `partial`), `layer="http_entity_body"`, optional `body: bytes` with `repr=False`, nullable HTTP status/media-type token, and a bounded unavailable reason. Validation rejects inconsistent states and non-byte bodies. Available empty bytes differ from a missing response. Headers, request/client/SDK objects and exception representations are not exported. WWGM must hash and persist these exact bytes itself; AgentMap supplies no filesystem path, digest or competing identity.

The body is the complete entity supplied to the SDK parser after HTTP content decoding. Whitespace, Unicode, nulls, unknown provider fields, multiple text/tool blocks, invalid JSON and non-JSON error bodies survive independently of SDK/LangChain projection. It is neither a model dump nor compressed transfer/framing bytes. Interrupted uncompressed reads retain observed prefixes. Interrupted compressed reads explicitly report unavailable entity evidence rather than relabel compressed chunks as decoded bytes.

The collector is created only after successful admission and bound through a ContextVar. A cached transport stores no current job, attempt, response or body. Settlement seals the collector; late worker-thread responses cannot change it or attribute bytes to a later attempt. More than one observed response in an attempt is a capture failure, never last-response-wins. Sync/async transport close methods delegate to HTTPX; SDK clients retain their normal close ownership.

## Production wiring and failure behavior

Governed clients retain their separate cache/retry policy. OpenAI receives observed `http_client` and `http_async_client` instances. A narrow AgentMap-owned Anthropic wrapper subclass overrides only its two SDK construction properties to supply observed HTTPX clients; generation and normalization remain inherited. Google receives an explicit dual sync/async HTTPX transport through its supported `client_args` surface. That transport selects HTTPX through the real SDK's backend rule, even when aiohttp is installed; no production backend flag is patched.

Observation is qualified to the retained versions: `langchain-openai 1.1.14` / `openai 2.32.0`, `langchain-anthropic 0.3.21` / `anthropic 0.75.0`, and `langchain-google-genai 4.0.0` / `google-genai 1.55.0`. Other versions fail before physical dispatch until qualified. Governed streaming client creation fails explicitly. Unrelated ungoverned clients keep their defaults. No provider/model choice changed.

All received-body paths merge evidence into the mandatory settlement callback, including SDK parse failure, provider error, AgentMap receipt/normalization failure, timeout and cancellation. A complete body remains available after cancellation. Metadata observation failure preserves complete bytes, lets the SDK finish parsing so measured usage/cost can be collected, settles once with `classification="capture_error"` and `error_type="ResponseCaptureFailure"`, then raises a sanitized governance refusal. Interrupted reads also refuse after settlement. Host callback exceptions retain their existing identity and pass-through behavior. Governed provider errors retain their typed retry classification but expose generic messages, so error-body text does not reach ordinary error/log/telemetry projections.

The host must still perform ledger reconciliation and immutable body persistence independently before allowing another attempt. If either host obligation fails, retain the other's successful evidence and raise. This dependency implements no WWGM payload write, terminal manifest, SQL or process-death durability.

## Verification

All commands used `env -u VIRTUAL_ENV uv run --frozen` in the isolated dependency environment. Logs listed below remain beside this report.

| Check | Result | Evidence |
|---|---|---|
| Initial regression reproduction | Missing-envelope/body assertions failed; two providers exercised real wrappers over fake HTTPX | `red.log` |
| Observation failure and error-body disclosure regressions | 4 failures before fixes, 15 controls passed | `red-failure-controls.log` |
| Partial thread-read regression | 1 expected failure before prefix retention, 15 controls passed | `red-thread.log` |
| Governed streaming factory regression | 1 expected failure before rejection | `red-streaming.log` |
| `pytest -o addopts= -q tests/fresh_suite/unit/services/llm/test_response_evidence*.py tests/fresh_suite/unit/services/llm/test_governed_clients.py tests/fresh_suite/unit/services/llm/test_attempt_lifecycle*.py` | **78 passed** (41 new response-evidence cases plus 37 retained lifecycle/client cases) | `green-final-focused.log` |
| `pytest --cov=agentmap --cov-report=xml -ra` on final code | **5,494 passed**, 48 skipped, 1 deselected, 5 warnings, 228 subtests passed | `gate-pytest-final.log` |
| `black --check src/ tests/` | Pass; 774 files unchanged | `gate-black-final.log` |
| `isort --check-only src/ tests/` | Pass | `gate-isort-final.log` |
| `flake8 src/ tests/` | Pass, no diagnostics | `gate-flake8-all.log` |
| Flake8 on all changed Python paths | Pass | `gate-flake8-changed-final.log` |
| `git diff --check` | Pass | Worker execution |
| `mypy src` | **Non-green baseline:** 1,626 errors in 248 files; zero new or removed normalized diagnostics relative to the earlier slice | `gate-mypy-final.log`, `mypy-comparison.json` |

AgentMap **TD-052** remains the owner of the inherited mypy baseline. New annotation errors discovered here were fixed; no new typing regression is waived. Required dependency CI commands and full Flake8 pass locally; do not claim a zero-error type gate. Full-suite skips include disabled/manual/live-provider tests. Five pre-existing suspend/messaging AsyncMock warnings remain; this is not an all-tests-ran or warning-free claim. Live CI, its Python matrix/all-extras environment, dependency review/QA and package release have not run.

**Test-isolation incident:** In the first red run, Google's alternate aiohttp backend escaped the initial HTTPX-only fake transport. Synthetic invalid API-key requests reached Google and returned HTTP 400 `API_KEY_INVALID`; the retained log records this. No valid credential or paid extraction was used. Subsequent body tests exercise the actual production-wired HTTPX transport, assert fake HTTP request counts, and explicitly refuse unstubbed aiohttp requests without forcing Google's backend selection. Do not describe the entire initial reproduction as zero external HTTP.

The defect class is loss or misattribution of physical response evidence before parsing or across completion boundaries. The sweep covered all three provider builders, both HTTPX transport modes, primary/fallback construction, normal/error/receipt/normalization/cancellation/timeout settlement, cached-client ordering, concurrent calls, worker-thread late completion and unsupported streaming. One shared observer/collector and version-qualified construction provide the structural guard. Tests include real wrappers with fake low-level HTTPX transports, cap refusal after billed non-text, known normalization retries above/below cap, distinct managed-call bodies, real OpenAI-to-Anthropic fallback, interrupted reads, empty/decoded compressed bodies, secret-marker exclusion, host completion failure and late-thread sealing. Existing WWGM B102/TD-140 own the remaining persistence and integration work.

## Parent next steps

1. Review this exact dependency commit together with the retained lifecycle slice; audit the whole response-evidence defect class and production SDK construction. Retain the TD-052 type-gate caveat.
2. Dispatch B102 WWGM integration against this candidate and TD-140's committed persistence slice `9d3df38f`. TD-140 remains unresolved until real physical calls use those methods; this report does not advance it.
3. Implement immutable per-attempt body payloads, hashes/lengths, complete ordered manifests and terminal journal/plan-item binding. Cover successful/unresolved/fault terminals, independent ledger/file/terminal failures, conflicting or missing payloads, replay with zero new calls, and the combined real-database/process-death counterfactuals.
4. Keep paid extraction gated. Publish/release AgentMap only after review and required checks, then update WWGM's released minimum version/lock and verify CI. A local editable candidate is not release evidence.

The shared AgentMap checkout still has only its pre-existing untracked `.worktrees/`. Its `llm_service.py` SHA-256 remains `bc24e553436dbfb6b987463683abca85705bda6e43fcf76f4cbca36d8d98ee28`. All task changes are isolated in the authorized dependency worktree. Stop this dispatch here; the parent owns further work and workflow transitions.
