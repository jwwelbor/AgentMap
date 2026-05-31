"""Shared service-name normalization helpers for declaration loading."""

import re
from typing import Iterable, List, Set

DECLARED_SERVICE_NAME_ALIASES = {
    "logging_service": ("logging_service",),
    "config_service": ("config_service",),
    "app_config_service": ("app_config_service",),
    "storage_config_service": ("storage_config_service",),
    "execution_tracking_service": ("execution_tracking_service",),
    "llm_service": ("llm_service", "llm", "LLMService"),
    "llm_routing_service": ("llm_routing_service",),
    "llm_routing_config_service": ("llm_routing_config_service",),
    "routing_cache": ("routing_cache",),
    "prompt_complexity_analyzer": ("prompt_complexity_analyzer",),
    "orchestrator_service": (
        "orchestrator_service",
        "orchestrator",
        "OrchestratorService",
    ),
    "storage_service_manager": (
        "storage_service_manager",
        "storage_service",
        "storage",
        "StorageService",
        "StorageServiceManager",
    ),
    "csv": ("csv", "csv_service", "CSVService"),
    "json": ("json", "json_service", "JSONService"),
    "vector": ("vector", "vector_service", "VectorService"),
    "file": ("file", "file_service", "FileService"),
    "blob_storage_service": (
        "blob_storage_service",
        "blob_storage",
        "blob",
        "BlobStorageService",
    ),
    "memory": ("memory", "memory_service", "MemoryService"),
    "prompt_manager_service": (
        "prompt_manager_service",
        "prompt_service",
        "prompt",
        "PromptService",
        "PromptManagerService",
    ),
    "node_registry": (
        "node_registry",
        "node_registry_service",
        "NodeRegistry",
        "NodeRegistryService",
    ),
}


def _normalize_service_token(value: str) -> str:
    """Normalize a service token for lookup."""
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


_NORMALIZED_SERVICE_NAME_LOOKUP = {
    _normalize_service_token(alias): canonical
    for canonical, aliases in DECLARED_SERVICE_NAME_ALIASES.items()
    for alias in aliases
}


def is_known_declared_service_name(value: str) -> bool:
    """Return True if the token maps to a known canonical injectable service."""
    if not isinstance(value, str):
        return False
    return _normalize_service_token(value) in _NORMALIZED_SERVICE_NAME_LOOKUP


def normalize_declared_service_name(value: str) -> str:
    """
    Normalize a declared service token to its canonical internal service name.

    Known aliases (e.g. ``LLMService`` -> ``llm_service``) are mapped to their
    canonical name. Unknown tokens are returned unchanged so that
    host-registered services and any service outside the built-in alias map
    pass through untouched; whether such a service actually exists is validated
    later, at injection time, where the registered service names are known.

    Raises:
        ValueError: If the token is not a string (a structural error).
    """
    if not isinstance(value, str):
        raise ValueError(f"Service token must be a string, got {type(value).__name__}")

    normalized = _normalize_service_token(value)
    return _NORMALIZED_SERVICE_NAME_LOOKUP.get(normalized, value)


def normalize_declared_service_names(values: Iterable[str]) -> List[str]:
    """
    Normalize a sequence of declared service tokens, preserving order.

    Duplicate canonical names are removed while preserving the first occurrence.
    """
    normalized: List[str] = []
    seen = set()

    for value in values:
        canonical = normalize_declared_service_name(value)
        if canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)

    return normalized


def expand_declared_service_names(values: Iterable[str]) -> Set[str]:
    """
    Expand declared service tokens into every name they may match at injection.

    For each token the result contains the original token **and** its canonical
    alias (when the token is a known built-in service). This lets the different
    injection consumers all resolve the same declaration:

    * core-service injection accepts either form (``llm`` or ``llm_service``),
    * storage injection keys on the bare canonical names (``csv``/``json``/...),
    * host-protocol injection matches the registered service name verbatim
      (e.g. a host service literally named ``file_service``).

    Keeping both forms avoids the collision where a host service shares a name
    with a built-in storage alias (``file_service`` -> ``file``): the canonical
    ``file`` satisfies storage while the original ``file_service`` still matches
    the host registration.
    """
    expanded: Set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue
        expanded.add(value)
        canonical = _NORMALIZED_SERVICE_NAME_LOOKUP.get(_normalize_service_token(value))
        if canonical:
            expanded.add(canonical)

    return expanded
