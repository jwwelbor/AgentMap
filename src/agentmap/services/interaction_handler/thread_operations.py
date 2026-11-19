"""Thread operations mixin."""

import pickle
import time
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, TypeGuard

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.human_interaction import HumanInteractionRequest
from agentmap.models.storage.types import StorageResult, WriteMode

from .bundle_utils import extract_bundle_info, extract_graph_name


def _is_metadata_mapping(value: object) -> TypeGuard[Dict[str, Any]]:
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _deserialize_metadata(data: bytes) -> Dict[str, Any]:
    metadata: object = pickle.loads(data)
    if not _is_metadata_mapping(metadata):
        raise ValueError("Thread metadata must be a string-keyed mapping")
    return metadata


class ThreadOperationsMixin:
    if TYPE_CHECKING:
        logger: Logger
        threads_collection: str

        def _write_collection(
            self,
            collection: str,
            data: Any,
            document_id: Optional[str] = None,
            mode: WriteMode = WriteMode.WRITE,
            **kwargs: Any,
        ) -> StorageResult[Any]: ...

        def _read_collection(
            self, collection: str, document_id: Optional[str] = None, **kwargs: Any
        ) -> Any: ...

        def _find_legacy_thread_file(self, thread_id: str) -> Optional[Path]: ...

    def _store_thread_metadata_suspend_only(
        self,
        thread_id: str,
        checkpoint_data: Dict[str, Any],
        bundle: Optional[GraphBundle] = None,
        bundle_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        thread_metadata = {
            "thread_id": thread_id,
            "graph_name": extract_graph_name(bundle, bundle_context, checkpoint_data),
            "bundle_info": extract_bundle_info(bundle, bundle_context),
            "node_name": checkpoint_data.get("node_name", "unknown"),
            "pending_interaction_id": None,
            "status": "suspended",
            "created_at": time.time(),
            "checkpoint_data": {
                "inputs": checkpoint_data.get("inputs", {}),
                "agent_context": checkpoint_data.get("agent_context", {}),
                "execution_tracker": checkpoint_data.get("execution_tracker"),
            },
        }
        result = self._write_collection(
            collection=self.threads_collection,
            data=pickle.dumps(thread_metadata),
            document_id=f"{thread_id}.pkl",
            mode=WriteMode.WRITE,
            binary_mode=True,
        )
        if not result.success:
            raise RuntimeError(
                f"Failed to store suspend thread metadata: {result.error}"
            )
        self.logger.debug(f"Stored suspend-only thread metadata for: {thread_id}")

    def _store_thread_metadata(
        self,
        thread_id: str,
        interaction_request: HumanInteractionRequest,
        checkpoint_data: Dict[str, Any],
        bundle: Optional[GraphBundle] = None,
        bundle_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        thread_metadata = {
            "thread_id": thread_id,
            "graph_name": extract_graph_name(
                bundle,
                bundle_context,
                checkpoint_data,
                fallback=interaction_request.node_name,
            ),
            "bundle_info": extract_bundle_info(bundle, bundle_context),
            "node_name": interaction_request.node_name,
            "pending_interaction_id": str(interaction_request.id),
            "status": "paused",
            "created_at": time.time(),
            "checkpoint_data": {
                "inputs": checkpoint_data.get("inputs", {}),
                "agent_context": checkpoint_data.get("agent_context", {}),
                "execution_tracker": checkpoint_data.get("execution_tracker"),
            },
        }
        result = self._write_collection(
            collection=self.threads_collection,
            data=pickle.dumps(thread_metadata),
            document_id=f"{thread_id}.pkl",
            mode=WriteMode.WRITE,
            binary_mode=True,
        )
        if not result.success:
            raise RuntimeError(f"Failed to store thread metadata: {result.error}")
        self.logger.debug(f"Stored thread metadata for: {thread_id}")

    def get_thread_metadata(self, thread_id: str) -> Optional[Dict[str, Any]]:
        try:
            file_data = self._read_collection(
                collection=self.threads_collection,
                document_id=f"{thread_id}.pkl",
                binary_mode=True,
            )
            if file_data:
                if not isinstance(file_data, bytes):
                    raise TypeError("Stored thread metadata must be bytes")
                return _deserialize_metadata(file_data)
            legacy_file = self._find_legacy_thread_file(thread_id)
            if legacy_file is None:
                return None
            with legacy_file.open("rb") as f:
                thread_data = _deserialize_metadata(f.read())
            self._write_collection(
                collection=self.threads_collection,
                data=pickle.dumps(thread_data),
                document_id=f"{thread_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )
            return thread_data
        except Exception as e:
            self.logger.error(
                f"Failed to retrieve thread metadata for {thread_id}: {str(e)}"
            )
            return None

    def _update_thread_status(
        self,
        thread_id: str,
        new_status: str,
        additional_fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            file_data = self._read_collection(
                collection=self.threads_collection,
                document_id=f"{thread_id}.pkl",
                binary_mode=True,
            )
            if not file_data:
                legacy_file = self._find_legacy_thread_file(thread_id)
                if not legacy_file:
                    return False
                with legacy_file.open("rb") as f:
                    file_data = f.read()
            if not isinstance(file_data, bytes):
                raise TypeError("Stored thread metadata must be bytes")
            thread_data = _deserialize_metadata(file_data)
            thread_data["status"] = new_status
            thread_data["pending_interaction_id"] = None
            if additional_fields:
                thread_data.update(additional_fields)
            result = self._write_collection(
                collection=self.threads_collection,
                data=pickle.dumps(thread_data),
                document_id=f"{thread_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )
            return result.success
        except Exception as e:
            self.logger.error(f"Error updating thread status for {thread_id}: {str(e)}")
            return False

    def mark_thread_resuming(
        self, thread_id: str, last_response_id: Optional[str] = None
    ) -> bool:
        fields: Dict[str, Any] = {"resumed_at": time.time()}
        if last_response_id:
            fields["last_response_id"] = last_response_id
        return self._update_thread_status(thread_id, "resuming", fields)

    def unmark_thread_resuming(self, thread_id: str) -> bool:
        """Reset a thread from 'resuming' back to a re-resumable state.

        Called when an async resume is cancelled after the thread was already
        marked 'resuming'.  Resetting the status to 'suspended' ensures a
        subsequent resume attempt is not blocked (REQ-F-009).

        Args:
            thread_id: Thread identifier to reset.

        Returns:
            True if the reset succeeded, False otherwise.
        """
        return self._update_thread_status(thread_id, "suspended", {})

    def mark_thread_completed(self, thread_id: str) -> bool:
        return self._update_thread_status(
            thread_id, "completed", {"completed_at": time.time()}
        )

    def cleanup_expired_threads(self, max_age_hours: int = 24) -> int:
        self.logger.info(f"Thread cleanup triggered (max age: {max_age_hours}h)")
        return 0
