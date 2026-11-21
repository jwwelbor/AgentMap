"""Opt-in JSONL persistence for normalized physical LLM attempts."""

import asyncio
import json
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from agentmap.models.llm_attempt import LLMAttemptDescription, LLMAttemptOutcome


@dataclass(frozen=True)
class _PendingAttempt:
    request_datetime: datetime
    provider: str


class LLMAttemptFileLogger:
    """Write one sanitized JSONL record per governed provider attempt."""

    _SUCCESS = frozenset({"text", "empty", "non_text"})
    _SAFE_ERROR_TYPE = re.compile(r"[^A-Za-z0-9_.-]")

    def __init__(self, directory: Path, logging_service: Any):
        self._directory = directory
        self._logger = logging_service.get_class_logger(self)
        self._pending: Dict[str, _PendingAttempt] = {}
        self._pending_lock = threading.Lock()
        self._write_lock = threading.Lock()

    async def before_attempt(self, description: LLMAttemptDescription) -> str:
        return self.before_attempt_sync(description)

    def before_attempt_sync(self, description: LLMAttemptDescription) -> str:
        attempt_id = uuid.uuid4().hex
        with self._pending_lock:
            self._pending[attempt_id] = _PendingAttempt(
                request_datetime=datetime.now(timezone.utc),
                provider=description.resolved_provider,
            )
        return attempt_id

    async def after_attempt(self, attempt_id: str, outcome: LLMAttemptOutcome) -> None:
        await asyncio.to_thread(self.after_attempt_sync, attempt_id, outcome)

    def after_attempt_sync(self, attempt_id: str, outcome: LLMAttemptOutcome) -> None:
        with self._pending_lock:
            pending = self._pending.pop(attempt_id, None)
        if pending is None:
            return

        success = outcome.classification in self._SUCCESS
        response_datetime = outcome.response_datetime
        if response_datetime is None and (
            success or outcome.response_evidence.unavailable_reason != "no_response"
        ):
            response_datetime = datetime.now(timezone.utc)
        error_message = None
        if not success:
            error_type = self._SAFE_ERROR_TYPE.sub(
                "", outcome.error_type or "ProviderError"
            )
            error_message = f"Provider attempt failed ({error_type or 'ProviderError'})"

        cost_amount = outcome.cost_amount
        cost_currency = outcome.cost_currency
        if cost_amount is None and outcome.cost_usd is not None:
            cost_amount, cost_currency = outcome.cost_usd, "USD"

        record = {
            "request_datetime": pending.request_datetime.isoformat(),
            "response_datetime": (
                response_datetime.isoformat() if response_datetime else None
            ),
            "provider": pending.provider,
            "input_tokens": outcome.usage.input_tokens if outcome.usage else None,
            "output_tokens": outcome.usage.output_tokens if outcome.usage else None,
            "cost_usd": str(outcome.cost_usd) if outcome.cost_usd is not None else None,
            "cost_amount": str(cost_amount) if cost_amount is not None else None,
            "cost_currency": cost_currency,
            "was_success": success,
            "error_message": error_message,
        }
        try:
            self._append_record(pending.request_datetime, record)
        except OSError as error:
            self._logger.warning(
                "Local LLM attempt log write failed (%s)", type(error).__name__
            )

    def _append_record(
        self, request_datetime: datetime, record: Dict[str, Any]
    ) -> None:
        day = request_datetime.astimezone(timezone.utc).date().isoformat()
        path = self._directory / f"llm-calls-{day}.jsonl"
        serialized = json.dumps(record, separators=(",", ":"), ensure_ascii=True)
        with self._write_lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as output:
                output.write(serialized + "\n")
