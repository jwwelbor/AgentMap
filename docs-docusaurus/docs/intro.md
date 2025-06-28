---
sidebar_position: 1
title: AgentMap - Build Agentic AI Workflows with Multi-Agent Systems
description: Build autonomous multi-agent AI workflows with CSV files. RAG AI support, vector databases, LLM orchestration, and custom agentic AI development. No-code agent framework.
keywords: [agentic AI workflows, multi-agent systems, RAG AI, retrieval augmented generation, LLM orchestration, autonomous AI agents, vector database integration, agent framework, multi-agent AI]
image: /img/agentmap-hero.png
---

# Welcome to AgentMap

**Build Agentic AI Workflows with Multi-Agent Systems** - Autonomous agents that think, decide, and act!

AgentMap makes it incredibly easy to create autonomous multi-agent AI systems using familiar CSV files. Whether you're building RAG AI applications, LLM orchestration systems, or complex agentic workflows, AgentMap handles the complexity while you focus on your AI goals.

## 🚀 Get Started in 5 Minutes

Ready to build your first AI workflow? Our quick start guide will have you up and running with a working weather bot in under 10 minutes.

**[👉 Start the Quick Start Guide](./getting-started/quick-start)**

## ✨ What Makes AgentMap Special?

### 🤖 **Agentic AI Workflows**
Create autonomous agents that make decisions, route intelligently, and adapt behavior based on context. True agentic AI that goes beyond simple automation.

### 🧠 **Multi-Agent Orchestration** 
Combine specialized AI agents seamlessly. LLM reasoning, vector search, document processing, and custom logic - all working together in intelligent coordination.

### 🔍 **Native RAG AI Support**
Built-in vector database integration (Chroma, FAISS) for retrieval-augmented generation. Create knowledge-aware agents that reference your data.

### 📝 **CSV-Based Configuration**
Define complex multi-agent systems in simple CSV files. Version control friendly, collaborative, and no YAML complexity.

### 🌐 **Production-Grade Multi-LLM**
Orchestrate OpenAI, Anthropic, and Google models with memory management, routing, and failover capabilities.

## 📊 Examples: Agentic AI Systems You Can Build

- **🧠 RAG AI Chatbots** - Knowledge-aware agents with vector search and memory - **[See Tutorial](./tutorials/rag-chatbot)**
- **🔄 Multi-Agent Research** - Autonomous agents that gather, analyze, and synthesize information - **[See Tutorial](./tutorials/multi-agent-research)**  
- **🎯 Intelligent Document Processing** - Agentic workflows for document understanding and extraction - **[See Tutorial](./tutorials/document-analyzer)**
- **🤖 Autonomous Customer Support** - Multi-agent systems with intent classification and specialized handlers - **[See Tutorial](./tutorials/customer-support-bot)**
- **🔗 Adaptive API Orchestration** - Self-routing agents that choose optimal APIs and fallbacks - **[See Tutorial](./tutorials/api-integration)**
- **📈 Agentic Data Pipelines** - Intelligent ETL with decision-making and quality assessment - **[See Tutorial](./tutorials/data-processing-pipeline)**

## 🎯 How Agentic AI Works in AgentMap

1. **📝 Define** - Create a CSV file describing your multi-agent system
2. **🤖 Configure** - Set up autonomous agents with reasoning capabilities and data sources  
3. **🚀 Deploy** - Launch your agentic workflow and watch agents collaborate autonomously

## 🧭 Navigation Guide

### 🏃‍♂️ **[Quick Start](./getting-started/quick-start)** 
Build your first workflow in 5 minutes with our step-by-step guide.

### 📚 **[Tutorials](./tutorials)**
Deep dive into AgentMap features with comprehensive examples and explanations:
- **[Weather Bot](./tutorials/weather-bot)** - API integration with AI processing
- **[Data Processing Pipeline](./tutorials/data-processing-pipeline)** - Transform and validate data
- **[Customer Support Bot](./tutorials/customer-support-bot)** - Intent classification and routing
- **[API Integration](./tutorials/api-integration)** - Connect to external services
- **[Document Analyzer](./tutorials/document-analyzer)** - AI-powered document processing

### 📖 **[Guides](./guides/)**
Detailed documentation on specific topics:
- **[Understanding Workflows](./guides/understanding-workflows)** - Core concepts and patterns
- **[Advanced Features](./guides/advanced/)** - Memory, routing, and optimization
- **[Best Practices](./guides/best-practices/)** - Production-ready workflows

### 🔧 **[Reference](./reference)**
Complete API and configuration documentation:
- **[Agent Types](./reference/agent-types)** - All available agent types
- **[CSV Schema](./reference/csv-schema)** - Complete CSV format reference
- **[CLI Commands](./reference/cli-commands)** - Command-line interface guide

## 🎓 Learning Path for New Users

For developers new to AgentMap, we recommend this learning progression:

### **1. Quick Start** (5 minutes)
Build your first working workflow with our [Quick Start Guide](./getting-started/quick-start)

### **2. Core Concepts** (15 minutes)
Understand the fundamentals:
- **[Core Features](./overview/core-features)** - AgentMap capabilities and architecture
- **[Understanding Workflows](./guides/understanding-workflows)** - How workflows work
- **[CSV Schema](./reference/csv-schema)** - Workflow definition format

### **3. Hands-On Practice** (30 minutes)
Build real workflows with tutorials:
- **[Weather Bot](./tutorials/weather-bot)** - API integration basics
- **[Data Pipeline](./tutorials/data-processing-pipeline)** - Data transformation
- **[Support Bot](./tutorials/customer-support-bot)** - AI-powered routing

### **4. Advanced Topics** (60 minutes)
Dive deeper into AgentMap:
- **[Agent Development Contract](./guides/advanced/agent-development-contract)** - Custom agent creation
- **[State Management](./guides/state-management)** - Data flow patterns
- **[Memory Management](./guides/advanced/memory-and-orchestration/memory-management)** - Conversational AI and persistence
- **[Infrastructure Services](./guides/infrastructure/storage-services-overview)** - File, database, and cloud operations

### **5. Production Deployment**
Prepare for real-world use:
- **[Execution Tracking](./guides/operations/execution-tracking)** - Performance monitoring and debugging
- **[Testing Workflows](./guides/operations/testing-patterns)** - Quality assurance
- **[Host Service Integration](./guides/advanced/host-service-integration)** - Enterprise integration

## 🏗️ Key Architecture Concepts

### **Clean Architecture Pattern**
AgentMap follows clean architecture principles:
- **Models Layer**: Pure data containers with no business logic
- **Services Layer**: All business logic and orchestration  
- **Dependency Injection**: Automatic service wiring and lifecycle management
- **Protocol-Based Injection**: Type-safe service configuration using Python protocols

### **Service Injection System**
The [Dependency Injection](./reference/dependency-injection) system provides:
- **DI Container**: Centralized service registry with automatic dependency resolution
- **Service Lifecycle**: Lazy instantiation and singleton pattern
- **Graceful Degradation**: Optional services fail gracefully when unavailable
- **Protocol-Based Injection**: Services injected based on interface implementation

### **Agent Development Patterns**
The [Agent Development Contract](./guides/advanced/agent-development-contract) framework defines:
- Modern constructor patterns with infrastructure service injection
- Protocol-based business service configuration  
- Debugging hooks and service information methods
- Complete implementation examples

## 📚 Complete Documentation Index

### **Core Concepts**
- **[Core Features](./overview/core-features)** - Overview of AgentMap capabilities and features
- **[CSV Schema](./reference/csv-schema)** - Complete CSV schema reference
- **[State Management](./guides/state-management)** - How data flows between agents

### **Agent Development**
- **[Agent Development Contract](./guides/advanced/agent-development-contract)** - Required interface and patterns for all agents
- **[Service Injection Patterns](./guides/advanced/service-injection-patterns)** - Protocol-based dependency injection system
- **[Agent Types Reference](./reference/agent-types)** - Built-in agent types and basic usage
- **[Advanced Agent Types](./guides/advanced/advanced-agent-types)** - Advanced agents and comprehensive context configuration

### **Workflow Management**
- **[Memory Management](./guides/advanced/memory-and-orchestration/memory-management)** - Template system and conversation management
- **[Orchestration Patterns](./guides/advanced/memory-and-orchestration/orchestration-patterns)** - Dynamic workflow routing and orchestration
- **[Example Workflows](./examples/)** - Complete workflow examples

### **Operations and Tools**
- **[CLI Commands](./reference/cli-commands)** - Command-line interface and tools
- **[CLI Graph Inspector](./reference/cli-graph-inspector)** - Debug and analyze workflows
- **[Execution Tracking](./guides/operations/execution-tracking)** - Performance monitoring and debugging
- **[Infrastructure Services](./guides/infrastructure/storage-services-overview)** - Unified storage operations for CSV, files, and data
- **[Cloud Storage Integration](./guides/infrastructure/cloud-storage-integration)** - Cloud storage integration

### **Advanced Topics**
- **[Host Service Integration](./guides/advanced/host-service-integration)** - Extend AgentMap with custom services and agents
- **[Service Registry Patterns](./guides/infrastructure/service-registry-patterns)** - Registry patterns for managing services
- **[Testing Workflows](./guides/operations/testing-patterns)** - Testing patterns and best practices

## 🤝 Community & Support

- **[GitHub Repository](https://github.com/jwwelbor/AgentMap)** - Source code, issues, and contributions
- **[Discussions](https://github.com/jwwelbor/AgentMap/discussions)** - Community Q&A and workflow sharing
- **[Issue Tracker](https://github.com/jwwelbor/AgentMap/issues)** - Bug reports and feature requests

---

**Ready to start building?** 🎉

**[Begin Quick Start Guide →](./getting-started/quick-start)**
