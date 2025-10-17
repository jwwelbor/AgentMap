"""Unit tests for the modern GraphCheckpointService implementation."""

import pickle
import unittest
from typing import Any, Dict, Optional
from unittest import mock

from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
from agentmap.services.storage.types import StorageResult, WriteMode


class InMemoryFileStorage:
    """Simple in-memory file storage stub mimicking FileStorageService."""

    def __init__(self):
        self._collections: Dict[str, Dict[str, bytes]] = {}

    def _bucket(self, collection: Optional[str]) -> Dict[str, bytes]:
        key = collection or ""
        return self._collections.setdefault(key, {})

    def write(
        self,
        *,
        collection: Optional[str],
        data: bytes,
        document_id: str,
        mode: WriteMode,
        binary_mode: bool = False,
    ) -> StorageResult:
        if not binary_mode:
            # Implementation always writes pickle bytes; enforce expectation
            raise ValueError("GraphCheckpointService should write in binary mode")
        self._bucket(collection)[document_id] = data
        return StorageResult(success=True)

    def read(
        self,
        *,
        collection: Optional[str],
        document_id: Optional[str] = None,
        binary_mode: bool = False,
    ) -> Any:
        bucket = self._bucket(collection)
        if document_id is None:
            # LangGraph checkpoint saver expects a sequence of filenames
            return list(bucket.keys())
        return bucket.get(document_id)

    def delete(
        self,
        *,
        collection: Optional[str],
        document_id: str,
    ) -> StorageResult:
        bucket = self._bucket(collection)
        bucket.pop(document_id, None)
        return StorageResult(success=True)

    def exists(
        self,
        *,
        collection: Optional[str],
        document_id: str,
    ) -> bool:
        return document_id in self._bucket(collection)


class TestGraphCheckpointServiceCore(unittest.TestCase):
    """Validate core behaviour of GraphCheckpointService."""

    def setUp(self) -> None:
        self.file_storage = InMemoryFileStorage()
        self.system_storage_manager = mock.Mock()
        self.system_storage_manager.get_file_storage.return_value = self.file_storage

        self.logging_service = mock.Mock()
        self.logger = mock.Mock()
        self.logging_service.get_class_logger.return_value = self.logger

        self.service = GraphCheckpointService(
            system_storage_manager=self.system_storage_manager,
            logging_service=self.logging_service,
        )

    def test_initialization_uses_file_storage_namespace(self):
        self.system_storage_manager.get_file_storage.assert_called_once_with(
            "checkpoints"
        )
        self.assertIs(self.service.file_storage, self.file_storage)

    def test_put_persists_checkpoint_document(self):
        config = {"configurable": {"thread_id": "thread-123"}}
        checkpoint = {"state": {"value": 1}, "versions_seen": {"node": {"a", "b"}}}
        metadata = {"source": "unit"}

        result = self.service.put(config=config, checkpoint=checkpoint, metadata=metadata)

        self.assertTrue(result["success"])
        stored = self.file_storage.read(collection="")
        self.assertEqual(len(stored), 1)
        document_id = stored[0]
        payload = pickle.loads(self.file_storage.read(collection="", document_id=document_id, binary_mode=True))

        self.assertIn("checkpoint", payload)
        self.assertIn("metadata", payload)
        restored_checkpoint = self.service.serde.loads_typed(payload["checkpoint"])
        self.assertIsInstance(restored_checkpoint["versions_seen"]["node"], list)

    def test_put_handles_storage_failure(self):
        self.service.file_storage.write = mock.Mock(
            return_value=StorageResult(success=False, error="boom")
        )

        config = {"configurable": {"thread_id": "thread-err"}}
        checkpoint = {"state": {}}
        metadata = {}

        result = self.service.put(config=config, checkpoint=checkpoint, metadata=metadata)

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.logger.error.assert_called()

    def test_get_tuple_returns_latest_checkpoint(self):
        config = {"configurable": {"thread_id": "thread-1"}}
        checkpoint1 = {"state": {"value": "first"}}
        checkpoint2 = {"state": {"value": "second"}}

        self.service.put(config=config, checkpoint=checkpoint1, metadata={"idx": 1})
        self.service.put(config=config, checkpoint=checkpoint2, metadata={"idx": 2})

        result = self.service.get_tuple(config)

        self.assertIsNotNone(result)
        self.assertEqual(result.checkpoint["state"]["value"], "second")
        self.assertEqual(result.metadata["idx"], 2)

    def test_get_tuple_returns_none_for_missing_thread(self):
        config = {"configurable": {"thread_id": "missing"}}
        self.assertIsNone(self.service.get_tuple(config))

    def test_get_tuple_handles_identical_timestamps(self):
        """Test that when timestamps are identical, latest file wins (insertion order)."""
        config = {"configurable": {"thread_id": "thread-timing"}}
        checkpoint1 = {"state": {"value": "first"}}
        checkpoint2 = {"state": {"value": "second"}}

        # Mock datetime to return the same timestamp for both checkpoints
        with mock.patch("agentmap.services.graph.graph_checkpoint_service.datetime") as mock_dt:
            fixed_time = "2025-10-15T12:00:00.000000"
            mock_dt.utcnow.return_value.isoformat.return_value = fixed_time

            self.service.put(config=config, checkpoint=checkpoint1, metadata={"idx": 1})
            self.service.put(config=config, checkpoint=checkpoint2, metadata={"idx": 2})

        # Should return the second checkpoint (latest by insertion order)
        result = self.service.get_tuple(config)

        self.assertIsNotNone(result)
        self.assertEqual(result.checkpoint["state"]["value"], "second")
        self.assertEqual(result.metadata["idx"], 2)

    def test_put_writes_saves_write_documents(self):
        config = {"configurable": {"thread_id": "thread-w"}}
        task_id = "task-7"
        writes = [("state", {"foo": "bar"})]

        self.service.put_writes(config=config, writes=writes, task_id=task_id)

        stored = self.file_storage.read(collection="writes")
        self.assertEqual(len(stored), 1)
        document_id = stored[0]
        payload = pickle.loads(
            self.file_storage.read(
                collection="writes", document_id=document_id, binary_mode=True
            )
        )
        raw_restored_writes = self.service.serde.loads_typed(payload["writes"])
        normalised_writes = [
            tuple(entry) if isinstance(entry, list) and len(entry) == 2 else entry
            for entry in raw_restored_writes
        ]
        self.assertEqual(normalised_writes, list(writes))
        self.assertEqual(payload["task_id"], task_id)

    def test_get_service_info_matches_new_contract(self):
        info = self.service.get_service_info()
        self.assertEqual(info["service_name"], "GraphCheckpointService")
        self.assertEqual(info["storage_type"], "pickle")
        self.assertTrue(info["storage_available"])
        self.assertTrue(info["capabilities"]["langgraph_put"])
        self.assertTrue(info["implements_base_checkpoint_saver"])


class TestInterruptResumeWorkflowCore(unittest.TestCase):
    """Backward-compatible checks for interrupt/resume models."""

    def test_execution_interrupted_exception_structure(self):
        from uuid import uuid4

        from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
        from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType

        thread_id = "workflow_test_thread"
        interaction_request = HumanInteractionRequest(
            id=uuid4(),
            thread_id=thread_id,
            node_name="test_node",
            interaction_type=InteractionType.TEXT_INPUT,
            prompt="Test prompt",
        )
        checkpoint_data = {"test": "data"}

        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        self.assertEqual(exception.thread_id, thread_id)
        self.assertEqual(exception.interaction_request, interaction_request)
        self.assertEqual(exception.checkpoint_data, checkpoint_data)
        self.assertIn(thread_id, str(exception))

    def test_human_interaction_request_structure(self):
        from uuid import uuid4

        from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType

        request_id = uuid4()
        request = HumanInteractionRequest(
            id=request_id,
            thread_id="test_thread",
            node_name="test_node",
            interaction_type=InteractionType.APPROVAL,
            prompt="Please approve",
            context={"key": "value"},
            options=["approve", "reject"],
            timeout_seconds=300,
        )

        self.assertEqual(request.id, request_id)
        self.assertEqual(request.thread_id, "test_thread")
        self.assertEqual(request.node_name, "test_node")
        self.assertEqual(request.interaction_type, InteractionType.APPROVAL)
        self.assertEqual(request.prompt, "Please approve")
        self.assertEqual(request.context["key"], "value")
        self.assertEqual(request.options, ["approve", "reject"])
        self.assertEqual(request.timeout_seconds, 300)

    def test_required_components_are_importable(self):
        try:
            from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
            from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
            from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
            from agentmap.services.interaction_handler_service import InteractionHandlerService
        except ImportError as exc:  # pragma: no cover - explicit failure for missing deps
            self.fail(f"Required component could not be imported: {exc}")


if __name__ == "__main__":
    unittest.main()
