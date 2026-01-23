from agentmap.models.embeddings import EmbeddingOutput
from agentmap.services.vector.vector_storage_service import (
    InMemoryVectorIndex,
    VectorStorageService,
)


def test_roundtrip_inmemory_index():
    index = InMemoryVectorIndex()
    vss = VectorStorageService(index=index)

    vecs = [
        EmbeddingOutput(
            id="npc:ser-calen",
            vector=[1.0, 0.0, 0.0],
            dim=3,
            model="test",
            metric="cosine",
        ),
        EmbeddingOutput(
            id="loc:black-bridge",
            vector=[0.0, 1.0, 0.0],
            dim=3,
            model="test",
            metric="cosine",
        ),
    ]
    metas = [
        {"type": "npc", "name": "Ser Calen"},
        {"type": "location", "name": "Black Bridge"},
    ]

    res = vss.write_embedded(collection="wormwood", vectors=vecs, metadatas=metas)
    assert res.count == 2

    # query near Ser Calen
    hits = vss.query(query_vector=[0.99, 0.01, 0.0], k=1)
    assert hits and hits[0][0] == "npc:ser-calen"

    # filter by metadata
    hits = vss.query(query_vector=[0.01, 0.99, 0.0], k=1, filters={"type": "location"})
    assert hits and hits[0][0] == "loc:black-bridge"
