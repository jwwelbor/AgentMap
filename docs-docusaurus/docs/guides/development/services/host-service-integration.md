---
title: "Host Service Integration & Registry Patterns"
description: "Complete guide to extending AgentMap with custom services using protocol-based dependency injection and service registry patterns for domain-specific functionality"
keywords:
  - host services
  - service registry
  - custom services
  - protocol integration
  - dependency injection
  - service protocols
  - custom agents
  - clean architecture
  - service patterns
sidebar_position: 3
---

# Host Service Integration & Registry Patterns

AgentMap's Host Service Integration allows you to extend AgentMap with your own custom services and agents while leveraging AgentMap's dependency injection system and service registry. This enables host applications to define domain-specific services that are automatically injected into compatible agents through protocol-based discovery.

:::info Related Documentation
- [Service Injection Patterns](/docs/contributing/service-injection) - AgentMap's built-in protocol-based dependency injection system
- [Agent Development Contract](../agents/agent-development-contract) - Required agent interface and patterns
- [Advanced Agent Types](../agents/advanced-agent-types) - Context configuration for services
- [Storage Services Overview](/docs/reference/services/storage-services-overview) - Core storage service concepts
:::

## Prerequisites

Before implementing host service integration, you should be familiar with:

- **AgentMap Fundamentals**: Basic workflow creation and agent development
- **Service Injection Patterns**: Read [Service Injection Patterns](/docs/contributing/service-injection) to understand AgentMap's built-in DI system
- **Agent Contract**: Review [Agent Development Contract](../agents/agent-development-contract) for required patterns
- **Python Protocols**: Understanding of `typing.Protocol` and `@runtime_checkable` decorator

## Overview

Host Service Integration bridges the gap between AgentMap's workflow orchestration capabilities and your application's domain-specific functionality. The system provides:

- **Protocol-Based Discovery**: Type-safe service contracts using Python protocols
- **Dependency Injection**: Automatic service configuration for agents
- **Service Registry**: Centralized management of all host services
- **Loose Coupling**: Clean separation between host services and AgentMap logic
- **Extensibility**: Easy integration of custom business services

## Architecture

### Core Components

```
Host Application
├── Protocols (interfaces)
│   ├── DatabaseServiceProtocol
│   ├── EmailServiceProtocol
│   └── CustomServiceProtocol
├── Services (implementations) 
│   ├── DatabaseService
│   ├── EmailService
│   └── CustomService
└── Agents (consumers)
    ├── DatabaseAgent
    ├── EmailAgent
    └── CustomAgent

        ↓ Automatic Injection ↓
        
AgentMap Container
├── Service Registration
├── HostServiceRegistry
├── Protocol Discovery
├── Dependency Injection
└── Graph Execution
```

### Integration Flow

1. **Protocol Definition**: Define service interfaces using Python protocols
2. **Service Implementation**: Create concrete service classes that provide functionality
3. **Agent Creation**: Build agents that implement protocols to receive services
4. **Registration**: Register services with AgentMap's HostServiceRegistry
5. **Configuration**: Configure services through AgentMap's configuration system
6. **Discovery**: Registry discovers services by protocol
7. **Injection**: AgentMap automatically injects services into compatible agents
8. **Execution**: Agents use injected services during graph execution

## Core Concepts

### Protocols

Protocols define the interface contract between agents and services. They specify what methods an agent must implement to receive a particular service.

```python title="Service Protocol Examples" {4,9,14,19}
from typing import Protocol, runtime_checkable, Any, List, Dict
from abc import abstractmethod

@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    """Protocol for agents that need database access."""
    
    @abstractmethod
    def configure_database_service(self, database_service: Any) -> None:
        """Configure the agent with a database service."""
        ...

@runtime_checkable
class EmailServiceProtocol(Protocol):
    """Protocol for email service implementations."""
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email to the specified recipient."""
        ...
    
    def send_bulk_email(self, recipients: List[str], subject: str, body: str) -> Dict[str, bool]:
        """Send email to multiple recipients."""
        ...
    
    def validate_email(self, email: str) -> bool:
        """Validate email address format."""
        ...
```

**Key Requirements:**
- Must use `@runtime_checkable` decorator
- Should end with "ServiceProtocol" by convention
- Configuration methods should follow pattern: `configure_{service_name}_service`
- Must be abstract protocols, not concrete classes

:::tip Protocol Naming Convention
Follow the pattern `{ServiceName}ServiceProtocol` for consistency with AgentMap's built-in protocols like `LLMServiceProtocol` and `StorageServiceProtocol`.
:::

### Services

Services provide the actual implementation of functionality that agents need. They contain business logic, external integrations, or data access code.

```python title="Service Implementation Examples" {6,11,25,35}
class DatabaseService:
    """Concrete database service implementation."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self._initialize_database()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute database query and return results."""
        # Implementation here
        pass

class SMTPEmailService:
    """SMTP-based email service implementation."""
    
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = to
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False
```

### Custom Agents

Custom agents implement one or more protocols to automatically receive the corresponding services.

```python title="Custom Agent Implementation" {3,11,16,23}
from agentmap.agents.base_agent import BaseAgent

class DatabaseAgent(BaseAgent, DatabaseServiceProtocol):
    """Agent that performs database operations."""
    
    def __init__(self, name: str, prompt: str = "", context: Dict[str, Any] = None, 
                 logger=None, **kwargs):
        super().__init__(name, prompt, context, logger, **kwargs)
        self.database_service = None
    
    def configure_database_service(self, database_service: Any) -> None:
        """Configure database service (called automatically by AgentMap)."""
        self.database_service = database_service
        self.logger.debug(f"Database service configured for {self.name}")
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent logic using injected service."""
        if not self.database_service:
            raise ValueError("Database service not configured")
        
        operation = state.get("operation", "query")
        
        if operation == "get_users":
            users = self.database_service.execute_query("SELECT * FROM users")
            return {**state, "users": users}
        
        # Handle other operations...
        return state
```

## Implementation Guide

### Step 1: Define Your Protocol

Create a protocol interface that defines how agents will interact with your service.

```python title="protocols/my_service_protocol.py" {4,9}
from typing import Protocol, runtime_checkable, Any
from abc import abstractmethod

@runtime_checkable
class MyServiceProtocol(Protocol):
    """Protocol for agents that need my custom service."""
    
    @abstractmethod
    def configure_my_service(self, service: Any) -> None:
        """Configure the agent with my service."""
        ...
```

### Step 2: Implement Your Service

Create a concrete service class that provides the actual functionality.

```python title="services/my_service.py" {8,16,30}
import logging
from typing import Dict, Any

class MyService:
    """Custom service implementation."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.api_key = config.get("api_key")
        self.timeout = config.get("timeout", 30)
    
    def do_something(self, data: Any) -> Dict[str, Any]:
        """Perform service operation."""
        try:
            # Your service logic here
            result = self._process_data(data)
            self.logger.info(f"Service operation completed: {result}")
            return {"success": True, "result": result}
        except Exception as e:
            self.logger.error(f"Service operation failed: {e}")
            return {"success": False, "error": str(e)}

# Factory function for dependency injection
def create_my_service(app_config_service, logging_service) -> MyService:
    """Factory function to create MyService with dependencies."""
    config = app_config_service.get_host_service_config("my_service")
    logger = logging_service.get_logger("my_service")
    return MyService(config["configuration"], logger)
```

### Step 3: Create Your Agent

Build an agent that implements your protocol to automatically receive your service.

```python title="agents/my_agent.py" {5,11,15,22}
from typing import Dict, Any
from agentmap.agents.base_agent import BaseAgent
from protocols.my_service_protocol import MyServiceProtocol

class MyAgent(BaseAgent, MyServiceProtocol):
    """Agent that uses my custom service."""
    
    def __init__(self, name: str, prompt: str = "", context: Dict[str, Any] = None,
                 logger=None, **kwargs):
        super().__init__(name, prompt, context, logger, **kwargs)
        self.my_service = None
    
    def configure_my_service(self, service: Any) -> None:
        """Configure my service (called automatically)."""
        self.my_service = service
        self.logger.debug(f"My service configured for {self.name}")
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent using my service."""
        if not self.my_service:
            return {**state, "error": "My service not available"}
        
        # Use your service
        data = state.get("data", {})
        result = self.my_service.do_something(data)
        
        return {
            **state,
            "my_service_result": result,
            "agent_name": self.name
        }
```

### Step 4: Register With AgentMap

Register your service and agent with AgentMap's dependency injection system and service registry.

```python title="Application Initialization" {10,15,22,32}
from agentmap.di.containers import ApplicationContainer
from agentmap.di import initialize_di
from services.my_service import create_my_service
from protocols.my_service_protocol import MyServiceProtocol
from agents.my_agent import MyAgent

# Initialize the DI container
container = initialize_di()

# Method 1: Register using factory function
container.register_host_factory(
    service_name="my_service",
    factory_function=create_my_service,
    dependencies=["app_config_service", "logging_service"],
    protocols=[MyServiceProtocol]
)

# Method 2: Register using HostServiceRegistry
registry = container.host_service_registry()

# Register service provider
registry.register_service_provider(
    service_name="my_service",
    provider=create_my_service,  # Can be instance, class, or factory
    protocols=[MyServiceProtocol],
    metadata={
        "provider": "custom",
        "version": "1.0",
        "description": "My custom service implementation"
    }
)

# Register your agent
agent_registry = container.agent_registry_service()
agent_registry.register_agent("my_agent", MyAgent)
```

### Step 5: Configure

Add configuration for your service in AgentMap's configuration file.

```yaml title="agentmap_config.yaml" {2,6,10}
host_application:
  enabled: true
  protocol_folders:
    - "protocols"  # Where your protocol files are located
  services:
    my_service:
      enabled: true
      configuration:
        api_key: "${MY_API_KEY}"
        timeout: 30
        retries: 3
```

## Service Registry Patterns

The HostServiceRegistry provides powerful patterns for managing services:

### Registry Setup and Configuration

```python title="Registry Setup Examples"
from agentmap.di import initialize_di

# Initialize the DI container
container = initialize_di()

# Get the HostServiceRegistry
registry = container.host_service_registry()

# Register multiple services
def setup_host_services(registry):
    """Set up all host services."""
    
    # Email service
    email_service = SMTPEmailService(
        smtp_host="smtp.company.com",
        smtp_port=587,
        username="agentmap@company.com",
        password="secure_password"
    )
    
    registry.register_service_provider(
        service_name="email_service",
        provider=email_service,
        protocols=[EmailServiceProtocol],
        metadata={
            "provider": "smtp",
            "version": "1.0"
        }
    )
    
    # Database service (using factory)
    db_factory = lambda: DatabaseServiceFactory.create_postgres_service(
        "postgresql://user:pass@localhost:5432/agentmap"
    )
    
    registry.register_service_provider(
        service_name="database_service",
        provider=db_factory,
        protocols=[DatabaseServiceProtocol],
        metadata={
            "provider": "postgresql",
            "version": "14.0"
        }
    )
```

### Service Discovery

```python title="Service Discovery Patterns" {6,15,24}
def discover_available_services(registry):
    """Discover all available services and their capabilities."""
    
    services_info = {}
    
    for service_name in registry.list_registered_services():
        # Get service metadata
        metadata = registry.get_service_metadata(service_name)
        protocols = registry.get_service_protocols(service_name)
        
        # Test service availability
        validation = registry.validate_service_provider(service_name)
        
        services_info[service_name] = {
            "protocols": [p.__name__ for p in protocols],
            "metadata": metadata,
            "available": validation["valid"],
            "validation_errors": validation.get("failed_checks", [])
        }
    
    return services_info

# Protocol-based discovery
def configure_agent_from_registry(agent, registry):
    """Configure agent with all matching services from registry."""
    configured_count = 0
    
    for service_name in registry.list_registered_services():
        protocols = registry.get_service_protocols(service_name)
        
        for protocol in protocols:
            # Check if agent implements the protocol
            if isinstance(agent, protocol):
                provider = registry.get_service_provider(service_name)
                if provider:
                    service = provider() if callable(provider) else provider
                    
                    # Derive configuration method name from protocol
                    protocol_name = protocol.__name__
                    base_name = protocol_name.replace('ServiceProtocol', '').replace('Protocol', '')
                    method_name = f"configure_{base_name.lower()}_service"
                    
                    if hasattr(agent, method_name):
                        getattr(agent, method_name)(service)
                        configured_count += 1
    
    return configured_count
```

### Lazy Loading Pattern

```python title="Lazy Service Loading"
class LazyServiceProvider:
    """Provider that creates services on-demand."""
    
    def __init__(self, factory_func, *args, **kwargs):
        self.factory_func = factory_func
        self.args = args
        self.kwargs = kwargs
        self._instance = None
        self._lock = threading.Lock()
    
    def __call__(self):
        """Get service instance, creating if necessary."""
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self.factory_func(*self.args, **self.kwargs)
        return self._instance

# Usage with lazy loading
def setup_lazy_services(registry):
    """Set up services with lazy loading."""
    
    email_factory = LazyServiceProvider(
        SMTPEmailService,
        smtp_host="smtp.company.com",
        smtp_port=587,
        username="agentmap@company.com",
        password="secure_password"
    )
    
    registry.register_service_provider(
        service_name="email_service",
        provider=email_factory,
        protocols=[EmailServiceProtocol],
        metadata={"lazy_loaded": True}
    )
```

## Advanced Patterns

### Multi-Service Agents

Agents can implement multiple protocols to receive multiple services:

```python title="Multi-Service Agent" {1,7,10,13,17}
class MultiServiceAgent(BaseAgent, DatabaseServiceProtocol, EmailServiceProtocol):
    """Agent that uses multiple services."""
    
    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.database_service = None
        self.email_service = None
    
    def configure_database_service(self, service: Any) -> None:
        self.database_service = service
    
    def configure_email_service(self, service: Any) -> None:
        self.email_service = service
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Use both services together
        data = self.database_service.get_data()
        self.email_service.send_report(data)
        return {**state, "report_sent": True}
```

### Service Middleware

Add cross-cutting concerns like logging, metrics, and error handling:

```python title="Service Middleware Pattern" {8,15,19,31}
class ServiceMiddleware:
    """Middleware for service operations with logging, metrics, etc."""
    
    def __init__(self, service, logger=None, metrics=None):
        self.service = service
        self.logger = logger
        self.metrics = metrics
    
    def __getattr__(self, name):
        """Proxy method calls to underlying service."""
        attr = getattr(self.service, name)
        
        if callable(attr):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    if self.logger:
                        self.logger.info(f"Calling {name} on {type(self.service).__name__}")
                    
                    result = attr(*args, **kwargs)
                    
                    if self.metrics:
                        duration = time.time() - start_time
                        self.metrics.record_operation(
                            service=type(self.service).__name__,
                            operation=name,
                            duration=duration,
                            success=True
                        )
                    
                    return result
                
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error in {name}: {e}")
                    
                    if self.metrics:
                        duration = time.time() - start_time
                        self.metrics.record_operation(
                            service=type(self.service).__name__,
                            operation=name,
                            duration=duration,
                            success=False,
                            error=str(e)
                        )
                    
                    raise
            
            return wrapper
        
        return attr
```

### Circuit Breaker Pattern

Implement resilience patterns for service reliability:

```python title="Circuit Breaker Implementation"
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker for service resilience."""
    
    def __init__(self, failure_threshold=5, timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
```

### Graceful Degradation

Handle cases where services might not be available:

```python title="Graceful Degradation Pattern" {6,14,20}
class RobustAgent(BaseAgent, DatabaseServiceProtocol):
    """Agent with graceful degradation."""
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if hasattr(self, 'database_service') and self.database_service:
            # Use database if available
            try:
                data = self.database_service.get_data()
                return {**state, "data": data, "source": "database"}
            except Exception as e:
                self.logger.warning(f"Database failed, using fallback: {e}")
        
        # Fallback to alternative approach
        fallback_data = self._get_fallback_data()
        return {**state, "data": fallback_data, "source": "fallback"}
```

## Integration with AgentMap Workflows

### Workflow Configuration

Use service-aware agents in your workflows:

```csv title="CSV Workflow with Services"
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
ServiceFlow,LoadData,,Load user data,csv_reader,ValidateData,ErrorHandler,,users,data/users.csv
ServiceFlow,ValidateData,,Validate with service,ServiceValidator,ProcessData,ErrorHandler,users,validated_users,
ServiceFlow,ProcessData,,Process data,DataProcessor,SendNotifications,ErrorHandler,validated_users,processed_data,
ServiceFlow,SendNotifications,,Send via email service,NotificationAgent,LogResults,ErrorHandler,processed_data,notification_results,
ServiceFlow,LogResults,,Log to database,DatabaseLogger,End,ErrorHandler,notification_results,log_result,
ServiceFlow,End,,Completion,Echo,,,log_result,final_message,Processing complete with services
ServiceFlow,ErrorHandler,,Handle errors,Echo,End,,error,error_message,Error: {error}
```

### Agent Context Configuration

Configure agent contexts with service requirements:

```yaml title="Agent Context Configuration"
# Service-aware agent contexts
agents:
  NotificationAgent:
    type: "notification_agent"
    services:
      - "email_service"
      - "database_service"
    config:
      default_sender: "system@company.com"
      retry_count: 3
      timeout: 30
  
  DataProcessor:
    type: "data_processor"
    services:
      - "cache_service"
      - "database_service"
    config:
      cache_ttl: 300
      batch_size: 100
```

## Testing

### Unit Testing with Mocks

```python title="Service Testing" {8,15,25}
import unittest
from unittest.mock import Mock, MagicMock

class TestServiceIntegration(unittest.TestCase):
    """Test service integration with agents."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_registry = Mock()
        self.mock_email_service = Mock()
        self.mock_db_service = Mock()
        
        # Configure mock email service
        self.mock_email_service.send_email.return_value = True
        self.mock_email_service.validate_email.return_value = True
        
        # Configure mock database service
        self.mock_db_service.query.return_value = [{"id": 1, "name": "test"}]
        self.mock_db_service.execute.return_value = True
    
    def test_agent_with_email_service(self):
        """Test agent functionality with email service."""
        # Arrange
        agent = NotificationAgent()
        agent.configure_email_service(self.mock_email_service)
        
        inputs = {
            "type": "email",
            "recipient": "test@example.com",
            "subject": "Test",
            "message": "Test message"
        }
        
        # Act
        result = agent.process(inputs)
        
        # Assert
        self.assertEqual(result["status"], "sent")
        self.mock_email_service.send_email.assert_called_once_with(
            "test@example.com", "Test", "Test message"
        )
```

### Integration Testing

```python title="Integration Testing"
class TestServiceRegistryIntegration(unittest.TestCase):
    """Integration tests for service registry."""
    
    def setUp(self):
        """Set up integration test environment."""
        from agentmap.di import initialize_di
        
        self.container = initialize_di()
        self.registry = self.container.host_service_registry()
        
        # Set up real services for testing
        self._setup_test_services()
    
    def test_service_registration_and_discovery(self):
        """Test complete service registration and discovery flow."""
        # Test registration
        self.assertTrue(self.registry.is_service_registered("test_email_service"))
        
        # Test discovery
        email_services = self.registry.discover_services_by_protocol(EmailServiceProtocol)
        self.assertIn("test_email_service", email_services)
        
        # Test metadata
        metadata = self.registry.get_service_metadata("test_email_service")
        self.assertTrue(metadata.get("test"))
        
        # Test provider retrieval
        provider = self.registry.get_service_provider("test_email_service")
        self.assertIsNotNone(provider)
```

## API Reference

### ApplicationContainer Methods

#### `register_host_factory()`

Register a host service using a factory function.

```python
def register_host_factory(
    self,
    service_name: str,
    factory_function: callable,
    dependencies: Optional[List[str]] = None,
    protocols: Optional[List[Type]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None
```

**Parameters:**
- `service_name`: Unique name for the service
- `factory_function`: Function that creates the service instance
- `dependencies`: List of dependency service names from the container
- `protocols`: List of protocols this service implements
- `metadata`: Optional metadata about the service

#### `register_host_service()`

Register a host service using a class path.

```python
def register_host_service(
    self,
    service_name: str,
    service_class_path: str,
    dependencies: Optional[List[str]] = None,
    protocols: Optional[List[Type]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    singleton: bool = True
) -> None
```

### HostServiceRegistry Methods

#### `register_service_provider()`

Register a service provider with the registry.

```python
def register_service_provider(
    self,
    service_name: str,
    provider: Any,
    protocols: List[Type] = None,
    metadata: Dict[str, Any] = None
) -> None
```

#### `get_service_provider()`

Retrieve a registered service provider.

```python
def get_service_provider(self, service_name: str) -> Optional[Any]
```

#### `discover_services_by_protocol()`

Find all services implementing a specific protocol.

```python
def discover_services_by_protocol(self, protocol: Type) -> List[str]
```

#### `list_registered_services()`

Get list of all registered service names.

```python
def list_registered_services(self) -> List[str]
```

## Configuration Reference

### Host Application Configuration

The `host_application` section in your AgentMap configuration controls host service integration.

```yaml title="Complete Configuration Example"
host_application:
  # Enable/disable host service integration
  enabled: true
  
  # Folders to scan for protocol definitions
  protocol_folders:
    - "protocols"
    - "custom_protocols"
  
  # Service configurations
  services:
    email_service:
      enabled: true
      configuration:
        smtp_host: "${SMTP_HOST}"
        smtp_port: 587
        username: "${EMAIL_USER}"
        password: "${EMAIL_PASSWORD}"
        
    database_service:
      enabled: true
      configuration:
        host: "${DATABASE_HOST}"
        port: 5432
        database: "agentmap"
        user: "${DATABASE_USER}"
        password: "${DATABASE_PASSWORD}"
        pool_size: 10
        
    cache_service:
      enabled: true
      configuration:
        redis_url: "${REDIS_URL}"
        ttl_default: 300
        max_connections: 50
```

### Environment Variables

Host services can use environment variables in configuration:

```bash title="Environment Setup"
export SMTP_HOST="smtp.company.com"
export EMAIL_USER="agentmap@company.com"
export EMAIL_PASSWORD="secure-password"
export DATABASE_HOST="prod-db.company.com"
export DATABASE_USER="agentmap_user"
export DATABASE_PASSWORD="db-password"
export REDIS_URL="redis://localhost:6379/0"
```

## Best Practices

### Service Design Guidelines

:::tip Service Design Best Practices

1. **Protocol-First Design**: Define protocols before implementations
2. **Immutable Interfaces**: Keep protocol interfaces stable across versions
3. **Error Handling**: Implement comprehensive error handling and logging
4. **Resource Management**: Properly manage connections, file handles, etc.
5. **Thread Safety**: Ensure services are thread-safe for concurrent access
6. **Documentation**: Document service behavior, limitations, and dependencies
7. **Configuration Validation**: Check required settings early
8. **Graceful Degradation**: Provide fallback behavior when possible

:::

### Implementation Checklist

<details>
<summary>Service Implementation Checklist</summary>

**Protocol Definition**:
- [ ] Use `@runtime_checkable` decorator
- [ ] Define clear method signatures with type hints
- [ ] Document expected behavior and exceptions
- [ ] Consider async variants if needed

**Implementation**:
- [ ] Handle all error conditions gracefully
- [ ] Implement proper resource cleanup
- [ ] Add logging for debugging
- [ ] Include configuration validation
- [ ] Support both sync and async patterns if applicable

**Testing**:
- [ ] Unit tests for all public methods
- [ ] Integration tests with real dependencies
- [ ] Error condition testing
- [ ] Performance testing for critical paths
- [ ] Mock interfaces for dependent services

**Documentation**:
- [ ] API documentation with examples
- [ ] Configuration options
- [ ] Error codes and meanings
- [ ] Performance characteristics
- [ ] Dependencies and requirements

</details>

## Troubleshooting

### Common Issues

#### Service Not Being Injected

**Symptoms:**
- Agent's configure method never called
- Service attribute is None
- "Service not configured" errors

**Solutions:**
1. Verify protocol implementation:
   ```python
   # Check if agent implements protocol
   assert isinstance(my_agent, MyServiceProtocol)
   ```

2. Check service registration:
   ```python
   # Verify service is registered
   services = container.get_host_services()
   assert "my_service" in services
   ```

3. Enable debug logging:
   ```yaml
   logging:
     level: DEBUG
   ```

#### Import Errors

**Symptoms:**
- ModuleNotFoundError when loading protocols/services
- ImportError during agent registration

**Solutions:**
1. Check Python path includes your modules
2. Verify file names and directory structure
3. Ensure `__init__.py` files exist in package directories

#### Configuration Not Loading

**Symptoms:**
- Service receives empty or default configuration
- Environment variables not being resolved

**Solutions:**
1. Verify YAML syntax is correct
2. Check environment variables are set:
   ```bash
   echo $MY_API_KEY
   ```
3. Use absolute paths for protocol folders

### Debugging Tips

1. **Enable Verbose Logging**:
   ```yaml
   logging:
     level: DEBUG
     format: "[%(asctime)s] %(name)s %(levelname)s: %(message)s"
   ```

2. **Check Service Registration**:
   ```python
   # In your application
   container = ApplicationContainer()
   services = container.get_host_services()
   print(f"Registered services: {list(services.keys())}")
   ```

3. **Test Service Instantiation**:
   ```python
   # Verify service can be created
   service = container.get_host_service_instance("my_service")
   assert service is not None
   ```

4. **Debug Service Discovery**:
   ```python
   def debug_service_discovery(registry):
       """Debug service registry state."""
       services = registry.list_registered_services()
       print(f"Registered services: {services}")
       
       for service_name in services:
           protocols = registry.get_service_protocols(service_name)
           metadata = registry.get_service_metadata(service_name)
           print(f"  {service_name}: {[p.__name__ for p in protocols]} - {metadata}")
   ```

## Migration Guide

If you're migrating from a different AgentMap integration approach:

### From Manual Service Injection

**Before:**
```python
# Manual injection
agent = MyAgent("test")
agent.database_service = DatabaseService(config)
```

**After:**
```python
# Protocol-based injection
class MyAgent(BaseAgent, DatabaseServiceProtocol):
    def configure_database_service(self, service):
        self.database_service = service

# Service automatically injected by AgentMap
```

### From Hardcoded Dependencies

**Before:**
```python
class MyAgent(BaseAgent):
    def __init__(self, name, database_url):
        super().__init__(name)
        self.db = Database(database_url)  # Hardcoded
```

**After:**
```python
class MyAgent(BaseAgent, DatabaseServiceProtocol):
    def configure_database_service(self, service):
        self.database_service = service  # Injected
```

This approach provides better testability, configuration management, and separation of concerns.

## Next Steps

After implementing host service integration:

### Immediate Next Steps
1. **Test Your Integration**: Use the patterns in this guide to verify your implementation
2. **Configure Services**: Review the configuration reference for production setup
3. **Monitor Services**: Implement health checks and metrics collection
4. **Debug Issues**: Use the troubleshooting section for common problems

### Advanced Topics
1. **Service Middleware**: Add cross-cutting concerns like logging and metrics
2. **Circuit Breakers**: Implement resilience patterns for reliability
3. **Service Discovery**: Automate service discovery in dynamic environments
4. **Performance Optimization**: Profile and optimize service interactions

### Integration with AgentMap Ecosystem
1. **Workflow Development**: Use in complex multi-agent workflows
2. **Prompt Management**: Integrate with template systems
3. **Execution Tracking**: Monitor with performance tracking tools
4. **Storage Integration**: Combine with data storage operations

:::tip Complete Examples
For hands-on learning, check out the [Agent Development Guide](/docs/guides/development/agents/agent-development) which includes complete working examples of host service integration patterns.
:::
