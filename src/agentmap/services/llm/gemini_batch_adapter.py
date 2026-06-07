"""
Thin wrapper over the Google Gemini Developer API Batch endpoint.

Isolates all provider I/O for batch execution from the service facade.
The ``google-genai`` SDK import is gated so a missing optional dependency
raises ``LLMDependencyError`` rather than a bare ``ImportError``.

Gemini-specific concerns handled here:
- Inline request submission: ``client.batches.create(model=..., requests=[...])``
  where each request carries a ``key`` (sanitized via ``GEMINI_KEY_RE``).
- Status mapping: Gemini ``JOB_STATE_*`` → normalized ``LLMBatchStatus``
- Result demux: inline responses (``job.inline_responses``) keyed by ``key``
  → map back to caller ``spec_id`` — no ``result_ref`` for inline batches.
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
from agentmap.services.llm._batch_ids import GEMINI_KEY_RE as _GEMINI_KEY_RE
from agentmap.services.llm._batch_ids import build_spec_id_map as _build_spec_id_map


class GeminiBatchAdapter:
    """
    Thin SDK wrapper for the Gemini Developer API Batch endpoint.

    The ``google-genai`` package import is deferred to ``__init__`` and gated
    in a ``try/except ImportError`` block.  If the package is absent,
    instantiation raises ``LLMDependencyError`` rather than letting a bare
    ``ImportError`` propagate.

    ``submit`` sends inline requests keyed by sanitized ``key`` (Gemini's
    per-request identifier).  Results are read directly from the inline
    response list returned by the job object — no separate download step and
    no ``result_ref`` (unlike OpenAI's file-backed approach).

    The caller-facing return shape is the same as ``AnthropicBatchAdapter``
    and ``OpenAIBatchAdapter``:
    ``(provider_batch_id, spec_id_map, expires_at)``
    where ``expires_at`` is always ``None`` for inline Gemini batches.
    """

    # Satisfies BatchAdapterProtocol class attributes.
    provider_name: str = "google"
    # Developer API batch cancellation support: set False until confirmed
    # supported; callers must check supports_cancel before calling cancel().
    supports_cancel: bool = False

    # Gemini JOB_STATE_* → normalized LLMBatchStatus.
    # Unknown state values map to FAILED (deterministic, documented — D-3).
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
        model: str,
        max_tokens: int,
        request_options: Dict[str, Any],
    ) -> Tuple[str, Dict[str, str], Optional[str]]:
        """
        Submit an inline batch to the Gemini Developer API.

        Each spec is converted to a request dict with a sanitized ``key`` field
        (Gemini's per-request identifier).  ``client.batches.create`` is called
        with the full request list.

        Returns ``(provider_batch_id, spec_id_map, None)`` where ``None`` is
        the ``expires_at`` — Gemini inline batches do not expose an expiry.
        ``spec_id_map`` maps each caller ``spec_id`` to its sanitized ``key``
        sent to Gemini.
        """
        spec_id_map = _build_spec_id_map(specs, _GEMINI_KEY_RE)

        requests = self._build_requests(
            specs, spec_id_map, model, max_tokens, request_options
        )

        response = self._client.batches.create(
            model=model,
            requests=requests,
        )

        provider_batch_id = getattr(response, "name", None)
        if not provider_batch_id:
            raise LLMServiceError(
                "Gemini SDK returned a batch response with no 'name' field. "
                "The batch may or may not have been submitted — check the Gemini dashboard."
            )

        # Inline Gemini batches never return an expiry timestamp
        return provider_batch_id, spec_id_map, None

    def _build_requests(
        self,
        specs: List[LLMCallSpec],
        spec_id_map: Dict[str, str],
        model: str,
        max_tokens: int,
        request_options: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Build the inline request list for ``client.batches.create``.

        Each entry has a ``key`` (sanitized spec_id) and a ``request`` dict
        following the Gemini GenerateContent schema with ``contents`` and
        ``generationConfig``.
        """
        requests = []
        for spec in specs:
            key = spec_id_map[spec.spec_id]
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

            generation_config: Dict[str, Any] = {"maxOutputTokens": max_tokens}
            effective_model = spec.model if spec.model is not None else model
            if spec.temperature is not None:
                generation_config["temperature"] = spec.temperature
            for k, v in request_options.items():
                generation_config.setdefault(k, v)

            requests.append(
                {
                    "key": key,
                    "model": effective_model,
                    "contents": contents,
                    "generationConfig": generation_config,
                }
            )
        return requests

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    def poll(self, provider_batch_id: str) -> BatchPollResult:
        """
        Retrieve current batch status from the Gemini API.

        Returns a ``BatchPollResult`` with already-normalized ``LLMBatchStatus``.
        ``result_ref`` is always ``None`` for inline Gemini batches — results
        are read from the job's inline response list in ``fetch_results``.
        Unknown ``state`` values map to ``LLMBatchStatus.FAILED``.
        """
        job = self._client.batches.get(provider_batch_id)

        raw_state = getattr(job, "state", None)
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
        Cancel an in-progress batch.

        ``supports_cancel`` is ``False`` for the Developer API; this method
        raises ``LLMServiceError`` so callers that skip the capability check
        receive an explicit failure rather than a silent no-op.
        """
        raise LLMServiceError(
            "GeminiBatchAdapter: the Gemini Developer API does not support "
            "batch cancellation.  Check supports_cancel before calling cancel()."
        )

    # ------------------------------------------------------------------
    # Fetch results
    # ------------------------------------------------------------------

    def fetch_results(
        self,
        provider_batch_id: str,
        spec_id_map: Dict[str, str],
        result_ref: Optional[str] = None,
    ) -> Generator[LLMBatchResultRecord, None, None]:
        """
        Read and yield results from a completed inline Gemini batch.

        Gemini inline batches store results directly on the job object via
        ``inline_responses``.  ``result_ref`` is unused (always ``None`` for
        inline batches) — results are always fetched by re-retrieving the job.

        Results are demuxed by ``key`` (not position) back to the caller's
        ``spec_id``.  Responses whose ``key`` is absent from ``spec_id_map``
        are skipped with a warning to tolerate any extra records the provider
        may inject.

        Yields ``LLMBatchResultRecord`` for each inline response.
        """
        # Build reverse map: key → original spec_id
        key_to_spec: Dict[str, str] = {v: k for k, v in spec_id_map.items()}

        job = self._client.batches.get(provider_batch_id)
        inline_responses = getattr(job, "inline_responses", None) or []

        for item in inline_responses:
            key = getattr(item, "key", None)
            spec_id = key_to_spec.get(key) if key else None

            if spec_id is None:
                self._logger.warning(
                    "GeminiBatchAdapter.fetch_results: key %r not in spec_id_map "
                    "for batch %s — skipping record",
                    key,
                    provider_batch_id,
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
