from agentmap.exceptions.base_exceptions import AgentMapException

class CollectionNotFoundError(AgentMapException):
    """Exception raised when a collection is not found in the storage configuration."""
    pass

class DocumentNotFoundError(AgentMapException):
    """Exception raised when a document is not found in the storage system."""
    pass

class StorageConnectionError(AgentMapException):
    """Exception raised when there is an error connecting to the storage system."""
    pass

class StorageOperationError(AgentMapException):
    """Exception raised when there is an error performing a storage operation."""
    pass

class StorageConfigurationError(AgentMapException):
    """Exception raised when there is an error in the storage configuration."""
    pass

class StorageAuthenticationError(AgentMapException):
    """Exception raised when there is an error authenticating with the storage system."""
    pass


    