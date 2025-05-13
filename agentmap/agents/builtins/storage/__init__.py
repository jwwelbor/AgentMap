"""
Storage agents for AgentMap.

These agents provide interfaces to different storage backends,
including CSV files, JSON documents, Firebase, and other databases.
"""

from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent

# Import document storage base classes
from agentmap.agents.builtins.storage.document import (
    DocumentStorageAgent, DocumentReaderAgent, DocumentWriterAgent,
    DocumentResult, WriteMode, DocumentPathMixin
)

# Import CSV agents
from agentmap.agents.builtins.storage.csv import (
    CSVAgent, CSVReaderAgent, CSVWriterAgent
)

# Import JSON document agents
from agentmap.agents.builtins.storage.json import (
    JSONDocumentAgent, JSONDocumentReaderAgent, JSONDocumentWriterAgent,

)

from agentmap.agents.builtins.storage.file import (
    FileReaderAgent, FileWriterAgent
)

from agentmap.agents.builtins.storage.vector import (
    VectorAgent, VectorReaderAgent, VectorWriterAgent
)


# Conditionally import Firebase agents if firebase-admin is available
try:
    from agentmap.agents.builtins.storage.firebase import (
        FirebaseDocumentAgent, FirebaseDocumentReaderAgent, FirebaseDocumentWriterAgent
    )
    _firebase_available = True
except ImportError:
    FirebaseDocumentReaderAgent = None
    FirebaseDocumentWriterAgent = None
    _firebase_available = False

# Import config utilities
from agentmap.config import get_storage_config_path, load_storage_config

__all__ = [
    # Base classes
    'BaseStorageAgent',
    'DocumentStorageAgent',
    'DocumentReaderAgent',
    'DocumentWriterAgent',
    'DocumentResult',
    'WriteMode',
    'DocumentPathMixin',
    
    # CSV agents
    'CSVAgent',
    'CSVReaderAgent',
    'CSVWriterAgent',
    
    # JSON document agents
    'JSONDocumentAgent',
    'JSONDocumentReaderAgent',
    'JSONDocumentWriterAgent',

    # File agents
    'FileReaderAgent',
    'FileWriterAgent',

    #Vector store agents
    'VectorAgent',
    'VectorReaderAgent',
    'VectorWriterAgent',
    
    # Config utilities
    'get_storage_config_path',
    'load_storage_config',
]

# Add Firebase agents if available
if _firebase_available:
    __all__.extend([
        'FirebaseDocumentAgent',
        'FirebaseDocumentReaderAgent',
        'FirebaseDocumentWriterAgent',
    ])

if _json_cloud_available:
    __all__.extend([
        'JSONCloudDocumentAgent',
        'JSONCloudDocumentReaderAgent',
        'JSONCloudDocumentWriterAgent',
    ])