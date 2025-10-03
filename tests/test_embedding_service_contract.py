from agentmap.models.embeddings import EmbeddingInput
from agentmap.services.embeddings.openai_embedding_service import OpenAIEmbeddingService
import os
import pytest


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_openai_embedding_shapes_and_norm():
    svc = OpenAIEmbeddingService()
    items = [EmbeddingInput(id="a", text="A wizard opens a portal."), EmbeddingInput(id="b", text="A warrior draws a blade.")]
    outs = svc.embed_batch(items, model="text-embedding-3-small")

    assert len(outs) == 2
    dim = outs[0].dim
    assert all(len(o.vector) == dim for o in outs)
    # normalized
    import math
    for o in outs:
        n = math.sqrt(sum(x * x for x in o.vector))
        assert 0.99 <= n <= 1.01
