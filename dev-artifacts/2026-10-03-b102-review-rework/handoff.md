# B102 AgentMap dependency review rework handoff

Branch: `fix/wwgm-b102-physical-attempts` in
`/home/jwwel/projects/agentmap/.worktrees/s010-physical-attempts`.
Reviewed predecessor: `770df282a2292bec99e5e93f219f604965f24ac9`.
Code repair: `03535978a5088dddb696dd8b3c4cc9e2473a1cd6`.
The earlier dependency commits `f34562f2` and `a625d16a` are preserved.

**Recommended outcome: return the corrected dependency candidate to review. Keep
B102 in development.** This dispatch repaired the four AgentMap findings from
the completed six-angle review; it did not implement WWGM host persistence,
advance Shark, repoint the editable dependency, publish, or merge.

## Findings and changes

1. **B1, Google redirect:** The qualified Google HTTPX client now sets
   `follow_redirects=False`. `ResponseCollector.start_request()` is a shared
   pre-dispatch guard in both transport modes, so a second request under one
   collector is refused before reaching HTTPX's underlying transport. A sealed
   collector refuses late requests. The first response body and HTTP status
   remain the evidence when a redirect is rejected.
2. **B2, capture plus SDK error:** The exception settlement now prioritizes
   `capture_error` and `ResponseCaptureFailure` when the collector failed,
   retaining known response/body and usage/cost fields. Ordinary provider
   failures, no-response timeouts, and cancellation preserve their existing
   classifications and sanitized public behavior.
3. **B3, factory size:** Only governed client construction moved to the
   existing `observed_clients.py`. The factory is 345 physical lines, under
   AgentMap's 350-line limit. Routing and cache ownership remain in the
   factory; all three provider version/retry controls remain covered.
4. **N1, duplicate body storage:** The redundant per-stream chunk list is
   gone. The collector retains one identity-body prefix during a read and
   releases it after complete body capture. Interrupted identity and compressed
   reads retain their distinct evidence rules.

## Defect-class sweep

Class: an SDK or transport can send another physical request after one host
admission, or settle a failed capture under a provider error, while extra body
buffers obscure the evidence cost. Mechanical surface: three governed provider
builders (OpenAI, Anthropic, Google), two transport modes, the public async
primary and fallback paths, both collector seal states, and success/error/
interrupted capture outcomes. The 3 x 2 provider/mode combinations have real
wrapper redirect tests; all three providers have public-service capture-plus-
SDK-error tests. The existing fallback and lifecycle tests cover both routing
paths and ordinary timeout/cancellation controls. The one confirmed redirect
instance was Google; all providers now share the pre-dispatch guard. The
observer failure classification existed in one exception path; it is fixed at
the shared settlement seam. Both stream modes used the duplicate accumulator;
both now use the collector. No sibling was deferred.

Structural guard: `ResponseCollector.start_request()` is called before every
observed sync/async HTTPX dispatch. Tests force redirect following back on in
the real Google wrapper and prove the guard still blocks the second wire call,
with one admission, one settlement, and the first response body. A late sealed
collector is also tested. All new HTTP tests fail closed on unstubbed HTTPX
and aiohttp paths; they use synthetic credentials and fake transports only.

## Verification

Commands ran in this worktree with `env -u VIRTUAL_ENV uv run --frozen`.
Logs below remain in this artifact directory. The test-first run had six
expected failures and three passing controls: Google redirected twice; all
three providers settled observer-plus-SDK errors as `provider_error`; and both
transport modes forwarded a second request. The new streamed-body release
assertion was added after the shared patch; `counterfactual-partial.log` records
its expected failure with the prior `record()` behavior restored in memory.

| Check | Exact result | Evidence |
|---|---|---|
| Focused lifecycle, wrapper, response, factory and budget selection | 211 passed, 6 subtests passed | `green-focused-final.log` |
| Full `pytest --cov=agentmap --cov-report=xml -ra` | 5,508 passed, 48 skipped, 1 deselected, 5 warnings, 228 subtests passed | `gate-pytest-final.log` |
| `black --check src/ tests/` | Passed, 775 files unchanged | `gate-black.log` |
| `isort --check-only --sp pyproject.toml src/ tests/` | Passed | `gate-isort.log` |
| `flake8 src/ tests/` | Passed | `gate-flake8-final.log` |
| `mypy src/` | Non-green inherited TD-052 baseline: 1,626 errors in 248 files; no added or removed normalized error/note diagnostics relative to `2026-10-03-b102-response-evidence/gate-mypy-final.log` | `gate-mypy.log` |
| `git diff --check` | Passed | Code commit preflight |

The 48 skips include manual and credential-dependent tests; the benchmark is
deselected. The five warnings are retained in the full log. Do not describe
the type check as green; AgentMap TD-052 owns its existing baseline. No new
typing diagnostic was introduced by this patch.

## Parent continuation

Review the exact corrected AgentMap candidate and audit the whole request-
dispatch and capture-settlement class, including the forced-redirect
counterfactual. Keep B102 in development until the review passes and WWGM uses
TD-140's committed persistence methods around real physical calls. WWGM still
owns immutable body payloads, manifests, terminal journal/plan-item binding,
combined database/process-death proof, and its own gates. Release, lock update,
live CI, and paid extraction remain gated. This handoff claims no B102 pass.
