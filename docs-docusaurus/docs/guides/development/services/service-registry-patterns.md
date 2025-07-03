# Service Registry Patterns

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';

The HostServiceRegistry provides a powerful way for your application to register its services and make them available to AgentMap agents through protocol-based dependency injection. This enables seamless integration between AgentMap workflows and existing application infrastructure.

:::info Service Registry Benefits
- **Protocol-Based Discovery**: Type-safe service contracts using Python protocols
- **Dependency Injection**: Automatic service configuration for agents
- **Loose Coupling**: Clean separation between host services and AgentMap logic
- **Extensibility**: Easy integration of custom business services
- **Centralized Management**: Single registry for all host services
:::

## Overview

The HostServiceRegistry is a centralized registry that:
- Stores host application services and their providers
- Tracks which protocols each service implements
- Provides service discovery by protocol
- Manages service metadata and lifecycle

## Architecture Patterns

### Protocol-Based Service Contracts

Define clear service contracts using Python's `Protocol` with `@runtime_checkable`:

```python
from typing import Protocol, runtime_checkable, Any, List, Dict

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

@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    """Protocol for database service implementations."""
    
    def query(self, sql: str, params: Dict[str, Any] = None) -> List[Dict]:
        """Execute a query and return results."""
        ...
    
    def execute(self, sql: str, params: Dict[str, Any] = None) -> bool:
        """Execute a statement and return success status."""
        ...
    
    def transaction(self) -> Any:
        """Get a transaction context manager."""
        ...

@runtime_checkable
class CacheServiceProtocol(Protocol):
    """Protocol for cache service implementations."""
    
    def get(self, key: str) -> Any:
        """Get value from cache."""
        ...
    
    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache with optional TTL."""
        ...
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        ...
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        ...
```

### Service Implementation Patterns

<Tabs>
<TabItem value="simple" label="Simple Implementation">

```python
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
            # SMTP implementation
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
    
    def send_bulk_email(self, recipients: List[str], subject: str, body: str) -> Dict[str, bool]:
        """Send email to multiple recipients."""
        results = {}
        for recipient in recipients:
            results[recipient] = self.send_email(recipient, subject, body)
        return results
    
    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
```

</TabItem>
<TabItem value="factory" label="Factory Pattern">

```python
class DatabaseServiceFactory:
    """Factory for creating database service instances."""
    
    @staticmethod
    def create_postgres_service(connection_string: str):
        """Create PostgreSQL service instance."""
        
        class PostgresService:
            def __init__(self, conn_str: str):
                self.connection_string = conn_str
                self._pool = None
            
            def _get_connection(self):
                # Implementation would use connection pooling
                import psycopg2
                return psycopg2.connect(self.connection_string)
            
            def query(self, sql: str, params: Dict[str, Any] = None) -> List[Dict]:
                """Execute query and return results."""
                try:
                    with self._get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(sql, params or {})
                            columns = [desc[0] for desc in cursor.description]
                            return [
                                dict(zip(columns, row)) 
                                for row in cursor.fetchall()
                            ]
                except Exception as e:
                    print(f"Query failed: {e}")
                    return []
            
            def execute(self, sql: str, params: Dict[str, Any] = None) -> bool:
                """Execute statement."""
                try:
                    with self._get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(sql, params or {})
                            conn.commit()
                    return True
                except Exception as e:
                    print(f"Execute failed: {e}")
                    return False
            
            def transaction(self):
                """Get transaction context manager."""
                return self._get_connection()
        
        return PostgresService(connection_string)
```

</TabItem>
<TabItem value="async" label="Async Implementation">

```python
import asyncio
from typing import AsyncContextManager

@runtime_checkable
class AsyncCacheServiceProtocol(Protocol):
    """Async cache service protocol."""
    
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any, ttl: int = None) -> None: ...
    async def delete(self, key: str) -> bool: ...

class RedisAsyncService:
    """Async Redis cache service implementation."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None
    
    async def _get_redis(self):
        """Get Redis connection."""
        if self._redis is None:
            import aioredis
            self._redis = await aioredis.from_url(self.redis_url)
        return self._redis
    
    async def get(self, key: str) -> Any:
        """Get value from Redis."""
        redis = await self._get_redis()
        value = await redis.get(key)
        if value:
            import json
            return json.loads(value)
        return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in Redis."""
        redis = await self._get_redis()
        import json
        serialized = json.dumps(value)
        if ttl:
            await redis.setex(key, ttl, serialized)
        else:
            await redis.set(key, serialized)
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        redis = await self._get_redis()
        result = await redis.delete(key)
        return result > 0
```

</TabItem>
</Tabs>

## Registry Setup and Configuration

### Basic Registry Usage

<Tabs>
<TabItem value="setup" label="Registry Setup">

```python
from agentmap.di import initialize_di

# Initialize the DI container
container = initialize_di()

# Get the HostServiceRegistry
registry = container.host_service_registry()

# Register services with the registry
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
        provider=email_service,  # Can be instance, class, or factory
        protocols=[EmailServiceProtocol],
        metadata={
            "provider": "smtp",
            "version": "1.0",
            "description": "Corporate SMTP email service"
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
            "version": "14.0",
            "connection_pool": True
        }
    )
    
    # Cache service
    cache_service = RedisService("redis://localhost:6379/0")
    
    registry.register_service_provider(
        service_name="cache_service",
        provider=cache_service,
        protocols=[CacheServiceProtocol],
        metadata={
            "provider": "redis",
            "version": "7.0",
            "cluster": False
        }
    )

# Set up services
setup_host_services(registry)
```

</TabItem>
<TabItem value="config" label="Configuration-Based Setup">

```python
# Configuration-driven service setup
import yaml

def setup_services_from_config(registry, config_path: str):
    """Set up services from configuration file."""
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    for service_name, service_config in config.get('services', {}).items():
        provider_type = service_config['provider']
        
        if provider_type == 'smtp_email':
            provider = SMTPEmailService(
                smtp_host=service_config['smtp_host'],
                smtp_port=service_config['smtp_port'],
                username=service_config['username'],
                password=service_config['password']
            )
            protocols = [EmailServiceProtocol]
        
        elif provider_type == 'postgres_db':
            provider = DatabaseServiceFactory.create_postgres_service(
                service_config['connection_string']
            )
            protocols = [DatabaseServiceProtocol]
        
        elif provider_type == 'redis_cache':
            provider = RedisService(service_config['redis_url'])
            protocols = [CacheServiceProtocol]
        
        else:
            continue
        
        registry.register_service_provider(
            service_name=service_name,
            provider=provider,
            protocols=protocols,
            metadata=service_config.get('metadata', {})
        )

# Configuration file example (services.yaml)
services_config = """
services:
  email_service:
    provider: smtp_email
    smtp_host: smtp.company.com
    smtp_port: 587
    username: agentmap@company.com
    password: ${EMAIL_PASSWORD}
    metadata:
      provider: smtp
      version: "1.0"
  
  database_service:
    provider: postgres_db
    connection_string: postgresql://user:pass@localhost:5432/agentmap
    metadata:
      provider: postgresql
      version: "14.0"
  
  cache_service:
    provider: redis_cache
    redis_url: redis://localhost:6379/0
    metadata:
      provider: redis
      version: "7.0"
"""
```

</TabItem>
</Tabs>

## Service Discovery and Configuration

### Manual Service Configuration

<Tabs>
<TabItem value="explicit" label="Explicit Configuration">

```python
class NotificationAgent(BaseAgent):
    """Agent that sends notifications using host services."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._email_service = None
        self._database_service = None
    
    def configure_email_service(self, email_service: Any) -> None:
        """Configure email service for this agent."""
        self._email_service = email_service
        self.log_info("Email service configured")
    
    def configure_database_service(self, database_service: Any) -> None:
        """Configure database service for this agent."""
        self._database_service = database_service
        self.log_info("Database service configured")
    
    def process(self, inputs: dict) -> Any:
        """Process notification request."""
        notification_type = inputs.get("type", "email")
        
        if notification_type == "email" and self._email_service:
            success = self._email_service.send_email(
                to=inputs['recipient'],
                subject=inputs['subject'],
                body=inputs['message']
            )
            
            # Log to database if available
            if self._database_service:
                self._database_service.execute(
                    "INSERT INTO notifications (type, recipient, success) VALUES (%s, %s, %s)",
                    {"type": "email", "recipient": inputs['recipient'], "success": success}
                )
            
            return {"status": "sent" if success else "failed"}
        
        return {"status": "error", "message": "Service not available"}

# Manual configuration
def configure_agent_manually(agent, registry):
    """Manually configure agent with services."""
    
    # Configure email service
    email_provider = registry.get_service_provider("email_service")
    if email_provider:
        email_service = email_provider() if callable(email_provider) else email_provider
        agent.configure_email_service(email_service)
    
    # Configure database service
    db_provider = registry.get_service_provider("database_service")
    if db_provider:
        db_service = db_provider() if callable(db_provider) else db_provider
        agent.configure_database_service(db_service)
```

</TabItem>
<TabItem value="protocol" label="Protocol-Based Configuration">

```python
def configure_agent_from_registry(agent, registry):
    """Configure agent with all matching services from registry."""
    configured_count = 0
    
    for service_name in registry.list_registered_services():
        protocols = registry.get_service_protocols(service_name)
        
        for protocol in protocols:
            # Check if agent implements the protocol (indicating it can use the service)
            if hasattr(agent, '_get_protocol_methods'):
                # Custom method to check protocol compatibility
                if agent._supports_protocol(protocol):
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

# Protocol-aware agent
class ServiceAwareAgent(BaseAgent):
    """Agent that can automatically discover and use host services."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._services = {}
        self._supported_protocols = [
            EmailServiceProtocol,
            DatabaseServiceProtocol,
            CacheServiceProtocol
        ]
    
    def _supports_protocol(self, protocol):
        """Check if this agent supports a protocol."""
        return protocol in self._supported_protocols
    
    def configure_email_service(self, service):
        self._services['email'] = service
    
    def configure_database_service(self, service):
        self._services['database'] = service
    
    def configure_cache_service(self, service):
        self._services['cache'] = service
    
    def get_service(self, service_type: str):
        """Get configured service by type."""
        return self._services.get(service_type)
    
    def process(self, inputs: dict) -> Any:
        """Process with automatic service discovery."""
        operation = inputs.get("operation")
        
        if operation == "send_email":
            email_service = self.get_service('email')
            if email_service:
                return email_service.send_email(
                    inputs['to'], 
                    inputs['subject'], 
                    inputs['body']
                )
        
        elif operation == "query_data":
            db_service = self.get_service('database')
            if db_service:
                return db_service.query(inputs['sql'], inputs.get('params'))
        
        elif operation == "cache_data":
            cache_service = self.get_service('cache')
            if cache_service:
                cache_service.set(inputs['key'], inputs['value'], inputs.get('ttl'))
                return {"status": "cached"}
        
        return {"status": "error", "message": "Required service not available"}
```

</TabItem>
</Tabs>

### Service Discovery Patterns

<Tabs>
<TabItem value="discovery" label="Service Discovery">

```python
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

# Service health monitoring
class ServiceHealthMonitor:
    """Monitor health of registered services."""
    
    def __init__(self, registry):
        self.registry = registry
        self.health_cache = {}
    
    def check_service_health(self, service_name: str) -> dict:
        """Check health of a specific service."""
        try:
            provider = self.registry.get_service_provider(service_name)
            if not provider:
                return {"status": "not_found"}
            
            # Create service instance
            service = provider() if callable(provider) else provider
            
            # Protocol-specific health checks
            protocols = self.registry.get_service_protocols(service_name)
            
            health_results = {}
            for protocol in protocols:
                if protocol == EmailServiceProtocol:
                    # Test email service
                    health_results["email"] = self._test_email_service(service)
                elif protocol == DatabaseServiceProtocol:
                    # Test database service
                    health_results["database"] = self._test_database_service(service)
                elif protocol == CacheServiceProtocol:
                    # Test cache service
                    health_results["cache"] = self._test_cache_service(service)
            
            overall_health = all(result.get("healthy", False) for result in health_results.values())
            
            return {
                "status": "healthy" if overall_health else "degraded",
                "checks": health_results,
                "timestamp": time.time()
            }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _test_email_service(self, service) -> dict:
        """Test email service connectivity."""
        try:
            # Test email validation (lightweight check)
            is_valid = service.validate_email("test@example.com")
            return {"healthy": True, "validation_working": is_valid}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _test_database_service(self, service) -> dict:
        """Test database service connectivity."""
        try:
            # Simple health check query
            result = service.query("SELECT 1 as health_check")
            return {"healthy": len(result) > 0, "query_working": True}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _test_cache_service(self, service) -> dict:
        """Test cache service connectivity."""
        try:
            # Test set/get operation
            test_key = f"health_check_{time.time()}"
            service.set(test_key, "test_value", ttl=60)
            value = service.get(test_key)
            service.delete(test_key)
            
            return {
                "healthy": value == "test_value",
                "set_get_working": True
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def get_all_service_health(self) -> dict:
        """Get health status for all registered services."""
        health_report = {}
        
        for service_name in self.registry.list_registered_services():
            health_report[service_name] = self.check_service_health(service_name)
        
        return health_report
```

</TabItem>
<TabItem value="lazy" label="Lazy Loading">

```python
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
    
    # Email service - created only when first accessed
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
    
    # Database service - connection pool created on demand
    db_factory = LazyServiceProvider(
        DatabaseServiceFactory.create_postgres_service,
        "postgresql://user:pass@localhost:5432/agentmap"
    )
    
    registry.register_service_provider(
        service_name="database_service", 
        provider=db_factory,
        protocols=[DatabaseServiceProtocol],
        metadata={"lazy_loaded": True, "connection_pool": True}
    )
```

</TabItem>
</Tabs>

## Integration with AgentMap Workflows

### Workflow Configuration

<Tabs>
<TabItem value="csv" label="CSV Workflow with Services">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ServiceFlow,LoadData,,Load user data,csv_reader,ValidateData,ErrorHandler,,users,data/users.csv
ServiceFlow,ValidateData,,Validate with service,ServiceValidator,ProcessData,ErrorHandler,users,validated_users,
ServiceFlow,ProcessData,,Process data,DataProcessor,SendNotifications,ErrorHandler,validated_users,processed_data,
ServiceFlow,SendNotifications,,Send via email service,NotificationAgent,LogResults,ErrorHandler,processed_data,notification_results,
ServiceFlow,LogResults,,Log to database,DatabaseLogger,End,ErrorHandler,notification_results,log_result,
ServiceFlow,End,,Completion,Echo,,,log_result,final_message,Processing complete with services
ServiceFlow,ErrorHandler,,Handle errors,Echo,End,,error,error_message,Error: {error}
```

</TabItem>
<TabItem value="context" label="Agent Context Configuration">

```yaml
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
  
  ServiceValidator:
    type: "validator_agent"
    services:
      - "database_service"
    config:
      validation_rules:
        - "email_format"
        - "phone_format"
        - "required_fields"
```

</TabItem>
</Tabs>

### Advanced Service Patterns

<Tabs>
<TabItem value="middleware" label="Service Middleware">

```python
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

# Registry with middleware
def register_service_with_middleware(registry, service_name, service, protocols, metadata=None):
    """Register service with automatic middleware wrapping."""
    
    # Create middleware-wrapped service
    wrapped_service = ServiceMiddleware(
        service,
        logger=logging.getLogger(f"service.{service_name}"),
        metrics=MetricsCollector()
    )
    
    registry.register_service_provider(
        service_name=service_name,
        provider=wrapped_service,
        protocols=protocols,
        metadata={**(metadata or {}), "middleware_enabled": True}
    )
```

</TabItem>
<TabItem value="circuit" label="Circuit Breaker Pattern">

```python
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

class ResilientServiceWrapper:
    """Service wrapper with circuit breaker protection."""
    
    def __init__(self, service, circuit_breaker=None):
        self.service = service
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
    
    def __getattr__(self, name):
        """Proxy method calls with circuit breaker protection."""
        attr = getattr(self.service, name)
        
        if callable(attr):
            def wrapper(*args, **kwargs):
                return self.circuit_breaker.call(attr, *args, **kwargs)
            return wrapper
        
        return attr
```

</TabItem>
</Tabs>

## Testing Service Integration

### Unit Testing

<Tabs>
<TabItem value="mocking" label="Service Mocking">

```python
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
        
        # Configure mock registry
        self.mock_registry.get_service_provider.side_effect = self._get_service_provider
    
    def _get_service_provider(self, service_name):
        """Mock service provider lookup."""
        if service_name == "email_service":
            return self.mock_email_service
        elif service_name == "database_service":
            return self.mock_db_service
        return None
    
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
    
    def test_service_discovery(self):
        """Test service discovery mechanism."""
        # Arrange
        agent = ServiceAwareAgent()
        
        # Act
        configured_count = configure_agent_from_registry(agent, self.mock_registry)
        
        # Assert
        self.assertGreater(configured_count, 0)
        self.mock_registry.list_registered_services.assert_called()
```

</TabItem>
<TabItem value="integration" label="Integration Testing">

```python
class TestServiceRegistryIntegration(unittest.TestCase):
    """Integration tests for service registry."""
    
    def setUp(self):
        """Set up integration test environment."""
        from agentmap.di import initialize_di
        
        self.container = initialize_di()
        self.registry = self.container.host_service_registry()
        
        # Set up real services for testing
        self._setup_test_services()
    
    def _setup_test_services(self):
        """Set up test services."""
        # Mock email service for testing
        class TestEmailService:
            def send_email(self, to: str, subject: str, body: str) -> bool:
                return True  # Always succeed in tests
            
            def validate_email(self, email: str) -> bool:
                return "@" in email
        
        # Register test service
        self.registry.register_service_provider(
            service_name="test_email_service",
            provider=TestEmailService(),
            protocols=[EmailServiceProtocol],
            metadata={"test": True}
        )
    
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
        
        # Test service functionality
        service = provider() if callable(provider) else provider
        self.assertTrue(service.send_email("test@example.com", "Test", "Body"))
    
    def test_agent_configuration_with_registry(self):
        """Test agent configuration using registry."""
        # Create agent
        agent = NotificationAgent()
        
        # Configure with registry
        configure_agent_manually(agent, self.registry)
        
        # Test agent functionality
        result = agent.process({
            "type": "email",
            "recipient": "test@example.com", 
            "subject": "Test",
            "message": "Test message"
        })
        
        self.assertEqual(result["status"], "sent")
```

</TabItem>
</Tabs>

## Best Practices

### Service Design Guidelines

:::tip Service Design Best Practices

1. **Protocol-First Design**: Define protocols before implementations
2. **Immutable Interfaces**: Keep protocol interfaces stable across versions
3. **Error Handling**: Implement comprehensive error handling and logging
4. **Resource Management**: Properly manage connections, file handles, etc.
5. **Thread Safety**: Ensure services are thread-safe for concurrent access
6. **Documentation**: Document service behavior, limitations, and dependencies

:::

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

### Registry Management

<Tabs>
<TabItem value="lifecycle" label="Service Lifecycle">

```python
class ServiceRegistry:
    """Enhanced service registry with lifecycle management."""
    
    def __init__(self):
        self._services = {}
        self._lifecycle_hooks = {}
    
    def register_service_with_lifecycle(self, service_name, provider, protocols, 
                                      startup=None, shutdown=None, metadata=None):
        """Register service with lifecycle hooks."""
        
        self.register_service_provider(service_name, provider, protocols, metadata)
        
        if startup or shutdown:
            self._lifecycle_hooks[service_name] = {
                "startup": startup,
                "shutdown": shutdown
            }
    
    def startup_services(self):
        """Initialize all registered services."""
        for service_name, hooks in self._lifecycle_hooks.items():
            if hooks.get("startup"):
                try:
                    hooks["startup"]()
                    print(f"Service {service_name} started successfully")
                except Exception as e:
                    print(f"Failed to start service {service_name}: {e}")
    
    def shutdown_services(self):
        """Clean up all registered services."""
        for service_name, hooks in self._lifecycle_hooks.items():
            if hooks.get("shutdown"):
                try:
                    hooks["shutdown"]()
                    print(f"Service {service_name} shut down successfully")
                except Exception as e:
                    print(f"Failed to shut down service {service_name}: {e}")

# Usage with lifecycle management
def setup_services_with_lifecycle(registry):
    """Set up services with proper lifecycle management."""
    
    # Database service with connection management
    db_service = DatabaseService()
    
    registry.register_service_with_lifecycle(
        service_name="database_service",
        provider=db_service,
        protocols=[DatabaseServiceProtocol],
        startup=db_service.connect,
        shutdown=db_service.disconnect,
        metadata={"managed_lifecycle": True}
    )
```

</TabItem>
<TabItem value="monitoring" label="Service Monitoring">

```python
class ServiceMetrics:
    """Collect and track service usage metrics."""
    
    def __init__(self):
        self.call_counts = {}
        self.error_counts = {}
        self.response_times = {}
    
    def record_call(self, service_name, method_name, duration, success=True):
        """Record a service method call."""
        key = f"{service_name}.{method_name}"
        
        # Update call count
        self.call_counts[key] = self.call_counts.get(key, 0) + 1
        
        # Update error count
        if not success:
            self.error_counts[key] = self.error_counts.get(key, 0) + 1
        
        # Update response times
        if key not in self.response_times:
            self.response_times[key] = []
        self.response_times[key].append(duration)
    
    def get_service_stats(self, service_name):
        """Get statistics for a specific service."""
        stats = {
            "calls": {},
            "errors": {},
            "avg_response_time": {}
        }
        
        for key in self.call_counts:
            if key.startswith(f"{service_name}."):
                method = key.split(".", 1)[1]
                stats["calls"][method] = self.call_counts[key]
                stats["errors"][method] = self.error_counts.get(key, 0)
                
                times = self.response_times.get(key, [])
                if times:
                    stats["avg_response_time"][method] = sum(times) / len(times)
        
        return stats

# Global metrics instance
service_metrics = ServiceMetrics()

# Instrumented service wrapper
class MetricsServiceWrapper:
    """Service wrapper that collects metrics."""
    
    def __init__(self, service, service_name):
        self.service = service
        self.service_name = service_name
    
    def __getattr__(self, name):
        attr = getattr(self.service, name)
        
        if callable(attr):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                
                try:
                    result = attr(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start_time
                    service_metrics.record_call(
                        self.service_name, name, duration, success
                    )
            
            return wrapper
        
        return attr
```

</TabItem>
</Tabs>

## Troubleshooting

### Common Issues

<details>
<summary>Service Not Found</summary>

**Problem**: `get_service_provider` returns `None`

**Solutions**:
1. Verify service is registered: `registry.is_service_registered("service_name")`
2. Check service name spelling
3. Ensure registration happened before lookup
4. Review registry initialization order

```python
# Debug service registration
def debug_registry(registry):
    """Debug registry state."""
    services = registry.list_registered_services()
    print(f"Registered services: {services}")
    
    for service_name in services:
        protocols = registry.get_service_protocols(service_name)
        metadata = registry.get_service_metadata(service_name)
        print(f"  {service_name}: {[p.__name__ for p in protocols]} - {metadata}")
```

</details>

<details>
<summary>Protocol Recognition Issues</summary>

**Problem**: Protocol-based discovery not working

**Solutions**:
1. Ensure protocol is decorated with `@runtime_checkable`
2. Import protocol from correct module
3. Verify agent actually implements protocol methods
4. Check isinstance() calls work as expected

```python
# Test protocol recognition
def test_protocol_recognition():
    """Test if service implements expected protocol."""
    service = MyEmailService()
    
    print(f"Implements EmailServiceProtocol: {isinstance(service, EmailServiceProtocol)}")
    
    # Check individual methods
    required_methods = ['send_email', 'validate_email']
    for method in required_methods:
        has_method = hasattr(service, method)
        print(f"Has {method}: {has_method}")
```

</details>

<details>
<summary>Service Configuration Failures</summary>

**Problem**: Agent configuration methods not called

**Solutions**:
1. Check configuration method exists on agent
2. Verify method name follows convention
3. Ensure service instance created correctly
4. Review agent initialization order

```python
# Debug agent configuration
def debug_agent_configuration(agent, registry):
    """Debug agent service configuration."""
    print(f"Agent type: {type(agent).__name__}")
    
    # Check available configuration methods
    config_methods = [
        method for method in dir(agent) 
        if method.startswith('configure_') and method.endswith('_service')
    ]
    print(f"Available config methods: {config_methods}")
    
    # Check services in registry
    for service_name in registry.list_registered_services():
        protocols = registry.get_service_protocols(service_name)
        for protocol in protocols:
            protocol_name = protocol.__name__
            base_name = protocol_name.replace('ServiceProtocol', '').replace('Protocol', '')
            expected_method = f"configure_{base_name.lower()}_service"
            
            has_method = hasattr(agent, expected_method)
            print(f"Service {service_name} -> Method {expected_method}: {has_method}")
```

</details>

## Related Documentation

- [Storage Services Overview](/docs/guides/development/services/storage/storage-services-overview) - Core storage service concepts
- [Cloud Storage Integration](/docs/guides/development/services/storage/cloud-storage-integration) - Cloud storage for services
- [Agent Development Guide](/docs/guides/development/agents/agent-development) - Building service-capable agents
- [Dependency Injection](/docs/reference/dependency-injection) - DI container patterns

:::tip Next Steps

The service registry provides a powerful foundation for integrating AgentMap with existing application infrastructure. Consider implementing:
1. **Health monitoring** for all registered services
2. **Circuit breaker patterns** for resilience
3. **Service discovery automation** for dynamic environments
4. **Metrics collection** for performance monitoring

:::
