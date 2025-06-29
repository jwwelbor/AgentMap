---
title: AgentMap Core Features & Capabilities - Complete AI Workflow Platform Overview
description: Comprehensive overview of AgentMap's features, architecture patterns, and implementation capabilities for AI agent workflow orchestration. Multi-LLM support, storage integration, and more.
keywords: [AgentMap features, AI workflow platform, multi-LLM integration, workflow orchestration, agent architecture, CSV workflows, storage integration, vector databases]
image: /img/agentmap-hero.png
sidebar_position: 3
tags: [features, architecture, overview, capabilities]
---

# AgentMap Core Features & Capabilities

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

### Agent Ecosystem (20+ Built-in Types)
- **Core Agents**: Default, Echo, Branching, Success/Failure, Input
- **LLM Agents**: OpenAI (GPT), Anthropic (Claude), Google (Gemini) with unified interface
- **Storage Agents**: CSV, JSON, File operations with local and cloud support
- **Advanced Agents**: Vector databases, Orchestrator, Summary, Graph agents
- **Custom Agent Support**: Full scaffolding system for extension

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

### Powerful CLI System
- Workflow execution with state management
- Auto-scaffolding for custom agents and functions
- Graph compilation and export capabilities
- Configuration management and validation

### Scaffolding & Code Generation
- Automatic generation of custom agent boilerplate
- Function template creation with proper signatures
- Documentation generation with context-aware comments
- Best practice templates and examples

### Development Tools
- Hot reloading for rapid development cycles
- Comprehensive logging and debugging support
- Execution tracking with configurable success policies
- Performance monitoring and metrics

## 📊 Execution & Monitoring

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
- Storage abstraction layers

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
| `branching` | Conditional routing | Looks for success indicators | Returns routing decision |
| `success` | Always succeeds | Any | Returns success message |
| `failure` | Always fails | Any | Returns failure message |

### LLM Agent Types

| Agent Type | Provider | Features | Configuration |
|------------|----------|----------|---------------|
| `openai` (aliases: `gpt`, `chatgpt`) | OpenAI | GPT models, memory | Model, temperature, memory settings |
| `claude` (alias: `anthropic`) | Anthropic | Claude models, memory | Model, temperature, memory settings |  
| `gemini` (alias: `google`) | Google | Gemini models, memory | Model, temperature, memory settings |

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

## Next Steps

:::tip Ready to Get Started?
- **Quick Start**: Begin with our [5-minute tutorial](../getting-started.md)
- **Build Your First Workflow**: Follow the [quick start guide](../getting-started.md)
- **Explore Examples**: Check out [example workflows](../examples/)
:::

:::info Deep Dive Topics
- **[State Management](../guides/learning-paths/core/state-management.md)**: Understand data flow between agents
- **[Agent Development](../guides/development/agents/agent-development.md)**: Create custom agents
- **[Infrastructure Guide](../guides/deploying/index.md)**: Work with files, databases and cloud storage
:::

## Related Documentation

- **[CSV Schema Reference](../reference/csv-schema.md)**: Complete schema documentation
- **[Agent Types Reference](../reference/agent-types.md)**: All available agent types
- **[CLI Commands](../reference/cli-commands.md)**: Command-line tools and options
