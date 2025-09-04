---
sidebar_position: 4
title: Installation Guide
description: Complete installation and configuration guide for AgentMap. Multiple providers, production setup, troubleshooting.
keywords: [installation, configuration, setup, multiple providers, production, troubleshooting]
---

# Installation Guide

This guide covers complete AgentMap installation, from basic setup to production-ready configuration with multiple providers.

## 📋 Installation Options

### Option 1: Basic Installation
```bash
pip install agentmap
```

### Option 2: Install with Specific Providers
```bash
# All LLM providers at once
pip install agentmap[llm]

# Individual providers
pip install agentmap[anthropic]    # For Claude
pip install agentmap[google]       # For Gemini
pip install agentmap[openai]       # For OpenAI (included by default)
```

### Option 3: Full Installation (All Features)
```bash
pip install agentmap[all]
```

## 🔍 Verify Installation

Run the diagnostic tool to check your installation:

```bash
agentmap diagnose
```

**Expected Output for Successful Installation:**
```
AgentMap Dependency Diagnostics
=============================

LLM Dependencies:
LLM feature enabled: True
  Openai: ✅ Available [Registry: reg=True, val=True, avail=True]
  Anthropic: ✅ Available [Registry: reg=True, val=True, avail=True]
  Google: ✅ Available [Registry: reg=True, val=True, avail=True]

Storage Dependencies:
Storage feature enabled: True
  csv: ✅ Available [Registry: reg=True, val=True, avail=True]
  json: ✅ Available [Registry: reg=True, val=True, avail=True]
  file: ✅ Available [Registry: reg=True, val=True, avail=True]
  vector: ✅ Available [Registry: reg=True, val=True, avail=True]

Environment Information:
  Python Version: 3.11.4
  Current Directory: /path/to/your/project
```

## 🔑 API Key Configuration

### Quick Setup (Environment Variables)

**Choose one or more providers:**

```bash
# OpenAI (recommended for beginners)
export OPENAI_API_KEY="sk-your-openai-key-here"

# Anthropic (Claude)
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-key-here"

# Google (Gemini)
export GOOGLE_API_KEY="your-google-api-key-here"
```

### Persistent Setup (.env file)

Create a `.env` file in your project directory:

```bash
# OpenAI
OPENAI_API_KEY=sk-your-openai-key-here

# Anthropic  
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Google
GOOGLE_API_KEY=your-google-api-key-here

# Optional: LangSmith for monitoring
LANGSMITH_API_KEY=your-langsmith-key-here
LANGCHAIN_PROJECT="your-project-name"
```

### Getting API Keys

| Provider | Get Key From | Documentation |
|----------|-------------|---------------|
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | [OpenAI Docs](https://platform.openai.com/docs) |
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com/) | [Anthropic Docs](https://docs.anthropic.com/) |
| **Google** | [ai.google.dev](https://ai.google.dev/) | [Google AI Docs](https://ai.google.dev/docs) |

## ⚙️ Configuration Files

### Basic Configuration

Create `agentmap_config.yaml`:

```yaml
# Basic configuration
csv_path: "workflows/main.csv"
autocompile: true

# Single LLM provider
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-4-turbo"
    temperature: 0.7
```

### Multi-Provider Configuration

```yaml
# Multi-provider setup with intelligent routing
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
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.7
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-1.5-pro"
    temperature: 0.7

# Intelligent routing
routing:
  enabled: true
  cost_optimization:
    enabled: true
    prefer_cost_effective: true
  routing_matrix:
    anthropic:
      low: "claude-3-haiku-20240307"
      medium: "claude-3-5-sonnet-20241022"
      high: "claude-3-opus-20240229"
    openai:
      low: "gpt-3.5-turbo"
      medium: "gpt-4-turbo"
      high: "gpt-4"
    google:
      low: "gemini-1.5-flash"
      medium: "gemini-1.5-pro"
      high: "gemini-1.5-pro"

# Memory for stateful conversations
memory:
  enabled: true
  default_type: "buffer_window"
  buffer_window_size: 5
```

### Production Configuration

```yaml
# Production-ready configuration
csv_path: "workflows/production.csv"
storage_config_path: "agentmap_storage.yaml"

# Advanced routing with cost optimization
routing:
  enabled: true
  routing_matrix:
    anthropic:
      low: "claude-3-haiku-20240307"
      medium: "claude-3-5-sonnet-20241022"
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

# Execution tracking
execution:
  tracking:
    enabled: true
    track_outputs: true
    track_timing: true

# Performance settings
performance:
  connection_pooling: true
  cache_enabled: true
  max_concurrent_requests: 10
```

## 🗄️ Storage Configuration

Create `agentmap_storage.yaml` for advanced storage backends:

```yaml
# Multi-provider storage configuration
storage:
  # CSV storage (default)
  csv:
    enabled: true
    default_path: "data/"
  
  # JSON storage
  json:
    enabled: true
    default_path: "data/"
  
  # Vector database
  vector:
    enabled: true
    provider: "chromadb"
    config:
      persist_directory: "data/vector_store"
      collection_name: "agentmap_vectors"
  
  # Firebase integration
  firebase:
    enabled: true
    credentials_path: "path/to/firebase-credentials.json"
    database_url: "https://your-project.firebaseio.com"
  
  # Azure Blob Storage
  blob:
    enabled: true
    account_name: "your-storage-account"
    account_key: "env:AZURE_STORAGE_KEY"
    container_name: "agentmap-data"
```

## 🧪 Development Workflow with Scaffolding

AgentMap provides powerful scaffolding for rapid development:

### 1. Design Your Workflow

```csv
graph_name,node_name,agent_type,next_node,context,input_fields,output_field,prompt
SmartBot,start,input,analyze,,,user_query,
SmartBot,analyze,DataAnalyzer,respond,"{""services"": [""llm"", ""storage""]}",user_query,analysis,Analyze this query: {user_query}
SmartBot,respond,ResponseGenerator,end,"{""services"": [""llm""]}",analysis,response,Generate response for: {analysis}
SmartBot,end,echo,,,response,final_output
```

### 2. Generate Agent Code

```bash
# Scaffold agents with automatic service detection
agentmap scaffold --graph SmartBot
```

**Output:**
```
✅ Scaffolded 2 agents/functions.
📊 Service integration: 2 with services, 0 basic agents
📁 Created files:
    data_analyzer_agent.py
    response_generator_agent.py
```

### 3. Generated Agent Example

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

### 4. Test and Deploy

```bash
# Test the workflow
agentmap run --graph SmartBot --state '{"user_query": "What is machine learning?"}'

# Compile for production
agentmap compile --graph SmartBot
```

## 🐛 Troubleshooting

### Common Installation Issues

#### Issue: No LLM providers available
```
LLM Dependencies:
  Openai: ❌ Not available (Missing: langchain_openai)
  Anthropic: ❌ Not available (Missing: langchain_anthropic)
```

**Solution**: Install LLM dependencies
```bash
# Install all providers
pip install agentmap[llm]

# Or install individually
pip install langchain-openai langchain-anthropic langchain-google-genai
```

#### Issue: Features disabled
```
LLM feature enabled: False
```

**Solution**: Check configuration format
```yaml
# agentmap_config.yaml - Ensure boolean values
features:
  llm: true      # Must be boolean, not string "true"
  storage: true
```

#### Issue: API key not working
```bash
# Verify key is set
echo $OPENAI_API_KEY

# Test key directly
python -c "import openai; client = openai.OpenAI(); print('API key works!')"
```

#### Issue: Permission denied
```bash
# Fix permissions
chmod +x $(which agentmap)

# Or reinstall
pip uninstall agentmap
pip install agentmap
```

#### Issue: Module import errors
```bash
# Clean installation
pip uninstall agentmap
pip cache purge
pip install agentmap

# Verify installation
agentmap diagnose
```

### Performance Issues

#### Issue: Slow workflow execution
```yaml
# Add performance optimizations
performance:
  connection_pooling: true
  cache_enabled: true
  max_concurrent_requests: 10
```

#### Issue: Memory usage
```yaml  
# Limit memory usage
memory:
  buffer_window_size: 3  # Reduce from default 5
  
execution:
  tracking:
    track_outputs: false  # Disable if not needed
```

### Network Issues

#### Issue: Connection timeouts
```yaml
# Increase timeouts
llm:
  openai:
    timeout: 60  # Default is 30
    max_retries: 3
```

#### Issue: Rate limiting
```yaml
# Add rate limiting
performance:
  rate_limiting:
    enabled: true
    requests_per_minute: 30
```

## 🔒 Security Best Practices

### API Key Security
- ✅ Use environment variables, never hardcode keys
- ✅ Use `.env` files for local development
- ✅ Add `.env` to `.gitignore`
- ✅ Use secrets management in production
- ❌ Never commit API keys to version control

### File Permissions
```bash
# Secure configuration files
chmod 600 agentmap_config.yaml
chmod 600 agentmap_storage.yaml
chmod 600 .env
```

### Production Security
```yaml
# Production security settings
security:
  jwt_secret: "env:JWT_SECRET_KEY"
  cors_origins: ["https://yourdomain.com"]
  max_request_size: "10MB"
  
logging:
  level: "INFO"  # Don't log sensitive data in DEBUG
  sanitize_secrets: true
```

## 📊 Monitoring and Observability

### LangSmith Integration
```yaml
tracing:
  enabled: true
  mode: "langsmith"
  project: "my-agentmap-project" 
  langsmith_api_key: "env:LANGSMITH_API_KEY"
```

### Custom Logging
```yaml
logging:
  level: INFO
  file_path: "/var/log/agentmap/app.log"
  rotation: daily
  max_files: 7
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Metrics Collection
```yaml
metrics:
  enabled: true
  provider: "prometheus"
  endpoint: "/metrics"
  track_request_duration: true
  track_error_rates: true
```

## 🚀 Deployment Options

### Local Development
```bash
# Run workflows directly
agentmap run --csv workflow.csv --graph MyGraph

# Run as API server
agentmap serve --host 0.0.0.0 --port 8000
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["agentmap", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Deployment
See the [Deployment Guide](/docs/deployment) for comprehensive deployment options including:
- FastAPI integration
- Kubernetes deployment  
- AWS Lambda functions
- Azure Functions
- Google Cloud Run

## 🎓 Next Steps

Now that you have AgentMap fully configured:

- **[Learning Path](/docs/learning/basic-agents)** - Structured tutorials from basic to advanced
- **[Built-in Agents](/docs/agents/built-in-agents)** - Discover all available agent types
- **[Configuration Examples](/docs/configuration/examples)** - Ready-to-use configuration patterns
- **[Deployment Guide](/docs/deployment)** - Deploy to production environments

## 🤝 Getting Help

- **Documentation**: Browse the sidebar for specific guides
- **GitHub Issues**: [Report bugs or request features](https://github.com/jwwelbor/AgentMap/issues)
- **Discussions**: [Join the community](https://github.com/jwwelbor/AgentMap/discussions)
- **Support**: Check the [troubleshooting section](/docs/configuration/troubleshooting) for common issues

---

**Installation complete!** You're ready to build sophisticated AI workflows with AgentMap.
