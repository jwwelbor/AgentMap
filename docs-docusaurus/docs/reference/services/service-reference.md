---
sidebar_position: 1
title: Service Reference
description: Quick reference for all AgentMap services with context parameters and usage examples
---

# Service Reference

Quick reference for all AgentMap services, organized by category with context parameters and implementation details.

import ServiceCatalog from '@site/src/components/ServiceCatalog';

<ServiceCatalog />

## Service Categories

### Core Services
Essential business logic services that form the backbone of AgentMap workflows.

### Infrastructure Services  
Technical services providing logging, state management, and system utilities.

### Configuration Services
Services managing application and storage configuration with smart defaults.

### Storage Services
Data persistence services supporting multiple storage types and formats.

### Validation Services
Services ensuring data integrity and configuration correctness.

### Execution Services
Services tracking and managing workflow execution with policy evaluation.

## Context Parameter Usage

All services accept context parameters in Python dictionary format:

```python
context = {
    'provider': 'openai',
    'model': 'gpt-4',
    'temperature': 0.7
}
```

When using services in CSV workflows, context should be specified as JSON:

```csv
name,description,type,context
llm_node,Generate response,llm,"{\"provider\": \"openai\", \"model\": \"gpt-4\"}"
```

## Service Integration

Services integrate through dependency injection in the DI container:

```python
# Services are automatically injected based on protocols
container = Container()
graph_runner = container.graph_runner_service()
# GraphRunnerService has CompilationService, ExecutionTrackingService, etc. injected
```

## Protocol Implementation

Services implement specific protocols to define their capabilities:

- **LLMServiceProtocol**: Language model integration
- **StorageServiceProtocol**: Data persistence operations  
- **LoggingServiceProtocol**: Structured logging functionality
- **ValidationServiceProtocol**: Data validation operations

## Common Usage Patterns

### 1. Graph Building and Execution
```python
# Build graph from CSV
graph_builder = container.graph_builder_service()
graph = graph_builder.build_from_csv(Path("workflow.csv"))

# Run with tracking
runner = container.graph_runner_service()
result = runner.run_graph("MyWorkflow", {'input': 'data'})
```

### 2. Storage Operations
```python
# Get storage service
storage_manager = container.storage_manager()
csv_service = storage_manager.get_service("csv")

# Read/write data
data = csv_service.read("users", format="records")
result = csv_service.write("users", new_data)
```

### 3. Configuration Management
```python
# Get configuration
config = container.app_config_service()
csv_path = config.get_csv_path()
llm_config = config.get_llm_config("openai")
```

### 4. Validation
```python
# Validate CSV files
validator = container.validation_service()
result = validator.validate_csv(Path("workflow.csv"))
if not result.is_valid:
    for error in result.errors:
        print(f"Error: {error.message}")
```

## Error Handling

Services follow consistent error handling patterns:

- **Graceful Degradation**: Optional services return None if unavailable
- **Clear Error Messages**: ValidationResult objects with detailed error information
- **Logging Integration**: All errors are properly logged with context
- **Type Safety**: Strong typing prevents common configuration errors

## Service Lifecycle

1. **Lazy Creation**: Services created when first requested from container
2. **Singleton Pattern**: Services cached for reuse within container scope
3. **Dependency Injection**: All dependencies automatically resolved
4. **Optional Services**: LLM and external services handle missing configuration gracefully

## Best Practices

1. **Always use DI container** - Never instantiate services directly
2. **Check for None returns** - Optional services may not be available
3. **Use proper typing** - Leverage type hints for better IDE support
4. **Handle validation errors** - Always check ValidationResult objects
5. **Use context parameters** - Configure services through context when possible

## Adding Custom Services

To extend AgentMap with custom services:

1. **Create service class** with proper constructor injection
2. **Implement relevant protocols** for capability declaration
3. **Register in DI container** with dependency resolution
4. **Add to documentation** following the patterns shown above
5. **Write comprehensive tests** using the real DI container

Example custom service:
```python
class CustomAnalyticsService:
    def __init__(self, storage_manager: StorageManager, 
                 logging_service: LoggingService):
        self.storage = storage_manager
        self.logger = logging_service.get_class_logger(self)
    
    def track_event(self, event: str, data: Dict[str, Any]) -> bool:
        self.logger.info(f"Tracking event: {event}")
        # Implementation here
        return True

# Register in container
class Container:
    def custom_analytics_service(self) -> CustomAnalyticsService:
        return self._get_or_create('_custom_analytics_service',
            lambda: CustomAnalyticsService(
                storage_manager=self.storage_manager(),
                logging_service=self.logging_service()
            )
        )
```
