"""Re-exports InteractionHandlerService for backwards compatibility."""
from agentmap.services.interaction_handler import InteractionHandlerService, RequestOperationsMixin, StorageHelpersMixin, ThreadOperationsMixin, extract_bundle_info, extract_graph_name
__all__ = ["InteractionHandlerService", "StorageHelpersMixin", "ThreadOperationsMixin", "RequestOperationsMixin", "extract_bundle_info", "extract_graph_name"]
