---
sidebar_position: 1
title: Service-Aware Scaffolding System
description: Complete guide to AgentMap's intelligent code generation system for creating service-integrated agent classes and routing functions
keywords: [scaffolding, code generation, service integration, LLM agents, storage agents, templates, developer productivity]
---

# Service-Aware Scaffolding System

AgentMap's **service-aware scaffolding system** is a sophisticated code generation feature that automatically creates custom agent classes and routing functions from CSV definitions. It analyzes CSV context to detect service requirements and generates complete, working code with automatic service integration.

:::tip Why Scaffolding Matters
The scaffolding system can **reduce custom agent development time by 90%** by automatically generating service-integrated code, proper documentation, and usage examples. It's the difference between writing 100+ lines of boilerplate code and having it generated in seconds.
:::

## How Service-Aware Scaffolding Works

The scaffolding system follows this intelligent process:

1. **CSV Analysis**: Parses your workflow CSV to identify unknown agent types and functions
2. **Service Detection**: Analyzes context fields to determine required services (LLM, storage, vector, etc.)
3. **Architecture Selection**: Chooses unified vs. separate service protocols based on requirements
4. **Code Generation**: Creates complete agent classes with proper service integration
5. **Template Composition**: Uses IndentedTemplateComposer for clean, properly formatted code

## Core Components

### ServiceRequirementParser
Automatically detects and maps service requirements from CSV context:

```python
# Context analysis examples
"{\"services\": [\"llm\", \"storage\"]}"     # → LLMCapableAgent + StorageCapableAgent
"{\"services\": [\"vector\", \"memory\"]}"   # → VectorCapableAgent + MemoryCapableAgent  
"services: llm|csv|json"                    # → LLMCapableAgent + CSVCapableAgent + JSONCapableAgent
```

### IndentedTemplateComposer
Generates clean, properly indented code using modular templates:

- **Master template** system with section insertion
- **Service integration** examples and documentation
- **Proper Python formatting** with textwrap.indent()
- **Context-aware variable substitution**

### AgentRegistryService Integration
Prevents conflicts by only scaffolding unknown agent types:

- **Conflict detection**: Checks existing built-in and custom agents
- **Smart skipping**: Avoids regenerating already-available agents
- **Efficient workflow**: Focuses only on needed custom agents

## Supported Services

### Service Categories

**LLM Services:**
- `"llm"` - Multi-provider LLM service (OpenAI, Anthropic, Google)

**Storage Services:**

*Unified approach:*
- `"storage"` - Generic storage service supporting all types (CSV, JSON, File, Vector, Memory)

*Separate service approach:*
- `"csv"` - CSV file operations
- `"json"` - JSON file operations  
- `"file"` - General file operations
- `"vector"` - Vector search and embeddings
- `"memory"` - In-memory data storage

**Other Services:**
- `"node_registry"` - Access to graph node metadata for dynamic routing

### Architecture Auto-Selection

The system automatically chooses the optimal service architecture:

**Unified Architecture** (when `"storage"` is requested):
```python
class Agent(BaseAgent, StorageCapableAgent):
    def __init__(self):
        self.storage_service: StorageServiceProtocol = None
    
    def process(self, inputs):
        # Unified interface for all storage types
        csv_data = self.storage_service.read("csv", "input.csv")
        json_result = self.storage_service.write("json", "output.json", data)
```

**Separate Architecture** (when specific types are requested):
```python
class Agent(BaseAgent, CSVCapableAgent, VectorCapableAgent):
    def __init__(self):
        self.csv_service: Any = None
        self.vector_service: Any = None
    
    def process(self, inputs):
        # Specific service interfaces
        csv_data = self.csv_service.read("data.csv")
        similar_docs = self.vector_service.search(collection="docs", query="query")
```

## Scaffolding Command Reference

### Basic Commands

```bash
# Scaffold all unknown agents and functions
agentmap scaffold

# Scaffold specific graph only  
agentmap scaffold --graph MyWorkflow

# Custom output directories
agentmap scaffold --output ./custom_agents --functions ./custom_functions

# Use custom CSV file
agentmap scaffold --csv ./workflows/special.csv --config ./custom_config.yaml
```

### Command Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--graph` | `-g` | Graph name to scaffold agents for | All graphs |
| `--csv` | | CSV path override | Config default |
| `--output` | `-o` | Custom directory for agent output | Config: custom_agents_path |
| `--functions` | `-f` | Custom directory for function output | Config: functions_path |
| `--config` | `-c` | Path to custom config file | agentmap_config.yaml |

## Service Context Configuration

### JSON Format (Recommended)

```csv
Context
"{""services"": [""llm"", ""storage""]}"
"{""services"": [""llm"", ""vector"", ""memory""]}"
"{""services"": [""csv"", ""json"", ""file""]}"
```

### String Format (Alternative)

```csv  
Context
"services: llm|storage"
"services: vector|memory|llm"
"services: csv|json"
```

### Service Configuration Examples

**Multi-Service Agent:**
```csv
graph_name,node_name,agent_type,context,prompt,input_fields,output_field
AIWorkflow,ProcessData,IntelligentProcessor,"{""services"": [""llm"", ""vector"", ""storage"", ""memory""]}","Analyze: {data}",data,analysis
```

**Storage-Specific Agent:**
```csv
graph_name,node_name,agent_type,context,prompt,input_fields,output_field
DataFlow,SaveResults,DataPersistence,"{""services"": [""csv"", ""json""]}","Save to: {format}",results|format,saved_path
```

## Generated Code Structure

### Agent Class Template

The scaffolding system generates complete agent classes:

```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from typing import Dict, Any

class IntelligentProcessorAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    """
    Analyze: {data} with LLM and storage capabilities
    
    Node: ProcessData
    Expected input fields: data
    Expected output field: analysis
    
    Available Services:
    - self.llm_service: LLM service for calling language models
    - self.storage_service: Generic storage service (supports all storage types)
    """
    
    def __init__(self):
        super().__init__()
        
        # Service attributes (automatically injected during graph building)
        self.llm_service: LLMServiceProtocol = None
        self.storage_service: StorageServiceProtocol = None
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return the analysis result.
        
        Args:
            inputs (dict): Contains input values with keys: data
            
        Returns:
            The analysis result
        """
        # Access input fields
        data_value = inputs.get("data")
        
        # LLM SERVICE:
        if hasattr(self, 'llm_service') and self.llm_service:
            response = self.llm_service.call_llm(
                provider="openai",  # or "anthropic", "google"
                messages=[{"role": "user", "content": data_value}],
                model="gpt-4"  # optional
            )
            analysis_result = response.get("content")
        
        # STORAGE SERVICE:
        if hasattr(self, 'storage_service') and self.storage_service:
            # Save analysis for future reference
            self.storage_service.write("json", "analysis_results.json", {
                "data": data_value,
                "analysis": analysis_result,
                "timestamp": "2024-01-01T00:00:00Z"
            })
        
        return analysis_result

# ===== SERVICE USAGE EXAMPLES =====
#
# This agent has access to the following services:
#
# LLM SERVICE:
# if hasattr(self, 'llm_service') and self.llm_service:
#     message = {"role": "user", "content": inputs.get("query")}
#     response = self.llm_service.call_llm(
#         provider="openai",  # or "anthropic", "google"
#         messages=[message],
#         model="gpt-4"  # optional
#     )
#     return response.get("content")
#
# STORAGE SERVICE:
# if hasattr(self, 'storage_service') and self.storage_service:
#     data = self.storage_service.read("data_key")
#     
#     # Write storage data  
#     result = self.storage_service.write("output_key", processed_data)
#     return result
```

### Function Template

For routing functions:

```python
from typing import Dict, Any

def choose_specialist(state: Any, success_node="DataExpert", failure_node="GeneralHandler") -> str:
    """
    Route to specialized agents based on query analysis.
    
    Args:
        state: The current graph state
        success_node (str): Node to route to on success
        failure_node (str): Node to route to on failure
        
    Returns:
        str: Name of the next node to execute
    
    Node: Classifier
    Node Context: Route to specialized agents
    
    Available in state:
    - user_query: Input from previous node
    - classification: Expected output to generate
    - last_action_success: Boolean indicating if previous action succeeded
    - error: Error message if previous action failed
    - routing_error: Error message from routing function itself
    """
    # TODO: Implement routing logic
    # Determine whether to return success_node or failure_node
    
    # Example implementation (replace with actual logic):
    query = state.get("user_query", "")
    
    # Route to specialist based on query content
    if any(keyword in query.lower() for keyword in ["data", "analysis", "statistics"]):
        return "DataExpert"
    elif any(keyword in query.lower() for keyword in ["image", "vision", "photo"]):
        return "VisionExpert"
    else:
        return "GeneralHandler"
```

## Development Workflow Integration

### Complete Development Cycle

**1. Design Phase:**
```csv
# Define workflow with service requirements
graph_name,node_name,agent_type,context,input_fields,output_field
SmartBot,analyzer,DataAnalyzer,"{""services"": [""llm"", ""storage""]}",query,analysis
SmartBot,responder,ResponseBot,"{""services"": [""llm""]}",analysis,response
```

**2. Scaffolding Phase:**
```bash
agentmap scaffold --graph SmartBot
```

**3. Customization Phase:**
```python
# Edit generated agents to implement specific logic
class DataAnalyzerAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    def process(self, inputs):
        # Your custom implementation here
        query = inputs.get("query")
        
        # Use LLM for analysis
        analysis = self.llm_service.call_llm(
            provider="anthropic",
            messages=[{"role": "user", "content": f"Analyze: {query}"}],
            model="claude-3-opus-20240229"
        )
        
        # Store for future reference
        self.storage_service.write("json", f"analysis_{hash(query)}.json", analysis)
        
        return analysis.get("content")
```

**4. Testing Phase:**
```bash
agentmap run --graph SmartBot --state '{"query": "What is AI?"}'
```

**5. Production Phase:**
```bash
agentmap compile --graph SmartBot
```

## Advanced Usage Patterns

### Multi-Service Integration

Create agents that use multiple service types:

```csv
Context
"{""services"": [""llm"", ""vector"", ""storage"", ""memory""]}"
```

**Generated Agent:**
```python
class AdvancedAgent(BaseAgent, LLMCapableAgent, VectorCapableAgent, StorageCapableAgent, MemoryCapableAgent):
    def process(self, inputs):
        query = inputs.get("query")
        
        # 1. Search vector database for relevant context
        relevant_docs = self.vector_service.search(
            collection="knowledge_base",
            query=query
        )
        
        # 2. Check memory for previous context
        session_data = self.memory_service.get("session_context")
        
        # 3. Use LLM with enriched context
        enriched_prompt = f"Query: {query}\nContext: {relevant_docs}\nHistory: {session_data}"
        response = self.llm_service.call_llm(
            provider="openai",
            messages=[{"role": "user", "content": enriched_prompt}]
        )
        
        # 4. Store result for future reference
        self.storage_service.write("json", "responses.json", {
            "query": query,
            "response": response.get("content"),
            "context_used": relevant_docs
        })
        
        return response.get("content")
```

### Custom Output Directories

Organize generated code with custom directory structures:

```bash
# Scaffold to project-specific directories
agentmap scaffold \
  --output ./src/agents/custom \
  --functions ./src/routing \
  --graph ProductionWorkflow
```

### Environment Configuration

```bash
# Configure via environment variables
export AGENTMAP_CUSTOM_AGENTS_PATH="./my_project/agents"
export AGENTMAP_FUNCTIONS_PATH="./my_project/functions"
agentmap scaffold
```

## Best Practices

### CSV Design for Scaffolding

**✅ Good Practice:**
```csv
graph_name,node_name,agent_type,context,description,input_fields,output_field,prompt
SmartWorkflow,DataProcessor,IntelligentProcessor,"{""services"": [""llm"", ""storage""]}","Process data using AI",raw_data,processed_data,"Analyze and clean: {raw_data}"
```

**❌ Avoid:**
```csv
graph_name,node_name,agent_type,context
SmartWorkflow,Process,Agent,services:llm
```

### Service Selection Guidelines

**Use unified storage** when you need multiple storage types:
```csv
Context
"{""services"": [""storage""]}"  # Enables CSV, JSON, File, Vector, Memory through one interface
```

**Use separate services** when you need specific functionality:
```csv
Context  
"{""services"": [""vector"", ""memory""]}"  # Specific vector search and memory operations
```

### Customization Patterns

**Start with generated templates** and enhance:

```python
# Generated code provides the structure
def process(self, inputs):
    # Generated service integration
    if hasattr(self, 'llm_service') and self.llm_service:
        # Add your custom logic here
        response = self.llm_service.call_llm(
            provider="anthropic",  # Customize provider
            messages=self._build_custom_messages(inputs),  # Custom message builder
            model="claude-3-opus-20240229"  # Specific model
        )
    
    # Add post-processing, validation, etc.
    return self._process_response(response)

def _build_custom_messages(self, inputs):
    """Custom message building logic"""
    # Your implementation
    
def _process_response(self, response):
    """Custom response processing"""
    # Your implementation
```

## Troubleshooting

### Common Issues

**Problem: No agents scaffolded**
```bash
$ agentmap scaffold
No unknown agents or functions found to scaffold.
```
**Solution:** All agent types in your CSV are already built-in or previously scaffolded. This is normal.

**Problem: Service parsing errors**
```bash
Unknown services: ['invalid_service']. Available: ['llm', 'storage', 'csv', 'json', 'file', 'vector', 'memory', 'node_registry']
```
**Solution:** Check your context field for typos in service names.

**Problem: Template loading errors**
```bash
Template not found: scaffold/master_template.txt
```
**Solution:** This indicates a system installation issue. Reinstall AgentMap.

### Debug Commands

```bash
# Validate CSV before scaffolding
agentmap validate-csv --csv your_workflow.csv

# Check system status
agentmap diagnose

# View configuration paths
agentmap config
```

## Performance Tips

### Scaffolding Optimization

- **Batch operations**: Scaffold all graphs at once rather than individually
- **Cache management**: Templates are cached automatically for faster generation
- **Directory preparation**: Pre-create output directories for faster file operations

```bash
# Efficient: Scaffold all graphs at once
agentmap scaffold

# Less efficient: Individual graph scaffolding
agentmap scaffold --graph Graph1
agentmap scaffold --graph Graph2
```

### Template System Performance

The IndentedTemplateComposer includes caching:

```python
# Template caching statistics (for debugging)
composer.get_cache_stats()
# Returns: {"cache_size": 8, "hits": 15, "misses": 8, "hit_rate": 0.65}
```

## Integration with Other Features

### With Agent Development

Scaffolding integrates seamlessly with [Agent Development](agents/) workflows:

1. **Scaffold** generates the agent structure
2. **Agent Development** guides customize the implementation
3. **Service Integration** provides the service layer
4. **Testing** validates the complete solution

### With CLI Commands

Scaffolding works with all CLI operations:

```bash
# Scaffold → Validate → Test → Compile → Deploy workflow
agentmap scaffold --graph MyWorkflow
agentmap validate-csv --csv workflow.csv
agentmap run --graph MyWorkflow --state '{"input": "test"}'
agentmap compile --graph MyWorkflow
```

### With Configuration Management

Use configuration files to set scaffolding defaults:

```yaml
# agentmap_config.yaml
paths:
  custom_agents: "./src/agents/custom"
  functions: "./src/functions"
  csv_path: "./workflows"

scaffolding:
  default_overwrite: false
  generate_examples: true
  include_service_docs: true
```

## Related Documentation

### 🚀 **Getting Started**
- **[Development Workflow](/docs/getting-started#development-workflow-with-scaffolding)**: Complete scaffold → customize → deploy cycle
- **[Quick Start Guide](/docs/getting-started)**: Your first scaffolded agent

### 🛠️ **Development Guides**
- **[Agent Development](agents/)**: Customizing scaffolded agents
- **[Service Integration](../services/)**: Working with LLM, storage, and vector services
- **[Best Practices](best-practices)**: Code organization and patterns

### 📖 **Reference Documentation**
- **[CLI Commands Reference](/docs/deployment/cli-commands#scaffolding-commands)**: Complete scaffolding command options
- **[CSV Schema Reference](/docs/reference/csv-schema)**: Context field service configuration
- **[Agent Types Reference](/docs/reference/agent-types)**: Built-in agents vs. custom agents

### 🔧 **Advanced Topics**
- **[Template System](/docs/templates)**: Understanding template composition
- **[Service Protocols](/docs/reference/services/)**: Service interface details
- **[Testing Patterns](/docs/guides/development/testing)**: Testing scaffolded agents
