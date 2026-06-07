"""
Unit tests for LLMBatchHandle serialization and BatchHandleRepository persistence.

Covers:
- TC-AC1-03: handle.to_dict() is a plain dict; json.dumps() succeeds; no anthropic SDK types
- TC-AC2-03: BatchHandleRepository.load_from_dict preserves spec_id_map
- TC-AC9-01: saved JSON contains no api_key field
"""

import json
import os
import tempfile

import pytest

from agentmap.models.llm_execution import (
    LLMBatchHandle,
    LLMBatchRequestCounts,
    LLMBatchStatus,
)


def _make_handle(**kwargs):
    """Convenience factory for LLMBatchHandle in known states."""
    defaults = dict(
        agentmap_batch_id="amatch_test123",
        provider_batch_id="msgbatch_abc123",
        status=LLMBatchStatus.IN_PROGRESS,
        provider="anthropic",
        model="claude-sonnet-4-6",
        spec_id_map={"spec-1": "spec-1", "needs/sanitize": "a3f9c2"},
        results_url=None,
        expires_at="2026-06-08T00:00:00Z",
        request_counts=None,
    )
    defaults.update(kwargs)
    return LLMBatchHandle(**defaults)


class TestLLMBatchHandleSerialization:
    """TC-AC1-03: handle.to_dict() is a plain dict; json.dumps() succeeds."""

    def test_to_dict_returns_plain_dict(self):
        """to_dict() must return a plain dict with no non-serializable values."""
        handle = _make_handle()
        result = handle.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_is_json_serializable(self):
        """json.dumps(handle.to_dict()) must succeed without error."""
        handle = _make_handle()
        result = handle.to_dict()
        # Must not raise
        json.dumps(result)

    def test_to_dict_contains_no_api_key(self):
        """to_dict() must not contain 'api_key' key."""
        handle = _make_handle()
        result = handle.to_dict()
        assert "api_key" not in result

    def test_to_dict_contains_required_fields(self):
        """to_dict() must contain all required fields."""
        handle = _make_handle()
        result = handle.to_dict()
        assert result["agentmap_batch_id"] == "amatch_test123"
        assert result["provider_batch_id"] == "msgbatch_abc123"
        assert "spec_id_map" in result

    def test_to_dict_status_is_string(self):
        """Status in dict must be a string (not an enum), for JSON portability."""
        handle = _make_handle()
        result = handle.to_dict()
        assert isinstance(result["status"], str)


class TestBatchHandleRepositoryRoundTrip:
    """TC-AC2-03: BatchHandleRepository.load_from_dict preserves spec_id_map."""

    def test_load_from_dict_preserves_spec_id_map(self):
        """Restored handle spec_id_map must match original exactly."""
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        handle = _make_handle(
            spec_id_map={"my-spec": "my-spec", "needs/sanitize": "a3f9c2"}
        )
        data = handle.to_dict()
        restored = BatchHandleRepository.load_from_dict(data)
        assert restored.spec_id_map == {"my-spec": "my-spec", "needs/sanitize": "a3f9c2"}

    def test_load_from_dict_preserves_all_identity_fields(self):
        """Restored handle identity fields must match original."""
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        handle = _make_handle()
        data = handle.to_dict()
        restored = BatchHandleRepository.load_from_dict(data)
        assert restored.agentmap_batch_id == handle.agentmap_batch_id
        assert restored.provider_batch_id == handle.provider_batch_id
        assert restored.status == handle.status

    def test_load_from_dict_status_is_enum(self):
        """Restored handle status must be LLMBatchStatus enum, not a raw string."""
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        handle = _make_handle()
        data = handle.to_dict()
        restored = BatchHandleRepository.load_from_dict(data)
        assert isinstance(restored.status, LLMBatchStatus)


class TestBatchHandleRepositoryPersistence:
    """TC-AC9-01: BatchHandleRepository.save writes JSON without api_key field."""

    def test_save_writes_json_file(self):
        """save(handle) must write a JSON file to the batch directory."""
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        with tempfile.TemporaryDirectory() as tmp_path:
            repo = BatchHandleRepository(batch_dir=tmp_path)
            handle = _make_handle()
            repo.save(handle)
            expected_file = os.path.join(tmp_path, f"{handle.agentmap_batch_id}.json")
            assert os.path.exists(expected_file)

    def test_save_written_json_excludes_api_key(self):
        """JSON file must not contain 'api_key' key."""
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        with tempfile.TemporaryDirectory() as tmp_path:
            repo = BatchHandleRepository(batch_dir=tmp_path)
            handle = _make_handle()
            repo.save(handle)
            expected_file = os.path.join(tmp_path, f"{handle.agentmap_batch_id}.json")
            with open(expected_file) as f:
                json_data = json.loads(f.read())
            assert "api_key" not in json_data

    def test_save_written_json_has_correct_agentmap_batch_id(self):
        """JSON file must contain correct agentmap_batch_id."""
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        with tempfile.TemporaryDirectory() as tmp_path:
            repo = BatchHandleRepository(batch_dir=tmp_path)
            handle = _make_handle()
            repo.save(handle)
            expected_file = os.path.join(tmp_path, f"{handle.agentmap_batch_id}.json")
            with open(expected_file) as f:
                json_data = json.loads(f.read())
            assert json_data["agentmap_batch_id"] == handle.agentmap_batch_id

    def test_save_written_json_preserves_spec_id_map(self):
        """JSON file must contain spec_id_map matching handle."""
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        with tempfile.TemporaryDirectory() as tmp_path:
            repo = BatchHandleRepository(batch_dir=tmp_path)
            handle = _make_handle(spec_id_map={"s1": "s1", "s2/sub": "a1b2c3"})
            repo.save(handle)
            expected_file = os.path.join(tmp_path, f"{handle.agentmap_batch_id}.json")
            with open(expected_file) as f:
                json_data = json.loads(f.read())
            assert json_data["spec_id_map"] == {"s1": "s1", "s2/sub": "a1b2c3"}
