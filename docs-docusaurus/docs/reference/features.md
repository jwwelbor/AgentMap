---
title: Features & Capabilities
description: Comprehensive overview of AgentMap's features, architecture patterns, and implementation capabilities for AI agent workflow orchestration. Multi-LLM support, storage integration, and more.
keywords: [AgentMap features, AI workflow platform, multi-LLM integration, workflow orchestration, agent architecture, CSV workflows, storage integration, vector databases]
image: /img/agentmap-hero.png
sidebar_position: 1
tags: [features, architecture, overview, capabilities, reference]
---

# Features & Capabilities

AgentMap is a sophisticated **agentic AI orchestration framework** that transforms simple CSV files into powerful autonomous multi-agent AI systems. This comprehensive guide covers the complete feature set for building **RAG AI applications**, **multi-agent workflows**, and **LLM orchestration systems**.

## 🎯 Core Agentic AI Features

### Autonomous Multi-Agent Workflows
- **Agentic decision-making** with intelligent routing and autonomous behavior
- **Multi-agent collaboration** where specialized agents coordinate and communicate
- **Self-directed execution** with agents that adapt and respond to changing conditions
- **Hierarchical agent systems** with supervisor and worker agent patterns
- **Event-driven autonomy** where agents react intelligently to triggers and state changes

### RAG AI & Vector Database Integration
- **Native vector database support** (Chroma, FAISS, Pinecone) for retrieval-augmented generation
- **Semantic search agents** that intelligently query knowledge bases
- **Document processing pipelines** with chunking, embedding, and retrieval
- **Knowledge-aware LLM agents** that combine reasoning with retrieved context
- **Multi-modal RAG systems** supporting text, code, and structured data

### Agent Ecosystem (16+ Built-in Types)
- **Core Agents** (10 types): Default, Echo, Branching, Success, Failure, Input, Graph, Human, Orchestrator, Summary
- **LLM Agents** (4 types): OpenAI (GPT), Anthropic (Claude), Google (Gemini), LLM (base) with unified interface
- **Storage Agents** (6 types): CSV (reader/writer), JSON (reader/writer), File (reader/writer), Vector (reader/writer), Document (reader/writer), Blob Storage
- **Custom Agent Support**: Full scaffolding system for extension with service-aware generation

## 🤖 AI & LLM Capabilities

### Multi-LLM Integration
- Unified interface across OpenAI, Anthropic, Google providers
- Configurable models, temperature, and parameters per node
- Automatic prompt template processing with field substitution
- Memory management with conversation history and context retention

### Memory Management System
- **Multiple memory types**: Buffer, Buffer Window, Summary, Token Buffer
- **Declarative memory configuration** through CSV Context field
- **Automatic serialization/deserialization** between nodes
- **Shared memory** across multi-agent workflows

### Advanced AI Features
- **Intelligent orchestration** with dynamic routing based on content analysis
- **Vector database integration** for semantic search and document retrieval
- **Document processing** with chunking and metadata extraction
- **Prompt management system** with registry, file, and YAML references

## 💾 Storage & Integration

### Universal Storage Support
- **Local Storage**: CSV, JSON, file operations with LangChain integration
- **Cloud Storage**: Azure Blob, AWS S3, Google Cloud Storage with URI-based access
- **Databases**: Firebase integration, vector stores (Chroma, FAISS)
- **Document Processing**: PDF, Word, Markdown, HTML with intelligent chunking

### Storage Configuration
- Centralized storage configuration with provider-specific settings
- Environment variable support for credentials
- Container/bucket mapping with logical names
- Multiple authentication methods per provider

## 🛠️ Developer Experience

### Service-Aware Scaffolding System
AgentMap's **most powerful productivity feature** - an intelligent code generation system that analyzes CSV workflows and automatically creates service-integrated agent classes:

- **Service-aware code generation**: Automatically detects service requirements from CSV context and generates agents with proper LLM, storage, vector, and memory service integration
- **Multi-architecture support**: Unified storage vs. separate service protocols based on requirements analysis
- **Template system**: Sophisticated IndentedTemplateComposer with modular agent and function templates
- **Agent registry integration**: Conflict detection to avoid scaffolding existing agents
- **Complete workflow integration**: Scaffold → customize → test → deploy development cycle

**Supported Services**: LLM (OpenAI, Anthropic, Google), Storage (CSV, JSON, File, Vector, Memory), Node Registry

**Example Usage**:
```bash
# Service-aware scaffolding with automatic service detection
agentmap scaffold --graph IntelligentWorkflow

# Generated agents with service integration
class DataAnalyzerAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    # Automatic service injection and usage examples included
```

### Powerful CLI System
- Workflow execution with state management and real-time feedback (`run`)
- Advanced scaffolding commands with service integration (`scaffold`)
- Bundle management and caching (`update-bundle`)
- Configuration management and comprehensive validation (`init-config`, `validate`, `diagnose`, `refresh`)

**Available Commands**: `run`, `scaffold`, `update-bundle`, `init-config`, `validate`, `diagnose`, `refresh`

**Repository Workflows** - Execute workflows from CSV repository:
```bash
# Direct repository execution
agentmap run workflow/GraphName

# Repository with CSV file  
agentmap run workflows/hello_world.csv --graph HelloWorld

# Traditional file execution
agentmap run path/to/workflow.csv --graph GraphName
```

### Advanced Code Generation
- **Context-aware templates**: Service requirements parsed from CSV context fields
- **Protocol integration**: Automatic inheritance from LLMCapableAgent, StorageCapableAgent, etc.
- **Usage examples**: Generated code includes service integration examples and best practices
- **Function scaffolding**: Complete routing function generation with context-aware logic

### Development Tools
- Hot reloading for rapid development cycles
- Comprehensive logging and debugging support
- Execution tracking with configurable success policies
- Performance monitoring and metrics

## 📊 Execution & Monitoring

### High-Performance Bundle System
- **Bundle-based caching**: Intelligent graph compilation and caching for 10x faster execution
- **Static analysis optimization**: Declaration-based analysis eliminates runtime overhead
- **Repository workflows**: Execute workflows directly with `agentmap run workflow/GraphName` syntax
- **Composite key lookups**: Efficient bundle retrieval using CSV hash + graph name
- **Smart invalidation**: Bundles automatically refresh when CSV content changes

### Execution Tracking System
- **Two-tier tracking**: Minimal (always on) and Detailed (optional)
- **Policy-based success evaluation** with multiple strategies
- **Real-time execution path monitoring**
- **Performance metrics** and timing information

### Success Policies
- All nodes must succeed
- Final node success only
- Critical nodes success
- Custom policy functions

### State Management
- Immutable state transitions with comprehensive data flow
- Multiple state formats support (dict, Pydantic, custom)
- Memory serialization and field mapping
- Error handling and recovery mechanisms

## 🏗️ Architecture & Extensibility

### Service-Oriented Design
- Clean separation of concerns with dependency injection
- Pluggable architecture with consistent interfaces
- Agent contract system for custom implementations
- Storage abstraction layers with unified service registry

### Bundle-Based Execution
- **Pre-compiled workflows**: CSV files compiled to cached bundle objects for faster execution
- **Static analysis**: Declaration-based graph validation eliminates runtime overhead
- **Intelligent caching**: Bundles automatically invalidate when source CSV changes
- **Repository integration**: Direct execution from workflow repositories without local files

### Advanced Routing
- Conditional branching based on execution success
- Function-based routing with custom logic
- Multi-target routing for parallel processing
- Orchestrator-based intelligent routing

## CSV Schema System

### Core Columns
| Column | Required | Description | Examples |
|--------|----------|-------------|----------|
| `GraphName` | ✅ | Workflow identifier | `ChatBot`, `DocumentProcessor` |
| `Node` | ✅ | Unique node name within graph | `GetInput`, `ProcessData`, `SaveResults` |
| `Edge` | ❌ | Direct connection to next node | `NextNode`, `func:custom_router` |
| `Context` | ❌ | Node configuration (JSON or text) | `{"memory_key":"chat_history"}` |
| `AgentType` | ❌ | Type of agent to use | `openai`, `claude`, `csv_reader` |
| `Success_Next` | ❌ | Next node on success | `ProcessData`, `Success\|Backup` |
| `Failure_Next` | ❌ | Next node on failure | `ErrorHandler`, `Retry` |
| `Input_Fields` | ❌ | State fields to extract as input | `user_input\|context\|memory` |
| `Output_Field` | ❌ | Field to store agent output | `response`, `processed_data` |
| `Prompt` | ❌ | Agent prompt or configuration | `"You are helpful: {input}"`, `prompt:system_instructions` |
| `Description` | ❌ | Documentation for the node | `"Validates user input format"` |

**Note**: Column names support case-insensitive matching and aliases. For example, `GraphName` accepts `graph_name`, `workflow_name`; `AgentType` accepts `agent_type`, `Agent`; `Node` accepts `node_name`, `NodeName`, etc.

### Advanced Routing Patterns

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CSVTable from '@site/src/components/CSVTable';

<Tabs>
<TabItem value="conditional" label="Conditional Branching">

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataFlow,Validate,,Conditional validation logic,branching,Transform,ErrorHandler,raw_data,validation_result,`}
  title="Conditional Branching Example"
  filename="conditional_branching"
/>

</TabItem>
<TabItem value="parallel" label="Multiple Targets">

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
Parallel,Distribute,,Split data for parallel processing,default,ProcessA|ProcessB|ProcessC,,data,distributed_tasks,`}
  title="Parallel Processing Example"
  filename="parallel_targets"
/>

</TabItem>
<TabItem value="function" label="Function-Based Routing">

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
Smart,Classifier,func:choose_specialist,Route to specialized agents,default,,,user_query,classification,`}
  title="Function-Based Routing Example"
  filename="function_routing"
/>

</TabItem>
</Tabs>

## Agent Types Reference

### Core Agent Types

| Agent Type | Purpose | Input Behavior | Output Behavior |
|------------|---------|----------------|-----------------|
| `default` | Basic processing | Any fields | Returns message with prompt |
| `echo` | Pass-through | First input field | Returns input unchanged |
| `input` | User interaction | Ignored | Prompts user, returns input |
| `human` | Human-in-the-loop | Any fields | Prompts human for input |
| `branching` | Conditional routing | Looks for success indicators | Returns routing decision |
| `success` | Always succeeds | Any | Returns success message |
| `failure` | Always fails | Any | Returns failure message |
| `graph` | Sub-graph execution | Any fields | Executes nested graph workflow |
| `orchestrator` | Intelligent routing | Query and context | Routes to best available agent |
| `summary` | Content summarization | Text content | Returns summarized content |

### LLM Agent Types

| Agent Type | Provider | Features | Configuration |
|------------|----------|----------|---------------|
| `llm` | Generic | Base LLM agent, unified interface | Provider, model, temperature, memory settings |
| `openai` (aliases: `gpt`) | OpenAI | GPT models, memory | Model, temperature, memory settings |
| `anthropic` (alias: `claude`) | Anthropic | Claude models, memory | Model, temperature, memory settings |  
| `google` (alias: `gemini`) | Google | Gemini models, memory | Model, temperature, memory settings |

### Storage Agent Types

#### File Operations
| Agent Type | Purpose | Required Input | Output |
|------------|---------|----------------|--------|
| `file_reader` | Read documents | `collection` (file path) | Document content with metadata |
| `file_writer` | Write files | `collection` (path), `data` | Operation result |

#### Structured Data
| Agent Type | Purpose | Required Input | Output |
|------------|---------|----------------|--------|
| `csv_reader` | Read CSV files | `collection` (file path) | Parsed CSV data |
| `csv_writer` | Write CSV files | `collection` (path), `data` | Operation result |
| `json_reader` | Read JSON files | `collection` (file path) | JSON data |
| `json_writer` | Write JSON files | `collection` (path), `data` | Operation result |
| `document_reader` | Read documents | `collection` (file path) | Document content with metadata |
| `document_writer` | Write documents | `collection` (path), `data` | Operation result |

#### Cloud Storage
| Agent Type | Purpose | URI Format | Authentication |
|------------|---------|------------|----------------|
| `cloud_json_reader` | Read from cloud | `azure://container/file.json` | Connection string/keys |
| `cloud_json_writer` | Write to cloud | `s3://bucket/file.json` | AWS credentials |

#### Vector Databases
| Agent Type | Purpose | Configuration | Use Cases |
|------------|---------|---------------|-----------|
| `vector_reader` | Similarity search | Store configuration | Document retrieval, semantic search |
| `vector_writer` | Store embeddings | Store configuration | Knowledge base building |

## Feature Status & Availability

### Implementation Status
- 🟢 **Stable**: Core agents (10), LLM integration (4 providers), storage services (6 types), scaffolding system
- 🟡 **Beta**: Vector database integration, orchestrator routing, bundle caching system
- 🔵 **Validated**: All documented CLI commands and CSV schema verified against current implementation (v2024.09.03)

### CLI Commands Status
**Available Commands** (verified in `main_cli.py`):
- `run` - Execute workflows with bundle caching and repository support
- `scaffold` - Generate agents with service integration  
- `update-bundle` - Manage bundle cache and compilation
- `validate` - Validate CSV and configurations
- `diagnose` - System diagnostics and health checks
- `refresh` - Refresh caches and registries
- `init-config` - Initialize configuration files

**Note**: Previously documented commands `export`, `resume`, `validate-csv`, `validate-config`, and `validate-all` are not currently implemented.

## Next Steps

:::tip Ready to Get Started?
- **Quick Start**: Begin with our [5-minute tutorial](/docs/getting-started)
- **Build Your First Workflow**: Follow the [quick start guide](/docs/getting-started)
- **Explore Examples**: Check out [example workflows](/docs/templates/)
:::

:::info Deep Dive Topics
- **[State Management](/docs/contributing/state-management)**: Understand data flow between agents
- **[Agent Development](/docs/guides/development/agents/agent-development)**: Create custom agents
- **[Infrastructure Guide](/docs/deployment/)**: Work with files, databases and cloud storage
:::

## Related Documentation

- **[Architecture Guide](/docs/reference/architecture)**: Deep dive into AgentMap's service-oriented architecture, bundle system, and dependency injection
- **[CSV Schema Reference](/docs/reference/csv-schema)**: Complete schema documentation with column specifications
- **[Agent Types Reference](/docs/reference/agent-types)**: All available agent types with implementation details
- **[CLI Commands](/docs/deployment/cli-commands)**: Command-line tools and options
