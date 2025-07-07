---
sidebar_position: 8
title: Configuration Reference
description: Complete configuration options for AgentMap deployment including agent settings, API keys, environment variables, and production configurations.
keywords: [deployment configuration, production config, environment variables, API configuration, security settings]
---

# Configuration Reference

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>Configuration</strong></span>
</div>

AgentMap offers flexible configuration options to customize agent behavior, API integrations, and system settings for different deployment environments. This guide covers all available configuration parameters for development, staging, and production deployments.

## Environment Variables

### Core Settings

```bash
# API Configuration
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key

# AgentMap Settings
AGENTMAP_LOG_LEVEL=INFO
AGENTMAP_MAX_RETRIES=3
AGENTMAP_TIMEOUT=30

# Storage Configuration
AGENTMAP_STORAGE_PATH=./data
AGENTMAP_TEMP_PATH=./temp
```

### Database Configuration

```bash
# Vector Database
VECTOR_DB_URL=your_vector_db_url
VECTOR_DB_API_KEY=your_vector_db_key

# Traditional Database
DATABASE_URL=postgresql://user:password@localhost:5432/agentmap
REDIS_URL=redis://localhost:6379
```

## Agent Configuration

### Default Agent Settings

```json
{
  "default_agent_config": {
    "temperature": 0.7,
    "max_tokens": 1000,
    "timeout": 30,
    "retry_attempts": 3,
    "model": "gpt-3.5-turbo"
  }
}
```

### LLM Agent Configuration

```csv
Context
"{'temperature': 0.7, 'model': 'gpt-4', 'max_tokens': 500, 'top_p': 0.9}"
```

**Available Parameters:**
- `temperature`: Controls randomness (0.0-2.0)
- `model`: LLM model to use
- `max_tokens`: Maximum response length
- `top_p`: Nucleus sampling parameter
- `frequency_penalty`: Reduces repetition
- `presence_penalty`: Encourages topic diversity

### File Agent Configuration

```csv
Context
"{'encoding': 'utf-8', 'mode': 'read', 'chunk_size': 1000}"
```

**Available Parameters:**
- `encoding`: File encoding (utf-8, ascii, etc.)
- `mode`: File operation mode (read, write, append)
- `chunk_size`: Size for chunked reading
- `should_split`: Split large files into chunks

### CSV Agent Configuration

```csv
Context
"{'format': 'records', 'delimiter': ',', 'id_field': 'id'}"
```

**Available Parameters:**
- `format`: Output format (records, dict, list)
- `delimiter`: CSV delimiter character
- `id_field`: Primary key field name
- `encoding`: File encoding

## System Configuration

### Logging Configuration

```python
# logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'agentmap.log',
        },
    },
    'loggers': {
        'agentmap': {
            'handlers': ['default', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}
```

### Performance Configuration

```python
# performance_config.py
PERFORMANCE_CONFIG = {
    'max_concurrent_agents': 10,
    'agent_timeout': 30,
    'memory_limit_mb': 512,
    'enable_caching': True,
    'cache_ttl_seconds': 3600,
    'enable_metrics': True,
    'metrics_port': 8080
}
```

## Advanced Configuration

### Custom Agent Registration

```python
from agentmap import AgentMap, Agent

# Register custom agent type
class CustomAgent(Agent):
    def execute(self, input_data):
        # Custom implementation
        return processed_data

# Register with AgentMap
agent_map = AgentMap()
agent_map.register_agent_type('custom', CustomAgent)
```

### Service Injection Configuration

```python
# services_config.py
SERVICES_CONFIG = {
    'database': {
        'type': 'postgresql',
        'url': 'postgresql://localhost:5432/agentmap',
        'pool_size': 10
    },
    'cache': {
        'type': 'redis',
        'url': 'redis://localhost:6379',
        'ttl': 3600
    },
    'messaging': {
        'type': 'rabbitmq',
        'url': 'amqp://localhost:5672',
        'exchange': 'agentmap'
    }
}
```

### Security Configuration

```python
# security_config.py
SECURITY_CONFIG = {
    'api_key_encryption': True,
    'secure_temp_files': True,
    'input_validation': True,
    'output_sanitization': True,
    'allowed_file_types': ['.csv', '.json', '.txt', '.md'],
    'max_file_size_mb': 100,
    'enable_audit_logging': True
}
```

## Configuration Files

### agentmap.config.json

```json
{
  "version": "1.0",
  "agents": {
    "default_timeout": 30,
    "max_retries": 3,
    "enable_parallel_execution": true
  },
  "storage": {
    "temp_directory": "./temp",
    "output_directory": "./output",
    "auto_cleanup": true
  },
  "logging": {
    "level": "INFO",
    "file": "agentmap.log",
    "rotate": true
  },
  "performance": {
    "memory_limit": "1GB",
    "cpu_limit": "80%"
  }
}
```

### Environment-Specific Configs

```bash
# development.env
AGENTMAP_ENV=development
AGENTMAP_DEBUG=true
AGENTMAP_LOG_LEVEL=DEBUG

# production.env
AGENTMAP_ENV=production
AGENTMAP_DEBUG=false
AGENTMAP_LOG_LEVEL=INFO
AGENTMAP_ENABLE_METRICS=true
```

## Configuration Loading

### Python API

```python
from agentmap import AgentMap

# Load from file
agent_map = AgentMap(config_file='agentmap.config.json')

# Load from environment
agent_map = AgentMap.from_env()

# Custom configuration
config = {
    'agents': {'default_timeout': 60},
    'logging': {'level': 'DEBUG'}
}
agent_map = AgentMap(config=config)
```

### CLI Configuration

```bash
# Use specific config file
agentmap run --config production.config.json workflow.csv

# Override specific settings
agentmap run --timeout 60 --log-level DEBUG workflow.csv

# Environment-based loading
AGENTMAP_CONFIG=production.config.json agentmap run workflow.csv
```

## Validation and Debugging

### Configuration Validation

```python
from agentmap.config import validate_config

# Validate configuration
config = load_config('agentmap.config.json')
is_valid, errors = validate_config(config)

if not is_valid:
    print("Configuration errors:", errors)
```

### Debug Configuration

```bash
# Show current configuration
agentmap config show

# Validate configuration file
agentmap config validate agentmap.config.json

# Test configuration
agentmap config test --dry-run
```

## Best Practices

### 1. Environment Separation
- Use different config files for development/staging/production
- Store sensitive data in environment variables
- Never commit API keys to version control

### 2. Performance Optimization
- Adjust agent timeout based on your use case
- Enable caching for repeated operations
- Monitor memory usage and adjust limits

### 3. Security
- Encrypt sensitive configuration data
- Use secure file permissions for config files
- Regularly rotate API keys

### 4. Monitoring
- Enable comprehensive logging in production
- Set up metrics collection
- Configure alerting for configuration errors

## Troubleshooting

### Common Issues

**Configuration Not Found**
```bash
Error: Configuration file not found: agentmap.config.json
Solution: Ensure file exists and path is correct
```

**Invalid API Key**
```bash
Error: Invalid OpenAI API key
Solution: Verify API key in environment variables
```

**Memory Limit Exceeded**
```bash
Error: Agent execution exceeded memory limit
Solution: Increase memory_limit in configuration
```

### Configuration Debugging

```python
# Enable configuration debugging
import logging
logging.getLogger('agentmap.config').setLevel(logging.DEBUG)

# Print effective configuration
from agentmap import AgentMap
agent_map = AgentMap()
print(agent_map.get_effective_config())
```

## Migration Guide

### Upgrading Configuration

When upgrading AgentMap versions, configuration files may need updates:

```python
from agentmap.config import migrate_config

# Migrate old config to new format
old_config = load_config('old_config.json')
new_config = migrate_config(old_config, target_version='2.0')
save_config(new_config, 'agentmap.config.json')
```

For detailed configuration examples and use cases, see the [Agent Development Guide](/docs/guides/development/agents/agent-development), [CLI Deployment Guide](./cli-deployment), [FastAPI Deployment Guide](./fastapi-standalone), and [Service Injection Patterns](/docs/contributing/service-injection).
