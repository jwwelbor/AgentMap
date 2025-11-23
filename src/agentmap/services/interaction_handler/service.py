"""Main InteractionHandlerService class."""

from typing import Any, Dict, Optional

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.system_manager import SystemStorageManager

from .request_operations import RequestOperationsMixin
from .storage_helpers import StorageHelpersMixin
from .thread_operations import ThreadOperationsMixin


class InteractionHandlerService(
    StorageHelpersMixin, ThreadOperationsMixin, RequestOperationsMixin
):
    def __init__(
        self,
        system_storage_manager: SystemStorageManager,
        logging_service: LoggingService,
    ):
        self.logger = logging_service.get_class_logger(self)
        self.file_storage = system_storage_manager.get_file_storage("interactions")
        self.requests_collection = "requests"
        self.threads_collection = "threads"
        self.responses_collection = "responses"
        self.logger.info(
            "[InteractionHandlerService] Initialized with pickle serialization"
        )

    def handle_execution_interruption(
        self,
        exception: ExecutionInterruptedException,
        bundle: Optional[GraphBundle] = None,
        bundle_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        thread_id = exception.thread_id
        self.logger.info(f"Handling execution interruption for thread: {thread_id}")
        try:
            if exception.interaction_request is None:
                self._store_thread_metadata_suspend_only(
                    thread_id=thread_id,
                    checkpoint_data=exception.checkpoint_data,
                    bundle=bundle,
                    bundle_context=bundle_context,
                )
                return
            self._store_interaction_request(exception.interaction_request)
            self._store_thread_metadata(
                thread_id=thread_id,
                interaction_request=exception.interaction_request,
                checkpoint_data=exception.checkpoint_data,
                bundle=bundle,
                bundle_context=bundle_context,
            )
            from agentmap.deployment.cli.display_utils import (
                display_interaction_request,
            )

            display_interaction_request(exception.interaction_request)
        except Exception as e:
            self.logger.error(
                f"Failed to handle interaction for thread {thread_id}: {str(e)}"
            )
            raise RuntimeError(f"Interaction handling failed: {str(e)}") from e

    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service": "InteractionHandlerService",
            "storage_type": "pickle",
            "storage_namespace": "interactions",
            "file_storage_available": self.file_storage.is_healthy(),
            "collections": {
                "requests": self.requests_collection,
                "threads": self.threads_collection,
                "responses": self.responses_collection,
            },
            "capabilities": {
                "exception_handling": True,
                "thread_metadata_storage": True,
                "bundle_context_preservation": True,
                "cli_interaction_display": True,
                "lifecycle_management": True,
                "cleanup_support": True,
                "handles_sets": True,
                "binary_storage": True,
            },
        }
