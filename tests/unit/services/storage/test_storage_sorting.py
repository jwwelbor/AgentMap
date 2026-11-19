"""Shared ordering contract for JSON and in-memory document stores."""

import pytest

from agentmap.services.storage.memory.query_engine import QueryEngine
from agentmap.services.storage.memory_helpers import MemoryStorageHelpers


@pytest.mark.parametrize(
    "sort_documents",
    [QueryEngine.apply_query_filter, MemoryStorageHelpers.apply_query_filter],
)
def test_memory_query_paths_sort_mixed_values_consistently(sort_documents):
    documents = {
        "object": {"rank": {"nested": 1}},
        "string-z": {"rank": "z"},
        "number": {"rank": 3},
        "none": {"rank": None},
        "boolean": {"rank": False},
        "list": {"rank": ["a"]},
        "string-a": {"rank": "a"},
    }

    result = sort_documents(documents, {"sort": "rank"})

    assert list(result) == [
        "none",
        "boolean",
        "number",
        "string-a",
        "string-z",
        "list",
        "object",
    ]


@pytest.mark.parametrize(
    "sort_documents",
    [QueryEngine.apply_query_filter, MemoryStorageHelpers.apply_query_filter],
)
def test_memory_query_paths_ignore_malformed_sort_controls(sort_documents):
    documents = {"one": {"rank": 2}, "two": {"rank": 1}}

    result = sort_documents(documents, {"sort": ["rank"], "order": ["desc"]})

    assert list(result) == ["one", "two"]
