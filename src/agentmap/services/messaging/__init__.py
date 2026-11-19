"""
Messaging services module for AgentMap.

This module provides cloud-agnostic messaging capabilities for publishing
messages to message queues/topics across different cloud providers.
"""

from typing import Any, Optional, Type

from agentmap.services.messaging.messaging_service import (
    CloudMessageAdapter,
    CloudProvider,
    MessagePriority,
    MessagingService,
)

# Import adapters for availability checking
AWSMessageAdapter: Optional[Type[Any]]
try:
    from agentmap.services.messaging.aws_adapter import (
        AWSMessageAdapter as _AWSMessageAdapter,
    )

    AWSMessageAdapter = _AWSMessageAdapter
except ImportError:
    AWSMessageAdapter = None

GCPMessageAdapter: Optional[Type[Any]]
try:
    from agentmap.services.messaging.gcp_adapter import (
        GCPMessageAdapter as _GCPMessageAdapter,
    )

    GCPMessageAdapter = _GCPMessageAdapter
except ImportError:
    GCPMessageAdapter = None

AzureMessageAdapter: Optional[Type[Any]]
try:
    from agentmap.services.messaging.azure_adapter import (
        AzureMessageAdapter as _AzureMessageAdapter,
    )

    AzureMessageAdapter = _AzureMessageAdapter
except ImportError:
    AzureMessageAdapter = None

LocalMessageAdapter: Optional[Type[Any]]
try:
    from agentmap.services.messaging.local_adapter import (
        LocalMessageAdapter as _LocalMessageAdapter,
    )

    LocalMessageAdapter = _LocalMessageAdapter
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
