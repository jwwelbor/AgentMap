"""
Messaging services module for AgentMap.

This module provides cloud-agnostic messaging capabilities for publishing
messages to message queues/topics across different cloud providers.
"""

from agentmap.services.messaging.messaging_service import (
    CloudMessageAdapter,
    CloudProvider,
    MessagePriority,
    MessagingService,
)

# Import adapters for availability checking
try:
    from agentmap.services.messaging.aws_adapter import AWSMessageAdapter
except ImportError:
    AWSMessageAdapter = None

try:
    from agentmap.services.messaging.gcp_adapter import GCPMessageAdapter
except ImportError:
    GCPMessageAdapter = None

try:
    from agentmap.services.messaging.azure_adapter import AzureMessageAdapter
except ImportError:
    AzureMessageAdapter = None

try:
    from agentmap.services.messaging.local_adapter import LocalMessageAdapter
except ImportError:
    LocalMessageAdapter = None

__all__ = [
    "MessagingService",
    "CloudProvider",
    "MessagePriority",
    "CloudMessageAdapter",
    "AWSMessageAdapter",
    "GCPMessageAdapter",
    "AzureMessageAdapter",
    "LocalMessageAdapter",
]
