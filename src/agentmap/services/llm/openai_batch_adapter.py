"""
Thin wrapper over the OpenAI SDK Batch API.

Isolates all provider I/O for batch execution from the service facade.
The SDK import is gated so a missing optional dependency raises
``LLMDependencyError`` rather than a bare ``ImportError``.

OpenAI-specific concerns handled here:
- JSONL file staging: ``files.create(purpose="batch")`` before ``batches.create``
- Status mapping: OpenAI batch ``status`` → normalized ``LLMBatchStatus``
- Result demux: ``files.content(result_ref)`` → parse JSONL → map by ``custom_id``
- Usage normalization: ``prompt_tokens`` → ``input_tokens``, ``completion_tokens``
  → ``output_tokens`` (no cache fields for OpenAI)

Pattern mirrors ``anthropic_batch_adapter.py``.
"""

import json
from typing import Any, Dict, Generator, List, Optional, Tuple

from agentmap.exceptions import LLMDependencyError, LLMServiceError
from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchRequestCounts,
    LLMBatchResultRecord,
    LLMBatchStatus,
    LLMCallSpec,
    LLMExecutionError,
    LLMUsage,
)
from agentmap.services.llm._batch_ids import CUSTOM_ID_RE as _CUSTOM_ID_RE
from agentmap.services.llm._batch_ids import build_spec_id_map as _build_spec_id_map


class OpenAIBatchAdapter:
    """
    Thin SDK wrapper for the OpenAI Batch API.

    The ``openai`` package import is deferred to ``__init__`` and gated in a
    ``try/except ImportError`` block.  If the package is absent, instantiation
    raises ``LLMDependencyError`` rather than letting a bare ``ImportError``
    propagate.

    ``submit`` hides the mandatory two-step file-staging entirely:
    1. Build JSONL bytes (one line per spec).
    2. ``files.create(purpose="batch")`` → get ``input_file_id``.
    3. ``batches.create(input_file_id, ...)`` → get batch.

    The caller never sees a file id; the return tuple is
    ``(provider_batch_id, spec_id_map, expires_at)`` — same shape as
    ``AnthropicBatchAdapter.submit``.
    """

    # Satisfies BatchAdapterProtocol class attributes.
    provider_name: str = "openai"
    supports_cancel: bool = True

    # OpenAI batch.status → normalized LLMBatchStatus.
    # Unknown status values map to FAILED (deterministic, documented decision D-3).
    _STATUS_MAP: Dict[str, LLMBatchStatus] = {
        "validating": LLMBatchStatus.IN_PROGRESS,
        "in_progress": LLMBatchStatus.IN_PROGRESS,
        "finalizing": LLMBatchStatus.IN_PROGRESS,
        "completed": LLMBatchStatus.ENDED,
        "failed": LLMBatchStatus.FAILED,
        "expired": LLMBatchStatus.EXPIRED,
        "cancelling": LLMBatchStatus.CANCELING,
        "cancelled": LLMBatchStatus.CANCELED,
    }

    def __init__(self, api_key: str, logger: Any) -> None:
        try:
            import openai  # noqa: PLC0415
        except ImportError:
            raise LLMDependencyError(
                "The 'openai' package is required for batch execution. "
                "Install it with: pip install openai"
            )
        self._client = openai.OpenAI(api_key=api_key)
        self._logger = logger

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(
        self,
        specs: List[LLMCallSpec],
        resolved_params: List[Dict[str, Any]],
    ) -> Tuple[str, Dict[str, str], Optional[str]]:
        """
        Submit a batch to the OpenAI Batch API.

        ``resolved_params[i]`` contains the already conflict-free param dict for
        ``specs[i]`` (model, max_tokens, temperature, pass-throughs).  The
        adapter must NOT merge or apply ``setdefault`` against any other source
        (D-8: centralized resolver).

        Builds one JSONL line per spec, stages the file via ``files.create``,
        then calls ``batches.create``.  The file id never crosses the service
        boundary.

        Returns ``(provider_batch_id, spec_id_map, expires_at)`` where
        ``spec_id_map`` maps each caller ``spec_id`` to its ``custom_id``
        sent to OpenAI.
        """
        spec_id_map = _build_spec_id_map(specs, _CUSTOM_ID_RE)

        jsonl_bytes = self._build_jsonl(specs, spec_id_map, resolved_params)

        # Stage the file; file_id stays local — never returned to caller
        file_obj = self._client.files.create(
            file=("batch_requests.jsonl", jsonl_bytes),
            purpose="batch",
        )
        file_id = getattr(file_obj, "id", None)
        if not file_id:
            raise LLMServiceError(
                "OpenAI SDK returned a file response with no 'id' field. "
                "File staging may have failed — check OpenAI dashboard."
            )

        response = self._client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )

        provider_batch_id = getattr(response, "id", None)
        if not provider_batch_id:
            raise LLMServiceError(
                "OpenAI SDK returned a batch response with no 'id' field. "
                "The batch may or may not have been submitted — check OpenAI dashboard."
            )

        expires_at: Optional[str] = None
        if hasattr(response, "expires_at") and response.expires_at is not None:
            expires_at = str(response.expires_at)

        return provider_batch_id, spec_id_map, expires_at

    def _build_jsonl(
        self,
        specs: List[LLMCallSpec],
        spec_id_map: Dict[str, str],
        resolved_params: List[Dict[str, Any]],
    ) -> bytes:
        """
        Build JSONL bytes for the OpenAI Batch API.

        Each line is a JSON object with keys: ``custom_id``, ``method``,
        ``url``, ``body``.  The ``body`` follows the Chat Completions schema.

        ``resolved_params[i]`` is consumed directly — no merging or setdefault
        (D-8: centralized resolver).
        """
        # CR5-2: guard against silent truncation if lists ever misalign
        if len(specs) != len(resolved_params):
            raise LLMServiceError(
                f"specs/resolved_params length mismatch: {len(specs)} specs vs "
                f"{len(resolved_params)} resolved param dicts — this is a bug."
            )
        lines = []
        for spec, rp in zip(specs, resolved_params):
            custom_id = spec_id_map[spec.spec_id]
            body: Dict[str, Any] = {"messages": spec.messages}
            body.update(rp)  # model, max_tokens, temperature, pass-throughs

            record = {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            }
            lines.append(json.dumps(record).encode())

        return b"\n".join(lines)

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    def poll(self, provider_batch_id: str) -> BatchPollResult:
        """
        Retrieve current batch status from the OpenAI API.

        Returns a ``BatchPollResult`` with already-normalized ``LLMBatchStatus``.
        ``result_ref`` is set to ``output_file_id`` so the service can pass it
        straight to ``fetch_results`` without any extra mapping.
        Unknown ``status`` values map to ``LLMBatchStatus.FAILED``.
        """
        batch = self._client.batches.retrieve(provider_batch_id)

        counts: Optional[LLMBatchRequestCounts] = None
        if hasattr(batch, "request_counts") and batch.request_counts is not None:
            rc = batch.request_counts
            counts = LLMBatchRequestCounts(
                processing=getattr(rc, "processing", None),
                succeeded=getattr(rc, "succeeded", None),
                errored=getattr(rc, "errored", None),
                canceled=getattr(rc, "canceled", None),
                expired=getattr(rc, "expired", None),
            )

        raw_status = getattr(batch, "status", None)
        normalized_status = self._STATUS_MAP.get(raw_status, LLMBatchStatus.FAILED)
        if raw_status not in self._STATUS_MAP:
            self._logger.warning(
                "OpenAIBatchAdapter.poll: unknown status %r for batch %s — "
                "mapping to FAILED",
                raw_status,
                provider_batch_id,
            )

        output_file_id: Optional[str] = getattr(batch, "output_file_id", None)

        return BatchPollResult(
            status=normalized_status,
            request_counts=counts,
            result_ref=output_file_id,
            ended_at=getattr(batch, "ended_at", None),
        )

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel(self, provider_batch_id: str) -> None:
        """
        Cancel an in-progress batch.

        Delegates to ``client.batches.cancel()``.  The caller is responsible
        for polling afterwards to observe the status transition.
        """
        self._client.batches.cancel(provider_batch_id)

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
        Download and parse batch results from the OpenAI output file.

        ``result_ref`` must be the ``output_file_id`` from ``poll``.
        Results are demuxed by ``custom_id`` (not position) back to the
        caller's ``spec_id``.

        Yields ``LLMBatchResultRecord`` for each JSONL record.  Records whose
        ``custom_id`` is absent from ``spec_id_map`` are skipped (logged as
        a warning) to tolerate any extra records the provider may inject.
        """
        if result_ref is None:
            raise LLMServiceError(
                f"OpenAIBatchAdapter.fetch_results: batch {provider_batch_id!r} has no "
                "output_file_id — the batch completed but produced no retrievable output "
                "file. This is an error condition, not an empty result set. Check the "
                "OpenAI dashboard for details."
            )

        # Build reverse map: custom_id → original spec_id
        custom_to_spec: Dict[str, str] = {v: k for k, v in spec_id_map.items()}

        file_response = self._client.files.content(result_ref)
        raw_bytes: bytes = file_response.content

        for raw_line in raw_bytes.split(b"\n"):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                self._logger.warning(
                    "OpenAIBatchAdapter.fetch_results: failed to parse JSONL line: %s",
                    exc,
                )
                continue

            custom_id = item.get("custom_id")
            spec_id = custom_to_spec.get(custom_id) if custom_id else None

            if spec_id is None:
                self._logger.warning(
                    "OpenAIBatchAdapter.fetch_results: custom_id %r not in spec_id_map "
                    "— skipping record",
                    custom_id,
                )
                continue

            error_payload = item.get("error")
            response_payload = item.get("response")

            # Item-level error (the request itself failed)
            if error_payload:
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type=error_payload.get("code", "unknown"),
                        message=error_payload.get("message", ""),
                        retryable=False,
                    ),
                )
                continue

            if response_payload is None:
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type="missing_response",
                        message=(
                            "OpenAI returned a batch record with no response and no error "
                            "payload — cannot determine result."
                        ),
                        retryable=False,
                    ),
                )
                continue

            status_code = response_payload.get("status_code", 200)
            body = response_payload.get("body") or {}

            if status_code != 200:
                # HTTP-level error from the provider
                error_detail = body.get("error", {}) if isinstance(body, dict) else {}
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type=error_detail.get("code", "http_error"),
                        message=error_detail.get(
                            "message", f"HTTP {status_code} from OpenAI"
                        ),
                        retryable=False,
                    ),
                )
                continue

            # Parse successful response
            choices = body.get("choices") or []
            content: Optional[str] = None
            if choices:
                msg = choices[0].get("message") or {}
                content = msg.get("content")

            if not content:
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type="empty_content",
                        message=(
                            "OpenAI returned a succeeded result with no text content — "
                            "treating as errored to avoid silent data loss."
                        ),
                        retryable=False,
                    ),
                )
                continue

            # Normalize usage: OpenAI uses prompt_tokens/completion_tokens
            usage: Optional[LLMUsage] = None
            usage_raw = body.get("usage")
            if usage_raw:
                usage = LLMUsage(
                    input_tokens=usage_raw.get("prompt_tokens"),
                    output_tokens=usage_raw.get("completion_tokens"),
                    # OpenAI standard batches do not expose cache fields
                    cache_creation_input_tokens=None,
                    cache_read_input_tokens=None,
                )

            yield LLMBatchResultRecord(
                spec_id=spec_id,
                status="succeeded",
                provider="openai",
                model=body.get("model"),
                content=content,
                usage=usage,
            )
