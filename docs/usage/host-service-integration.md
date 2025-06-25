# Host Service Integration

AgentMap's Host Service Integration allows you to extend AgentMap with your own custom services and agents while leveraging AgentMap's dependency injection system. This enables host applications to define domain-specific services that are automatically injected into compatible agents.

> **Related Documentation**: 
> - [Service Injection](service_injection.md) - AgentMap's built-in protocol-based dependency injection system
> - [Host Service Registry](host_service_registry.md) - Registry API for managing host services
> - [Agent Development Contract](agent_contract.md) - Required agent interface and patterns
> - [Advanced Agent Types](advanced_agent_types.md) - Context configuration for services

## Prerequisites

Before implementing host service integration, you should be familiar with:

- **AgentMap Fundamentals**: Basic workflow creation and agent development
- **Service Injection Patterns**: Read [Service Injection](service_injection.md) to understand AgentMap's built-in DI system
- **Agent Contract**: Review [Agent Development Contract](agent_contract.md) for required patterns
- **Python Protocols**: Understanding of `typing.Protocol` and `@runtime_checkable` decorator

## Table of Contents

- [Prerequisites](#prerequisites)
- [Overview](#overview)
- [Architecture](#architecture)
- [Core Concepts](#core-concepts)
- [Implementation Guide](#implementation-guide)
- [Configuration Reference](#configuration-reference)
- [Advanced Topics](#advanced-topics)
- [API Reference](#api-reference)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)
- [Migration Guide](#migration-guide)
- [Next Steps](#next-steps)
- [See Also](#see-also)

## Overview

Host Service Integration bridges the gap between AgentMap's workflow orchestration capabilities and your application's domain-specific functionality. Instead of being limited to AgentMap's built-in agents, you can:

- **Define Custom Services**: Implement services specific to your domain (database access, external APIs, business logic)
- **Create Protocol Interfaces**: Define contracts that specify how agents interact with services
- **Build Custom Agents**: Create agents that implement your protocols and automatically receive service dependencies
- **Maintain Clean Architecture**: Keep services separate from agents while ensuring automatic dependency injection

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
├── Protocol Discovery
├── Dependency Injection
└── Graph Execution
```

### Integration Flow

1. **Protocol Definition**: Define service interfaces using Python protocols
2. **Service Implementation**: Create concrete service classes that provide functionality
3. **Agent Creation**: Build agents that implement protocols to receive services
4. **Registration**: Register services with AgentMap's dependency injection container
5. **Configuration**: Configure services through AgentMap's configuration system
6. **Execution**: AgentMap automatically injects services into compatible agents during graph execution

## Core Concepts

### Protocols

Protocols define the interface contract between agents and services. They specify what methods an agent must implement to receive a particular service.

```python
from typing import Protocol, runtime_checkable, Any
from abc import abstractmethod

@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    """Protocol for agents that need database access."""
    
    @abstractmethod
    def configure_database_service(self, database_service: Any) -> None:
        """Configure the agent with a database service.
        
        Args:
            database_service: Database service instance
        """
        ...
```

**Key Requirements:**
- Must use `@runtime_checkable` decorator
- Should end with "ServiceProtocol" by convention
- Configuration methods should follow pattern: `configure_{service_name}_service`
- Must be abstract protocols, not concrete classes

> **See Also**: [Agent Development Contract](agent_contract.md#protocol-based-service-configuration) for more details on protocol implementation patterns.

### Services

Services provide the actual implementation of functionality that agents need. They contain business logic, external integrations, or data access code.

```python
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
```

**Key Requirements:**
- Should accept configuration and logger in constructor
- Should provide clean, domain-specific APIs
- Should handle errors gracefully
- Should follow dependency injection patterns

### Custom Agents

Custom agents implement one or more protocols to automatically receive the corresponding services.

```python
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

**Key Requirements:**
- Must inherit from `BaseAgent` and implement one or more service protocols
- Must implement all abstract methods from the protocols
- Should handle cases where services are not available (graceful degradation)
- Should validate service availability before use

> **See Also**: [Agent Development Contract](agent_contract.md) for complete agent implementation requirements and [Service Injection](service_injection.md#complete-implementation-examples) for AgentMap's built-in service patterns.

## Implementation Guide

### Step 1: Define Your Protocol

Create a protocol interface that defines how agents will interact with your service.

```python
# protocols/my_service_protocol.py
from typing import Protocol, runtime_checkable, Any
from abc import abstractmethod

@runtime_checkable
class MyServiceProtocol(Protocol):
    """Protocol for agents that need my custom service."""
    
    @abstractmethod
    def configure_my_service(self, service: Any) -> None:
        """Configure the agent with my service.
        
        Args:
            service: MyService instance
        """
        ...
```

### Step 2: Implement Your Service

Create a concrete service class that provides the actual functionality.

```python
# services/my_service.py
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
    
    def _process_data(self, data: Any) -> Any:
        """Internal processing logic."""
        # Implementation here
        return data

# Factory function for dependency injection
def create_my_service(app_config_service, logging_service) -> MyService:
    """Factory function to create MyService with dependencies.
    
    Args:
        app_config_service: AppConfigService instance
        logging_service: LoggingService instance
    
    Returns:
        Configured MyService instance
    """
    config = app_config_service.get_host_service_config("my_service")
    logger = logging_service.get_logger("my_service")
    return MyService(config["configuration"], logger)
```

### Step 3: Create Your Agent

Build an agent that implements your protocol to automatically receive your service.

```python
# agents/my_agent.py
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

Register your service and agent with AgentMap's dependency injection system.

```python
# In your application initialization
from agentmap.di.containers import ApplicationContainer
from services.my_service import create_my_service
from protocols.my_service_protocol import MyServiceProtocol
from agents.my_agent import MyAgent

# Get the application container
container = ApplicationContainer()

# Register your service
container.register_host_factory(
    service_name="my_service",
    factory_function=create_my_service,
    dependencies=["app_config_service", "logging_service"],
    protocols=[MyServiceProtocol]
)

# Register your agent
agent_registry = container.agent_registry_service()
agent_registry.register_agent("my_agent", MyAgent)
```

### Step 5: Configure

Add configuration for your service in AgentMap's configuration file.

```yaml
# agentmap_config.yaml
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

## Configuration Reference

> **Related**: [Storage Services](storage_services.md) for storage configuration patterns and [Advanced Agent Types](advanced_agent_types.md) for agent context configuration.

### Host Application Configuration

The `host_application` section in your AgentMap configuration controls host service integration.

```yaml
host_application:
  # Enable/disable host service integration
  enabled: true
  
  # Folders to scan for protocol definitions
  protocol_folders:
    - "protocols"
    - "custom_protocols"
  
  # Service configurations
  services:
    service_name:
      enabled: true
      configuration:
        # Service-specific configuration
        key: value
```

### Service Configuration Structure

```yaml
services:
  my_service:
    # Enable/disable this specific service
    enabled: true
    
    # Configuration passed to service constructor
    configuration:
      api_key: "${MY_API_KEY}"  # Environment variable
      timeout: 30
      base_url: "https://api.example.com"
      retry_attempts: 3
      
      # Nested configuration
      database:
        host: "localhost"
        port: 5432
        name: "myapp"
```

### Environment Variables

Host services can use environment variables in configuration:

```yaml
services:
  database_service:
    configuration:
      host: "${DATABASE_HOST}"
      password: "${DATABASE_PASSWORD}"
      api_key: "${API_KEY}"
```

Set these in your environment:

```bash
export DATABASE_HOST="prod-db.company.com"
export DATABASE_PASSWORD="secure-password"
export API_KEY="your-api-key"
```

## Advanced Topics

### Multi-Service Agents

Agents can implement multiple protocols to receive multiple services:

```python
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

### Protocol Composition

Create composite protocols for agents that need multiple related services:

```python
@runtime_checkable
class FullStackProtocol(
    DatabaseServiceProtocol, 
    EmailServiceProtocol, 
    NotificationServiceProtocol, 
    Protocol
):
    """Composite protocol for agents needing multiple services."""
    pass

class FullStackAgent(BaseAgent, FullStackProtocol):
    """Agent that gets all three services automatically."""
    # Implement all three configure methods
    pass
```

### Graceful Degradation

Handle cases where services might not be available:

```python
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

### Service Dependencies

Services can depend on other services or AgentMap components:

```python
def create_advanced_service(database_service, email_service, logging_service):
    """Service that depends on other services."""
    logger = logging_service.get_logger("advanced_service")
    return AdvancedService(database_service, email_service, logger)

# Register with dependencies
container.register_host_factory(
    service_name="advanced_service",
    factory_function=create_advanced_service,
    dependencies=["database_service", "email_service", "logging_service"],
    protocols=[AdvancedServiceProtocol]
)
```

### Error Handling Patterns

Implement robust error handling in services and agents:

```python
class RobustService:
    """Service with comprehensive error handling."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.circuit_breaker = CircuitBreaker()
    
    def call_external_api(self, data: Any) -> Dict[str, Any]:
        """Make external API call with error handling."""
        try:
            # Circuit breaker pattern
            if self.circuit_breaker.is_open():
                raise Exception("Circuit breaker is open")
            
            # Make API call
            response = self._make_api_call(data)
            self.circuit_breaker.record_success()
            return {"success": True, "data": response}
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            self.logger.error(f"API call failed: {e}")
            
            # Return error response instead of raising
            return {
                "success": False, 
                "error": str(e),
                "fallback_available": True
            }
```

## API Reference

> **Note**: This section covers host service-specific methods. For complete AgentMap container documentation, see [Dependency Injection Guide](../architecture/dependency_injection_guide.md).
> For host service registry operations, see [Host Service Registry](host_service_registry.md).

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

#### `configure_host_protocols()`

Configure host protocols on an agent instance.

```python
def configure_host_protocols(self, agent: Any) -> int
```

**Parameters:**
- `agent`: Agent instance to configure

**Returns:**
- Number of services configured on the agent

#### `get_host_services()`

Get information about all registered host services.

```python
def get_host_services(self) -> Dict[str, Dict[str, Any]]
```

**Returns:**
- Dictionary mapping service names to service information

### AppConfigService Methods

#### `get_host_application_config()`

Get host application configuration with defaults.

```python
def get_host_application_config(self) -> Dict[str, Any]
```

#### `get_host_service_config()`

Get configuration for a specific host service.

```python
def get_host_service_config(self, service_name: str) -> Dict[str, Any]
```

#### `is_host_application_enabled()`

Check if host application support is enabled.

```python
def is_host_application_enabled(self) -> bool
```

## Best Practices

### Protocol Design

1. **Use Descriptive Names**: Protocol names should clearly indicate their purpose
   ```python
   # Good
   class DatabaseServiceProtocol(Protocol): ...
   class EmailNotificationProtocol(Protocol): ...
   
   # Avoid
   class ServiceProtocol(Protocol): ...
   class Protocol1(Protocol): ...
   ```

2. **Keep Protocols Focused**: Each protocol should represent a single responsibility
   ```python
   # Good - focused protocols
   class DatabaseReadProtocol(Protocol): ...
   class DatabaseWriteProtocol(Protocol): ...
   
   # Avoid - overly broad protocol
   class DatabaseEverythingProtocol(Protocol): ...
   ```

3. **Use Runtime Checkable**: Always use `@runtime_checkable` decorator
   ```python
   from typing import Protocol, runtime_checkable
   
   @runtime_checkable
   class MyServiceProtocol(Protocol):
       # Protocol definition
   ```

### Service Implementation

1. **Follow Dependency Injection**: Accept dependencies in constructor
   ```python
   class MyService:
       def __init__(self, config: Dict[str, Any], logger: logging.Logger):
           self.config = config
           self.logger = logger
   ```

2. **Handle Configuration Gracefully**: Provide sensible defaults
   ```python
   def __init__(self, config: Dict[str, Any], logger: logging.Logger):
       self.timeout = config.get("timeout", 30)
       self.retries = config.get("retries", 3)
       self.base_url = config.get("base_url", "https://api.default.com")
   ```

3. **Implement Error Recovery**: Don't let service failures crash agents
   ```python
   def call_api(self, data):
       try:
           return self._make_call(data)
       except Exception as e:
           self.logger.error(f"API call failed: {e}")
           return {"error": str(e), "fallback": True}
   ```

### Agent Development

1. **Validate Service Availability**: Check services before use
   ```python
   def run(self, state):
       if not self.my_service:
           return {**state, "error": "Service not available"}
       # Use service
   ```

2. **Implement Graceful Degradation**: Provide fallback behavior
   ```python
   def run(self, state):
       if hasattr(self, 'database_service'):
           return self._use_database(state)
       else:
           return self._use_fallback(state)
   ```

3. **Log Service Usage**: Help with debugging and monitoring
   ```python
   def configure_my_service(self, service):
       self.my_service = service
       self.logger.info(f"Service configured for {self.name}")
   ```

### Configuration Management

1. **Use Environment Variables**: Keep secrets out of config files
   ```yaml
   services:
     my_service:
       configuration:
         api_key: "${API_KEY}"  # From environment
         secret: "${MY_SECRET}"
   ```

2. **Organize by Environment**: Use different configs for dev/test/prod
   ```yaml
   # development.yaml
   host_application:
     services:
       database_service:
         configuration:
           host: "localhost"
   
   # production.yaml
   host_application:
     services:
       database_service:
         configuration:
           host: "${PROD_DB_HOST}"
   ```

3. **Validate Configuration**: Check required settings early
   ```python
   def __init__(self, config, logger):
       required_keys = ["api_key", "base_url"]
       for key in required_keys:
           if key not in config:
               raise ValueError(f"Missing required config: {key}")
   ```

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
3. Use absolute paths for protocol folders:
   ```yaml
   protocol_folders:
     - "/absolute/path/to/protocols"
   ```

#### Protocol Not Found

**Symptoms:**
- Protocol discovery fails
- "No protocol implementations found" warnings

**Solutions:**
1. Check protocol folder configuration
2. Ensure protocols use `@runtime_checkable`
3. Verify protocol naming conventions

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
   
   protocols = container.get_protocol_implementations()
   print(f"Protocol implementations: {protocols}")
   ```

3. **Test Service Instantiation**:
   ```python
   # Verify service can be created
   service = container.get_host_service_instance("my_service")
   assert service is not None
   ```

4. **Validate Agent Protocol Implementation**:
   ```python
   from protocols.my_service_protocol import MyServiceProtocol
   
   agent = MyAgent("test")
   assert isinstance(agent, MyServiceProtocol)
   assert hasattr(agent, 'configure_my_service')
   ```

## Examples

### Complete Working Examples

For hands-on learning, explore these complete examples:

- **[Host Integration Example](../examples/host_integration/)** - Complete example with database, email, and notification services
- **[Basic Integration Test](../examples/host_integration/test_basic_integration.py)** - Simple verification test
- **[Comprehensive Tests](../examples/host_integration/test_host_integration.py)** - Full test suite

### What the Examples Demonstrate

- **Protocol Definition**: How to define clean service interfaces
- **Service Implementation**: Best practices for service development with proper error handling
- **Multi-Service Agents**: Agents that use multiple services together
- **Configuration Patterns**: YAML configuration examples for different scenarios
- **Testing Strategies**: Comprehensive testing patterns for host integration

### Related Examples

- **[AgentMap Agent Types](agentmap_agent_types.md)** - Built-in agents using AgentMap's service injection
- **[Service Injection Examples](service_injection.md#complete-implementation-examples)** - AgentMap's built-in service patterns

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
1. **Test Your Integration**: Use the patterns in [Examples](#examples) to verify your implementation
2. **Configure Services**: Review [Configuration Reference](#configuration-reference) for production setup
3. **Debug Issues**: Use [Troubleshooting](#troubleshooting) section for common problems

### Advanced Topics
1. **Registry Management**: Learn [Host Service Registry](host_service_registry.md) for advanced service management
2. **Built-in Service Patterns**: Study [Service Injection](service_injection.md) for AgentMap's internal patterns
3. **Agent Development**: Master [Agent Development Contract](agent_contract.md) for advanced agent patterns
4. **Context Configuration**: Explore [Advanced Agent Types](advanced_agent_types.md) for service-specific configuration

### Integration with AgentMap Ecosystem
1. **Storage Integration**: Combine with [Storage Services](storage_services.md) for data operations
2. **Workflow Development**: Use in [AgentMap Example Workflows](agentmap_example_workflows.md)
3. **Prompt Management**: Integrate with [Prompt Management](prompt_management_in_agentmap.md)
4. **Execution Tracking**: Monitor with [AgentMap Execution Tracking](agentmap_execution_tracking.md)

## See Also

### Core Documentation
- **[Service Injection](service_injection.md)** - AgentMap's built-in protocol-based dependency injection system
- **[Agent Development Contract](agent_contract.md)** - Required interface and patterns for all agents
- **[Host Service Registry](host_service_registry.md)** - Registry API for managing host services

### Related Guides
- **[Advanced Agent Types](advanced_agent_types.md)** - Context configuration for services
- **[Storage Services](storage_services.md)** - Unified storage operations patterns
- **[AgentMap Agent Types](agentmap_agent_types.md)** - Built-in agents using service injection

### Architecture Documentation
- **[Clean Architecture Overview](../architecture/clean_architecture_overview.md)** - Overall architecture principles
- **[Dependency Injection Guide](../architecture/dependency_injection_guide.md)** - Complete DI container documentation
- **[Service Catalog](../architecture/service_catalog.md)** - Complete list of AgentMap services

### Operational Guides
- **[AgentMap CLI Documentation](agentmap_cli_documentation.md)** - Command-line tools for service debugging
- **[AgentMap Execution Tracking](agentmap_execution_tracking.md)** - Performance monitoring and debugging
- **[Prompt Management in AgentMap](prompt_management_in_agentmap.md)** - Template system integration
