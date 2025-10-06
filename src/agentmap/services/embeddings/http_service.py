from __future__ import annotations

from typing import Iterable

import httpx

from agentmap.models.embeddings import EmbeddingInput, EmbeddingOutput, Metric


class HttpEmbeddingService:
    """Calls a remote /embed endpoint (e.g., Cloud Run GPU service).
    The endpoint should accept {texts, model, metric, normalize} and return
    {model, dim, metric, vectors} where vectors is a list[list[float]].
    """

    def __init__(
        self,
        base_url: str,
        timeout_s: float = 60.0,
        headers: dict[str, str] | None = None,
    ):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._headers = headers or {}

    def embed_batch(
        self,
        items: Iterable[EmbeddingInput],
        model: str,
        metric: Metric = "cosine",
        normalize: bool = True,
    ) -> list[EmbeddingOutput]:
        items = list(items)
        if not items:
            return []
        texts = [it.text for it in items]
        ids = [it.id for it in items]
        metas = [it.metadata for it in items]

        with httpx.Client(timeout=self._timeout, headers=self._headers) as client:
            r = client.post(
                f"{self._base}/embed",
                json={
                    "texts": texts,
                    "model": model,
                    "metric": metric,
                    "normalize": normalize,
                },
            )
            r.raise_for_status()
            data = r.json()

        dim = int(data.get("dim", 0))
        vectors = data.get("vectors", [])
        model_o = data.get("model", model)

        outs: list[EmbeddingOutput] = []
        for _id, _vec, _meta in zip(ids, vectors, metas):
            outs.append(
                EmbeddingOutput(
                    id=_id,
                    vector=list(map(float, _vec)),
                    dim=dim,
                    model=model_o,
                    metric=metric,
                    metadata=_meta,
                )
            )
        return outs
