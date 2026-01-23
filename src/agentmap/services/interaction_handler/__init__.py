"""
Interaction handler service package.

This package provides infrastructure for managing human-in-the-loop interactions
by catching ExecutionInterruptedException, storing thread metadata, and coordinating
with CLI handlers for interaction display and resumption.

The package is organized into:
- service.py: Main InteractionHandlerService class
- storage_helpers.py: Storage helper mixin
- thread_operations.py: Thread lifecycle management mixin
- request_operations.py: Request/response management mixin
- bundle_utils.py: Bundle information extraction utilities
"""

from .bundle_utils import extract_bundle_info, extract_graph_name
from .request_operations import RequestOperationsMixin
from .service import InteractionHandlerService
from .storage_helpers import StorageHelpersMixin
from .thread_operations import ThreadOperationsMixin

__all__ = [
    "InteractionHandlerService",
    "StorageHelpersMixin",
    "ThreadOperationsMixin",
    "RequestOperationsMixin",
    "extract_bundle_info",
    "extract_graph_name",
]
