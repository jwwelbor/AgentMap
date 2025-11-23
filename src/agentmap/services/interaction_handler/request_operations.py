"""Request operations mixin."""
import pickle, time
from typing import Any, Dict, Optional
from agentmap.models.human_interaction import HumanInteractionRequest
from agentmap.services.storage.types import WriteMode

class RequestOperationsMixin:
    def _store_interaction_request(self, request: HumanInteractionRequest) -> None:
        request_data = {"id": str(request.id), "thread_id": request.thread_id, "node_name": request.node_name, "interaction_type": request.interaction_type.value, "prompt": request.prompt, "context": request.context or {}, "options": request.options or [], "timeout_seconds": request.timeout_seconds, "created_at": request.created_at.isoformat(), "status": "pending"}
        result = self._write_collection(collection=self.requests_collection, data=pickle.dumps(request_data), document_id=f"{request.id}.pkl", mode=WriteMode.WRITE, binary_mode=True)
        if not result.success: raise RuntimeError(f"Failed to store interaction request: {result.error}")
        self.logger.debug(f"Stored interaction request: {request.id}")

    def save_interaction_response(self, response_id: str, thread_id: str, action: str, data: Optional[Dict[str, Any]] = None) -> bool:
        try:
            response_data = {"response_id": response_id, "thread_id": thread_id, "action": action, "data": data or {}, "timestamp": time.time()}
            result = self._write_collection(collection=self.responses_collection, data=pickle.dumps(response_data), document_id=f"{response_id}.pkl", mode=WriteMode.WRITE, binary_mode=True)
            if result.success:
                self.logger.debug(f"Saved interaction response: {response_id}")
                return True
            self.logger.error(f"Failed to save interaction response: {result.error}")
            return False
        except Exception as e:
            self.logger.error(f"Error saving interaction response {response_id}: {str(e)}")
            return False
