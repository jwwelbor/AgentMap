---
title: Configuration Overview
sidebar_position: 1
description: Complete configuration guide for AgentMap including YAML structure, environment variables, and deployment scenarios.
keywords: [configuration, YAML, environment variables, deployment, setup]
---

# Configuration Overview

AgentMap provides a sophisticated configuration system that supports multiple deployment scenarios, advanced LLM routing, comprehensive storage backends, and extensive customization options. This guide covers the complete configuration capabilities available in AgentMap.

## 🏗️ Configuration Architecture

AgentMap uses a **hierarchical configuration system** with multiple layers:

1. **Main Configuration File** (`agentmap_config.yaml`) - Core application settings
2. **Storage Configuration File** (`agentmap_config_storage.yaml`) - Storage provider settings  
3. **Environment Variables** - Runtime overrides and sensitive credentials
4. **Default Values** - Built-in fallbacks for all optional settings

## 📋 Quick Configuration Checklist

### Basic Setup (5 minutes)
- [ ] Set up [environment variables](environment-variables) for API keys
- [ ] Create basic [main configuration](main-config) file
- [ ] Configure [storage providers](storage-config) if using external storage

### Production Setup (30 minutes)
- [ ] Configure [LLM routing](main-config#llm-routing-configuration) for cost optimization
- [ ] Set up [authentication](main-config#authentication-configuration) and security
- [ ] Configure [logging and tracing](main-config#logging-and-tracing) for monitoring
- [ ] Review [performance settings](main-config#performance-optimization)

### Advanced Setup (1 hour)
- [ ] Implement [custom paths](main-config#paths-configuration) for agents and functions
- [ ] Configure [memory management](main-config#memory-configuration) for stateful workflows
- [ ] Set up [host application integration](main-config#host-application-configuration)
- [ ] Configure [cost optimization](main-config#cost-optimization) policies

## 🚀 Configuration Capabilities

### Core Features
- **Multiple LLM Providers**: OpenAI, Anthropic, Google with automatic routing
- **Storage Backends**: CSV, JSON, Vector databases, Cloud storage, Firebase
- **Authentication**: JWT, API keys, Supabase integration
- **Environment Overrides**: Complete runtime configuration control

### Advanced Features  
- **Intelligent LLM Routing**: Provider × complexity matrix with cost optimization
- **Multi-Provider Storage**: Seamless switching between local and cloud storage
- **Memory Management**: Multiple buffer types with configurable policies
- **Execution Tracking**: Comprehensive workflow monitoring and success policies
- **Performance Optimization**: Caching, cost controls, and resource management

### Enterprise Features
- **Service Discovery**: Host application protocol integration
- **Tracing & Monitoring**: LangSmith integration with local export options
- **Security**: Comprehensive authentication and authorization system
- **Scalability**: Configuration for high-throughput production deployments

## 📚 Configuration Guide Structure

### [Main Configuration](main-config)
Complete YAML structure covering all core AgentMap settings including LLM providers, routing, memory, execution, and performance optimization.

### [Storage Configuration](storage-config)  
Comprehensive guide to storage providers including CSV, JSON, Vector databases, Firebase, and cloud storage with authentication and optimization settings.

### [Environment Variables](environment-variables)
Complete reference of environment variables for API keys, storage credentials, system overrides, and security settings.

### [Configuration Examples](examples)
Working configuration examples for different deployment scenarios including local development, production, and cloud integration.

### [Troubleshooting](troubleshooting)
Common configuration issues, validation errors, and debugging guidance with solutions.

## 🎯 Configuration by Use Case

### Local Development
```yaml
# Minimal configuration for getting started
csv_path: "examples/HelloWorld.csv"
autocompile: true
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-3.5-turbo"
```

### Production Deployment
```yaml
# Production-ready configuration with routing and optimization
csv_path: "workflows/production.csv"
autocompile: true
storage_config_path: "agentmap_config_storage.yaml"

routing:
  enabled: true
  cost_optimization:
    enabled: true
    prefer_cost_effective: true
    max_cost_tier: "high"

logging:
  file_path: "/var/log/agentmap/app.log"
  
tracing:
  enabled: true
  mode: "langsmith"
  project: "production-workflows"
```

### Multi-Cloud Integration
```yaml
# Advanced configuration with multiple cloud providers
storage_config_path: "agentmap_cloud_storage.yaml"

llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"

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
```

## 🔧 Configuration Validation

AgentMap uses **Pydantic models** for configuration validation, ensuring:

- ✅ **Type Safety**: All configuration values are properly typed and validated
- ✅ **Required Fields**: Missing required configuration triggers clear error messages  
- ✅ **Default Values**: Sensible defaults for all optional configuration
- ✅ **Range Validation**: Numeric values are validated against acceptable ranges
- ✅ **Enum Validation**: String values are validated against allowed options

### Validation Example
```python
# Configuration is automatically validated on startup
from agentmap.services.config import AppConfigService

config_service = AppConfigService("agentmap_config.yaml")
# ✅ Validates all configuration against Pydantic models
# ❌ Raises clear errors for invalid configuration
```

## 🚨 Security Best Practices

### Environment Variable Usage
- **Never** put sensitive credentials directly in YAML files
- **Always** use `env:VARIABLE_NAME` syntax for API keys and secrets
- **Use** separate environment files for different deployment stages

### File Permissions
```bash
# Secure configuration file permissions
chmod 600 agentmap_config.yaml
chmod 600 agentmap_config_storage.yaml
chmod 600 .env
```

### Production Security
- Use dedicated service accounts for cloud storage access
- Implement proper authentication and authorization policies  
- Enable tracing and monitoring for security auditing
- Regular rotation of API keys and access credentials

## 📈 Performance Configuration

### Cost Optimization
- Enable intelligent routing to use cost-effective models when appropriate
- Configure cost tier limits to prevent unexpected expenses
- Use caching to reduce redundant API calls

### Resource Management
- Configure memory buffers based on workflow complexity
- Set appropriate timeout and retry policies
- Enable performance tracing for optimization

### Scalability Settings
- Configure connection pooling for storage providers
- Set appropriate concurrency limits
- Enable request batching where supported

## 🔄 Configuration Updates

### Hot Reloading
Some configuration changes can be applied without restart:
- Environment variable changes
- Routing policy adjustments  
- Logging level modifications

### Restart Required
Other changes require application restart:
- Storage provider configuration
- Authentication settings
- Core path modifications

## 📖 Next Steps

1. **Start with [Main Configuration](main-config)** - Understand the complete YAML structure
2. **Configure [Storage](storage-config)** - Set up your data persistence layer
3. **Set [Environment Variables](environment-variables)** - Secure your credentials
4. **Review [Examples](examples)** - See working configurations for your use case
5. **Check [Troubleshooting](troubleshooting)** - Resolve common configuration issues

Ready to configure AgentMap for your specific needs? Choose the section that matches your current requirements and follow the detailed guides.
