"""Shared service-name normalization helpers for declaration loading."""

import re
from typing import Iterable, List

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


def format_supported_declared_service_names() -> str:
    """Return a human-readable list of supported service names and aliases."""
    return "; ".join(
        f"{canonical} (aliases: {', '.join(aliases)})"
        for canonical, aliases in DECLARED_SERVICE_NAME_ALIASES.items()
    )


def normalize_declared_service_name(value: str) -> str:
    """
    Normalize a declared service token to its canonical internal service name.

    Raises:
        ValueError: If the token is not a known injectable service name.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"Service token must be a string, got {type(value).__name__}"
        )

    normalized = _normalize_service_token(value)
    canonical = _NORMALIZED_SERVICE_NAME_LOOKUP.get(normalized)
    if canonical:
        return canonical

    raise ValueError(
        f"Unknown service token '{value}'. Expected canonical names/aliases: "
        f"{format_supported_declared_service_names()}"
    )


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
