from __future__ import annotations

from typing import Iterable, Protocol

from agentmap.models.embeddings import EmbeddingInput, EmbeddingOutput, Metric


class EmbeddingService(Protocol):
    def embed_batch(
        self,
        items: Iterable[EmbeddingInput],
        model: str,
        metric: Metric = "cosine",
        normalize: bool = True,
    ) -> list[EmbeddingOutput]:
        """Embed a batch of texts. Implementations must be deterministic for a
        given (text, model) pair and return outputs with consistent dimensionality.
        """
        ...
