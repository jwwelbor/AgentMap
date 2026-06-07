"""
Thin wrapper over the Google Gemini Developer API Batch endpoint.

Isolates all provider I/O for batch execution from the service facade.
The ``google-genai`` SDK import is gated so a missing optional dependency
raises ``LLMDependencyError`` rather than a bare ``ImportError``.

Gemini-specific concerns handled here:
- Inline request submission via ``client.batches.create(model=..., src=[...])``
  where each src entry is a dict with ``contents`` and optional ``config``.
  NOTE: The real SDK signature is ``create(*, model, src, config=None)``,
  NOT ``create(model=, requests=)``.  Confirmed against:
  https://ai.google.dev/gemini-api/docs/batch-api
- Request-to-response correlation is **positional** (index-based) for inline
  batches — there is no ``key`` field on inline src entries.  The adapter
  maintains an ordered ``spec_id_list`` to map index → original spec_id.
- Status mapping: Gemini ``state`` is an enum; access via ``state.name``
  to get ``JOB_STATE_*`` strings → normalized ``LLMBatchStatus``.
- Result access: ``batch_job.dest.inlined_responses`` (NOT ``job.inline_responses``).
  Each item has a ``response`` attribute (GenerateContentResponse) or an
  ``error`` attribute.
- Cancellation: ``client.batches.cancel(name=...)`` is supported; set
  ``supports_cancel=True``.
- Usage normalization: ``usage_metadata.prompt_token_count`` → ``input_tokens``,
  ``candidates_token_count`` → ``output_tokens`` (no cache fields for Gemini).

Vertex AI (service-account / GCS / BigQuery) is explicitly out of scope.

Pattern mirrors ``openai_batch_adapter.py``.
"""

from typing import Any, Dict, Generator, List, Optional, Tuple

from agentmap.exceptions import LLMDependencyError, LLMServiceError
from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchResultRecord,
    LLMBatchStatus,
    LLMCallSpec,
    LLMExecutionError,
    LLMUsage,
)


class GeminiBatchAdapter:
    """
    Thin SDK wrapper for the Gemini Developer API Batch endpoint.

    The ``google-genai`` package import is deferred to ``__init__`` and gated
    in a ``try/except ImportError`` block.  If the package is absent,
    instantiation raises ``LLMDependencyError`` rather than letting a bare
    ``ImportError`` propagate.

    ``submit`` sends inline requests via ``client.batches.create(model=...,
    src=[...])``.  Results are read positionally from
    ``batch_job.dest.inlined_responses`` — there is no key-based demux for
    inline batches; the adapter preserves an ordered ``spec_id_list`` as
    the ``spec_id_map`` value (stored as a JSON-encoded list in the handle)
    to recover the original spec_ids by position.

    API reference: https://ai.google.dev/gemini-api/docs/batch-api

    The caller-facing return shape is the same as ``AnthropicBatchAdapter``
    and ``OpenAIBatchAdapter``:
    ``(provider_batch_id, spec_id_map, expires_at)``
    where ``expires_at`` is always ``None`` for inline Gemini batches and
    ``spec_id_map`` is ``{"__ordered__": json-list-of-spec-ids}`` for
    positional demux.
    """

    # Satisfies BatchAdapterProtocol class attributes.
    provider_name: str = "google"
    # Gemini Developer API supports cancel via client.batches.cancel(name=...).
    # Confirmed: https://ai.google.dev/gemini-api/docs/batch-api
    supports_cancel: bool = True

    # Gemini state is an enum; access state.name for the string value.
    # Unknown state values map to FAILED (deterministic, documented — D-3).
    # Confirmed state strings: https://ai.google.dev/gemini-api/docs/batch-api
    _STATUS_MAP: Dict[str, LLMBatchStatus] = {
        "JOB_STATE_PENDING": LLMBatchStatus.IN_PROGRESS,
        "JOB_STATE_RUNNING": LLMBatchStatus.IN_PROGRESS,
        "JOB_STATE_SUCCEEDED": LLMBatchStatus.ENDED,
        "JOB_STATE_FAILED": LLMBatchStatus.FAILED,
        "JOB_STATE_CANCELLED": LLMBatchStatus.CANCELED,
        "JOB_STATE_EXPIRED": LLMBatchStatus.EXPIRED,
    }

    def __init__(self, api_key: str, logger: Any) -> None:
        try:
            from google import genai  # noqa: PLC0415
        except ImportError:
            raise LLMDependencyError(
                "The 'google-genai' package is required for Gemini batch execution. "
                "Install it with: pip install google-genai"
            )
        self._client = genai.Client(api_key=api_key)
        self._logger = logger

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(
        self,
        specs: List[LLMCallSpec],
        resolved_params: List[Dict[str, Any]],
    ) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Submit an inline batch to the Gemini Developer API.

        ``resolved_params[i]`` contains the already conflict-free param dict for
        ``specs[i]`` (model, max_tokens, temperature, pass-throughs).  The
        adapter must NOT merge or apply ``setdefault`` against any other source
        (D-8: centralized resolver).  Provider-specific key renames
        (``max_tokens`` → ``max_output_tokens``) are applied here, after
        resolution.

        Results are correlated positionally (not by key), so the returned
        ``spec_id_map`` encodes the ordered spec_id list under
        ``{"__ordered__": [spec_id, ...]}``.

        Returns ``(provider_batch_id, spec_id_map, None)`` where ``None`` is
        the ``expires_at`` — Gemini inline batches do not expose an expiry.

        SDK signature confirmed:
        ``client.batches.create(*, model, src, config=None)``
        https://ai.google.dev/gemini-api/docs/batch-api
        """
        # Build ordered list for positional demux
        spec_id_list = [spec.spec_id for spec in specs]
        spec_id_map: Dict[str, Any] = {"__ordered__": spec_id_list}

        # Derive batch-level model from first resolved dict (all specs share a
        # batch-level model after conflict resolution; per-spec overrides are
        # identical or absent in the resolved dict).
        batch_model = resolved_params[0].get("model") if resolved_params else None
        src = self._build_src(specs, resolved_params, batch_model)

        # Real SDK: create(*, model, src, config=None)
        # NOT create(model=, requests=) — the old shape does not exist.
        response = self._client.batches.create(
            model=batch_model,
            src=src,
        )

        provider_batch_id = getattr(response, "name", None)
        if not provider_batch_id:
            raise LLMServiceError(
                "Gemini SDK returned a batch response with no 'name' field. "
                "The batch may or may not have been submitted — check the Gemini dashboard."
            )

        # Inline Gemini batches never return an expiry timestamp
        return provider_batch_id, spec_id_map, None

    def _build_src(
        self,
        specs: List[LLMCallSpec],
        resolved_params: List[Dict[str, Any]],
        batch_model: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        Build the inline src list for ``client.batches.create``.

        Each entry is a GenerateContentRequest-shaped dict with ``contents``
        and a ``config`` sub-dict (GenerateContentConfig).  There is no
        ``key`` field for inline src entries — correlation is positional.

        Config field names follow the python-genai SDK snake_case convention:
        ``max_output_tokens`` (renamed from resolved ``max_tokens``) and
        ``temperature``.  The rename is applied here, after central resolution
        (D-8: provider-specific renames happen after resolution, never as
        conflict resolution).

        ``resolved_params[i]`` is consumed directly — no merging or setdefault
        against spec fields or request_options.

        Reference: https://ai.google.dev/gemini-api/docs/batch-api
        """
        src = []
        for spec, rp in zip(specs, resolved_params):
            # Convert messages to Gemini contents format
            contents = []
            for msg in spec.messages:
                role = msg.get("role", "user")
                # Gemini uses "model" for assistant; map accordingly
                if role == "assistant":
                    role = "model"
                contents.append(
                    {"role": role, "parts": [{"text": msg.get("content", "")}]}
                )

            # Build generation config from resolved dict only — no merging.
            # Apply Gemini-specific rename: max_tokens → max_output_tokens.
            generation_config: Dict[str, Any] = {}
            if "max_tokens" in rp:
                generation_config["max_output_tokens"] = rp["max_tokens"]
            if "temperature" in rp:
                generation_config["temperature"] = rp["temperature"]
            # Pass through any non-model, non-max_tokens, non-temperature keys
            for k, v in rp.items():
                if k not in ("max_tokens", "temperature", "model"):
                    generation_config[k] = v

            src.append(
                {
                    "contents": contents,
                    "config": generation_config,
                }
            )
        return src

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    def poll(self, provider_batch_id: str) -> BatchPollResult:
        """
        Retrieve current batch status from the Gemini API.

        ``state`` is an enum; the string is accessed via ``state.name``.
        Returns a ``BatchPollResult`` with already-normalized ``LLMBatchStatus``.
        ``result_ref`` is always ``None`` for inline Gemini batches — results
        are read positionally from the job's dest in ``fetch_results``.
        Unknown ``state.name`` values map to ``LLMBatchStatus.FAILED``.

        SDK signature confirmed: ``client.batches.get(*, name)``
        https://ai.google.dev/gemini-api/docs/batch-api
        """
        # Real SDK: get(*, name=...) — keyword-only, NOT positional
        job = self._client.batches.get(name=provider_batch_id)

        state_obj = getattr(job, "state", None)
        # state is an enum; .name gives the JOB_STATE_* string
        raw_state = getattr(state_obj, "name", None) if state_obj is not None else None
        normalized_status = self._STATUS_MAP.get(raw_state, LLMBatchStatus.FAILED)
        if raw_state not in self._STATUS_MAP:
            self._logger.warning(
                "GeminiBatchAdapter.poll: unknown state %r for batch %s — "
                "mapping to FAILED",
                raw_state,
                provider_batch_id,
            )

        return BatchPollResult(
            status=normalized_status,
            result_ref=None,  # Gemini inline batches have no result file
            ended_at=getattr(job, "end_time", None),
        )

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel(self, provider_batch_id: str) -> None:
        """
        Cancel an in-progress batch via ``client.batches.cancel(name=...)``.

        The Gemini Developer API supports cancellation.
        ``supports_cancel`` is ``True``; this method calls through to the SDK.

        SDK signature confirmed: ``client.batches.cancel(*, name)``
        https://ai.google.dev/gemini-api/docs/batch-api
        """
        # Real SDK: cancel(*, name=...) — keyword-only
        self._client.batches.cancel(name=provider_batch_id)

    # ------------------------------------------------------------------
    # Fetch results
    # ------------------------------------------------------------------

    def fetch_results(
        self,
        provider_batch_id: str,
        spec_id_map: Dict[str, Any],
        result_ref: Optional[str] = None,
    ) -> Generator[LLMBatchResultRecord, None, None]:
        """
        Read and yield results from a completed inline Gemini batch.

        Results live at ``batch_job.dest.inlined_responses`` (NOT
        ``job.inline_responses``).  Correlation is by **position** (index),
        matching the order of the original src list.  The ``spec_id_map``
        must contain ``{"__ordered__": [spec_id, ...]}``.

        ``result_ref`` is unused (always ``None`` for inline batches).

        Each inline response item has a ``response`` attribute
        (GenerateContentResponse) or an ``error`` attribute.

        SDK reference: https://ai.google.dev/gemini-api/docs/batch-api
        """
        # Recover ordered spec_id list from map
        spec_id_list: List[str] = spec_id_map.get("__ordered__", [])

        # Real SDK: get(*, name=...) — keyword-only
        job = self._client.batches.get(name=provider_batch_id)
        dest = getattr(job, "dest", None)
        # Results are at batch_job.dest.inlined_responses (NOT job.inline_responses)
        inlined_responses = (
            getattr(dest, "inlined_responses", None) if dest is not None else None
        ) or []

        for idx, item in enumerate(inlined_responses):
            # Positional demux: index in inlined_responses → spec_id_list[idx]
            if idx >= len(spec_id_list):
                self._logger.warning(
                    "GeminiBatchAdapter.fetch_results: response index %d has no "
                    "corresponding spec_id (spec_id_list length=%d) for batch %s "
                    "— skipping record",
                    idx,
                    len(spec_id_list),
                    provider_batch_id,
                )
                continue

            spec_id = spec_id_list[idx]

            # Check for item-level error first
            item_error = getattr(item, "error", None)
            if item_error is not None:
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type="provider_error",
                        message=str(item_error),
                        retryable=False,
                    ),
                )
                continue

            response = getattr(item, "response", None)
            if response is None:
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type="missing_response",
                        message=(
                            "Gemini returned an inline batch record with no response "
                            "payload — cannot determine result."
                        ),
                        retryable=False,
                    ),
                )
                continue

            # Extract text content from candidates[0].content.parts[0].text
            content: Optional[str] = None
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                first = candidates[0]
                parts = getattr(getattr(first, "content", None), "parts", None) or []
                if parts:
                    content = getattr(parts[0], "text", None)

            if not content:
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type="empty_content",
                        message=(
                            "Gemini returned a succeeded result with no text content — "
                            "treating as errored to avoid silent data loss."
                        ),
                        retryable=False,
                    ),
                )
                continue

            # Normalize usage: Gemini uses prompt_token_count/candidates_token_count
            usage: Optional[LLMUsage] = None
            usage_metadata = getattr(response, "usage_metadata", None)
            if usage_metadata is not None:
                usage = LLMUsage(
                    input_tokens=getattr(usage_metadata, "prompt_token_count", None),
                    output_tokens=getattr(
                        usage_metadata, "candidates_token_count", None
                    ),
                    # Gemini batch does not expose cache fields
                    cache_creation_input_tokens=None,
                    cache_read_input_tokens=None,
                )

            yield LLMBatchResultRecord(
                spec_id=spec_id,
                status="succeeded",
                provider="google",
                content=content,
                usage=usage,
            )
