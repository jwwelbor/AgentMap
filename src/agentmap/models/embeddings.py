from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Metric = Literal["cosine", "ip", "l2"]


@dataclass(frozen=True)
class EmbeddingInput:
    """Pure data container for text to embed."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingOutput:
    """Pure data container for produced vectors."""

    id: str
    vector: list[float]
    dim: int
    model: str
    metric: Metric
    metadata: dict[str, Any] = field(default_factory=dict)
