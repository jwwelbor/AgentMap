---
title: Getting Started with AgentMap
sidebar_position: 2
description: Get up and running with AgentMap in 5 minutes. Learn how to install, configure, and create your first AI workflow.
keywords: [getting started, quickstart, installation, setup, first workflow]
---

# Getting Started with AgentMap

Welcome to AgentMap! This guide will help you get up and running in just 5 minutes.

## 🚀 Quick Start

### 1. Installation

Install AgentMap using pip:

```bash
pip install agentmap
```

### 2. Set Up Your Environment

Create a `.env` file with your AI provider credentials:

```bash
# OpenAI
OPENAI_API_KEY=your-api-key-here

# Or Anthropic
ANTHROPIC_API_KEY=your-api-key-here

# Or Google
GOOGLE_API_KEY=your-api-key-here
```

### 3. Create Your First Workflow

Create a simple CSV file called `hello_world.csv`:

```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field
HelloWorld,start,input,greet,,,user_input
HelloWorld,greet,default,end,"Say hello to {user_input}",user_input,greeting
HelloWorld,end,echo,,,greeting,final_output
```

### 4. Verify Your Installation

Before running workflows, verify that AgentMap is properly installed and configured:

```bash
# Run comprehensive system diagnostics
agentmap diagnose
```

**Expected Output for Successful Installation:**
```
AgentMap Dependency Diagnostics
=============================

LLM Dependencies:
LLM feature enabled: True
  Openai: ✅ Available [Registry: reg=True, val=True, avail=True]
  Anthropic: ❌ Not available (Missing: langchain_anthropic) [Registry: reg=True, val=False, avail=False]
  Google: ❌ Not available (Missing: langchain_google_genai) [Registry: reg=True, val=False, avail=False]

Storage Dependencies:
Storage feature enabled: True
  csv: ✅ Available [Registry: reg=True, val=True, avail=True]
  json: ✅ Available [Registry: reg=True, val=True, avail=True]
  file: ✅ Available [Registry: reg=True, val=True, avail=True]
  vector: ❌ Not available (Missing: chromadb) [Registry: reg=True, val=False, avail=False]
  firebase: ❌ Not available (Missing: firebase_admin) [Registry: reg=True, val=False, avail=False]
  blob: ❌ Not available (Missing: azure-storage-blob) [Registry: reg=True, val=False, avail=False]

Installation Suggestions:
  For Anthropic support: pip install agentmap[anthropic] or pip install anthropic
  For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai
  For vector storage: pip install chromadb

Environment Information:
  Python Version: 3.11.4 (main, Jun  7 2023, 10:13:09) [Clang 14.0.6]
  Python Path: /usr/local/bin/python
  Current Directory: /Users/dev/agentmap

Relevant Package Versions:
  openai: v1.12.0
  anthropic: Not installed
  google.generativeai: Not installed
  langchain: v0.1.11
  langchain_google_genai: Not installed
  chromadb: Not installed
```

**✅ Good Signs**: At least one LLM provider (like OpenAI) shows as "Available" and basic storage (csv, json, file) are available.

**⚠️ Install Additional Providers** (Optional):
If you want to use multiple LLM providers or advanced storage:

```bash
# Install additional LLM providers
pip install agentmap[anthropic]  # For Claude
pip install agentmap[google]     # For Gemini

# Install vector storage for advanced workflows
pip install chromadb

# Verify all providers are now available
agentmap diagnose
```

### 5. Run Your First Workflow

```bash
agentmap run --graph HelloWorld --state '{"user_input": "World"}'
```

You should see:
```
Hello World!
```

**Troubleshooting**: If the workflow fails to run:
1. Check that your API key is properly set: `echo $OPENAI_API_KEY`
2. Run diagnostics again: `agentmap diagnose`
3. See the [Troubleshooting Guide](/docs/guides/troubleshooting) for detailed help

## 🔍 Installation Verification and Troubleshooting

### Common Installation Issues

**Issue: No LLM providers available**
```
LLM Dependencies:
  Openai: ❌ Not available (Missing: langchain_openai)
  Anthropic: ❌ Not available (Missing: langchain_anthropic)
  Google: ❌ Not available (Missing: langchain_google_genai)
```

**Solution**: Install LLM dependencies
```bash
# Install all LLM providers
pip install agentmap[llm]

# Or install specific providers
pip install agentmap[openai]     # Just OpenAI
pip install agentmap[anthropic]  # Just Anthropic
pip install agentmap[google]     # Just Google
```

**Issue: Features disabled**
```
LLM Dependencies:
LLM feature enabled: False
```

**Solution**: Check your configuration file format
```yaml
# agentmap_config.yaml - Ensure features are enabled
features:
  llm: true      # Must be boolean true, not string "true"
  storage: true
```

**Issue: API key not working**
```bash
# Verify your API key is properly set
echo $OPENAI_API_KEY

# Test API key directly
python -c "import openai; client = openai.OpenAI(); print('API key works!')"
```

**For more help**: See the comprehensive [Troubleshooting Guide](/docs/guides/troubleshooting) for detailed solutions to common issues.

## ⚙️ Advanced Configuration

While the quick start uses minimal configuration, AgentMap offers sophisticated configuration capabilities for production deployments:

### 🎯 Configuration Capabilities

- **Multiple LLM Providers**: OpenAI, Anthropic, Google with intelligent routing
- **Advanced Storage**: CSV, JSON, Vector databases, Firebase, Cloud storage  
- **Smart Routing**: Automatic provider selection based on task complexity and cost
- **Authentication**: JWT, API keys, Supabase integration
- **Performance Optimization**: Caching, connection pooling, rate limiting
- **Enterprise Features**: Monitoring, tracing, security, scalability

### 📋 Quick Configuration Setup

For more advanced features, create an `agentmap_config.yaml` file:

```yaml
# Basic configuration with multiple providers
csv_path: "workflows/main.csv"
autocompile: true

# Multiple LLM providers
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-4-turbo"
    temperature: 0.7
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-sonnet-20240229"
    temperature: 0.7

# Intelligent routing (cost optimization)
routing:
  enabled: true
  cost_optimization:
    enabled: true
    prefer_cost_effective: true

# Memory for stateful conversations
memory:
  enabled: true
  default_type: "buffer_window"
  buffer_window_size: 5

# Execution tracking
execution:
  tracking:
    enabled: true
    track_outputs: true
```

### 🚀 Production Configuration Example

```yaml
# Production-ready configuration
csv_path: "workflows/production.csv"
storage_config_path: "agentmap_storage.yaml"

# Advanced routing with all providers
routing:
  enabled: true
  routing_matrix:
    anthropic:
      low: "claude-3-haiku-20240307"
      medium: "claude-3-sonnet-20240229"
      high: "claude-3-opus-20240229"
    openai:
      low: "gpt-3.5-turbo"
      medium: "gpt-4-turbo"
      high: "gpt-4"
  cost_optimization:
    enabled: true
    max_cost_tier: "high"

# LangSmith monitoring
tracing:
  enabled: true
  mode: "langsmith"
  project: "production-workflows"
  langsmith_api_key: "env:LANGSMITH_API_KEY"

# Production logging
logging:
  file_path: "/var/log/agentmap/app.log"
  level: INFO
```

### 📚 Complete Configuration Guide

For comprehensive configuration documentation:

- **[Configuration Overview](reference/configuration/)** - Complete configuration system guide
- **[Main Configuration](reference/configuration/main-config)** - YAML structure and all options
- **[Storage Configuration](reference/configuration/storage-config)** - Multi-provider storage setup
- **[Environment Variables](reference/configuration/environment-variables)** - Complete credentials reference
- **[Configuration Examples](reference/configuration/examples)** - Production-ready examples
- **[Troubleshooting](reference/configuration/troubleshooting)** - Common issues and solutions

### ⚡ Quick Configuration Tips

1. **Start Simple**: Use basic configuration for development, add complexity for production
2. **Use Environment Variables**: Keep credentials secure with `env:VARIABLE_NAME` syntax
3. **Enable Routing**: Save costs with intelligent provider selection
4. **Configure Storage**: Set up persistent data storage for production workflows
5. **Add Monitoring**: Use LangSmith or local tracing for debugging and optimization

## 🔧 Development Workflow with Scaffolding

AgentMap's **service-aware scaffolding system** dramatically accelerates custom agent development. Here's the complete development cycle:

### Step 1: Design Your Workflow

Create a CSV with custom agents and service requirements:

```csv
graph_name,node_name,agent_type,next_on_success,context,input_fields,output_field,prompt
SmartBot,start,input,analyze,,,user_query,
SmartBot,analyze,DataAnalyzer,respond,"{""services"": [""llm"", ""storage""]}",user_query,analysis,Analyze this query: {user_query}
SmartBot,respond,ResponseGenerator,end,"{""services"": [""llm""]}",analysis,response,Generate response for: {analysis}
SmartBot,end,echo,,,response,final_output
```

### Step 2: Generate Agent Code

Use scaffolding to automatically generate service-integrated agents:

```bash
# Scaffold agents with automatic service detection
agentmap scaffold --graph SmartBot
```

**Output:**
```bash
✅ Scaffolded 2 agents/functions.
📊 Service integration: 2 with services, 0 basic agents
📁 Created files:
    data_analyzer_agent.py
    response_generator_agent.py

ℹ️  Edit generated files to implement your logic
```

### Step 3: Customize Generated Agents

The scaffolding system generates complete agents with service integration:

```python
# Generated: data_analyzer_agent.py
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from typing import Dict, Any

class DataAnalyzerAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    """
    Analyze this query: {user_query} with LLM and storage capabilities
    
    Available Services:
    - self.llm_service: LLM service for calling language models
    - self.storage_service: Generic storage service (supports all storage types)
    """
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        user_query_value = inputs.get("user_query")
        
        # LLM SERVICE: (ready to customize)
        if hasattr(self, 'llm_service') and self.llm_service:
            response = self.llm_service.call_llm(
                provider="openai",  # or "anthropic", "google"
                messages=[{"role": "user", "content": user_query_value}],
                model="gpt-4"
            )
            analysis_result = response.get("content")
        
        # STORAGE SERVICE: (ready to customize)
        if hasattr(self, 'storage_service') and self.storage_service:
            # Save analysis for future reference
            self.storage_service.write("json", "query_analysis.json", {
                "query": user_query_value,
                "analysis": analysis_result
            })
        
        return analysis_result
```

### Step 4: Test Your Workflow

```bash
# Test the workflow with your custom agents
agentmap run --graph SmartBot --state '{"user_query": "What is machine learning?"}'
```

### Step 5: Deploy and Scale

```bash
# Compile for production
agentmap compile --graph SmartBot

# Deploy as API (see deployment guides)
# Or integrate into your application
```

### 🎯 Scaffolding Benefits

- **🚀 10x faster development**: Generate complete agent classes in seconds
- **🔧 Service integration**: Automatic LLM, storage, vector service setup
- **📝 Documentation included**: Generated code includes usage examples
- **✅ Best practices**: Templates follow AgentMap patterns and conventions
- **🔄 Iterative development**: Scaffold → customize → test → deploy cycle

## 📚 Next Steps

Now that you have AgentMap running, explore these resources:

### Learn the Fundamentals
- [Basic Agents Tutorial](guides/learning/01-basic-agents) - Understand the core agent types
- [Custom Prompts Guide](guides/learning/02-custom-prompts) - Create sophisticated AI behaviors
- [CSV Schema Reference](reference/csv-schema) - Master the workflow definition format

### Build Real Applications
- [Example Workflows](templates/) - Ready-to-use templates for common tasks
- [Agent Catalog](reference/agent-catalog) - Explore all available agent types
- [Integration Guide](guides/development/integrations) - Connect to external services

### Deploy to Production
- [FastAPI Integration](deployment/fastapi-integration) - Build REST APIs
- [CLI Commands](deployment/cli-commands) - Master the command-line interface
- [Best Practices](guides/development/best-practices) - Production-ready patterns

## 🎯 Common Use Cases

### Data Processing Pipeline
```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field
DataPipeline,start,input,extract,,,raw_data
DataPipeline,extract,default,transform,"Extract key info from: {raw_data}",raw_data,extracted
DataPipeline,transform,default,save,"Clean and format: {extracted}",extracted,cleaned
DataPipeline,save,csv_writer,end,,cleaned,result
DataPipeline,end,echo,,,result,final_output
```

### Multi-Agent Research Assistant
```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field
Research,start,input,researcher,,,query
Research,researcher,default,summarizer,"Research this topic: {query}",query,research
Research,summarizer,default,end,"Summarize findings: {research}",research,summary
Research,end,echo,,,summary,final_output
```

## 🛠️ Production Configuration

AgentMap provides enterprise-grade configuration capabilities:

### 🔧 Key Configuration Features
- **Multi-Provider Support**: OpenAI, Anthropic, Google with intelligent routing
- **Cost Optimization**: Automatic provider selection based on complexity and cost
- **Storage Backends**: CSV, JSON, Vector databases, Firebase, Cloud storage
- **Security**: JWT authentication, API keys, environment variable management
- **Monitoring**: LangSmith integration, comprehensive logging, tracing
- **Performance**: Connection pooling, caching, rate limiting

### 📖 Configuration Documentation

For complete configuration setup:

- **[Configuration Overview](reference/configuration/)** - Start here for configuration concepts
- **[Main Configuration Reference](reference/configuration/main-config)** - Complete YAML options
- **[Storage Configuration](reference/configuration/storage-config)** - Multi-provider storage
- **[Environment Variables](reference/configuration/environment-variables)** - Secure credential management
- **[Configuration Examples](reference/configuration/examples)** - Ready-to-use configurations
- **[Troubleshooting Guide](reference/configuration/troubleshooting)** - Common issues and solutions

### ⚡ Quick Start Configuration

```yaml
# agentmap_config.yaml - Basic production setup
csv_path: "workflows/main.csv"
autocompile: true

llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-4-turbo"
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-sonnet-20240229"

routing:
  enabled: true
  cost_optimization:
    enabled: true
    prefer_cost_effective: true
```

## 🤝 Getting Help

- **Documentation**: You're here! Explore the sidebar for more guides
- **GitHub Issues**: [Report bugs or request features](https://github.com/jwwelbor/AgentMap/issues)
- **Discussions**: [Join the community](https://github.com/jwwelbor/AgentMap/discussions)

## 🎉 Ready to Build?

You now have everything you need to start building AI workflows with AgentMap. Check out the [Learning Path](guides/learning/) for a structured journey through all features.

Happy building! 🚀