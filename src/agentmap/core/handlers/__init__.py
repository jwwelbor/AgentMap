"""
Serverless handlers for AgentMap using the new service architecture.
"""

from agentmap.core.handlers.aws_lambda import lambda_handler
from agentmap.core.handlers.azure_functions import (
    azure_blob_handler,
    azure_http_handler,
    azure_queue_handler,
)
from agentmap.core.handlers.gcp_functions import (
    gcp_http_handler,
    gcp_pubsub_handler,
    gcp_storage_handler,
)

__all__ = [
    "lambda_handler",
    "gcp_http_handler",
    "gcp_pubsub_handler",
    "gcp_storage_handler",
    "azure_http_handler",
    "azure_blob_handler",
    "azure_queue_handler",
]
