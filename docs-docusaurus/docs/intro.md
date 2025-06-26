---
sidebar_position: 1
title: AgentMap Documentation - Build AI Workflows with CSV Files
description: Complete guide to AgentMap - build powerful AI workflows using simple CSV files. No coding required. Get started in 5 minutes with our quick start guide.
keywords: [AgentMap, AI workflows, CSV automation, no-code AI, agent orchestration, data pipelines, business automation]
image: /img/agentmap-hero.png
---

# Welcome to AgentMap

**Build AI Workflows with Simple CSV Files** - No coding required!

AgentMap makes it incredibly easy to create powerful AI workflows using familiar CSV files. Whether you're automating business processes, building data pipelines, or creating AI assistants, AgentMap handles the complexity while you focus on your goals.

## 🚀 Get Started in 5 Minutes

Ready to build your first AI workflow? Our quick start guide will have you up and running with a working weather bot in under 10 minutes.

**[👉 Start the Quick Start Guide](./getting-started/quick-start)**

## ✨ What Makes AgentMap Special?

### 📝 **CSV-Based Configuration**
Define your entire workflow in a simple CSV file. No complex YAML, no programming - just rows and columns that anyone can understand and edit.

### 🤖 **AI Agent Orchestration** 
Combine multiple AI agents seamlessly. Weather APIs, language models, data processors - all working together in harmony.

### ⚡ **Simple but Powerful**
Start with a basic workflow in minutes, then scale to enterprise complexity with advanced features like parallel processing, memory management, and custom routing.

### 🌐 **Production Ready**
Built for real-world use with enterprise-grade reliability, monitoring, and deployment capabilities.

## 📋 Examples: What You Can Build

- **🌐 API-Driven Bots** - API driven bots (e.g. WeatherBot, FlightBot, StatusBot) - **[See Tutorial](./tutorials/weather-bot)**
- **📊 Data Pipelines** - Transform and analyze data from multiple sources - **[See Tutorial](./tutorials/data-processing-pipeline)**  
- **📧 Customer Support Bots** - Smart categorization and automated responses - **[See Tutorial](./tutorials/customer-support-bot)**
- **🔍 Document Analyzers** - AI-powered document processing - **[See Tutorial](./tutorials/document-analyzer)**
- **🔗 API Integrations** - Connect to external services and APIs - **[See Tutorial](./tutorials/api-integration)**
- **💼 Business Automators** - Streamline invoicing, reporting, and communication

## 🎯 How It Works

1. **📝 Define** - Create a CSV file describing your workflow
2. **🤖 Configure** - Set up AI agents with roles and data sources  
3. **🚀 Deploy** - Launch your workflow and watch it work automatically

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

### 📖 **[Guides](./guides)**
Detailed documentation on specific topics:
- **[Understanding Workflows](./guides/understanding-workflows)** - Core concepts and patterns
- **[Advanced Features](./guides/advanced)** - Memory, routing, and optimization
- **[Best Practices](./guides/best-practices)** - Production-ready workflows

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
- **[Agent Development](./guides/agent-development)** - Custom agent creation
- **[State Management](./guides/state-management)** - Data flow patterns
- **[Memory & Conversations](./guides/memory-and-conversations)** - Conversational AI
- **[Storage & Data](./guides/storage-and-data)** - File and database operations

### **5. Production Deployment**
Prepare for real-world use:
- **[Monitoring & Debugging](./guides/monitoring-and-debugging)** - Performance tracking
- **[Testing Workflows](./advanced/testing-workflows)** - Quality assurance
- **[Custom Services](./advanced/custom-services)** - Enterprise integration

## 🏗️ Key Architecture Concepts

### **Clean Architecture Pattern**
AgentMap follows clean architecture principles:
- **Models Layer**: Pure data containers with no business logic
- **Services Layer**: All business logic and orchestration  
- **Dependency Injection**: Automatic service wiring and lifecycle management
- **Protocol-Based Injection**: Type-safe service configuration using Python protocols

### **Service Injection System**
The [Dependency Injection](./guides/dependency-injection) system provides:
- **DI Container**: Centralized service registry with automatic dependency resolution
- **Service Lifecycle**: Lazy instantiation and singleton pattern
- **Graceful Degradation**: Optional services fail gracefully when unavailable
- **Protocol-Based Injection**: Services injected based on interface implementation

### **Agent Development Patterns**
The [Agent Development](./guides/agent-development) framework defines:
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
- **[Agent Development](./guides/agent-development)** - Required interface and patterns for all agents
- **[Dependency Injection](./guides/dependency-injection)** - Protocol-based dependency injection system
- **[Built-in Agents](./reference/built-in-agents)** - Built-in agent types and basic usage
- **[Advanced Agents](./reference/advanced-agents)** - Advanced agents and comprehensive context configuration

### **Workflow Management**
- **[Memory & Conversations](./guides/memory-and-conversations)** - Template system and conversation management
- **[Intelligent Routing](./guides/intelligent-routing)** - Dynamic workflow routing and orchestration
- **[Workflow Patterns](./examples/workflow-patterns)** - Complete workflow examples

### **Operations and Tools**
- **[CLI Reference](./reference/cli-reference)** - Command-line interface and tools
- **[Graph Inspection](./tools/graph-inspection)** - Debugging and inspection tools
- **[Monitoring & Debugging](./guides/monitoring-and-debugging)** - Performance monitoring and debugging
- **[Storage & Data](./guides/storage-and-data)** - Unified storage operations for CSV, files, and data
- **[Cloud Storage](./guides/cloud-storage)** - Cloud storage integration

### **Advanced Topics**
- **[Custom Services](./advanced/custom-services)** - Extend AgentMap with custom services and agents
- **[Service Registry](./advanced/service-registry)** - Registry API for managing services
- **[Testing Workflows](./advanced/testing-workflows)** - Testing patterns and best practices

## 🤝 Community & Support

- **[GitHub Repository](https://github.com/jwwelbor/AgentMap)** - Source code, issues, and contributions
- **[Discussions](https://github.com/jwwelbor/AgentMap/discussions)** - Community Q&A and workflow sharing
- **[Issue Tracker](https://github.com/jwwelbor/AgentMap/issues)** - Bug reports and feature requests

---

**Ready to start building?** 🎉

**[Begin Quick Start Guide →](./getting-started/quick-start)**
