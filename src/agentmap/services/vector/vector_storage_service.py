from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from agentmap.models.embeddings import EmbeddingOutput


class VectorIndex(Protocol):
    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None: ...
    def search(
        self, query: list[float], k: int, filters: dict[str, Any] | None = None
    ) -> list[tuple[str, float, dict[str, Any]]]: ...


@dataclass
class UpsertResult:
    count: int


class InMemoryVectorIndex:
    """Simple index for tests and local dev; cosine similarity only."""

    def __init__(self) -> None:
        self._vecs: dict[str, tuple[list[float], dict[str, Any]]] = {}

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math

        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        for i, v, m in zip(ids, vectors, metadatas):
            self._vecs[i] = (v, m)

    def search(self, query: list[float], k: int, filters: dict[str, Any] | None = None):
        items = []
        for _id, (vec, meta) in self._vecs.items():
            if filters:
                # simple AND over equality filters in metadata
                if any(meta.get(k) != v for k, v in filters.items()):
                    continue
            score = self._cosine(query, vec)
            items.append((_id, score, meta))
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:k]


class VectorStorageService:
    """Storage- and index-agnostic interface with pluggable backends.

    This service **does not** create embeddings; use EmbeddingService.
    """

    def __init__(self, index: VectorIndex | None = None):
        self._index = index or InMemoryVectorIndex()

    # --- New preferred path: write pre-embedded ---
    def write_embedded(
        self,
        collection: str,
        vectors: Iterable[EmbeddingOutput],
        metadatas: Iterable[dict[str, Any]] | None = None,
    ) -> UpsertResult:
        ids: list[str] = []
        vecs: list[list[float]] = []
        metas: list[dict[str, Any]] = []
        metadatas = list(metadatas or [])

        for i, emb in enumerate(vectors):
            ids.append(emb.id)
            vecs.append(emb.vector)
            metas.append(
                (metadatas[i] if i < len(metadatas) else {})
                | {"collection": collection, "model": emb.model}
            )

        self._index.upsert(ids, vecs, metas)
        return UpsertResult(count=len(ids))

    # --- Query on vectors ---
    def query(
        self,
        query_vector: list[float],
        k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        return self._index.search(query_vector, k, filters)
