"""
Thin wrapper over the Anthropic SDK batches API.

Isolates all provider I/O for batch execution from the service facade.
The SDK import is gated so a missing optional dependency raises
``LLMDependencyError`` rather than a bare ``ImportError``.

Pattern mirrors ``src/agentmap/services/llm_client_factory.py`` ~169–190.
"""

import hashlib
import re
from typing import Any, Dict, Generator, List, Optional, Tuple

from agentmap.exceptions import LLMDependencyError
from agentmap.models.llm_execution import (
    LLMBatchResultRecord,
    LLMCallSpec,
    LLMExecutionError,
    LLMUsage,
)

# Regex for valid Anthropic custom_id values.
_CUSTOM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _sanitize_spec_id(spec_id: str) -> str:
    """
    Return a provider-safe custom_id for ``spec_id``.

    If ``spec_id`` already matches ``^[a-zA-Z0-9_-]{1,64}$``, return it
    unchanged.  Otherwise derive a deterministic SHA-1 hex string truncated
    to 64 characters.
    """
    if _CUSTOM_ID_RE.match(spec_id):
        return spec_id
    return hashlib.sha1(spec_id.encode()).hexdigest()[:64]


class AnthropicBatchAdapter:
    """
    Thin SDK wrapper for ``client.messages.batches.*``.

    The ``anthropic`` package import is deferred to ``__init__`` and gated in a
    ``try/except ImportError`` block.  If the package is absent, instantiation
    raises ``LLMDependencyError`` rather than letting a bare ``ImportError``
    propagate.
    """

    def __init__(self, api_key: str, logger: Any) -> None:
        try:
            import anthropic  # noqa: PLC0415
        except ImportError:
            raise LLMDependencyError(
                "The 'anthropic' package is required for batch execution. "
                "Install it with: pip install anthropic"
            )
        self._client = anthropic.Anthropic(api_key=api_key)
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
        Submit a batch to the Anthropic Batches API.

        Returns ``(provider_batch_id, spec_id_map, expires_at)`` where
        ``spec_id_map`` maps each caller ``spec_id`` to its ``custom_id``
        sent to Anthropic.

        ``cache_control`` blocks inside ``spec.messages`` are passed through
        unchanged (caching IS supported in batches per research §5.1).
        """
        spec_id_map: Dict[str, str] = {}
        requests = []

        for spec in specs:
            custom_id = _sanitize_spec_id(spec.spec_id)
            spec_id_map[spec.spec_id] = custom_id

            params: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": spec.messages,  # cache_control blocks pass through
            }

            # Merge per-spec overrides (temperature, etc.) — not request_options keys
            if spec.model is not None:
                params["model"] = spec.model
            if spec.temperature is not None:
                params["temperature"] = spec.temperature

            # Pass through any extra request_options that are batch-compatible
            for k, v in request_options.items():
                params.setdefault(k, v)

            requests.append({"custom_id": custom_id, "params": params})

        response = self._client.messages.batches.create(requests=requests)

        expires_at: Optional[str] = None
        if hasattr(response, "expires_at") and response.expires_at is not None:
            expires_at = str(response.expires_at)

        return response.id, spec_id_map, expires_at

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    def poll(self, provider_batch_id: str) -> Dict[str, Any]:
        """
        Retrieve current batch status from the Anthropic API.

        Returns a plain dict with ``processing_status``, ``request_counts``,
        ``results_url``, and ``ended_at`` fields extracted from the SDK
        response.
        """
        batch = self._client.messages.batches.retrieve(provider_batch_id)

        counts: Optional[Dict[str, Any]] = None
        if hasattr(batch, "request_counts") and batch.request_counts is not None:
            rc = batch.request_counts
            counts = {
                "processing": getattr(rc, "processing", None),
                "succeeded": getattr(rc, "succeeded", None),
                "errored": getattr(rc, "errored", None),
                "canceled": getattr(rc, "canceled", None),
                "expired": getattr(rc, "expired", None),
            }

        return {
            "processing_status": getattr(batch, "processing_status", None),
            "request_counts": counts,
            "results_url": getattr(batch, "results_url", None),
            "ended_at": getattr(batch, "ended_at", None),
        }

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel(self, provider_batch_id: str) -> None:
        """
        Cancel an in-progress batch.

        Delegates to ``client.messages.batches.cancel()``.  The caller is
        responsible for polling afterwards to observe the status transition.
        """
        self._client.messages.batches.cancel(provider_batch_id)

    # ------------------------------------------------------------------
    # Fetch results
    # ------------------------------------------------------------------

    def fetch_results(
        self,
        provider_batch_id: str,
        spec_id_map: Dict[str, str],
    ) -> Generator[LLMBatchResultRecord, None, None]:
        """
        Stream JSONL batch results lazily from the Anthropic API.

        Yields ``LLMBatchResultRecord`` for each item, with ``spec_id``
        restored from ``spec_id_map`` (custom_id → original spec_id).
        ``cache_control`` metadata is preserved on the usage object.

        This is a generator — results are NOT loaded all into memory.
        """
        # Build reverse map: custom_id -> original spec_id
        custom_to_spec: Dict[str, str] = {v: k for k, v in spec_id_map.items()}

        for item in self._client.messages.batches.results(provider_batch_id):
            custom_id = item.custom_id
            spec_id = custom_to_spec.get(custom_id, custom_id)
            result = item.result

            if result.type == "succeeded":
                msg = result.message
                # Extract text content
                content: Optional[str] = None
                if hasattr(msg, "content") and msg.content:
                    first = msg.content[0]
                    content = getattr(first, "text", None)

                # Build usage
                usage_obj = getattr(msg, "usage", None)
                usage: Optional[LLMUsage] = None
                if usage_obj is not None:
                    usage = LLMUsage(
                        input_tokens=getattr(usage_obj, "input_tokens", None),
                        output_tokens=getattr(usage_obj, "output_tokens", None),
                        cache_creation_input_tokens=getattr(
                            usage_obj, "cache_creation_input_tokens", None
                        ),
                        cache_read_input_tokens=getattr(
                            usage_obj, "cache_read_input_tokens", None
                        ),
                    )

                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="succeeded",
                    provider="anthropic",
                    model=getattr(msg, "model", None),
                    content=content,
                    usage=usage,
                )

            elif result.type == "errored":
                error_data = getattr(result, "error", None)
                error: Optional[LLMExecutionError] = None
                if error_data is not None:
                    error = LLMExecutionError(
                        error_type=getattr(error_data, "type", "unknown"),
                        message=getattr(error_data, "message", ""),
                        retryable=False,
                    )
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=error,
                )

            elif result.type == "canceled":
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="canceled",
                )

            elif result.type == "expired":
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="expired",
                )

            else:
                # Unknown item type — yield as errored to avoid silent data loss
                yield LLMBatchResultRecord(
                    spec_id=spec_id,
                    status="errored",
                    error=LLMExecutionError(
                        error_type="unknown_result_type",
                        message=f"Unrecognised result type: {result.type!r}",
                        retryable=False,
                    ),
                )
