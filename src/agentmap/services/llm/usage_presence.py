"""Provider presence adapters and the shared governed accounting validator."""

import json
import math
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from agentmap.models.llm_attempt import LLMResponseEvidence
from agentmap.models.llm_cost import LLMModelRates
from agentmap.models.llm_execution import LLMUsage

_FIELDS: Dict[str, Tuple[str, Dict[str, str]]] = {
    "anthropic": (
        "usage",
        {
            "input_tokens": "input_tokens",
            "output_tokens": "output_tokens",
            "cache_creation_input_tokens": "cache_creation_input_tokens",
            "cache_read_input_tokens": "cache_read_input_tokens",
        },
    ),
    "openai": (
        "usage",
        {
            "input_tokens": "prompt_tokens",
            "output_tokens": "completion_tokens",
        },
    ),
    "google": (
        "usageMetadata",
        {
            "input_tokens": "promptTokenCount",
            "output_tokens": "candidatesTokenCount",
            "cache_read_input_tokens": "cachedContentTokenCount",
        },
    ),
}
_RATE_NAMES = {
    "input_tokens": "input_per_1m",
    "output_tokens": "output_per_1m",
    "cache_creation_input_tokens": "cache_write_per_1m",
    "cache_read_input_tokens": "cache_read_per_1m",
}
_CONTAINER_UNAVAILABLE = "_container_unavailable"


def _unique_object(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    decoded: Dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise ValueError("provider evidence contains a duplicate JSON key")
        decoded[key] = value
    return decoded


def _decode_usage_container(
    evidence: LLMResponseEvidence, container: str
) -> Optional[Dict[str, Any]]:
    """Distinguish unavailable containers from valid optional-field omission."""
    if not isinstance(evidence, LLMResponseEvidence):
        return None
    if evidence.body is None:
        return None
    try:
        payload = json.loads(evidence.body, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, TypeError):
        return None
    source = payload.get(container) if isinstance(payload, dict) else None
    return source if isinstance(source, dict) else None


def _provider_measurements(
    provider: str, source: Dict[str, Any], fields: Dict[str, str]
) -> Dict[str, Any]:
    """Copy present provider fields without validating or defaulting counts."""
    values = {target: source[key] for target, key in fields.items() if key in source}
    if provider == "openai" and "prompt_tokens_details" in source:
        details = source["prompt_tokens_details"]
        if isinstance(details, dict):
            if "cached_tokens" in details:
                values["cache_read_input_tokens"] = details["cached_tokens"]
        else:
            values["cache_read_input_tokens"] = None
    if provider == "google" and "thoughtsTokenCount" in source:
        values["output_tokens"] = (
            values.get("output_tokens"),
            source["thoughtsTokenCount"],
        )
    return values


def provider_usage_presence(
    provider: str, evidence: LLMResponseEvidence
) -> Optional[Dict[str, Any]]:
    """Copy present fields only; absence must survive SDK defaulting."""
    if (
        not isinstance(evidence, LLMResponseEvidence)
        or evidence.status != "available"
        or provider not in _FIELDS
    ):
        return None
    container, fields = _FIELDS[provider]
    source = _decode_usage_container(evidence, container)
    if source is None:
        return {_CONTAINER_UNAVAILABLE: True}
    return _provider_measurements(provider, source, fields)


def _measurement(value: Any) -> Optional[int]:
    if isinstance(value, tuple):
        components = [_measurement(part) for part in value]
        if any(part is None for part in components):
            return None
        return sum(part for part in components if part is not None)
    return value if type(value) is int and value >= 0 else None


def _negative_measurement(value: Any) -> bool:
    if isinstance(value, tuple):
        return any(_negative_measurement(part) for part in value)
    if type(value) is float and not math.isfinite(value):
        return False
    return type(value) in (int, float) and value < 0


def validate_usage_presence(values: Mapping[str, Any]) -> LLMUsage:
    """Validate measurements without depending on a rate catalog or pricing."""
    if not isinstance(values, Mapping):
        raise TypeError("usage measurements must be a mapping")
    return LLMUsage(**{field: _measurement(values.get(field)) for field in _RATE_NAMES})


def capture_measurements(
    provider: str,
    evidence: LLMResponseEvidence,
) -> Tuple[Optional[LLMUsage], Optional[Dict[str, Any]]]:
    values = provider_usage_presence(provider, evidence)
    if values is not None:
        return validate_usage_presence(values), values
    return None, None


def _required_buckets_are_priceable(
    usage: LLMUsage, values: Mapping[str, Any], rates: LLMModelRates
) -> bool:
    """Unavailable required measurements contribute zero only at a zero rate."""
    for field, rate_name in _RATE_NAMES.items():
        required = (
            field in {"input_tokens", "output_tokens"}
            or field in values
            or values.get(_CONTAINER_UNAVAILABLE, False)
        )
        if (
            required
            and getattr(usage, field) is None
            and getattr(rates, rate_name) != Decimal(0)
        ):
            return False
    return True


def _inclusive_cache_pricing_usage(
    usage: LLMUsage, values: Mapping[str, Any], provider: str
) -> Optional[LLMUsage]:
    """Subtract inclusive cache tokens in a pricing copy of the measurements."""
    if provider not in {"openai", "google"} or "cache_read_input_tokens" not in values:
        return usage
    cached, total = usage.cache_read_input_tokens, usage.input_tokens
    if cached is None or total is None or cached > total:
        return None
    return replace(usage, input_tokens=total - cached)


def pricing_usage(
    usage: Optional[LLMUsage],
    values: Optional[Mapping[str, Any]],
    provider: str,
    rates: Optional[LLMModelRates],
) -> Optional[LLMUsage]:
    """Determine priceability only after measurements have been published."""
    if values is None or not isinstance(values, Mapping):
        return None
    if rates is None:
        return None
    if any(_negative_measurement(value) for value in values.values()):
        return None
    assert usage is not None
    if not _required_buckets_are_priceable(usage, values, rates):
        return None
    return _inclusive_cache_pricing_usage(usage, values, provider)
