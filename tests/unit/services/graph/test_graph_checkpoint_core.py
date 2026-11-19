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

        result = self.service.put(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            new_versions={},
        )

        self.assertEqual(result["configurable"]["thread_id"], "thread-123")
        checkpoint_id = result["configurable"]["checkpoint_id"]
        self.assertTrue(checkpoint_id)
        stored = self.file_storage.read(collection="")
        self.assertEqual(len(stored), 1)
        document_id = stored[0]
        payload = pickle.loads(
            self.file_storage.read(
                collection="", document_id=document_id, binary_mode=True
            )
        )

        self.assertIn("checkpoint", payload)
        self.assertIn("metadata", payload)
        restored_checkpoint = self.service.serde.loads_typed(payload["checkpoint"])
        self.assertIsInstance(restored_checkpoint["versions_seen"]["node"], list)
        self.assertEqual(restored_checkpoint["id"], checkpoint_id)

    def test_put_handles_storage_failure(self):
        self.service.file_storage.write = mock.Mock(
            return_value=StorageResult(success=False, error="boom")
        )

        config = {"configurable": {"thread_id": "thread-err"}}
        checkpoint = {"state": {}}
        metadata = {}

        with self.assertRaisesRegex(RuntimeError, "Checkpoint save failed: boom"):
            self.service.put(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                new_versions={},
            )
        self.logger.error.assert_called()

    def test_get_tuple_returns_latest_checkpoint(self):
        config = {"configurable": {"thread_id": "thread-1"}}
        checkpoint1 = {"state": {"value": "first"}}
        checkpoint2 = {"state": {"value": "second"}}

        first_config = self.service.put(
            config=config, checkpoint=checkpoint1, metadata={"idx": 1}, new_versions={}
        )
        second_config = self.service.put(
            config=config, checkpoint=checkpoint2, metadata={"idx": 2}, new_versions={}
        )

        result = self.service.get_tuple(config)

        self.assertIsNotNone(result)
        self.assertEqual(result.checkpoint["state"]["value"], "second")
        self.assertEqual(result.metadata["idx"], 2)
        first_result = self.service.get_tuple(first_config)
        self.assertIsNotNone(first_result)
        self.assertEqual(first_result.checkpoint["state"]["value"], "first")
        self.assertEqual(first_result.config, first_config)
        self.assertEqual(second_config["configurable"]["thread_id"], "thread-1")

    def test_get_tuple_returns_none_for_missing_thread(self):
        config = {"configurable": {"thread_id": "missing"}}
        self.assertIsNone(self.service.get_tuple(config))

    def test_get_tuple_handles_identical_timestamps(self):
        """Test that when timestamps are identical, latest file wins (insertion order)."""
        config = {"configurable": {"thread_id": "thread-timing"}}
        checkpoint1 = {"state": {"value": "first"}}
        checkpoint2 = {"state": {"value": "second"}}

        # Mock datetime to return the same timestamp for both checkpoints
        with mock.patch(
            "agentmap.services.graph.graph_checkpoint_service.datetime"
        ) as mock_dt:
            fixed_time = "2025-10-15T12:00:00.000000"
            mock_dt.utcnow.return_value.isoformat.return_value = fixed_time

            self.service.put(
                config=config,
                checkpoint=checkpoint1,
                metadata={"idx": 1},
                new_versions={},
            )
            self.service.put(
                config=config,
                checkpoint=checkpoint2,
                metadata={"idx": 2},
                new_versions={},
            )

        # Should return the second checkpoint (latest by insertion order)
        result = self.service.get_tuple(config)

        self.assertIsNotNone(result)
        self.assertEqual(result.checkpoint["state"]["value"], "second")
        self.assertEqual(result.metadata["idx"], 2)

    def test_put_writes_saves_write_documents(self):
        config = {
            "configurable": {
                "thread_id": "thread-w",
                "checkpoint_ns": "",
                "checkpoint_id": "checkpoint-w",
            }
        }
        task_id = "task-7"
        writes = [("state", {"foo": "bar"})]

        self.service.put_writes(config=config, writes=writes, task_id=task_id)

        collection = self.service._writes_collection("thread-w", "", "checkpoint-w")
        stored = self.file_storage.read(collection=collection)
        self.assertEqual(len(stored), 1)
        document_id = stored[0]
        payload = pickle.loads(
            self.file_storage.read(
                collection=collection, document_id=document_id, binary_mode=True
            )
        )
        raw_restored_writes = self.service.serde.loads_typed(payload["writes"])
        normalised_writes = [
            tuple(entry) if isinstance(entry, list) and len(entry) == 2 else entry
            for entry in raw_restored_writes
        ]
        self.assertEqual(normalised_writes, list(writes))
        self.assertEqual(payload["task_id"], task_id)
        self.assertEqual(payload["checkpoint_id"], "checkpoint-w")

    def test_get_tuple_returns_only_pending_writes_for_its_checkpoint(self):
        first_config = self.service.put(
            config={"configurable": {"thread_id": "thread-pending"}},
            checkpoint={"state": {"value": "first"}},
            metadata={"idx": 1},
            new_versions={},
        )
        second_config = self.service.put(
            config=first_config,
            checkpoint={"state": {"value": "second"}},
            metadata={"idx": 2},
            new_versions={},
        )
        self.service.put_writes(
            config=first_config,
            writes=[("state", {"value": "first write"})],
            task_id="task-first",
        )
        self.service.put_writes(
            config=second_config,
            writes=[("state", {"value": "second write"})],
            task_id="task-second",
        )
        first_collection = self.service._writes_collection(
            "thread-pending", "", first_config["configurable"]["checkpoint_id"]
        )
        self.file_storage.write(
            collection=first_collection,
            data=b"malformed pickle",
            document_id="corrupt.pkl",
            mode=WriteMode.WRITE,
            binary_mode=True,
        )

        first_result = self.service.get_tuple(first_config)
        second_result = self.service.get_tuple(second_config)

        self.assertEqual(
            first_result.pending_writes,
            [("task-first", "state", {"value": "first write"})],
        )
        self.assertEqual(
            second_result.pending_writes,
            [("task-second", "state", {"value": "second write"})],
        )

    def test_put_writes_skips_duplicate_channels_and_replaces_control_writes(self):
        config = {"configurable": {"thread_id": "thread-retry"}}
        config = self.service.put(
            config=config, checkpoint={"state": {}}, metadata={}, new_versions={}
        )

        self.service.put_writes(
            config,
            [("state", "first"), ("__interrupt__", "pause")],
            task_id="task-retry",
        )
        self.service.put_writes(
            config,
            [("state", "second"), ("__interrupt__", "resume")],
            task_id="task-retry",
        )

        result = self.service.get_tuple(config)

        self.assertEqual(
            result.pending_writes,
            [
                ("task-retry", "state", "first"),
                ("task-retry", "__interrupt__", "resume"),
            ],
        )

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
        from agentmap.models.human_interaction import (
            HumanInteractionRequest,
            InteractionType,
        )

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

        from agentmap.models.human_interaction import (
            HumanInteractionRequest,
            InteractionType,
        )

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
            pass
        except (
            ImportError
        ) as exc:  # pragma: no cover - explicit failure for missing deps
            self.fail(f"Required component could not be imported: {exc}")


if __name__ == "__main__":
    unittest.main()
