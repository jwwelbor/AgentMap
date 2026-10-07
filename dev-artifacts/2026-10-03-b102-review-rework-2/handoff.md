# B102 AgentMap dependency review rework handoff

Scope: isolated `fix/wwgm-b102-physical-attempts` worktree only. Reviewed base
`dc997387206552533b586c337add8d1b938676c7`; incoming reviewed candidate
`9d3bf7ecda3f76efd60789ae044956aa7f4c06b2`. This handoff is a dependency
slice, not B102 host acceptance.

## Commits and result

- `caf00d43851e6bae0bf3d7c7634f90cbc5d29b07` closes the three named review
  findings: lifecycle and factory size, plus real-wrapper confidentiality coverage.
- `d1db68a7214d28b2b663cac56c32da876416835a` closes the confidentiality
  sibling exposed by the new test: a suppressed Python `__context__` still made
  the raw SDK exception reachable from the public error. Failure settlement now
  runs after leaving the raw provider exception handler. The test failed for
  OpenAI, Anthropic and Google before this change and passes afterward.
- `6bd4a1e756cd43f381ed5c3fe732a7c41f4fc7b3` makes the offline transport
  refuse a second request or an unexpected provider host. It also commits the
  first version of this handoff.

The public `call_llm_async` path still admits once and settles once. Existing
focused tests cover billed non-text cap refusal, unknown charge, primary and
fallback routing, SDK errors, capture errors, redirects, cancellation, timeout,
sealed collectors, concurrent task isolation and ordinary ungoverned calls.
The new offline real-wrapper case covers all three qualified providers with
fake HTTP, normal provider errors and simultaneous observer failures. It seeds
distinct body, authorization, response-header, URL-query, SDK exception,
HTTP-response repr, client repr and observer-error markers. Only the exact
body marker appears in `response_evidence.body`; outcome metadata, public
exception and its cause/context graph, captured logs, and instrumented OTEL
span exceptions/events have no marker. HTTPX and aiohttp unstubbed requests
fail closed. A six-case coverage run emitted zero synthetic markers in its
terminal report. No provider network or paid extraction was used.

## Defect-class sweep

**Class 1:** B102-expanded functions crossing AgentMap's 50-line limit.
Mechanically compared AST function spans across all 10 changed production
paths against the pinned base. The reviewed head had four newly crossing
functions: `invoke_governed_attempt`, the OpenAI and Google builders, and the
retry loop. The sweep also found two directly expanded factory siblings already
over 50 at base: `get_or_create_client` and the Anthropic builder. All six are
now at or below 50 lines: 49, 43, 41, 47, 44 and 49 respectively. The new
failure/success helpers are 28/15 lines, the confidentiality test is 47, and
the factory file is 288 lines (350 limit). A parametrized AST regression guards
13 task-owned functions. Inherited oversized `LLMService` bodies (including
the existing telemetry waiver) were inventoried but not refactored; their
preexisting behavior was outside this dependency review repair.

**Class 2:** Raw transport/SDK representations leaking through public error or
telemetry projections. The surface inventory is the three qualified provider
wrappers, ordinary SDK error and SDK-plus-observer-error modes (six fake-HTTP
cases), plus outcome, error, error-chain, logger, captured log and OTEL span
sinks. One sibling leak was found in the public exception's suppressed context
chain and fixed centrally in the governed lifecycle runner. The central
settlement path and six-case marker regression guard this class. No other
marker projection failed. Cancellation and no-response cases retain their
existing separate tests and semantics.

## Verification

Verification logs are retained locally in `verification/` under this folder.

| Check | Result | Log |
| --- | --- | --- |
| `make test` | 5,527 passed, 48 skipped, 1 deselected, 5 warnings, 228 subtests passed | `make-test-final.log` |
| `make lint` | passed | `make-lint-final.log` |
| `uv run black --check src/ tests/` | passed, 776 files unchanged | `black-check-final.log` |
| `uv run isort --check-only src/ tests/` | passed | `isort-check-final.log` |
| Provider-error `pytest --cov=agentmap --cov-report=term` | six cases passed; zero secret markers in coverage output | `provider-error-coverage.log` |
| `make type-check` | non-green inherited TD-052 baseline: 1,626 errors in 248 files | `make-type-check-final.log` |

Normalized mypy error/note diagnostics match the earlier
`dev-artifacts/2026-10-03-b102-review-rework/gate-mypy.log` exactly: 1,767
diagnostics on each side, zero added or removed after line-number normalization.
The 48 skips, deselection and five warnings are not test passes. `git diff
--check` passed. No live CI, release or WWGM quality gate is claimed.

## Remaining parent-owned gates

Review this corrected dependency candidate, release and integrate the AgentMap
commit through the accepted dependency route, then resume B102's WWGM host
integration. TD-140's ledger and immutable payload obligations, journal/plan-item
binding, and terminal/process-death counterfactuals remain required. Do not
advance B102 to pass or run paid extraction from this dependency-only evidence.

**RECOMMENDED OUTCOME: blocked.** The parent retains B102 development for the
unfinished host slice and owns all Shark workflow transitions.
