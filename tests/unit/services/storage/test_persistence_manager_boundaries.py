"""Tests for validating JSON persistence payload shapes."""

import logging

import pytest

from agentmap.services.storage.memory.persistence_manager import PersistenceManager


@pytest.mark.parametrize("payload", ["[]", "null", "1", '"value"'])
def test_load_from_file_rejects_non_object_payloads(tmp_path, payload):
    persistence_file = tmp_path / "memory.json"
    persistence_file.write_text(payload, encoding="utf-8")

    manager = PersistenceManager(logging.getLogger(__name__))

    assert manager.load_from_file(str(persistence_file)) is None
