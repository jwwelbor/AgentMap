# examples/host_integration/host_protocols.py
"""
Example host service protocols for AgentMap integration.

This file demonstrates how host applications can define their own service protocols
that extend AgentMap's service injection system. These protocols follow the same
patterns as AgentMap's built-in protocols (LLMCapableAgent, StorageCapableAgent, etc.)
"""

from typing import Protocol, runtime_checkable, Dict, List, Any, Optional
from abc import abstractmethod


@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    """
    Protocol for database service capabilities.
    
    Agents implementing this protocol can be automatically configured with
    database services when the host application registers a database service.
    """
    
    @abstractmethod
    def configure_database_service(self, database_service: Any) -> None:
        """
        Configure the agent with a database service.
        
        Args:
            database_service: Database service instance providing data access
        """
        ...


@runtime_checkable
class EmailServiceProtocol(Protocol):
    """
    Protocol for email service capabilities.
    
    Agents implementing this protocol can send emails, notifications,
    and handle email-based workflows through the host application's email service.
    """
    
    @abstractmethod
    def configure_email_service(self, email_service: Any) -> None:
        """
        Configure the agent with an email service.
        
        Args:
            email_service: Email service instance for sending communications
        """
        ...


@runtime_checkable
class NotificationServiceProtocol(Protocol):
    """
    Protocol for notification service capabilities.
    
    Agents implementing this protocol can send notifications through
    various channels (Slack, Teams, webhooks, etc.) managed by the host application.
    """
    
    @abstractmethod
    def configure_notification_service(self, notification_service: Any) -> None:
        """
        Configure the agent with a notification service.
        
        Args:
            notification_service: Notification service for multi-channel messaging
        """
        ...


@runtime_checkable
class FileServiceProtocol(Protocol):
    """
    Protocol for file service capabilities.
    
    Agents implementing this protocol can interact with the host application's
    file management system for document processing, uploads, downloads, etc.
    """
    
    @abstractmethod
    def configure_file_service(self, file_service: Any) -> None:
        """
        Configure the agent with a file service.
        
        Args:
            file_service: File service for document and file operations
        """
        ...


@runtime_checkable
class WorkflowServiceProtocol(Protocol):
    """
    Protocol for workflow service capabilities.
    
    Agents implementing this protocol can trigger and participate in
    host application workflows, business processes, and integrations.
    """
    
    @abstractmethod
    def configure_workflow_service(self, workflow_service: Any) -> None:
        """
        Configure the agent with a workflow service.
        
        Args:
            workflow_service: Workflow service for business process integration
        """
        ...


# Example of a more complex protocol with additional methods
@runtime_checkable
class AdvancedDatabaseServiceProtocol(Protocol):
    """
    Advanced database protocol with additional capabilities.
    
    This demonstrates how protocols can include multiple methods
    and more sophisticated service integration patterns.
    """
    
    @abstractmethod
    def configure_database_service(self, database_service: Any) -> None:
        """Configure the agent with a database service."""
        ...
    
    @abstractmethod
    def get_database_status(self) -> Dict[str, Any]:
        """
        Get current database service status.
        
        Returns:
            Dictionary with database connection and operation status
        """
        ...
    
    @abstractmethod
    def validate_database_operations(self) -> List[str]:
        """
        Validate that database operations are working correctly.
        
        Returns:
            List of validation errors (empty if all valid)
        """
        ...


# Protocol composition example
@runtime_checkable
class FullServiceAgentProtocol(DatabaseServiceProtocol, EmailServiceProtocol, NotificationServiceProtocol, Protocol):
    """
    Example of protocol composition for agents that need multiple services.
    
    Agents implementing this protocol will automatically receive all
    configured services: database, email, and notification services.
    """
    pass


# Documentation and examples for host application developers
"""
USAGE EXAMPLES FOR HOST APPLICATION DEVELOPERS:

1. **Define Your Service Protocol**:
   ```python
   @runtime_checkable
   class MyCustomServiceProtocol(Protocol):
       @abstractmethod
       def configure_my_custom_service(self, service: Any) -> None:
           pass
   ```

2. **Create Agent Implementing Protocol**:
   ```python
   class MyAgent(BaseAgent, MyCustomServiceProtocol):
       def __init__(self, name, prompt, context, logger, ...):
           super().__init__(name, prompt, context, logger, ...)
           self.my_custom_service = None
       
       def configure_my_custom_service(self, service: Any) -> None:
           self.my_custom_service = service
           self.logger.debug(f"Configured custom service for {self.name}")
       
       def run(self, state):
           # Use self.my_custom_service here
           result = self.my_custom_service.do_something()
           return {"output": result}
   ```

3. **Register Service with Container**:
   ```python
   container.register_host_service(
       service_name="my_custom_service",
       service_class_path="myapp.services.MyCustomService",
       protocols=[MyCustomServiceProtocol]
   )
   ```

4. **Configure AgentMap**:
   ```yaml
   host_application:
     enabled: true
     protocol_folders:
       - "myapp/protocols"
     services:
       my_custom_service:
         enabled: true
         configuration:
           api_key: "your-api-key"
   ```

BEST PRACTICES:

1. **Protocol Naming**: Use descriptive names ending in "ServiceProtocol"
2. **Method Naming**: Use "configure_<service_name>_service" pattern
3. **Runtime Checkable**: Always use @runtime_checkable decorator
4. **Documentation**: Include clear docstrings for all protocols and methods
5. **Error Handling**: Implement proper error handling in configure methods
6. **Validation**: Consider adding validation methods for complex protocols
7. **Composition**: Use protocol composition for agents needing multiple services

INTEGRATION PATTERNS:

1. **Simple Service**: Single service, single protocol
2. **Multi-Service Agent**: One agent implementing multiple protocols
3. **Protocol Hierarchy**: Base protocols with specialized extensions
4. **Conditional Services**: Services that may or may not be available
5. **Service Dependencies**: Services that depend on other services

ERROR HANDLING EXAMPLES:

```python
def configure_database_service(self, database_service: Any) -> None:
    try:
        if not database_service:
            raise ValueError("Database service cannot be None")
        
        # Validate service has required methods
        if not hasattr(database_service, 'execute_query'):
            raise ValueError("Database service missing required 'execute_query' method")
        
        self.database_service = database_service
        self.logger.debug(f"Database service configured for {self.name}")
        
    except Exception as e:
        self.logger.error(f"Failed to configure database service for {self.name}: {e}")
        # Decide whether to raise or use graceful degradation
        raise  # or implement fallback behavior
```
"""
