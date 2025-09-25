# AgentMap

**Build and deploy LangGraph workflows from CSV files for fun and profit!**

AgentMap is a declarative orchestration framework that transforms simple CSV files into powerful AI agent workflows. Define complex multi-agent systems, conversational interfaces, and document processing pipelines without writing extensive code.

[![PyPI version](https://badge.fury.io/py/agentmap.svg)](https://badge.fury.io/py/agentmap)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🌟 Why AgentMap?

**Traditional Approach** - Complex code for simple workflows:
```python
# Hundreds of lines of LangGraph setup code
from langgraph import StateGraph
from langchain_openai import ChatOpenAI
# ... extensive boilerplate ...
```

**AgentMap Approach** - Simple CSV for complex workflows:
```csv
graph_name,node_name,agent_type,input_fields,output_field,prompt,next_on_success
ChatBot,GetInput,input,,user_input,How can I help you?,Respond
ChatBot,Respond,openai,user_input|memory,response,You are a helpful assistant: {user_input},GetInput
```

## 🚀 Key Features

### 🎯 **Declarative Workflow Definition**
- **CSV-Driven**: Define entire workflows in simple spreadsheets
- **Visual Design**: Easy to understand and modify workflow structure  
- **Version Control**: Track changes with standard Git workflows

### 🤖 **Rich Agent Ecosystem**
- **20+ Built-in Agents**: LLM providers, storage systems, utilities
- **Custom Agent Support**: Scaffold and integrate your own agents
- **Intelligent Orchestration**: Dynamic routing based on content analysis

### 🧠 **Advanced AI Capabilities**
- **Memory Management**: Conversational agents with context retention
- **Multi-LLM Support**: OpenAI, Claude, Gemini with unified interface
- **Vector Databases**: Semantic search and document retrieval
- **Prompt Management**: Centralized prompt organization and versioning

### 💾 **Universal Storage Integration**
- **Local Storage**: CSV, JSON, file operations
- **Cloud Storage**: Azure Blob, AWS S3, Google Cloud Storage
- **Databases**: Firebase, vector stores (Chroma, FAISS)
- **Document Processing**: PDF, Word, Markdown with LangChain integration

### 🛠️ **Developer Experience**
- **Powerful CLI**: Run, scaffold, compile, and export workflows
- **Auto-scaffolding**: Generate starter code for custom components
- **Execution Tracking**: Detailed monitoring with configurable success policies
- **Hot Reloading**: Rapid development and testing cycles

## 📦 Installation

### Base Installation
```bash
pip install agentmap
```

### Feature-Specific Installation
```bash
# LLM providers (OpenAI, Claude, Gemini)
pip install "agentmap[llm]"

# Storage integrations (Firebase, cloud, vector DBs)
pip install "agentmap[storage]"

# Everything included
pip install "agentmap[all]"
```

### Development Installation
```bash
# Clone and install for development
git clone https://github.com/jwwelbor/AgentMap.git
cd AgentMap
pip install -e ".[all]"
```

## ⚡ Quick Start

### 1. Create Your First Workflow

Create `hello_world.csv`:
```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
HelloWorld,Start,,Starting node,echo,Process,,input,initial_data,
HelloWorld,Process,,Process the greeting,openai,End,,initial_data,processed_greeting,"Make this greeting more enthusiastic: {initial_data}"
HelloWorld,End,,Final response,echo,,,processed_greeting,final_output,
```

### 2. Run the Workflow

**Via Python:**
```python
from agentmap.runner import run_graph

result = run_graph(
    graph_name="HelloWorld",
    initial_state={"input": "Hello, AgentMap!"},
    csv_path="hello_world.csv"
)

print(f"Result: {result['final_output']}")
print(f"Processing time: {result.get('total_duration', 0):.2f}s")
```

**Via CLI:**
```bash
agentmap run --graph HelloWorld --csv hello_world.csv --state '{"input": "Hello, AgentMap!"}'
```

### 3. Examine Execution Flow
```python
# View detailed execution path
for step in result.get("execution_steps", []):
    status = "✅" if step["success"] else "❌"
    print(f"{status} {step['node']} ({step['duration']:.3f}s)")
```

## ✨ Simplified Graph Naming (New Feature)

AgentMap now supports **intelligent default graph naming** that makes workflows even easier to create and run. No more specifying graph names for simple workflows!

### 🎯 Smart Defaults

**The filename automatically becomes your graph name:**

```bash
# Create customer_support.csv with any graph_name in the file
# The graph is automatically accessible as "customer_support"

agentmap run --csv customer_support.csv
# Automatically runs the graph from customer_support.csv
```

```python
from agentmap.runner import run_graph

# Graph name derived from filename automatically
result = run_graph(
    csv_path="customer_support.csv",  # Graph = "customer_support"
    initial_state={"user_query": "Help with my order"}
)
```

### 🔧 Custom Names with :: Syntax

**Override graph names when needed:**

```bash
# Run specific graph from multi-graph CSV
agentmap run --csv workflows.csv::ProductSupport

# HTTP API with URL encoding
curl -X POST "http://localhost:8000/execution/workflows.csv%3A%3AProductSupport"
```

```python
# Python API with custom graph name
result = run_graph(
    csv_path="workflows.csv::ProductSupport",
    initial_state={"product": "AgentMap"}
)
```

### 📊 Migration Guide

**Existing workflows continue working unchanged:**

```bash
# ✅ Traditional approach - still works
agentmap run --graph CustomerBot --csv customer_service.csv

# ✅ New simplified approach - easier!
agentmap run --csv customer_bot.csv
```

**Migration is optional and gradual:**

| Scenario | Traditional | New Simplified | Benefits |
|----------|------------|----------------|----------|
| Single graph per file | `--graph MyGraph --csv my_file.csv` | `--csv my_graph.csv` | Less typing, intuitive |
| Multiple graphs per file | `--graph Graph1 --csv multi.csv` | `--csv multi.csv::Graph1` | Clear syntax, URL-safe |
| API endpoints | `/execution/MyWorkflow/MyGraph` | `/execution/my_graph.csv` | RESTful, self-documenting |

### 🌟 Benefits

- **🚀 Faster Development**: Skip graph name specification for simple workflows
- **📖 Self-Documenting**: File names clearly indicate purpose
- **🔗 URL-Friendly**: Works seamlessly with HTTP APIs
- **🔄 Backward Compatible**: All existing workflows continue working
- **⚡ Zero Configuration**: Works out of the box

### 💡 Best Practices

**File Naming Convention:**
```bash
# Good: Descriptive, lowercase with underscores
customer_support.csv
product_onboarding.csv
data_processing_pipeline.csv

# Good: Specific use case names
order_status_check.csv
user_feedback_analysis.csv
```

**When to Use Each Approach:**

| Use Simplified Syntax When | Use Traditional Syntax When |
|----------------------------|------------------------------|
| ✅ Single graph per CSV file | ✅ Multiple graphs per CSV file |
| ✅ Developing new workflows | ✅ Migrating existing systems |
| ✅ Simple, focused workflows | ✅ Complex multi-graph systems |
| ✅ API-first applications | ✅ Legacy system integration |

## 📋 CSV Schema Reference

AgentMap workflows are defined using CSV files with the following columns:

| Column | Required | Description | Examples |
|--------|----------|-------------|----------|
| `graph_name` | ✅ | Workflow identifier | `ChatBot`, `DocumentProcessor` |
| `Node` | ✅ | Unique node name within graph | `GetInput`, `ProcessData`, `SaveResults` |
| `next_node` | ❌ | Direct connection to next node | `NextNode`, `func:custom_router` |
| `Context` | ❌ | Node configuration (JSON or text) | `{"memory_key":"chat_history"}` |
| `agent_type` | ❌ | Type of agent to use | `openai`, `claude`, `csv_reader` |
| `next_on_success` | ❌ | Next node on success | `ProcessData`, `Success\|Backup` |
| `next_on_failure` | ❌ | Next node on failure | `ErrorHandler`, `Retry` |
| `input_fields` | ❌ | State fields to extract as input | `user_input\|context\|memory` |
| `output_field` | ❌ | Field to store agent output | `response`, `processed_data` |
| `prompt` | ❌ | Agent prompt or configuration | `"You are helpful: {input}"`, `prompt:system_instructions` |
| `Description` | ❌ | Documentation for the node | `"Validates user input format"` |

### Advanced Routing Patterns

**Conditional Branching:**
```csv
graph_name,node_name,agent_type,next_on_success,next_on_failure,input_fields,output_field
DataFlow,Validate,branching,Transform,ErrorHandler,raw_data,validation_result
```

**Multiple Targets:**
```csv
graph_name,node_name,agent_type,next_on_success,input_fields,output_field
Parallel,Distribute,default,ProcessA|ProcessB|ProcessC,data,distributed_tasks
```

**Function-Based Routing:**
```csv
graph_name,node_name,next_node,agent_type,input_fields,output_field
Smart,Classifier,func:choose_specialist,default,user_query,classification
```

## 🤖 Agent Types Reference

### Core Agents

| Agent Type | Purpose | Input Behavior | Output Behavior |
|------------|---------|----------------|-----------------|
| `default` | Basic processing | Any fields | Returns message with prompt |
| `echo` | Pass-through | First input field | Returns input unchanged |
| `input` | User interaction | Ignored | Prompts user, returns input |
| `branching` | Conditional routing | Looks for success indicators | Returns routing decision |
| `success` | Always succeeds | Any | Returns success message |
| `failure` | Always fails | Any | Returns failure message |

**Example:**
```csv
TestFlow,GetData,input,,user_input,Enter your name:,ValidateData
TestFlow,ValidateData,branching,ProcessData,ErrorHandler,user_input,validation_result
TestFlow,ProcessData,default,End,,user_input,processed_result,"Processing: {user_input}"
```

### LLM Agents

| Agent Type | Provider | Features | Configuration |
|------------|----------|----------|---------------|
| `openai` (aliases: `gpt`, `chatgpt`) | OpenAI | GPT models, memory | Model, temperature, memory settings |
| `claude` (alias: `anthropic`) | Anthropic | Claude models, memory | Model, temperature, memory settings |  
| `gemini` (alias: `google`) | Google | Gemini models, memory | Model, temperature, memory settings |

**Memory-Enabled Conversation:**
```csv
ChatBot,GetInput,input,,user_message,What can I help with?,Respond
ChatBot,Respond,openai,user_message|chat_memory,response,"You are helpful. Human: {user_message}",GetInput
```

**Context Configuration:**
```csv
graph_name,node_name,context,agent_type,input_fields,output_field,prompt
Advanced,Analyze,"{\"memory_key\":\"analysis_history\",\"max_memory_messages\":10,\"model\":\"gpt-4\",\"temperature\":0.2}",openai,data|analysis_history,insights,"Analyze this data: {data}"
```

### LLM Routing & Unified Agent

AgentMap provides intelligent LLM routing capabilities through a unified `llm` agent that automatically selects the best provider and model based on task complexity, cost optimization, and availability. This modern approach simplifies workflow design while maintaining backward compatibility with provider-specific agents.

#### Unified LLM Agent

| Agent Type | Features | Routing Strategy | Configuration |
|------------|----------|------------------|---------------|
| `llm` | Multi-provider routing, cost optimization, automatic fallback | Content analysis, task complexity, provider availability | Routing rules, provider priorities, cost thresholds |

**Basic Unified Agent Usage:**
```csv
graph_name,node_name,agent_type,input_fields,output_field,prompt
SmartFlow,Process,llm,user_input,response,"You are a helpful assistant: {user_input}"
SmartFlow,Analyze,llm,data,analysis,"Analyze this data: {data}"
```

**Advanced Routing Configuration:**
```csv
graph_name,node_name,context,agent_type,input_fields,output_field,prompt
OptimizedFlow,ComplexTask,"{\"routing_strategy\":\"cost_optimized\",\"max_cost_per_request\":0.05,\"fallback_providers\":[\"openai\",\"claude\"],\"memory_key\":\"conversation\"}",llm,complex_input|conversation,detailed_output,"Provide detailed analysis: {complex_input}"
OptimizedFlow,SimpleTask,"{\"routing_strategy\":\"speed_first\",\"preferred_providers\":[\"openai\",\"gemini\"]}",llm,simple_input,quick_response,"Quick response to: {simple_input}"
```

#### Routing Strategies

**1. Cost-Optimized Routing**
```yaml
# In agentmap_config.yaml
llm:
  routing:
    default_strategy: "cost_optimized"
    cost_thresholds:
      simple_task: 0.01      # Max cost for simple tasks
      complex_task: 0.10     # Max cost for complex tasks
      reasoning_task: 0.25   # Max cost for reasoning tasks
    
    provider_costs:          # Cost per 1K tokens
      openai:
        gpt-3.5-turbo: 0.002
        gpt-4: 0.06
      anthropic:
        claude-3-haiku: 0.0015
        claude-3-sonnet: 0.015
      google:
        gemini-pro: 0.001
```

**2. Quality-First Routing**
```yaml
llm:
  routing:
    default_strategy: "quality_first"
    task_assignments:
      creative_writing: ["claude-3-sonnet", "gpt-4"]
      data_analysis: ["gpt-4", "claude-3-sonnet"]
      simple_qa: ["gpt-3.5-turbo", "gemini-pro"]
      reasoning: ["gpt-4", "claude-3-opus"]
    
    quality_thresholds:
      minimum_model_tier: "mid"  # low, mid, high
      require_reasoning: true    # For complex tasks
```

**3. Speed-Optimized Routing**
```yaml
llm:
  routing:
    default_strategy: "speed_first"
    latency_targets:
      realtime: 1.0          # Max 1 second response
      interactive: 3.0       # Max 3 second response
      batch: 10.0           # Max 10 second response
    
    provider_priorities:     # Ordered by typical response speed
      - "gemini-pro"
      - "gpt-3.5-turbo"
      - "claude-3-haiku"
```

#### Task Complexity Analysis

The routing system automatically analyzes task complexity to select appropriate models:

**Complexity Indicators:**
```yaml
llm:
  complexity_analysis:
    simple_indicators:
      - "short prompt (< 100 chars)"
      - "single question"
      - "factual lookup"
      - "basic formatting"
    
    complex_indicators:
      - "multi-step reasoning"
      - "code generation"
      - "creative writing"
      - "analysis of large data"
      - "prompt length > 1000 chars"
    
    reasoning_indicators:
      - "mathematical problems"
      - "logical deduction"
      - "multi-document synthesis"
      - "strategic planning"
```

**Automatic Task Classification:**
```csv
# Tasks are automatically classified and routed appropriately
Workflow,QuickAnswer,llm,question,answer,"What is the capital of France?"     # → Routes to fast, cheap model
Workflow,DeepAnalysis,llm,research_data,insights,"Analyze market trends across 50 data points and provide strategic recommendations"  # → Routes to high-capability model
Workflow,CodeReview,llm,code_snippet,review,"Review this Python function for bugs and optimization opportunities"  # → Routes to code-capable model
```

#### Provider Fallback & Reliability

**Automatic Fallback Configuration:**
```yaml
llm:
  reliability:
    enable_fallback: true
    max_retries: 3
    retry_delay: 1.0        # Seconds between retries
    
    fallback_chains:
      primary: ["openai/gpt-4", "anthropic/claude-3-sonnet", "google/gemini-pro"]
      cost_optimized: ["google/gemini-pro", "openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]
      speed_first: ["openai/gpt-3.5-turbo", "google/gemini-pro", "anthropic/claude-3-haiku"]
    
    health_checks:
      enabled: true
      check_interval: 300     # Check provider health every 5 minutes
      failure_threshold: 3    # Mark as unhealthy after 3 failures
```

**Error Handling in Workflows:**
```csv
graph_name,node_name,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
RobustFlow,MainProcess,"{\"fallback_providers\":[\"openai\",\"claude\",\"gemini\"],\"max_retries\":2}",llm,Success,HandleLLMFailure,user_input,response,"Process: {user_input}"
RobustFlow,HandleLLMFailure,echo,FallbackProcess,,error,fallback_message,"LLM service temporarily unavailable"
RobustFlow,FallbackProcess,default,Success,,user_input,response,"Fallback processing for: {user_input}"
```

#### Cost Monitoring & Budget Management

**Budget Controls:**
```yaml
llm:
  budget:
    enabled: true
    daily_limit: 50.00      # $50 daily limit
    monthly_limit: 1000.00  # $1000 monthly limit
    
    cost_tracking:
      log_requests: true
      alert_thresholds:
        warning: 0.80         # Alert at 80% of budget
        critical: 0.95       # Critical alert at 95%
    
    emergency_fallback:
      enabled: true
      fallback_to: "local"   # Use local models when budget exceeded
```

**Cost-Aware Routing in CSV:**
```csv
graph_name,node_name,context,agent_type,input_fields,output_field,prompt
BudgetFlow,ExpensiveTask,"{\"max_cost\":0.05,\"budget_category\":\"analysis\"}",llm,complex_data,results,"Detailed analysis: {complex_data}"
BudgetFlow,CheapTask,"{\"max_cost\":0.01,\"prefer_free\":true}",llm,simple_query,answer,"Quick answer: {simple_query}"
```

#### Integration with Existing Workflows

**Backward Compatibility:**
```csv
# Legacy approach - still supported
LegacyFlow,OldStyle,openai,user_input,response,"You are helpful: {user_input}"
LegacyFlow,OldStyle2,claude,user_input,response,"You are helpful: {user_input}"

# Modern approach - automatic routing
ModernFlow,NewStyle,llm,user_input,response,"You are helpful: {user_input}"
```

**Gradual Migration Pattern:**
```csv
# Phase 1: Keep existing agents, add routing for new nodes
MigrationFlow,ExistingProcess,openai,data,result1,"Process with OpenAI: {data}"
MigrationFlow,NewProcess,llm,data,result2,"Process with auto-routing: {data}"

# Phase 2: Replace existing agents one by one
MigrationFlow,UpdatedProcess,llm,data,result1,"Process with OpenAI: {data}"  # Same prompt, but now auto-routed
```

#### Advanced Routing Examples

**Multi-Model Workflow:**
```csv
graph_name,node_name,context,agent_type,input_fields,output_field,prompt
MultiModel,QuickFilter,"{\"routing_strategy\":\"speed_first\",\"task_type\":\"simple\"}",llm,user_query,filtered_query,"Extract key intent from: {user_query}"
MultiModel,DeepAnalysis,"{\"routing_strategy\":\"quality_first\",\"task_type\":\"complex\",\"min_model_tier\":\"high\"}",llm,filtered_query|context,detailed_analysis,"Provide comprehensive analysis: {filtered_query}"
MultiModel,Summary,"{\"routing_strategy\":\"cost_optimized\",\"task_type\":\"simple\"}",llm,detailed_analysis,summary,"Summarize: {detailed_analysis}"
```

**Context-Aware Routing:**
```csv
graph_name,node_name,context,agent_type,input_fields,output_field,prompt
ContextAware,Router,"{\"context_aware\":true,\"routing_factors\":[\"content_length\",\"complexity\",\"urgency\"]}",llm,user_input|context_metadata,routed_response,"Respond appropriately: {user_input}"
```

**A/B Testing Integration:**
```csv
graph_name,node_name,context,agent_type,input_fields,output_field,prompt
ABTest,VariantA,"{\"routing_strategy\":\"quality_first\",\"ab_test_group\":\"A\"}",llm,user_input,response_a,"High-quality response: {user_input}"
ABTest,VariantB,"{\"routing_strategy\":\"cost_optimized\",\"ab_test_group\":\"B\"}",llm,user_input,response_b,"Cost-optimized response: {user_input}"
```

#### Monitoring & Analytics

**Routing Decision Tracking:**
```python
# Access routing decisions in results
result = run_graph("SmartFlow", initial_state)

# View routing decisions
for step in result.get("execution_steps", []):
    if step.get("routing_info"):
        routing = step["routing_info"]
        print(f"Node {step['node']}:")
        print(f"  Chosen Provider: {routing['provider']}")
        print(f"  Model: {routing['model']}")
        print(f"  Strategy: {routing['strategy']}")
        print(f"  Cost: ${routing['cost']:.4f}")
        print(f"  Latency: {routing['latency']:.2f}s")
```

**Performance Analytics:**
```yaml
llm:
  analytics:
    enabled: true
    metrics:
      - "provider_usage"
      - "cost_per_request"
      - "latency_distribution"
      - "error_rates"
      - "routing_decisions"
    
    export:
      format: "json"          # json, csv, prometheus
      interval: "daily"       # hourly, daily, weekly
      destination: "logs/llm_analytics.json"
```

### Storage Agents

#### File Operations
| Agent Type | Purpose | Required Input | Output |
|------------|---------|----------------|--------|
| `file_reader` | Read documents | `collection` (file path) | Document content with metadata |
| `file_writer` | Write files | `collection` (path), `data` | Operation result |

**Document Processing Example:**
```csv
DocFlow,ReadDoc,"{\"should_split\":true,\"chunk_size\":1000}",file_reader,collection,documents,
DocFlow,Summarize,openai,documents,summary,"Summarize these documents: {documents}",SaveSummary
DocFlow,SaveSummary,file_writer,summary,result,output/summary.md
```

#### Structured Data
| Agent Type | Purpose | Required Input | Output |
|------------|---------|----------------|--------|
| `csv_reader` | Read CSV files | `collection` (file path) | Parsed CSV data |
| `csv_writer` | Write CSV files | `collection` (path), `data` | Operation result |
| `json_reader` | Read JSON files | `collection` (file path) | JSON data |
| `json_writer` | Write JSON files | `collection` (path), `data` | Operation result |

#### Cloud Storage
| Agent Type | Purpose | URI Format | Authentication |
|------------|---------|------------|----------------|
| `cloud_json_reader` | Read from cloud | `azure://container/file.json` | Connection string/keys |
| `cloud_json_writer` | Write to cloud | `s3://bucket/file.json` | AWS credentials |

**Cloud Storage Example:**
```csv
CloudFlow,LoadData,cloud_json_reader,collection,data,"azure://documents/input.json"
CloudFlow,SaveResults,cloud_json_writer,processed_data,result,"s3://output/results.json"
```

#### Vector Databases
| Agent Type | Purpose | Configuration | Use Cases |
|------------|---------|---------------|-----------|
| `vector_reader` | Similarity search | Store configuration | Document retrieval, semantic search |
| `vector_writer` | Store embeddings | Store configuration | Knowledge base building |

**Vector Search Example:**
```csv
SearchFlow,LoadDocs,vector_writer,documents,load_result,
SearchFlow,Search,vector_reader,query,search_results,
SearchFlow,Answer,openai,search_results|query,response,"Answer based on: {search_results}. Question: {query}"
```

### Orchestration Agent

The `orchestrator` agent provides intelligent, dynamic routing based on content analysis:

**Basic Orchestration:**
```csv
RouterFlow,MainRouter,orchestrator,available_nodes|user_input,next_node,"Route user request to appropriate handler"
RouterFlow,ProductInfo,openai,user_input,response,"I handle product information requests"
RouterFlow,TechSupport,openai,user_input,response,"I handle technical support questions"
RouterFlow,OrderStatus,openai,user_input,response,"I handle order status inquiries"
```

**Advanced Configuration:**
```csv
graph_name,node_name,context,agent_type,input_fields,output_field,prompt
SmartRouter,MainRouter,"{\"matching_strategy\":\"tiered\",\"confidence_threshold\":0.8,\"node_filter\":\"ProductInfo|TechSupport\"}",orchestrator,available_nodes|user_input,next_node,"Intelligently route user queries"
```

## 🧠 Advanced Features

### Memory Management

AgentMap supports conversational memory for LLM agents:

**Configuration Options:**
- `memory_key`: State field for memory storage (default: "memory")
- `max_memory_messages`: Maximum conversation history (default: unlimited)

**Multi-Turn Conversation:**
```csv
Interview,Welcome,default,,welcome_message,"Welcome to the interview!",AskQuestion
Interview,AskQuestion,"{\"memory_key\":\"interview_history\",\"max_memory_messages\":8}",claude,question_number|interview_history,current_question,"Ask interview question #{question_number}"
Interview,GetAnswer,input,current_question,user_answer,,EvaluateAnswer
Interview,EvaluateAnswer,"{\"memory_key\":\"interview_history\"}",claude,user_answer|interview_history,evaluation,"Evaluate this answer: {user_answer}"
```

**Memory State Evolution:**
```python
# Initial state
{"user_input": "Hello, how are you?"}

# After first response
{
    "user_input": "Hello, how are you?",
    "response": "I'm well, thanks for asking!",
    "memory": [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm well, thanks for asking!"}
    ]
}

# After second interaction
{
    "user_input": "Tell me about AI",
    "response": "AI is fascinating! Given our conversation...",
    "memory": [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm well, thanks for asking!"},
        {"role": "user", "content": "Tell me about AI"},
        {"role": "assistant", "content": "AI is fascinating! Given our conversation..."}
    ]
}
```

### Execution Tracking

AgentMap provides comprehensive execution tracking with configurable success policies:

**Configuration in `agentmap_config.yaml`:**
```yaml
execution:
  tracking:
    enabled: true              # Enable detailed tracking
    track_outputs: false       # Record output values
    track_inputs: false        # Record input values
  
  success_policy:
    type: "critical_nodes"     # Policy type
    critical_nodes:            # Critical nodes for success
      - "ValidateInput"
      - "ProcessPayment"
      - "SendConfirmation"
```

**Available Success Policies:**
- `all_nodes`: All executed nodes must succeed (default)
- `final_node`: Only the final node must succeed
- `critical_nodes`: All specified critical nodes must succeed
- `custom`: Use custom policy function

**Accessing Execution Data:**
```python
result = run_graph("PaymentFlow", initial_state)

# Policy-based success (always available)
if result["graph_success"]:
    print("Workflow succeeded according to policy!")

# Detailed execution summary (when detailed tracking enabled)
summary = result["__execution_summary"]
print(f"Total duration: {summary['total_duration']:.2f}s")
print(f"Execution path: {' → '.join(summary['execution_path'])}")

# Find failing nodes
failed_nodes = [
    node for node, data in summary["node_results"].items() 
    if not data["success"]
]
```

### Cloud Storage Integration

AgentMap seamlessly integrates with major cloud storage providers:

**Storage Configuration (`storage_config.yaml`):**
```yaml
json:
  default_provider: "local"
  providers:
    azure:
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
      default_container: "documents"
      containers:
        users: "users-container"
        reports: "reports-container"
    
    aws:
      region: "us-west-2"
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      default_bucket: "my-documents"
    
    gcp:
      project_id: "env:GCP_PROJECT_ID"
      credentials_file: "path/to/service-account.json"
      default_bucket: "documents"
```

**URI Formats:**
- Azure: `azure://container/path/file.json`
- AWS S3: `s3://bucket/path/file.json`  
- GCP: `gs://bucket/path/file.json`

### prompt Management

Centralized prompt management with multiple reference types:

**Registry Prompts (`prompts/registry.yaml`):**
```yaml
system_instructions: "You are a helpful AI assistant..."
customer_service: "You are a customer service representative..."
data_analyst: "You are a data analyst. Analyze the following data..."
```

**Usage in CSV:**
```csv
graph_name,node_name,agent_type,input_fields,output_field,prompt
Analysis,Analyze,openai,data,insights,prompt:data_analyst
Support,Respond,claude,user_query,response,prompt:customer_service
```

**File-Based Prompts:**
```csv
graph_name,node_name,agent_type,prompt
Complex,LongAnalysis,openai,file:prompts/detailed_analysis.txt
```

**YAML Key References:**
```csv
graph_name,node_name,agent_type,prompt
Multi,Specialized,claude,yaml:prompts/specialists.yaml#technical_support
```

## 🔧 Configuration

### Main Configuration (`agentmap_config.yaml`)

```yaml
# Default CSV file path
csv_path: "workflows/default.csv"

# Auto-compilation setting
autocompile: false

# Directory paths
paths:
  custom_agents: "agentmap/agents/custom"
  functions: "agentmap/functions"

# LLM provider settings
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-3.5-turbo"
    temperature: 0.7
  
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.7
  
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-pro"

# prompt management
prompts:
  directory: "prompts"
  registry_file: "prompts/registry.yaml"
  enable_cache: true

# Execution tracking
execution:
  tracking:
    enabled: false
    track_outputs: false
    track_inputs: false
  success_policy:
    type: "all_nodes"
```

### Environment Variables

```bash
# LLM Provider Keys
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export GOOGLE_API_KEY="your-google-key"

# Cloud Storage
export AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export GCP_PROJECT_ID="your-project-id"

# AgentMap Settings
export AGENTMAP_CONFIG_PATH="custom_config.yaml"
export AGENTMAP_CSV_PATH="workflows/main.csv"
```

## 💡 Practical Examples

### Simple Linear Workflow

**Use Case:** Basic data processing pipeline

```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
DataPipeline,LoadData,,Load CSV data,csv_reader,ValidateData,HandleError,collection,raw_data
DataPipeline,ValidateData,,Validate data format,branching,TransformData,HandleError,raw_data,validation_result
DataPipeline,TransformData,,Transform data,default,SaveResults,HandleError,raw_data,processed_data,"Clean and transform data"
DataPipeline,SaveResults,,Save processed data,csv_writer,End,HandleError,processed_data,save_result
DataPipeline,End,,Pipeline complete,echo,,,save_result,final_message
DataPipeline,HandleError,,Handle any errors,echo,End,,error,error_message
```

**Usage:**
```python
result = run_graph(
    "DataPipeline", 
    {"collection": "data/raw_sales.csv"}
)
```

### Conversational AI Assistant

**Use Case:** Multi-turn customer service bot

```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
CustomerBot,Welcome,,Welcome message,default,GetQuery,,user,welcome_message,"Welcome! How can I help you today?",GetQuery
CustomerBot,GetQuery,,Get user query,input,ClassifyIntent,,welcome_message,user_query,"How can I help you?",ClassifyIntent
CustomerBot,ClassifyIntent,,"{\"memory_key\":\"conversation_history\",\"max_memory_messages\":10}",claude,RouteQuery,HandleError,user_query|conversation_history,intent_classification,"Classify this customer query into: product_info, technical_support, billing, general. Query: {user_query}",RouteQuery
CustomerBot,RouteQuery,,Route to appropriate handler,func:route_by_intent,ProductInfo,HandleError,intent_classification,routing_decision
CustomerBot,ProductInfo,,"{\"memory_key\":\"conversation_history\"}",openai,AskFollowup,HandleError,user_query|conversation_history,response,"You are a product specialist. Help with this query: {user_query}",AskFollowup
CustomerBot,TechnicalSupport,,"{\"memory_key\":\"conversation_history\"}",openai,AskFollowup,HandleError,user_query|conversation_history,response,"You are technical support. Help with: {user_query}",AskFollowup
CustomerBot,Billing,,"{\"memory_key\":\"conversation_history\"}",openai,AskFollowup,HandleError,user_query|conversation_history,response,"You are billing support. Help with: {user_query}",AskFollowup
CustomerBot,AskFollowup,,Ask if user needs more help,input,GetQuery,End,response,followup_query,"Is there anything else I can help you with?",ClassifyIntent
CustomerBot,End,,End conversation,echo,,,response,final_message
CustomerBot,HandleError,,Handle errors,echo,GetQuery,,error,error_message
```

### Document Processing Pipeline

**Use Case:** Intelligent document analysis and summarization

```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
DocProcessor,LoadDocument,,"{\"should_split\":true,\"chunk_size\":1500,\"chunk_overlap\":200}",file_reader,AnalyzeStructure,HandleError,document_path,document_chunks
DocProcessor,AnalyzeStructure,,Analyze document structure,openai,ExtractEntities,HandleError,document_chunks,structure_analysis,"Analyze the structure and main topics of these document chunks: {document_chunks}"
DocProcessor,ExtractEntities,,Extract key entities,openai,GenerateSummary,HandleError,document_chunks,entities,"Extract key entities (people, organizations, dates, locations) from: {document_chunks}"
DocProcessor,GenerateSummary,,Generate comprehensive summary,claude,SaveResults,HandleError,document_chunks|structure_analysis|entities,comprehensive_summary,"Create a comprehensive summary incorporating structure analysis and entities: {structure_analysis} | Entities: {entities} | Content: {document_chunks}"
DocProcessor,SaveResults,,Save analysis results,json_writer,CreateReport,HandleError,comprehensive_summary|structure_analysis|entities,save_result
DocProcessor,CreateReport,,Create final report,openai,End,HandleError,comprehensive_summary|structure_analysis|entities,final_report,"Create a professional analysis report with: Summary: {comprehensive_summary} | Structure: {structure_analysis} | Key Entities: {entities}"
DocProcessor,End,,Processing complete,echo,,,final_report,completion_message
DocProcessor,HandleError,,Handle processing errors,echo,End,,error,error_message
```

### Multi-Modal Workflow with Cloud Storage

**Use Case:** Process documents from cloud storage with vector database integration

```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
CloudProcessor,LoadFromCloud,,Load document from cloud storage,cloud_json_reader,ProcessDocument,HandleError,cloud_path,document_data
CloudProcessor,ProcessDocument,,"{\"should_split\":true,\"chunk_size\":1000}",file_reader,StoreVectors,HandleError,document_data,processed_chunks
CloudProcessor,StoreVectors,,Store in vector database,vector_writer,AnalyzeContent,HandleError,processed_chunks,vector_storage_result
CloudProcessor,AnalyzeContent,,Analyze with AI,openai,SearchSimilar,HandleError,processed_chunks,analysis,"Analyze this document content: {processed_chunks}"
CloudProcessor,SearchSimilar,,Find similar documents,vector_reader,GenerateInsights,HandleError,analysis,similar_documents
CloudProcessor,GenerateInsights,,Generate insights,claude,SaveToCloud,HandleError,analysis|similar_documents,insights,"Generate insights comparing this analysis with similar documents: Analysis: {analysis} | Similar: {similar_documents}"
CloudProcessor,SaveToCloud,,Save results to cloud,cloud_json_writer,End,HandleError,insights,cloud_save_result
CloudProcessor,End,,Processing complete,echo,,,cloud_save_result,final_message
CloudProcessor,HandleError,,Handle any errors,echo,End,,error,error_message
```

### Intelligent Orchestration Workflow

**Use Case:** Dynamic routing based on user intent

```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
SmartRouter,MainOrchestrator,,"{\"matching_strategy\":\"tiered\",\"confidence_threshold\":0.8}",orchestrator,ExecuteHandler,HandleError,available_nodes|user_input,selected_handler,"Analyze user input and select the most appropriate handler"
SmartRouter,ProductSpecialist,,Product information handler,openai,GatherFeedback,HandleError,user_input,specialist_response,"I am a product specialist. User query: {user_input}. Context: I help with product features, pricing, comparisons, and availability."
SmartRouter,TechnicalSupport,,Technical support handler,openai,GatherFeedback,HandleError,user_input,specialist_response,"I am technical support. User query: {user_input}. Context: I help with troubleshooting, setup, configuration, and technical issues."
SmartRouter,BillingSupport,,Billing support handler,openai,GatherFeedback,HandleError,user_input,specialist_response,"I am billing support. User query: {user_input}. Context: I help with payments, invoices, refunds, and account billing."
SmartRouter,GeneralSupport,,General support handler,openai,GatherFeedback,HandleError,user_input,specialist_response,"I am general support. User query: {user_input}. Context: I provide general assistance and can escalate to specialists."
SmartRouter,ExecuteHandler,,Execute selected handler,func:execute_selected_handler,GatherFeedback,HandleError,selected_handler|user_input,handler_response
SmartRouter,GatherFeedback,,Collect user feedback,input,MainOrchestrator,End,specialist_response|handler_response,user_feedback,"Was this helpful? Do you have another question?"
SmartRouter,End,,Conversation complete,echo,,,specialist_response,final_response
SmartRouter,HandleError,,Handle routing errors,echo,End,,error,error_message
```

## 🛠️ CLI Reference

### Core Commands

**Run Workflows:**
```bash
# Basic execution
agentmap run --graph WorkflowName --state '{"input": "value"}'

# With custom CSV file
agentmap run --graph MyFlow --csv custom/workflow.csv --state '{"data": "test"}'

# Enable auto-compilation
agentmap run --graph MyFlow --autocompile --state '{"input": "value"}'

# Custom configuration
agentmap run --graph MyFlow --config custom_config.yaml --state '{"input": "value"}'
```

**Scaffolding:**
```bash
# Generate custom agents and functions for entire CSV
agentmap scaffold --csv workflows/my_workflow.csv

# Generate for specific graph
agentmap scaffold --graph MyWorkflow

# Custom output directories
agentmap scaffold --csv workflows/complex.csv --config custom_paths_config.yaml
```

**Graph Operations:**
```bash
# Compile graphs for performance
agentmap compile --graph ProductionWorkflow

# Export as Python code
agentmap export --graph MyFlow --output exported_workflow.py --format python

# Export with state schema
agentmap export --graph MyFlow --output workflow.py --state-schema pydantic
```

**Configuration Management:**
```bash
# View current configuration
agentmap config

# View specific config file
agentmap config --path custom_config.yaml

# Initialize storage configuration
agentmap storage-config --init

# View storage configuration
agentmap storage-config --path storage_config.yaml
```

### Scaffolding System

AgentMap's scaffolding system generates production-ready starter code:

**What Gets Generated:**

For custom agents:
```python
# Generated: agentmap/agents/custom/weather_agent.py
from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any

class WeatherAgent(BaseAgent):
    """
    Get weather data for specified location
    
    Node: WeatherNode
    Expected input fields: location
    Expected output field: weather_data
    Default prompt: Get current weather for {location}
    """
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return weather data.
        
        Args:
            inputs (dict): Contains input values with keys: location
            
        Returns:
            The weather data for the specified location
        """
        location = inputs.get("location")
        
        # TODO: Implement weather data retrieval
        # Example: Call weather API, process data, return results
        
        return f"Weather data for {location}: Sunny, 72°F"
```

For custom functions:
```python
# Generated: agentmap/functions/custom_router.py
from typing import Dict, Any

def custom_router(state: Any, success_node="Success", failure_node="Failure") -> str:
    """
    Custom routing logic based on state analysis.
    
    Args:
        state: The current graph state
        success_node (str): Node to route to on success
        failure_node (str): Node to route to on failure
        
    Returns:
        str: Name of the next node to execute
    
    Available in state:
    - user_input: Input from user
    - processed_data: Data from processing step
    """
    
    # TODO: Implement custom routing logic
    # Example: Analyze state contents and determine routing
    
    if state.get("last_action_success", True):
        return success_node
    else:
        return failure_node
```

### Development Workflow

**Typical Development Cycle:**

1. **Design:** Create CSV workflow definition
2. **Scaffold:** Generate custom components
   ```bash
   agentmap scaffold --csv my_workflow.csv
   ```
3. **Implement:** Fill in generated code templates
4. **Test:** Run workflow with test data
   ```bash
   agentmap run --graph TestFlow --state '{"test": "data"}'
   ```
5. **Debug:** Use execution tracking to identify issues
6. **Deploy:** Compile for production
   ```bash
   agentmap compile --graph ProductionFlow
   ```

## 🏗️ Architecture Overview

### System Components

```
AgentMap Architecture
├── 🎯 CSV Definition Layer
│   ├── Workflow definitions
│   ├── Node specifications  
│   └── Routing logic
│
├── 🤖 Agent Layer
│   ├── Built-in agents (20+ types)
│   ├── Custom agent scaffolding
│   └── LLM integrations
│
├── 🧠 Orchestration Layer
│   ├── Graph assembly
│   ├── Dynamic routing
│   ├── State management
│   └── Execution tracking
│
├── 💾 Storage Layer
│   ├── Local file systems
│   ├── Cloud storage providers
│   ├── Vector databases
│   └── Document processing
│
└── 🛠️ Developer Tools
    ├── CLI interface
    ├── Code generation
    ├── Configuration management
    └── Monitoring & debugging
```
### Clean Architecture Design

AgentMap follows clean architecture principles with clear separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│                   Core Layer                        │
│         (CLI, API, Serverless Handlers)            │
└──────────────────────┬──────────────────────────────┘
                       │ uses
┌──────────────────────▼──────────────────────────────┐
│                Services Layer                       │  
│   (Business Logic, Orchestration, Workflows)       │
│                                                     │
│  • GraphBuilderService  • CompilationService       │
│  • GraphRunnerService   • AgentFactoryService      │
│  • ExecutionTracking    • ValidationService        │
└──────────────────────┬──────────────────────────────┘
                       │ uses
┌──────────────────────▼──────────────────────────────┐
│                 Models Layer                        │
│        (Pure Data Containers, Entities)             │
│                                                     │
│  • Node  • Graph  • ExecutionSummary  • Result     │
└─────────────────────────────────────────────────────┘
                       ▲
┌──────────────────────┴──────────────────────────────┐
│             Infrastructure Layer                    │
│         (Storage, Logging, External APIs)          │
└─────────────────────────────────────────────────────┘
                       ▲
┌──────────────────────┴──────────────────────────────┐
│         Dependency Injection Container              │
│      (Service Registry, Dependency Wiring)         │
└─────────────────────────────────────────────────────┘
```

### Key Architectural Benefits

- **Separation of Concerns**: Models contain only data, services contain all business logic
- **Dependency Injection**: All services are injected, improving testability and flexibility
- **Clean Interfaces**: Protocol-based service injection for extensibility
- **Graceful Degradation**: Optional services fail gracefully when unavailable

### Data Flow Architecture

```
User Input → CSV Definition → Service Layer → Execution
     ↓            ↓               ↓              ↓
DI Container → Parser Service → Builder Service → Runner Service
     ↓            ↓               ↓              ↓  
Models ← Node Creation ← Graph Assembly ← State Management
     ↓            ↓               ↓              ↓
Result ← Execution Policy ← Tracking Service ← Output
```

### Service-Based Workflow

1. **Input Processing**: CSV parsed by CSVGraphParserService
2. **Model Creation**: GraphBuilderService creates pure data models
3. **Agent Creation**: AgentFactoryService creates agents with injected services
4. **Compilation**: CompilationService produces executable graph
5. **Execution**: GraphRunnerService orchestrates execution with tracking
6. **Result**: ExecutionResult with state, success status, and metrics

### Key Design Patterns

**1. Declarative Configuration**
- Workflows defined in CSV format
- Separation of logic from configuration
- Version control friendly

**2. Agent-Based Architecture**
- Modular, pluggable components
- Consistent interface across all agents
- Easy extensibility

**3. State-Driven Execution**
- Immutable state transitions
- Clear data flow between nodes
- Comprehensive execution tracking

**4. Service-Oriented Design**
- Storage abstraction layers
- Dependency injection
- Testable components

## 📚 Best Practices

### Workflow Design

**1. Start Simple, Scale Gradually**
```csv
# Good: Simple, clear workflow
SimpleFlow,Input,echo,Process,,user_input,processed_input
SimpleFlow,Process,default,Output,,processed_input,result,"Process: {processed_input}"
SimpleFlow,Output,echo,,,result,final_output
```

**2. Use Descriptive Node Names**
```csv
# Good: Clear purpose
UserRegistration,ValidateEmail,branching,CreateAccount,HandleValidationError,email,validation_result
UserRegistration,CreateAccount,default,SendWelcome,,email|validation_result,account_data

# Avoid: Generic names
UserRegistration,Node1,branching,Node2,Node3,email,result
```

**3. Implement Comprehensive Error Handling**
```csv
# Always include error handling paths
DataFlow,ProcessData,default,SaveResults,HandleProcessingError,input,processed_data
DataFlow,SaveResults,csv_writer,Success,HandleSaveError,processed_data,save_result
DataFlow,HandleProcessingError,echo,End,,error,error_message
DataFlow,HandleSaveError,echo,End,,error,error_message
```

### Memory Management

**1. Set Appropriate Memory Limits**
```csv
# Good: Reasonable memory limits
ChatBot,Respond,"{\"memory_key\":\"chat_history\",\"max_memory_messages\":20}",openai,user_input|chat_history,response,"You are helpful: {user_input}"

# Avoid: Unlimited memory in production
ChatBot,Respond,"{\"memory_key\":\"chat_history\"}",openai,user_input|chat_history,response,"You are helpful: {user_input}"
```

**2. Use Meaningful Memory Keys**
```csv
# Good: Descriptive memory keys
CustomerService,Respond,"{\"memory_key\":\"customer_conversation\"}",claude,user_query|customer_conversation,response
TechnicalSupport,Respond,"{\"memory_key\":\"technical_session\"}",openai,user_issue|technical_session,response

# Avoid: Generic memory keys
CustomerService,Respond,"{\"memory_key\":\"memory\"}",claude,user_query|memory,response
```

### Performance Optimization

**1. Use Appropriate Agent Types**
```csv
# Good: Efficient for simple operations
DataFlow,PassThrough,echo,NextStep,,data,data
DataFlow,SimpleMessage,default,NextStep,,data,message,"Processing {data}"

# Avoid: Overusing LLM agents for simple tasks
DataFlow,PassThrough,openai,NextStep,,data,data,"Just return: {data}"
```

**2. Implement Intelligent Caching**
```yaml
# In configuration
prompts:
  enable_cache: true
  
execution:
  tracking:
    enabled: true  # Only when needed
```

**3. Design for Parallel Execution**
```csv
# Use multiple success targets for parallel processing
Parallel,Distribute,default,ProcessorA|ProcessorB|ProcessorC,,data,distributed_tasks
Parallel,ProcessorA,default,Combine,,distributed_tasks.a,result_a
Parallel,ProcessorB,default,Combine,,distributed_tasks.b,result_b
Parallel,ProcessorC,default,Combine,,distributed_tasks.c,result_c
Parallel,Combine,default,End,,result_a|result_b|result_c,combined_results
```

### Security & Configuration

**1. Use Environment Variables for Secrets**
```yaml
# Good: Environment variable references
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"

# Avoid: Hardcoded keys
llm:
  openai:
    api_key: "sk-1234567890abcdef"
```

**2. Implement Input Validation**
```csv
# Include validation steps
UserFlow,ValidateInput,branching,ProcessInput,HandleInvalidInput,user_input,validation_result
UserFlow,ProcessInput,default,SaveResult,HandleProcessingError,user_input,processed_result
```

### Testing & Debugging

**1. Enable Detailed Tracking During Development**
```yaml
execution:
  tracking:
    enabled: true
    track_inputs: true
    track_outputs: true
  success_policy:
    type: "all_nodes"
```

**2. Create Test Workflows**
```csv
# Create simplified test versions
TestFlow,MockInput,default,TestProcessor,,test_data,mock_input,"Test input: {test_data}"
TestFlow,TestProcessor,echo,ValidateOutput,,mock_input,processed_output
TestFlow,ValidateOutput,branching,Success,Failure,processed_output,validation_result
```

**3. Use Execution Path Analysis**
```python
# Monitor execution paths
result = run_graph("ComplexFlow", test_state)

print("Execution Summary:")
print(f"Success: {result['graph_success']}")
print(f"Duration: {result.get('total_duration', 0):.2f}s")

for step in result.get("execution_steps", []):
    status = "✅" if step["success"] else "❌"
    print(f"  {status} {step['node']} ({step['duration']:.3f}s)")
```

## 🔍 Troubleshooting

### Common Issues and Solutions

**1. CSV Format Errors**
```
Error: Invalidnext_nodeDefinitionError
Solution: Don't use both next_node and next_on_success/next_on_failure in the same row
```

**2. Agent Not Found**
```
Error: Agent type 'custom_agent' not found
Solution: 
- Run: agentmap scaffold --csv your_workflow.csv
- Implement the generated agent class
- Ensure agent is in the correct directory
```

**3. Memory Issues**
```
Error: Memory serialization failed
Solution:
- Check memory_key is included in input_fields
- Verify memory configuration syntax
- Ensure consistent memory_key across nodes
```

**4. LLM Configuration**
```
Error: OpenAI API key not found
Solution:
- Set environment variable: export OPENAI_API_KEY="your-key"
- Or configure in agentmap_config.yaml
- Verify key is valid and has sufficient credits
```

**5. Storage Configuration**
```
Error: Collection 'users.json' not found
Solution:
- Check file path in storage_config.yaml
- Verify file exists and has correct permissions
- For cloud storage, check credentials and container/bucket access
```

### Debug Workflow

**1. Enable Verbose Logging**
```python
from agentmap.logging import get_logger

logger = get_logger("MyApp")
logger.setLevel("DEBUG")  # Enable detailed logging

result = run_graph("MyWorkflow", initial_state)
```

**2. Inspect State at Each Step**
```python
# Add debug nodes to inspect state
def debug_state(inputs):
    print(f"Current state: {inputs}")
    return inputs

# Or use echo agents strategically
```

**3. Test Individual Nodes**
```python
# Test specific agents in isolation
from agentmap.agents.registry import get_agent

agent = get_agent("openai")
result = agent.run({"test_input": "Hello"}, {"prompt": "Say hello back"})
```

## 📖 Additional Resources

### Documentation
- [AgentMap Documentation Site](https://jwwelbor.github.io/AgentMap/)
- [API Reference](https://jwwelbor.github.io/AgentMap/docs/reference/csv-schema)
- [Examples & Tutorials](https://jwwelbor.github.io/AgentMap/docs/tutorial/intro)

### Community
- [GitHub Issues](https://github.com/jwwelbor/AgentMap/issues)
- [Discussions](https://github.com/jwwelbor/AgentMap/discussions)
- [Contributing Guide](https://github.com/jwwelbor/AgentMap/blob/main/CONTRIBUTING.md)

### Related Projects
- [LangGraph](https://github.com/langchain-ai/langgraph) - The underlying workflow engine
- [LangChain](https://github.com/langchain-ai/langchain) - AI application framework
- [FastAPI](https://fastapi.tiangolo.com/) - API framework used in AgentMap server

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/amazing-feature`
3. **Make your changes and add tests**
4. **Run tests:** `pytest tests/`
5. **Commit changes:** `git commit -m 'Add amazing feature'`
6. **Push to branch:** `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Setup
```bash
# Clone and setup development environment
git clone https://github.com/jwwelbor/AgentMap.git
cd AgentMap

# Install development dependencies
pip install -e ".[dev,all]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=agentmap tests/
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **LangGraph Team** - For the powerful workflow engine
- **LangChain Community** - For the comprehensive AI toolkit
- **Open Source Contributors** - For making this project possible

---

**Ready to build your next AI workflow? Start with AgentMap today!**

```bash
pip install agentmap
agentmap scaffold --csv your_workflow.csv
```