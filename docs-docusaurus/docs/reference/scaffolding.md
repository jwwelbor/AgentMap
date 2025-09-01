---
sidebar_position: 7
title: Scaffolding Reference - API & Template System
description: Complete API reference for AgentMap's service-aware scaffolding system, template composition, and code generation capabilities
keywords: [scaffolding API, template system, code generation, service protocols, IndentedTemplateComposer, GraphScaffoldService]
---

# Scaffolding Reference - API & Template System

Complete API reference for AgentMap's **service-aware scaffolding system**, covering the core services, template composition engine, and code generation capabilities that power intelligent agent scaffolding.

:::info Related Documentation
- **[Scaffolding Guide](/docs/guides/development/scaffolding)**: Complete user guide and examples
- **[Service Integration](/docs/guides/development/service-integration)**: Service integration patterns
- **[CLI Commands](/docs/deployment/cli-commands#scaffolding-commands)**: Command-line scaffolding usage
:::

## Core Services

### GraphScaffoldService

The main service responsible for analyzing CSV files and generating agent code.

#### Methods

##### `scaffold_agents_from_csv(csv_path, options=None)`

Analyzes CSV file and generates agents with service integration.

**Parameters:**
- `csv_path` (Path): Path to CSV file containing graph definitions
- `options` (ScaffoldOptions, optional): Scaffolding configuration options

**Returns:**
- `ScaffoldResult`: Comprehensive scaffolding results with statistics

**Example:**
```python
from pathlib import Path
from agentmap.services.graph_scaffold_service import ScaffoldOptions, GraphScaffoldService

# Initialize service (typically via DI container)
service = container.graph_scaffold_service()

# Configure options
options = ScaffoldOptions(
    graph_name="MyWorkflow",
    output_path=Path("./custom_agents"),
    function_path=Path("./custom_functions"),
    overwrite_existing=False
)

# Execute scaffolding
result = service.scaffold_agents_from_csv(
    csv_path=Path("workflow.csv"),
    options=options
)

print(f"Created {result.scaffolded_count} agents")
print(f"Service stats: {result.service_stats}")
```

##### `scaffold_agent_class(agent_type, info, output_path=None)`

Scaffolds individual agent class file with service integration.

**Parameters:**
- `agent_type` (str): Type of agent to scaffold
- `info` (Dict[str, Any]): Agent information from CSV analysis
- `output_path` (Path, optional): Custom output directory

**Returns:**
- `Path | None`: Path to created file, or None if file exists and overwrite=False

##### `scaffold_edge_function(func_name, info, func_path=None)`

Scaffolds routing function file.

**Parameters:**
- `func_name` (str): Name of function to scaffold
- `info` (Dict[str, Any]): Function information from CSV analysis
- `func_path` (Path, optional): Custom function directory

**Returns:**
- `Path | None`: Path to created file, or None if file exists

##### `get_scaffold_paths(graph_name=None)`

Returns standard scaffold paths from configuration.

**Parameters:**
- `graph_name` (str, optional): Graph name (unused but kept for API consistency)

**Returns:**
- `Dict[str, Path]`: Dictionary with scaffold paths

```python
paths = service.get_scaffold_paths()
# Returns:
# {
#     "agents_path": Path("./custom_agents"),
#     "functions_path": Path("./functions"),
#     "csv_path": Path("./workflows")
# }
```

### ServiceRequirementParser

Parses service requirements from CSV context and maps to protocols.

#### Methods

##### `parse_services(context)`

Analyzes context and returns service requirements with automatic architecture detection.

**Parameters:**
- `context` (Any): Context from CSV (string, dict, or None)

**Returns:**
- `ServiceRequirements`: Parsed service information with protocols and usage examples

**Example:**
```python
from agentmap.services.graph_scaffold_service import ServiceRequirementParser

parser = ServiceRequirementParser()

# JSON format
context = '{"services": ["llm", "storage"]}'
requirements = parser.parse_services(context)

print(requirements.services)        # ["llm", "storage"]
print(requirements.protocols)       # ["LLMCapableAgent", "StorageCapableAgent"]
print(requirements.imports)         # ["from agentmap.services.protocols import LLMCapableAgent", ...]
print(requirements.attributes)      # [ServiceAttribute(name="llm_service", type_hint="LLMServiceProtocol", ...)]
print(requirements.usage_examples)  # {"llm": "# LLM SERVICE:\n...", "storage": "# STORAGE SERVICE:\n..."}
```

#### Service Architecture Logic

**Unified Architecture** (when `"storage"` is requested):
```python
# Input
context = '{"services": ["storage"]}'
requirements = parser.parse_services(context)

# Output
requirements.protocols == ["StorageCapableAgent"]
# Single service interface for all storage types
```

**Separate Architecture** (when specific types are requested):
```python
# Input
context = '{"services": ["csv", "json", "vector"]}'
requirements = parser.parse_services(context)

# Output
requirements.protocols == ["CSVCapableAgent", "JSONCapableAgent", "VectorCapableAgent"]
# Dedicated service interfaces for each type
```

### IndentedTemplateComposer

Template composition service with proper indentation handling.

#### Methods

##### `compose_template(agent_type, info, service_reqs)`

Composes complete agent template with service integration.

**Parameters:**
- `agent_type` (str): Type of agent to scaffold
- `info` (Dict[str, Any]): Agent information dictionary
- `service_reqs` (ServiceRequirements): Parsed service requirements

**Returns:**
- `str`: Complete agent template with correct indentation

**Example:**
```python
from agentmap.services.indented_template_composer import IndentedTemplateComposer

composer = IndentedTemplateComposer(app_config_service, logging_service)

# Compose agent template
template = composer.compose_template(
    agent_type="DataAnalyzer",
    info={
        "agent_type": "DataAnalyzer",
        "node_name": "ProcessData",
        "context": '{"services": ["llm", "storage"]}',
        "input_fields": ["data", "query"],
        "output_field": "analysis",
        "description": "AI-powered data analysis",
        "prompt": "Analyze {data} for {query}"
    },
    service_reqs=service_requirements
)

print(template)  # Complete Python agent class code
```

##### `compose_function_template(func_name, info)`

Composes function template with proper formatting.

**Parameters:**
- `func_name` (str): Name of function to scaffold
- `info` (Dict[str, Any]): Function information dictionary

**Returns:**
- `str`: Complete function template string

##### `get_cache_stats()`

Returns template caching statistics.

**Returns:**
- `Dict[str, Any]`: Cache statistics including hit rate and cached templates

```python
stats = composer.get_cache_stats()
# Returns:
# {
#     "cache_size": 8,
#     "hits": 15,
#     "misses": 8,
#     "hit_rate": 0.65,
#     "total_requests": 23,
#     "cached_templates": ["header.txt", "class_definition.txt", ...]
# }
```

##### `clear_template_cache()`

Clears template cache and resets statistics.

## Data Structures

### ScaffoldOptions

Configuration options for scaffolding operations.

```python
@dataclass
class ScaffoldOptions:
    graph_name: Optional[str] = None          # Graph name to filter by
    output_path: Optional[Path] = None        # Custom agent output directory
    function_path: Optional[Path] = None      # Custom function output directory  
    overwrite_existing: bool = False          # Whether to overwrite existing files
```

### ScaffoldResult

Result of scaffolding operations with comprehensive statistics.

```python
@dataclass
class ScaffoldResult:
    scaffolded_count: int                           # Total items scaffolded
    created_files: List[Path] = field(default_factory=list)     # Paths to created files
    skipped_files: List[Path] = field(default_factory=list)     # Paths to skipped files
    service_stats: Dict[str, int] = field(default_factory=dict) # Service integration statistics
    errors: List[str] = field(default_factory=list)             # Error messages
```

**Example:**
```python
result = ScaffoldResult(
    scaffolded_count=3,
    created_files=[
        Path("custom_agents/data_analyzer_agent.py"),
        Path("custom_agents/response_generator_agent.py"),
        Path("functions/route_handler.py")
    ],
    skipped_files=[Path("custom_agents/existing_agent.py")],
    service_stats={"with_services": 2, "without_services": 1},
    errors=[]
)
```

### ServiceRequirements

Container for parsed service requirements.

```python
class ServiceRequirements(NamedTuple):
    services: List[str]                      # List of requested services
    protocols: List[str]                     # Protocol class names to inherit
    imports: List[str]                       # Import statements to include
    attributes: List[ServiceAttribute]       # Service attributes for __init__
    usage_examples: Dict[str, str]          # Service usage examples by service name
```

### ServiceAttribute

Represents a service attribute to be added to an agent.

```python
@dataclass
class ServiceAttribute:
    name: str           # Attribute name (e.g., "llm_service")
    type_hint: str      # Type hint (e.g., "LLMServiceProtocol")
    documentation: str  # Documentation string
```

## Template System

### Template Structure

The scaffolding system uses a modular template approach with the following structure:

```
src/agentmap/templates/system/scaffold/
├── master_template.txt           # Main template with section placeholders
├── modular/                      # Section templates
│   ├── header.txt               # Import statements and docstring
│   ├── class_definition.txt     # Class declaration with protocols
│   ├── init_method.txt          # __init__ method with service attributes
│   ├── process_method.txt       # Main process method
│   ├── helper_methods.txt       # Additional helper methods
│   └── footer.txt               # Closing comments and examples
├── services/                     # Service usage examples
│   ├── llm_usage.txt            # LLM service usage example
│   ├── storage_usage.txt        # Storage service usage example
│   ├── vector_usage.txt         # Vector service usage example
│   ├── memory_usage.txt         # Memory service usage example
│   ├── csv_usage.txt            # CSV service usage example
│   ├── json_usage.txt           # JSON service usage example
│   ├── file_usage.txt           # File service usage example
│   └── node_registry_usage.txt  # Node registry usage example
└── function_template.txt         # Function template
```

### Template Variables

Templates use standard Python string formatting with these variables:

#### Agent Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `agent_type` | Original agent type from CSV | `"DataAnalyzer"` |
| `class_name` | Generated PascalCase class name | `"DataAnalyzerAgent"` |
| `class_definition` | Complete class declaration with protocols | `"class DataAnalyzerAgent(BaseAgent, LLMCapableAgent):"` |
| `service_description` | Service capabilities description | `" with LLM capabilities"` |
| `imports` | Import statements for services | `"from agentmap.services.protocols import LLMCapableAgent"` |
| `description` | Agent description from CSV | `"AI-powered data analysis"` |
| `node_name` | Node name from CSV | `"ProcessData"` |
| `input_fields` | Comma-separated input fields | `"data, query"` |
| `output_field` | Output field name | `"analysis"` |
| `services_doc` | Service documentation for docstring | `"Available Services:\n- self.llm_service: ..."` |
| `prompt_doc` | Prompt documentation | `"Default prompt: Analyze {data} for {query}"` |
| `service_attributes` | Service attribute declarations | `"self.llm_service: LLMServiceProtocol = None"` |
| `input_field_access` | Input field access code | `'data_value = inputs.get("data")'` |
| `service_usage_examples` | Service usage examples | `"# LLM SERVICE:\nif hasattr(self, 'llm_service')..."` |
| `context` | Context from CSV | `'{"services": ["llm"]}'` |

#### Function Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `func_name` | Function name | `"route_handler"` |
| `context` | Context from CSV | `"Route based on analysis result"` |
| `context_fields` | Available state fields documentation | `"- user_input: Input from previous node"` |
| `success_node` | Success routing target | `"ProcessData"` |
| `failure_node` | Failure routing target | `"ErrorHandler"` |
| `node_name` | Source node name | `"Router"` |
| `description` | Function description | `"Dynamic routing based on analysis"` |
| `output_field` | Expected output field | `"routing_decision"` |

### Template Loading

Templates are loaded using the internal template loading system:

```python
# Template loading priority:
# 1. Embedded resources (packaged with AgentMap)
# 2. Prompts directory (configurable location)
# 3. Error if not found

template_content = composer._load_template_internal("modular/header.txt")
```

### Custom Template Development

To create custom templates:

1. **Understand the structure**: Review existing templates in the codebase
2. **Use proper variables**: Reference the template variables table above
3. **Test template loading**: Ensure templates load correctly
4. **Handle indentation**: The system automatically handles indentation

**Example Custom Service Template:**
```python
# Custom service usage template: custom_service_usage.txt
if hasattr(self, '{attribute_name}') and self.{attribute_name}:
    result = self.{attribute_name}.process_data(
        input_data=inputs.get("{input_field}"),
        options={{"mode": "advanced"}}
    )
    return result.get("output")
```

## Error Handling

### Common Errors

#### Template Loading Errors

```python
# FileNotFoundError: Template not found
try:
    template = composer._load_template_internal("missing_template.txt")
except FileNotFoundError as e:
    print(f"Template not found: {e}")
```

#### Service Parsing Errors

```python
# ValueError: Unknown services
try:
    requirements = parser.parse_services('{"services": ["invalid_service"]}')
except ValueError as e:
    print(f"Service parsing error: {e}")
    # Output: Unknown services: ['invalid_service']. Available: ['llm', 'storage', ...]
```

#### File Creation Errors

```python
# Permission or path errors during file creation
try:
    result = service.scaffold_agents_from_csv(csv_path, options)
    if result.errors:
        for error in result.errors:
            print(f"Scaffolding error: {error}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Error Recovery

```python
def safe_scaffolding(csv_path: Path, options: ScaffoldOptions) -> ScaffoldResult:
    """Safe scaffolding with comprehensive error handling"""
    try:
        result = service.scaffold_agents_from_csv(csv_path, options)
        
        # Check for partial failures
        if result.errors:
            print(f"⚠️  {len(result.errors)} errors occurred:")
            for error in result.errors:
                print(f"   - {error}")
        
        # Report success metrics
        if result.scaffolded_count > 0:
            print(f"✅ Successfully scaffolded {result.scaffolded_count} items")
            if result.service_stats:
                with_services = result.service_stats.get("with_services", 0)
                without_services = result.service_stats.get("without_services", 0)
                print(f"📊 Service integration: {with_services} with services, {without_services} basic")
        
        return result
        
    except FileNotFoundError:
        print("❌ CSV file not found. Check the file path.")
        return ScaffoldResult(scaffolded_count=0, errors=["CSV file not found"])
    
    except PermissionError:
        print("❌ Permission denied. Check directory write permissions.")
        return ScaffoldResult(scaffolded_count=0, errors=["Permission denied"])
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return ScaffoldResult(scaffolded_count=0, errors=[str(e)])
```

## Performance & Optimization

### Template Caching

The system automatically caches templates for improved performance:

```python
# Cache statistics monitoring
stats = composer.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']:.2%}")

# Manual cache management
if stats['cache_size'] > 50:  # Cache getting large
    composer.clear_template_cache()
```

### Batch Operations

For optimal performance, scaffold multiple agents in one operation:

```python
# Efficient: Process entire CSV at once
result = service.scaffold_agents_from_csv(csv_path)

# Less efficient: Individual agent scaffolding
for agent_type, info in agent_info.items():
    service.scaffold_agent_class(agent_type, info)
```

### Memory Usage

Monitor memory usage for large scaffolding operations:

```python
import psutil
import os

def monitor_scaffolding_memory():
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Perform scaffolding
    result = service.scaffold_agents_from_csv(large_csv_path)
    
    final_memory = process.memory_info().rss
    memory_used = (final_memory - initial_memory) / 1024 / 1024  # MB
    
    print(f"Memory used: {memory_used:.2f} MB for {result.scaffolded_count} agents")
```

## Integration Examples

### CLI Integration

```python
# Integration with CLI commands
def cli_scaffold_command(graph: str, csv: str, output: str):
    """CLI command implementation"""
    try:
        # Initialize services via DI
        container = initialize_application()
        service = container.graph_scaffold_service()
        
        # Configure options from CLI args
        options = ScaffoldOptions(
            graph_name=graph,
            output_path=Path(output) if output else None,
            overwrite_existing=False
        )
        
        # Execute scaffolding
        result = service.scaffold_agents_from_csv(Path(csv), options)
        
        # Report results
        if result.scaffolded_count > 0:
            print(f"✅ Scaffolded {result.scaffolded_count} agents/functions")
            for file_path in result.created_files:
                print(f"   📁 Created: {file_path.name}")
        else:
            print("ℹ️  No agents to scaffold - all types already available")
            
    except Exception as e:
        print(f"❌ Scaffolding failed: {e}")
        sys.exit(1)
```

### Custom Service Integration

```python
# Extending the service parser for custom services
class CustomServiceParser(ServiceRequirementParser):
    def __init__(self):
        super().__init__()
        # Add custom service mappings
        self.separate_service_map.update({
            "database": {
                "protocol": "DatabaseCapableAgent",
                "import": "from myapp.protocols import DatabaseCapableAgent",
                "attribute": "database_service",
                "type_hint": "DatabaseServiceProtocol",
                "doc": "Database service for SQL operations"
            }
        })
    
    def _get_usage_example(self, service: str, service_protocol_map: Dict) -> str:
        if service == "database":
            return """# DATABASE SERVICE:
            if hasattr(self, 'database_service') and self.database_service:
                result = self.database_service.execute_query(
                    query="SELECT * FROM users WHERE id = %s",
                    params=[user_id]
                )
                return result.fetchall()"""
        
        return super()._get_usage_example(service, service_protocol_map)
```

### Testing Integration

```python
# Unit testing scaffolding operations
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

class TestScaffolding(unittest.TestCase):
    def setUp(self):
        self.mock_config = Mock()
        self.mock_logging = Mock()
        self.mock_function_service = Mock()
        self.mock_agent_registry = Mock()
        self.mock_template_composer = Mock()
        
        self.service = GraphScaffoldService(
            self.mock_config,
            self.mock_logging,
            self.mock_function_service,
            self.mock_agent_registry,
            self.mock_template_composer
        )
    
    def test_agent_scaffolding(self):
        """Test basic agent scaffolding functionality"""
        # Setup mocks
        self.mock_agent_registry.has_agent.return_value = False
        self.mock_template_composer.compose_template.return_value = "generated code"
        
        # Test data
        agent_info = {
            "DataAnalyzer": {
                "agent_type": "DataAnalyzer",
                "node_name": "ProcessData",
                "context": '{"services": ["llm"]}',
                "input_fields": ["data"],
                "output_field": "result"
            }
        }
        
        # Mock CSV reading
        with patch('builtins.open'), patch('csv.DictReader', return_value=[{
            "AgentType": "DataAnalyzer",
            "Node": "ProcessData",
            "Context": '{"services": ["llm"]}',
            "Input_Fields": "data",
            "Output_Field": "result"
        }]):
            result = self.service.scaffold_agents_from_csv(Path("test.csv"))
        
        # Assertions
        self.assertEqual(result.scaffolded_count, 1)
        self.assertEqual(len(result.created_files), 1)
        self.assertEqual(result.service_stats["with_services"], 1)
```
