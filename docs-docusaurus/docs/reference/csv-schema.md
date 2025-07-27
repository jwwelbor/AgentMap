---
sidebar_position: 1
title: CSV Schema Reference - Define Agentic AI Workflows & Multi-Agent Systems
description: Complete CSV schema reference for AgentMap agentic AI workflows. Learn to define autonomous multi-agent systems, RAG AI workflows, and LLM orchestration with CSV files.
keywords: [CSV schema, agentic AI workflows, multi-agent systems, RAG AI configuration, LLM orchestration, autonomous agents, agent routing, vector database workflows, agent framework CSV]
image: /img/agentmap-hero.png
---

# CSV Schema Reference

AgentMap uses CSV files to define **agentic AI workflows** as directed graphs where autonomous agents make decisions, route intelligently, and collaborate in multi-agent systems. Each row in the CSV represents an autonomous agent node that can reason, decide, and interact with other agents. This document explains how to structure CSV files for building sophisticated agentic AI systems.

**⚠️ IMPORTANT: JSON Configuration Format**

**AgentMap uses Python dictionary syntax for structured configuration in CSV files:**

✅ **Correct**: `"{'provider': 'openai', 'temperature': 0.7}"`  
❌ **Wrong**: `"{"provider": "openai", "temperature": 0.7}"` (breaks CSV parsing)

**Why Python dict syntax?**
- **CSV-friendly**: No comma conflicts or escaped quotes
- **Readable**: Clean and easy to edit in spreadsheets
- **Python-native**: AgentMap parses these as Python literals using `ast.literal_eval()`
- **Tool compatible**: Works perfectly with Pandas, Excel, Google Sheets

---

:::tip Quick Start
🚀 **New to AgentMap?** Start with our [Quick Start Guide](../getting-started) to build your first workflow, then return here for detailed schema reference.
:::

:::info Why CSV for Agentic AI?
**CSV files are perfect for multi-agent systems because they:**
- ✅ **Collaborative** - Teams can design agent workflows together in familiar spreadsheets
- ✅ **Version Control** - Track changes to agent configurations and routing logic
- ✅ **Visual** - See the entire multi-agent system structure at a glance
- ✅ **Accessible** - No programming required to design sophisticated agentic workflows
- ✅ **Scalable** - Define complex RAG AI and LLM orchestration systems easily
:::

import DownloadButton from '@site/src/components/DownloadButton';
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CSVTable from '@site/src/components/CSVTable';

## CSV Columns

| Column | Required | Description |
|--------|----------|-------------|
| `graph_name` | Yes | Name of the workflow graph. Multiple nodes can share the same graph_name to form a complete workflow. |
| `Node` | Yes | Unique identifier for this node within the graph. |
| `next_node` | No | Direct connection to another node. Use this for simple linear flows. |
| `Context` | No | Description or JSON configuration for the node. Can contain memory configuration. |
| `agent_type` | No | Type of agent to use (e.g., "openai", "claude", "echo"). Defaults to "Default" if not specified. |
| `next_on_success` | No | Where to go on success. Can be a node name or multiple nodes with pipe separators. |
| `next_on_failure` | No | Where to go on failure. Can be a node name or multiple nodes with pipe separators. |
| `input_fields` | No | State fields to extract as input for this agent. Pipe-separated list. |
| `output_field` | No | Field in state where this agent's output should be stored. |
| `Prompt` | No | Text or template used by LLM agents. For some agent types, this can be configuration data. Can reference managed prompts using the prompt: notation. |
| `Description` | No | Detailed documentation for the node's purpose. Unlike Context (which can be used for configuration), Description is solely for documentation and does not affect functionality. |

## Quick Start Templates

Get started quickly with these ready-to-use CSV templates:

<Tabs>
<TabItem value="basic" label="Basic Template" default>

<DownloadButton 
  filename="agentmap_basic_template.csv" 
  content={`graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt,description
MyFlow,Start,,Get user input,input,Process,ErrorHandler,,user_input,Enter your data:,Entry point for workflow
MyFlow,Process,,Process the input,default,End,ErrorHandler,user_input,result,,Main processing logic
MyFlow,ErrorHandler,,Handle any errors,echo,End,,error,error_message,,Error handling and display
MyFlow,End,,Complete the workflow,echo,,,result|error_message,output,,Final output node`}>
  📄 Download Basic Template
</DownloadButton>

</TabItem>
<TabItem value="advanced" label="Advanced Template">

<DownloadButton 
  filename="agentmap_advanced_template.csv" 
  content={`graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt,description
AdvancedFlow,GetInput,,Collect user requirements,input,RouteByType,ErrorHandler,,requirements,Describe your task:,User input collection with validation
AdvancedFlow,RouteByType,,"{'analysis_type': 'sentiment'|'summary'|'extraction'}",routing,AnalyzeSentiment|CreateSummary|ExtractData,ErrorHandler,requirements,route_decision,,Dynamic routing based on task type
AdvancedFlow,AnalyzeSentiment,,"{'provider': 'openai', 'temperature': 0.3}",llm,FormatResults,ErrorHandler,requirements,sentiment_analysis,Analyze the sentiment of this text: {requirements},Sentiment analysis with low temperature
AdvancedFlow,CreateSummary,,"{'provider': 'anthropic', 'model': 'claude-3-sonnet', 'max_tokens': 150}",llm,FormatResults,ErrorHandler,requirements,summary,Create a concise summary of: {requirements},Text summarization with token limit
AdvancedFlow,ExtractData,,"{'provider': 'openai', 'temperature': 0.1}",llm,FormatResults,ErrorHandler,requirements,extracted_data,Extract key entities and data from: {requirements},Data extraction with minimal creativity
AdvancedFlow,FormatResults,,"{'template': 'markdown'}",formatter,SaveResults,ErrorHandler,sentiment_analysis|summary|extracted_data,formatted_output,,Format results in markdown
AdvancedFlow,SaveResults,,"{'directory': 'outputs', 'timestamp': True}",file_writer,End,ErrorHandler,formatted_output,save_path,results_{timestamp}.md,Save results to file with timestamp
AdvancedFlow,ErrorHandler,,Handle errors gracefully,echo,End,,error,error_message,,Comprehensive error handling
AdvancedFlow,End,,Workflow completion,echo,,,formatted_output|save_path|error_message,final_output,,Final output with status`}>
  ⚙️ Download Advanced Template
</DownloadButton>

</TabItem>
<TabItem value="api" label="API Integration Template">

<DownloadButton 
  filename="agentmap_api_template.csv" 
  content={`graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt,description
APIFlow,GetQuery,,Collect search parameters,input,FetchData,ErrorHandler,,search_params,Enter search criteria:,User input for API query
APIFlow,FetchData,,"{'api_endpoint': 'https://api.example.com', 'method': 'GET', 'timeout': 30}",custom:APIAgent,ProcessData,ErrorHandler,search_params,api_response,,External API data fetching
APIFlow,ProcessData,,"{'provider': 'openai', 'temperature': 0.5}",llm,FormatOutput,ErrorHandler,api_response|search_params,processed_data,"Analyze this API data and provide insights: {api_response}",AI-powered data analysis
APIFlow,FormatOutput,,"{'format': 'json', 'pretty_print': True}",formatter,SaveData,ErrorHandler,processed_data,formatted_json,,JSON formatting with pretty print
APIFlow,SaveData,,"{'storage_type': 'local', 'backup': True}",data_store,End,ErrorHandler,formatted_json|search_params,storage_result,api_results/{search_params}_data.json,Persistent data storage
APIFlow,ErrorHandler,,"{'retry_count': 3, 'fallback_message': 'Service temporarily unavailable'}",error_handler,End,,error,error_details,,Robust error handling with retry
APIFlow,End,,"{'include_metadata': True}",summary,,,storage_result|formatted_json|error_details,final_result,,Comprehensive output with metadata`}>
  🔌 Download API Template
</DownloadButton>

</TabItem>
</Tabs>

## Field Details

### Routing Fields (next_node, next_on_success, next_on_failure)

You can define routing in two ways:
1. Using `next_node` for simple linear flows
2. Using `next_on_success` and `next_on_failure` for conditional branching based on `last_action_success`

:::warning Routing Rule Conflict
**⚠️ Important:** Don't use both `next_node` and `next_on_success`/`next_on_failure` in the same row - this will raise an `Invalidnext_nodeDefinitionError`.

Use either:
- `next_node` for simple linear flows
- `next_on_success`/`next_on_failure` for conditional branching
:::

### Function References

You can use function references for advanced routing:
```
func:function_name
```

The function should be defined in the functions directory and will be called to determine the next node.

### Context and Description Fields

AgentMap provides two fields for documenting and configuring nodes:

- **Context**: Can contain plain text description or JSON for advanced configuration
- **Description**: Purely for documentation purposes - doesn't affect functionality

Examples:

```csv
GraphA,Node1,"{'memory':{'type':'buffer'}}","This node processes user input to extract key entities",...
```

The Description field is useful for:
- Documenting complex node behavior
- Explaining the node's role in the workflow
- Documenting expected inputs and outputs
- Adding notes for other developers

## Service Configuration for Scaffolding

:::tip Service-Aware Scaffolding
AgentMap's **service-aware scaffolding system** automatically detects service requirements from the Context field and generates agents with proper service integration. This dramatically accelerates custom agent development.
:::

### Service Configuration Syntax

Use the Context field to specify service requirements for custom agents that will be scaffolded:

**JSON Format (Recommended):**
```csv
Context
"{""services"": [""llm"", ""storage""]}"
"{""services"": [""llm"", ""vector"", ""memory""]}"
"{""services"": [""csv"", ""json"", ""file""]}"
```

**String Format (Alternative):**
```csv
Context
"services: llm|storage"
"services: vector|memory|llm"
"services: csv|json"
```

### Supported Services

**LLM Services:**
- `"llm"` - Multi-provider LLM service (OpenAI, Anthropic, Google)

**Storage Services:**

*Unified Storage Architecture:*
- `"storage"` - Generic storage service supporting all types (CSV, JSON, File, Vector, Memory)

*Separate Service Architecture:*
- `"csv"` - CSV file operations
- `"json"` - JSON file operations  
- `"file"` - General file operations
- `"vector"` - Vector search and embeddings
- `"memory"` - In-memory data storage

**Other Services:**
- `"node_registry"` - Access to graph node metadata for dynamic routing

### Service Configuration Examples

<CSVTable 
  csvContent={`graph_name,node_name,agent_type,context,description,input_fields,output_field,prompt
AIWorkflow,Analyzer,IntelligentAnalyzer,"{""services"": [""llm""]}","AI-powered analysis agent",user_query,analysis,"Analyze: {user_query}"
AIWorkflow,DataProcessor,DataHandler,"{""services"": [""llm"", ""storage""]}","Process and store data",raw_data,processed_data,"Process: {raw_data}"
AIWorkflow,SearchAgent,DocumentRetriever,"{""services"": [""vector""]}","Semantic document search",search_query,relevant_docs,"Find docs for: {search_query}"
AIWorkflow,RAGAgent,SmartResponder,"{""services"": [""llm"", ""vector"", ""storage""]}","RAG-based response generation",question,answer,"Answer: {question}"`}
  title="Service Configuration Examples"
  filename="service_configuration_examples"
/>

### Generated Agent Structure

When you run `agentmap scaffold`, the system analyzes the Context field and generates agents with proper service integration:

**Example: LLM + Storage Service Configuration**
```csv
graph_name,node_name,agent_type,context
SmartWorkflow,DataAnalyzer,IntelligentProcessor,"{""services"": [""llm"", ""storage""]}"
```

**Generated Agent Code:**
```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from typing import Dict, Any

class IntelligentProcessorAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    """
    Generated agent with LLM and storage capabilities
    
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
        # Generated foundation with service integration examples
        # Ready to customize with your logic
        return "Your IntelligentProcessor implementation here"
```

### Service Architecture Selection

The scaffolding system automatically chooses the optimal service architecture:

**Unified Architecture** (when `"storage"` is requested):
```csv
Context
"{""services"": [""storage""]}"
```
Generates: `class Agent(BaseAgent, StorageCapableAgent)`
- Single service interface for all storage types
- Access CSV, JSON, File, Vector, Memory through one service

**Separate Architecture** (when specific types are requested):
```csv
Context
"{""services"": [""csv"", ""vector"", ""memory""]}"
```
Generates: `class Agent(BaseAgent, CSVCapableAgent, VectorCapableAgent, MemoryCapableAgent)`
- Dedicated service interfaces for each type
- Type-specific operations and optimizations

### Multi-Service Agent Configuration

**Comprehensive AI Agent:**
```csv
graph_name,node_name,agent_type,context
AdvancedWorkflow,AIProcessor,ComprehensiveAgent,"{""services"": [""llm"", ""vector"", ""storage"", ""memory"", ""node_registry""]}"
```

**Generated:**
```python
class ComprehensiveAgent(BaseAgent, LLMCapableAgent, VectorCapableAgent, StorageCapableAgent, MemoryCapableAgent, NodeRegistryUser):
    # All service capabilities integrated
    # Ready for complex multi-service workflows
```

### Best Practices for Service Configuration

**✅ Recommended:**
```csv
# Clear, specific service requirements
Context
"{""services"": [""llm"", ""storage""]}"

# Multi-service for complex agents
Context
"{""services"": [""llm"", ""vector"", ""memory""]}"

# Unified storage for multiple formats
Context
"{""services"": [""storage""]}"
```

**❌ Avoid:**
```csv
# Unclear or missing service specs
Context
"some services needed"

# Redundant service combinations
Context
"{""services"": [""storage"", ""csv"", ""json""]}"

# Invalid service names
Context
"{""services"": [""unknown_service""]}"
```

### Service Integration Workflow

1. **Design**: Specify service requirements in CSV Context field
2. **Scaffold**: Run `agentmap scaffold` to generate service-integrated agents
3. **Customize**: Enhance generated agents with your specific logic
4. **Test**: Validate service integration and functionality
5. **Deploy**: Use compiled agents in production workflows

```bash
# Complete workflow
agentmap scaffold --graph MyWorkflow        # Generate service-integrated agents
agentmap run --graph MyWorkflow              # Test with generated agents
agentmap compile --graph MyWorkflow         # Compile for production
```

### input_fields and output_field

These fields control data flow between nodes:
- `input_fields`: Which state values this node can access (pipe-separated)
- `output_field`: Where this node's output is stored in state

### Complex Routing

For complex routing patterns:
- Function references: `func:choose_next`
- Multiple targets: Use pipe-separator in next_on_success or next_on_failure

## Example CSV Structure

<CSVTable 
  csvContent={`graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt,description
WeatherFlow,GetLocation,,Get user location,input,FetchWeather,ErrorHandler,,location,Enter the city name:,Input node for weather workflow
WeatherFlow,FetchWeather,,"{'api_key': 'env:WEATHER_API'}",weather_api,GenerateReport,ErrorHandler,location,weather_data,,Fetches weather data from API
WeatherFlow,GenerateReport,,"{'provider': 'openai'}",llm,End,ErrorHandler,weather_data|location,report,Generate weather report for {location},Creates natural language weather report
WeatherFlow,ErrorHandler,,Handle any errors,echo,End,,error,error_message,,Error handling node
WeatherFlow,End,,Complete workflow,echo,,,report|error_message,output,,Final output node`}
  title="Complete Weather Workflow Example"
  filename="weather_workflow_example"
/>

## Best Practices

### Node Naming
- Use descriptive node names that indicate their purpose
- Avoid spaces and special characters
- Use PascalCase or snake_case consistently

### Graph Organization
- Group related nodes with consistent graph_name
- Design clear flow from start to end
- Include error handling paths

### Context Configuration
- Use JSON format for complex configurations
- Reference environment variables with `env:VARIABLE_NAME`
- Document configuration options in Description field

### Data Flow
- Specify input_fields to control what data flows between nodes
- Use output_field to name result storage consistently
- Avoid overwriting important state values

### Error Handling
- Always include error handling nodes
- Use next_on_failure to route to error handlers
- Design graceful degradation paths

### Documentation
- Use Description field for detailed node documentation
- Include expected inputs and outputs
- Document any special configuration requirements

## Validation Rules

### Required Fields
- **graph_name**: Must be non-empty string
- **Node**: Must be unique within the graph

### Routing Validation
- Cannot use both `next_node` and `next_on_success`/`next_on_failure` in the same row
- Raises `Invalidnext_nodeDefinitionError` if both are specified
- Target nodes in routing fields must exist in the graph

### Field References
- `input_fields` and `output_field` should reference valid state keys
- Pipe-separated lists must not contain empty values
- Function references must follow `func:function_name` format

### Context Validation
- JSON in Context field must be valid JSON syntax
- Environment variable references must use `env:VARIABLE_NAME` format
- Prompt references must use `prompt:template_name` format

## Error Handling

### Common Validation Errors

<Tabs>
<TabItem value="edge-error" label="next_node Definition Error" default>

:::danger Invalidnext_nodeDefinitionError
**❌ Wrong:** Using both next_node and next_on_success
```csv
# DON'T DO THIS
MyGraph,Node1,Next,config,agent,Success,Failure,input,output,prompt
```

**✅ Correct:** Use either next_node OR next_on_success/next_on_failure
```csv
# Option 1: Simple linear flow
MyGraph,Node1,Next,config,agent,,,input,output,prompt

# Option 2: Conditional branching
MyGraph,Node1,,config,agent,Success,Failure,input,output,prompt
```
:::

</TabItem>
<TabItem value="node-error" label="Node Reference Error">

:::danger NodeNotFoundError
**❌ Wrong:** Referencing non-existent node
```csv
# DON'T DO THIS - 'NonExistentNode' doesn't exist
MyGraph,Node1,,config,agent,NonExistentNode,,input,output,prompt
```

**✅ Correct:** Reference only defined nodes
```csv
# First define all nodes
MyGraph,Node1,,config,agent,Node2,,input,output,prompt
MyGraph,Node2,,config,agent,End,,input,output,prompt
MyGraph,End,,config,echo,,,output,final,
```
:::

</TabItem>
<TabItem value="json-error" label="JSON Format Error">

:::danger InvalidJSONError
**❌ Wrong:** Invalid JSON in Context
```csv
# DON'T DO THIS - Invalid JSON syntax
MyGraph,Node1,,{invalid json},agent,Next,,input,output,prompt
```

**✅ Correct:** Valid Pydantic model syntax
```csv
# Proper Python dictionary syntax
MyGraph,Node1,,"{'provider': 'openai', 'temperature': 0.7}",llm,Next,,input,output,prompt

# Or simple text
MyGraph,Node1,,Simple text description,agent,Next,,input,output,prompt
```
:::

</TabItem>
</Tabs>

### Best Practices for Error Prevention

1. **Validate CSV Structure**: Use `agentmap validate workflow.csv` before execution
2. **Test Small Graphs**: Start with simple graphs and add complexity gradually
3. **Check Node References**: Ensure all referenced nodes exist in the graph
4. **Validate JSON**: Use a JSON validator for complex Context configurations

## Common Patterns

### Linear Flow

<CSVTable 
  csvContent={`graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
MyGraph,Start,,Initial node,input,Process,,data,user_input,Enter data:
MyGraph,Process,,Process the data,transform,End,,user_input,result,
MyGraph,End,,Final output,echo,,,result,output,`}
  title="Linear Flow Pattern"
  filename="linear_flow_pattern"
/>

### Conditional Branching

<CSVTable 
  csvContent={`graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
MyGraph,Decision,,Make decision,branching,Success,Failure,input,decision,
MyGraph,Success,,Success path,echo,End,,decision,success_result,
MyGraph,Failure,,Failure path,echo,End,,decision,failure_result,
MyGraph,End,,Final output,echo,,,success_result|failure_result,output,`}
  title="Conditional Branching Pattern"
  filename="conditional_branching_pattern"
/>

### Parallel Processing

<CSVTable 
  csvContent={`graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
MyGraph,Split,,Split work,default,TaskA|TaskB|TaskC,Error,data,tasks,
MyGraph,TaskA,,Process A,worker_a,Join,Error,tasks,result_a,
MyGraph,TaskB,,Process B,worker_b,Join,Error,tasks,result_b,
MyGraph,TaskC,,Process C,worker_c,Join,Error,tasks,result_c,
MyGraph,Join,,Combine results,summary,End,Error,result_a|result_b|result_c,final_result,
MyGraph,End,,Output results,echo,,,final_result,output,`}
  title="Parallel Processing Pattern"
  filename="parallel_processing_pattern"
/>

## See Also

- [CLI Commands Reference](deployment/cli-commands) - Command-line interface documentation
- [Agent Types Reference](reference/agent-types) - Available agent types and their configurations
- [Quick Start Guide](../getting-started) - Build your first workflow
