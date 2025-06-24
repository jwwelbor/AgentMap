# Host Service Registry Integration Guide

The HostServiceRegistry provides a way for host applications to register their own services and make them available to AgentMap agents through protocol-based dependency injection.

## Overview

The HostServiceRegistry is a centralized registry that:
- Stores host application services and their providers
- Tracks which protocols each service implements
- Provides service discovery by protocol
- Manages service metadata

## Basic Usage

### 1. Get the Registry from DI Container

```python
from agentmap.di import initialize_di

# Initialize the DI container
container = initialize_di()

# Get the HostServiceRegistry
registry = container.host_service_registry()
```

### 2. Register Host Services

```python
from typing import Protocol, runtime_checkable

# Define a protocol for your service
@runtime_checkable
class EmailServiceProtocol(Protocol):
    def send_email(self, to: str, subject: str, body: str) -> bool: ...

# Implement the service
class MyEmailService:
    def send_email(self, to: str, subject: str, body: str) -> bool:
        # Your implementation
        return True

# Register with the registry
registry.register_service_provider(
    service_name="email_service",
    provider=MyEmailService,  # Can be class, factory, or instance
    protocols=[EmailServiceProtocol],
    metadata={"version": "1.0", "provider": "smtp"}
)
```

### 3. Configure Agents with Host Services

There are two approaches to configure agents with host services:

#### Option A: Manual Configuration (Recommended for Host Applications)

```python
# Define agent that can use the service
class NotificationAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._email_service = None
    
    def configure_email_service(self, email_service: Any) -> None:
        """Configure email service for this agent."""
        self._email_service = email_service
    
    def process(self, inputs: dict) -> Any:
        if self._email_service:
            return self._email_service.send_email(
                inputs['to'], 
                inputs['subject'], 
                inputs['body']
            )

# Manual configuration
email_provider = registry.get_service_provider("email_service")
if email_provider:
    email_service = email_provider() if callable(email_provider) else email_provider
    agent.configure_email_service(email_service)
```

#### Option B: Protocol-Based Auto-Configuration

```python
# Agent implements the protocol
class NotificationAgent(BaseAgent):
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Delegate to configured service."""
        return self._email_service.send_email(to, subject, body)
    
    def configure_email_service(self, email_service: Any) -> None:
        self._email_service = email_service

# Auto-configuration helper
def configure_agent_from_registry(agent, registry):
    """Configure agent with all matching services from registry."""
    configured_count = 0
    
    for service_name in registry.list_registered_services():
        protocols = registry.get_service_protocols(service_name)
        
        for protocol in protocols:
            if isinstance(agent, protocol):
                provider = registry.get_service_provider(service_name)
                if provider:
                    service = provider() if callable(provider) else provider
                    
                    # Derive configuration method name
                    protocol_name = protocol.__name__
                    base_name = protocol_name.replace('ServiceProtocol', '').replace('Protocol', '')
                    method_name = f"configure_{base_name.lower()}_service"
                    
                    if hasattr(agent, method_name):
                        getattr(agent, method_name)(service)
                        configured_count += 1
    
    return configured_count
```

## Service Discovery

### Find Services by Protocol

```python
# Find all services implementing a protocol
email_services = registry.discover_services_by_protocol(EmailServiceProtocol)
for service_name in email_services:
    provider = registry.get_service_provider(service_name)
    # Use the service...
```

### Get Service Metadata

```python
# Get metadata for a service
metadata = registry.get_service_metadata("email_service")
print(f"Version: {metadata.get('version')}")
print(f"Provider: {metadata.get('provider')}")
```

### List All Services

```python
# Get all registered services
all_services = registry.list_registered_services()
for service_name in all_services:
    print(f"Service: {service_name}")
    
    # Get protocols
    protocols = registry.get_service_protocols(service_name)
    for protocol in protocols:
        print(f"  Implements: {protocol.__name__}")
```

## Registry Management

### Update Service Metadata

```python
registry.update_service_metadata(
    "email_service",
    {"last_updated": "2024-01-15", "status": "active"}
)
```

### Validate Services

```python
validation = registry.validate_service_provider("email_service")
if validation["valid"]:
    print("Service is valid")
else:
    print(f"Validation failed: {validation.get('failed_checks')}")
```

### Unregister Services

```python
# Remove a single service
success = registry.unregister_service("email_service")

# Clear all services (use with caution)
registry.clear_registry()
```

### Get Registry Summary

```python
summary = registry.get_registry_summary()
print(f"Total services: {summary['total_services']}")
print(f"Total protocols: {summary['total_protocols']}")
print(f"Health: {summary['registry_health']}")
```

## Best Practices

1. **Define Clear Protocols**: Use Python's `Protocol` with `@runtime_checkable` for type-safe service contracts
2. **Use Factory Functions**: Register factory functions instead of instances for lazy initialization
3. **Include Metadata**: Add version, provider, and other metadata for service management
4. **Validate Services**: Use the validation features to ensure services are properly configured
5. **Handle Missing Services**: Always check if services exist before using them

## Integration with GraphRunnerService

While the GraphRunnerService has built-in support for host service configuration, host applications can also manually configure agents after creation:

```python
# During graph execution setup
graph_runner = container.graph_runner_service()
registry = container.host_service_registry()

# After agent creation, configure host services
def configure_agent_with_host_services(agent, registry):
    """Configure an agent with host services from registry."""
    # Implementation as shown above
    pass

# Apply to agents as needed in your host application
```

## Example: Complete Host Application Integration

```python
from agentmap.di import initialize_di
from typing import Protocol, runtime_checkable

# Step 1: Define your service protocols
@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    def query(self, sql: str) -> list: ...
    def execute(self, sql: str) -> bool: ...

@runtime_checkable
class CacheServiceProtocol(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...

# Step 2: Implement your services
class PostgresService:
    def query(self, sql: str) -> list:
        # Your implementation
        return []
    
    def execute(self, sql: str) -> bool:
        # Your implementation
        return True

class RedisService:
    def get(self, key: str) -> Any:
        # Your implementation
        return None
    
    def set(self, key: str, value: Any) -> None:
        # Your implementation
        pass

# Step 3: Initialize and register
container = initialize_di()
registry = container.host_service_registry()

# Register services
registry.register_service_provider(
    "database",
    PostgresService,
    protocols=[DatabaseServiceProtocol],
    metadata={"type": "postgres", "version": "14"}
)

registry.register_service_provider(
    "cache",
    RedisService,
    protocols=[CacheServiceProtocol],
    metadata={"type": "redis", "version": "7"}
)

# Step 4: Use in your agents
class DataProcessingAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._db_service = None
        self._cache_service = None
    
    def configure_database_service(self, db_service: Any) -> None:
        self._db_service = db_service
    
    def configure_cache_service(self, cache_service: Any) -> None:
        self._cache_service = cache_service
    
    def process(self, inputs: dict) -> Any:
        # Check cache first
        if self._cache_service:
            cached = self._cache_service.get(inputs['key'])
            if cached:
                return cached
        
        # Query database
        if self._db_service:
            result = self._db_service.query(inputs['query'])
            
            # Cache result
            if self._cache_service:
                self._cache_service.set(inputs['key'], result)
            
            return result
        
        return None
```

## Troubleshooting

### Service Not Found
- Verify the service is registered: `registry.is_service_registered("service_name")`
- Check the service name spelling
- Ensure registration happened before lookup

### Protocol Not Recognized
- Ensure protocol is decorated with `@runtime_checkable`
- Import protocol from the correct module
- Verify the agent actually implements the protocol methods

### Service Configuration Fails
- Check that configuration method exists on agent
- Verify method name follows convention: `configure_{service_type}_service`
- Ensure service instance is created correctly from provider

## Summary

The HostServiceRegistry provides a flexible way to extend AgentMap with host-specific services while maintaining clean separation of concerns. By using protocol-based service discovery and configuration, host applications can seamlessly integrate their services with AgentMap agents.
