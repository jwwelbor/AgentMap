"""
Storage operations for human interaction requests and responses.

Handles persistence of interaction requests and user responses
using pickle serialization for complex data types.
"""

import time
from typing import Any, Dict, Optional

from agentmap.models.human_interaction import HumanInteractionRequest
from agentmap.services.storage.types import WriteMode


class InteractionStorage:
    """
    Storage manager for interaction requests and responses.

    Handles:
    - Storing interaction requests from HumanAgent
    - Saving user responses
    - Pickle serialization for complex data types
    """

    def __init__(
        self,
        storage_helpers,
        requests_collection: str,
        responses_collection: str,
        logger,
    ):
        """
        Initialize interaction storage.

        Args:
            storage_helpers: StorageHelpers instance for operations
            requests_collection: Collection name for requests
            responses_collection: Collection name for responses
            logger: Logger instance
        """
        self.storage = storage_helpers
        self.requests_collection = requests_collection
        self.responses_collection = responses_collection
        self.logger = logger

    def store_interaction_request(self, request: HumanInteractionRequest) -> None:
        """
        Store interaction request to persistent storage using pickle.

        Args:
            request: The human interaction request to store

        Raises:
            RuntimeError: If storage operation fails
        """
        request_data = {
            "id": str(request.id),
            "thread_id": request.thread_id,
            "node_name": request.node_name,
            "interaction_type": request.interaction_type.value,
            "prompt": request.prompt,
            "context": request.context or {},
            "options": request.options or [],
            "timeout_seconds": request.timeout_seconds,
            "created_at": request.created_at.isoformat(),
            "status": "pending",
        }

        # Serialize to pickle
        data_bytes = self.storage.serialize_to_pickle(request_data)

        result = self.storage.write_collection(
            collection=self.requests_collection,
            data=data_bytes,
            document_id=f"{request.id}.pkl",
            mode=WriteMode.WRITE,
            binary_mode=True,
        )

        if not result.success:
            raise RuntimeError(f"Failed to store interaction request: {result.error}")

        self.logger.debug(
            f"📝 Stored interaction request: {request.id} for thread: {request.thread_id}"
        )

    def save_interaction_response(
        self,
        response_id: str,
        thread_id: str,
        action: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save user interaction response to storage.

        Args:
            response_id: Unique response ID
            thread_id: Thread ID this response belongs to
            action: User action (approve, reject, choose, respond, edit)
            data: Optional additional response data

        Returns:
            True if save successful, False otherwise
        """
        try:
            response_data = {
                "response_id": response_id,
                "thread_id": thread_id,
                "action": action,
                "data": data or {},
                "timestamp": time.time(),
            }

            # Serialize to pickle
            data_bytes = self.storage.serialize_to_pickle(response_data)

            result = self.storage.write_collection(
                collection=self.responses_collection,
                data=data_bytes,
                document_id=f"{response_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(
                    f"📝 Saved interaction response: {response_id} for thread: {thread_id}"
                )
                return True
            else:
                self.logger.error(
                    f"❌ Failed to save interaction response: {result.error}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"❌ Error saving interaction response {response_id}: {str(e)}"
            )
            return False
