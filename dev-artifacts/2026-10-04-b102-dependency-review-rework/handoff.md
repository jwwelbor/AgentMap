# B102 AgentMap dependency review rework

Date: 2026-10-04. Branch: `fix/wwgm-b102-physical-attempts`.
Task-owned implementation commit: `c236c9c39f86686a36991dbd25f2c2515bb4a7c8`.
Review input: WWGM `dev-artifacts/2026-10-03-2330-b102-dependency-review-35b3d6f/consolidated-body.md`, pinned AgentMap head `35b3d6fbee746bb28ab73c1f6d22ec9d00f1a2e4`.

## Disposition and repair

All five review findings were fixed under B102 in this isolated AgentMap worktree.

| Finding | Repair and counterfactual |
| --- | --- |
| B102-R1 credential collision | Cache identity now hashes the complete credential; no raw key enters a cache-key representation. Same-prefix credentials receive distinct clients for OpenAI, Anthropic and Google in ordinary/governed modes and both creation orders. Same-key reuse remains. A public fallback call proves that the selected credential's client dispatches instead of a prewarmed same-prefix client. The old exact-prefix cache tests were updated because their asserted behavior violated the accepted B102 isolation decision. |
| B102-R2 partial usage | Catalog cost is unknown when a chargeable input or output token bucket is missing. The measured partial usage remains on the outcome, and the public service's second physical call is refused. Existing two-bucket receipts continue to treat absent optional cache buckets as zero usage. |
| B102-R3 proxy bypass | `ObservedTransport` delegates through HTTPX clients so HTTPX retains environment proxy and `NO_PROXY` route selection; the Anthropic construction path also carries its explicit proxy. Offline real-wrapper tests cover all three providers, sync and async, proxy and bypass routes, one observed request and exact body capture. Anthropic's explicit proxy has both modes. Unstubbed aiohttp requests fail closed in these tests. |
| B102-R4 oversized test file | Provider-error confidentiality tests moved to `test_response_evidence_security.py`; the original and new modules have 228 and 175 lines. A structural test enforces the 350-line limit on both. |
| B102-N1 timing race | Both thread-timeout tests now wait for worker-start or recorded prefix progress before checking timeout sealing. A 0.5-second timeout is only the deadlock guard. |

The defect-class sweep covered complete credential identity across provider, mode, creation order and fallback selection; nullable input/output usage and the existing optional-cache contract; all qualified providers' sync/async environment and bypass routing plus Anthropic explicit routing; response-body and confidentiality controls; and both controlled late-thread timeout branches. The existing retry, redirect, cancellation, collector-sealing and provider-error suites ran in the focused and full checks.

## Verification

All commands used this worktree's `uv` environment and offline provider fakes. Logs are in `verification/`.

| Command | Result | Log |
| --- | --- | --- |
| Focused B102 ten-module pytest selection | Pass; 143 test cases | `focused.log` |
| `uv run black --check src tests` | Pass; 778 files unchanged | `black.log` |
| `uv run isort --check-only --sp pyproject.toml src tests` | Pass | `isort.log` |
| `make lint` | Pass | `lint.log` |
| `make test` | Pass: 5,559 passed, 48 skipped, 1 deselected, 6 warnings, 228 subtests passed | `make-test.log` |
| `uv run mypy src` | Non-green inherited TD-052 baseline: 1,626 errors in 248 files; `mypy.ini` parsing warning | `mypy.log` |

The 1,767 normalized mypy error/note diagnostics exactly match `dev-artifacts/2026-10-03-b102-review-rework-2/verification/make-type-check-final.log`: zero added and zero removed after line-number normalization. This comparison does not call the repository type check green. `git diff --check` passed before the implementation commit. No paid provider request, database mutation, publishing, merge, WWGM host edit, or Shark workflow-state command occurred.

## Parent control handoff

This is a repaired **dependency candidate**, not B102 acceptance. The parent retains B102 development. The remaining ordered gates are AgentMap review and package release; TD-140 ledger and immutable-payload durability; WWGM host integration and terminal/process-death counterfactuals; then the relevant WWGM review, QA, quality, and release checks. Do not use this dependency's green tests as proof that the managed non-text retry is fixed end to end.

RECOMMENDED OUTCOME: blocked
