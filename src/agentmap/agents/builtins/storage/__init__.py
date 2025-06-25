"""
Storage agents for AgentMap.

These agents provide interfaces to different storage backends,
including CSV files, JSON documents, Firebase, vector stores, and cloud storage.
"""

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent,
    log_operation,
)

# Import CSV agents
from agentmap.agents.builtins.storage.csv import (
    CSVAgent,
    CSVReaderAgent,
    CSVWriterAgent,
)

# Import document storage base classes
from agentmap.agents.builtins.storage.document import (
    DocumentPathMixin,
    DocumentReaderAgent,
    DocumentStorageAgent,
    DocumentWriterAgent,
)

# Import File agents
from agentmap.agents.builtins.storage.file import FileReaderAgent, FileWriterAgent

# Import JSON document agents
from agentmap.agents.builtins.storage.json import (
    JSONDocumentAgent,
    JSONDocumentReaderAgent,
    JSONDocumentWriterAgent,
)

# Import types from models (where they belong)
from agentmap.models.storage import DocumentResult, WriteMode

# Import Vector agents
try:
    from agentmap.agents.builtins.storage.vector import (
        VectorAgent,
        VectorReaderAgent,
        VectorWriterAgent,
    )

    _vector_available = True
except ImportError:
    VectorAgent = None
    VectorReaderAgent = None
    VectorWriterAgent = None
    _vector_available = False

# # Conditionally import Firebase agents if firebase-admin is available
# try:
#     from agentmap.agents.builtins.storage.firebase import (
#         FirebaseDocumentAgent, FirebaseDocumentReaderAgent, FirebaseDocumentWriterAgent
#     )
#     _firebase_available = True
# except ImportError:
#     FirebaseDocumentAgent = None
#     FirebaseDocumentReaderAgent = None
#     FirebaseDocumentWriterAgent = None
#     _firebase_available = False

# Conditionally import Cloud JSON agents
# try:
#     from agentmap.agents.builtins.storage.json import (
#         JSONCloudDocumentAgent, JSONCloudDocumentReaderAgent, JSONCloudDocumentWriterAgent
#     )
#     _json_cloud_available = True
# except ImportError:
#     JSONCloudDocumentAgent = None
#     JSONCloudDocumentReaderAgent = None
#     JSONCloudDocumentWriterAgent = None
#     _json_cloud_available = False

# Import config utilities
# from agentmap.config import get_storage_config_path, load_storage_config

__all__ = [
    # Base classes
    "BaseStorageAgent",
    "DocumentResult",
    "WriteMode",
    "log_operation",
    # Document storage
    "DocumentStorageAgent",
    "DocumentReaderAgent",
    "DocumentWriterAgent",
    "DocumentPathMixin",
    # CSV agents
    "CSVAgent",
    "CSVReaderAgent",
    "CSVWriterAgent",
    # JSON document agents
    "JSONDocumentAgent",
    "JSONDocumentReaderAgent",
    "JSONDocumentWriterAgent",
    # File agents
    "FileReaderAgent",
    "FileWriterAgent",
    # Config utilities
    "get_storage_config_path",
]

# Add Vector agents if available
if _vector_available:
    __all__.extend(
        [
            "VectorAgent",
            "VectorReaderAgent",
            "VectorWriterAgent",
        ]
    )

# # Add Firebase agents if available
# if _firebase_available:
#     __all__.extend([
#         'FirebaseDocumentAgent',
#         'FirebaseDocumentReaderAgent',
#         'FirebaseDocumentWriterAgent',
#     ])

# # Add Cloud JSON agents if available
# if _json_cloud_available:
#     __all__.extend([
#         'JSONCloudDocumentAgent',
#         'JSONCloudDocumentReaderAgent',
#         'JSONCloudDocumentWriterAgent',
#     ])
