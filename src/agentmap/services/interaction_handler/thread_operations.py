"""Thread operations mixin."""

import pickle
import time
from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.human_interaction import HumanInteractionRequest
from agentmap.services.storage.types import WriteMode

from .bundle_utils import extract_bundle_info, extract_graph_name


class ThreadOperationsMixin:
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
                return pickle.loads(file_data)
            legacy_file = self._find_legacy_thread_file(thread_id)
            if legacy_file is None:
                return None
            with legacy_file.open("rb") as f:
                thread_data = pickle.load(f)
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
            thread_data = pickle.loads(file_data)
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
        fields = {"resumed_at": time.time()}
        if last_response_id:
            fields["last_response_id"] = last_response_id
        return self._update_thread_status(thread_id, "resuming", fields)

    def mark_thread_completed(self, thread_id: str) -> bool:
        return self._update_thread_status(
            thread_id, "completed", {"completed_at": time.time()}
        )

    def cleanup_expired_threads(self, max_age_hours: int = 24) -> int:
        self.logger.info(f"Thread cleanup triggered (max age: {max_age_hours}h)")
        return 0
