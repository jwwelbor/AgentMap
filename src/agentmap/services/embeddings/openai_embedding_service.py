from __future__ import annotations

import os
from typing import Any, Iterable

from agentmap.models.embeddings import EmbeddingInput, EmbeddingOutput, Metric

_openai_client_type: Any = None
try:
    # Use the official OpenAI client if available
    from openai import OpenAI

    _openai_client_type = OpenAI
except Exception:  # pragma: no cover - library optional in tests
    pass


class OpenAIEmbeddingService:
    """EmbeddingService implementation using OpenAI/Azure OpenAI.

    Environment:
      - OPENAI_API_KEY or Azure OpenAI compatible env
    """

    def __init__(self, client: Any = None):
        self._client = client or (
            _openai_client_type() if _openai_client_type is not None else None
        )
        api_key = os.getenv("OPENAI_API_KEY")
        if self._client is None and not api_key:
            raise RuntimeError(
                "OpenAIEmbeddingService requires openai client installed or OPENAI_API_KEY set"
            )

    @staticmethod
    def _maybe_normalize(vec: list[float], enable: bool) -> list[float]:
        if not enable:
            return vec
        import math

        n = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / n for x in vec]

    def embed_batch(
        self,
        items: Iterable[EmbeddingInput],
        model: str,
        metric: Metric = "cosine",
        normalize: bool = True,
    ) -> list[EmbeddingOutput]:
        if self._client is None:
            raise RuntimeError("OpenAI client not available")

        texts = [it.text for it in items]
        ids = [it.id for it in items]
        metas = [it.metadata for it in items]

        # New /embeddings API
        resp = self._client.embeddings.create(model=model, input=texts)
        vectors = [d.embedding for d in resp.data]
        if not vectors:
            return []
        dim = len(vectors[0])

        outs: list[EmbeddingOutput] = []
        for _id, _vec, _meta in zip(ids, vectors, metas):
            v = self._maybe_normalize(list(_vec), normalize)
            outs.append(
                EmbeddingOutput(
                    id=_id,
                    vector=v,
                    dim=dim,
                    model=model,
                    metric=metric,
                    metadata=_meta,
                )
            )
        return outs
