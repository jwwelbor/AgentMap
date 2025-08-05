---
sidebar_position: 10
title: Config Validation Guide  
description: Complete guide to YAML configuration validation including schema validation, path checks, and LLM provider configuration
keywords: [config validation, YAML validation, schema validation, LLM configuration, environment variables]
---

# Config Validation Guide

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <a href="/docs/guides/development">Development</a> → <strong>Config Validation</strong></span>
</div>

The configuration validation system ensures your YAML configuration files are properly structured, contain valid settings, and reference accessible resources. This comprehensive guide covers all aspects of configuration validation from schema validation to environment setup.

## Validation Overview

Configuration validation operates at multiple levels to ensure complete system integrity:

1. **YAML Structure**: Valid YAML syntax and root-level organization
2. **Schema Validation**: Pydantic model validation for type safety
3. **Path Validation**: File and directory existence verification
4. **LLM Configuration**: Provider setup and API key validation
5. **Cross-Reference**: Inter-section dependency validation
6. **Environment**: System variable and dependency checks

## YAML Structure Validation

### Basic Format Requirements

Configuration files must be valid YAML dictionaries:

```yaml
# ✅ Valid: Dictionary at root level
paths:
  custom_agents: "./custom_agents"
llm:
  openai:
    api_key: "your_api_key"

# ❌ Invalid: List at root level  
- paths:
    custom_agents: "./custom_agents"
- llm:
    openai:
      api_key: "your_api_key"
```

### Section Organization

The validator recognizes these standard configuration sections:

- **`paths`**: Directory and file path configurations
- **`llm`**: LLM provider settings and API keys
- **`memory`**: Memory and conversation management
- **`prompts`**: Prompt template configuration  
- **`execution`**: Execution policies and behavior
- **`tracing`**: Monitoring and debugging setup

### Common Typo Detection

The system provides helpful suggestions for common section name typos:

```yaml
# Common typos and suggestions
path: "..."          # ⚠️ Did you mean 'paths'?
llms: "..."          # ⚠️ Did you mean 'llm'?  
memories: "..."      # ⚠️ Did you mean 'memory'?
prompt: "..."        # ⚠️ Did you mean 'prompts'?
exec: "..."          # ⚠️ Did you mean 'execution'?
trace: "..."         # ⚠️ Did you mean 'tracing'?
```

## Schema Validation

### Pydantic Model Validation

All configuration sections are validated against Pydantic models for type safety:

```yaml
# ✅ Valid configuration
execution:
  timeout_seconds: 300        # Valid: integer
  retry_attempts: 3           # Valid: integer  
  parallel_execution: true    # Valid: boolean

# ❌ Invalid configuration  
execution:
  timeout_seconds: "five"     # ❌ Error: Expected integer, got string
  retry_attempts: 3.5         # ❌ Error: Expected integer, got float
  parallel_execution: "yes"   # ❌ Error: Expected boolean, got string
```

### Field Validation Examples

**String Fields**
```yaml
# Valid string configurations
prompts:
  directory: "./prompts"              # ✅ Valid path string
  template_prefix: "agentmap_"        # ✅ Valid prefix string

# Invalid string configurations
prompts:
  directory: 123                      # ❌ Error: Expected string, got integer
```

**Boolean Fields**
```yaml
# Valid boolean configurations  
tracing:
  enabled: true                       # ✅ Valid boolean
  debug_mode: false                   # ✅ Valid boolean

# Invalid boolean configurations
tracing:
  enabled: "true"                     # ❌ Error: Expected boolean, got string
  debug_mode: 1                       # ❌ Error: Expected boolean, got integer
```

**Nested Object Validation**
```yaml
# Valid nested configuration
llm:
  openai:
    api_key: "sk-..."                 # ✅ Valid string
    model: "gpt-4"                    # ✅ Valid model name
    temperature: 0.7                  # ✅ Valid float

# Invalid nested configuration
llm:
  openai:
    api_key: 123                      # ❌ Error: Expected string, got integer
    temperature: "medium"             # ❌ Error: Expected number, got string
```

## Path Validation

### File Path Validation

The system validates paths for existence and accessibility:

```yaml
# CSV file validation
csv_path: "./workflows/main.csv"

# Validation checks:
# ✅ File exists and is readable
# ⚠️ Warning: File doesn't exist (will be created)
# ❌ Error: Path exists but is a directory, not a file
# ⚠️ Warning: Path doesn't have .csv extension
```

### Directory Path Validation

Directory paths are validated for existence and permissions:

```yaml
paths:
  custom_agents: "./custom_agents"        # ✅ Directory exists
  functions: "./functions"                # ℹ️ Directory will be created
  compiled_graphs: "/invalid/path"       # ⚠️ Parent directory doesn't exist

# Validation behavior:
# - Existing directories: ✅ Valid
# - Non-existing with valid parent: ℹ️ Info (will be created)
# - Invalid parent directory: ⚠️ Warning
# - Path exists but is a file: ❌ Error
```

### Storage Configuration Paths

Storage configuration paths receive special handling:

```yaml
storage_config_path: "./storage_config.yaml"

# Validation logic:
# - File exists: ✅ Valid, will be loaded
# - File doesn't exist: ℹ️ Info (will be created when needed)  
# - Path is directory: ❌ Error
# - Parent doesn't exist: ⚠️ Warning
```

### Prompts Directory Validation

Prompts-related paths are validated for accessibility:

```yaml
prompts:
  directory: "./prompts"                  # ℹ️ Will be created if needed
  registry_file: "./prompt_registry.yaml" # ℹ️ Will be created if needed

# Validation checks:
# - Valid parent directory required
# - Write permissions verified
# - File extension consistency checked
```

## LLM Provider Configuration

### Supported Providers

The system validates configuration for major LLM providers:

- **OpenAI**: GPT models and API configuration
- **Anthropic**: Claude models and API setup  
- **Google**: Gemini models and authentication

### API Key Validation

API keys are validated for format and presence:

```yaml
llm:
  openai:
    api_key: "sk-proj-..."              # ✅ Valid format and length
    
  anthropic:  
    api_key: "sk-ant-..."               # ✅ Valid format
    
  google:
    api_key: "AIza..."                  # ✅ Valid format

# Common issues:
llm:
  openai:
    api_key: "your_api_key"             # ❌ Error: Placeholder value detected
    api_key: "sk-123"                   # ⚠️ Warning: API key seems too short
```

### Environment Variable Integration

The system checks for API keys in environment variables:

```yaml
# No API key in config file
llm:
  openai:
    model: "gpt-4"
    # api_key not specified

# Validation checks:
# ✅ Info: OpenAI API key found in OPENAI_API_KEY environment variable
# ⚠️ Warning: No API key configured for openai (check OPENAI_API_KEY)
```

**Environment Variable Mapping**:
- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`  
- Google: `GOOGLE_API_KEY`

### Model Name Validation

The system provides guidance on model names:

```yaml
llm:
  openai:
    model: "gpt-4"                      # ✅ Known model
    model: "gpt-4-custom-fine-tune"     # ℹ️ Non-standard model noted

# Known models by provider:
# OpenAI: gpt-3.5-turbo, gpt-4, gpt-4-turbo-preview, gpt-4o
# Anthropic: claude-3-5-sonnet-20241022, claude-3-opus-20240229, claude-3-haiku-20240307  
# Google: gemini-1.0-pro, gemini-1.5-pro-latest, gemini-pro
```

### Temperature Validation

Temperature settings are validated for reasonable ranges:

```yaml
llm:
  openai:
    temperature: 0.7                    # ✅ Valid range (0-2)
    temperature: 2.5                    # ⚠️ Warning: Outside typical range 0-2
    temperature: "medium"               # ❌ Error: Must be a number
```

## Cross-Reference Validation

### Tracing Configuration

When tracing is enabled, the system validates dependent configurations:

```yaml
tracing:
  enabled: true
  mode: "langsmith"
  project: "my_project"
  langsmith_api_key: "ls_..."

# Validation checks:
# ✅ Valid: All required fields present
# ⚠️ Warning: API key not found (check LANGCHAIN_API_KEY environment variable)
# ⚠️ Warning: Project name appears to be placeholder
```

**LangSmith Mode Validation**:
```yaml
tracing:
  enabled: true
  mode: "langsmith"
  project: "your_project_name"          # ⚠️ Warning: Placeholder detected
  langsmith_api_key: ""                 # ⚠️ Warning: Check LANGCHAIN_API_KEY env var
```

**Local Mode Validation**:
```yaml
tracing:
  enabled: true  
  mode: "local"
  local_directory: "./traces"           # ℹ️ Directory will be created
  local_directory: "/invalid/path"      # ⚠️ Warning: Parent directory doesn't exist
```

### Execution Policy Validation

Execution policies are validated for completeness:

```yaml
execution:
  success_policy:
    type: "critical_nodes"
    critical_nodes: []                  # ⚠️ Warning: No critical nodes specified

execution:
  success_policy:
    type: "custom"
    custom_function: ""                 # ❌ Error: Custom function not specified
```

**Policy Type Validation**:
- **`all_nodes`**: No additional configuration required
- **`critical_nodes`**: Requires non-empty critical_nodes list
- **`custom`**: Requires custom_function specification

## Validation Output Examples

### Successful Validation

```bash
🔍 Validating configuration file: agentmap_config.yaml
✅ Configuration file format is valid
ℹ️ Found 4 configuration sections: paths, llm, execution, tracing
✅ Configuration schema validation passed
ℹ️ Custom agents directory will be created: ./custom_agents
ℹ️ OpenAI API key found in environment variable OPENAI_API_KEY
ℹ️ LLM providers configured: openai, anthropic
✅ Validation completed successfully
```

### Validation with Warnings

```bash
🔍 Validating configuration file: agentmap_config.yaml
✅ Configuration file format is valid
ℹ️ Found 3 configuration sections: paths, llm, tracing

⚠️ Config Validation Warnings:
  1. No API key configured for anthropic
     Field: llm.anthropic.api_key
     Suggestion: Set api_key in config or ANTHROPIC_API_KEY environment variable
  2. Tracing enabled but project name not configured  
     Field: tracing.project
     Suggestion: Set a meaningful project name for tracing
     
ℹ️ Validation complete with 0 errors and 2 warnings
```

### Validation with Errors

```bash
🔍 Validating configuration file: agentmap_config.yaml

❌ Config Validation Errors:
  1. Schema validation error: Expected boolean, got string
     Field: execution.parallel_execution
     Value: "true"
  2. CSV path is not a file: ./workflows/
     Field: csv_path
  3. OpenAI API key appears to be a placeholder
     Field: llm.openai.api_key, Value: your_api_key_here
     Suggestion: Replace with your actual API key
```

## Common Configuration Errors

### Schema Validation Errors

**Type Mismatches**
```yaml
# ❌ String where boolean expected
execution:
  parallel_execution: "true"            # Should be: true

# ❌ String where number expected  
llm:
  openai:
    temperature: "0.7"                  # Should be: 0.7

# ❌ Number where string expected
paths:
  custom_agents: 123                    # Should be: "./custom_agents"
```

### Path Configuration Errors

**Invalid Path References**
```yaml
# ❌ Directory specified for file path
csv_path: "./workflows/"                # Should be: "./workflows/main.csv"

# ❌ Non-existent parent directory
paths:
  custom_agents: "/nonexistent/agents"  # Parent /nonexistent/ doesn't exist
```

### LLM Configuration Errors

**API Key Issues**
```yaml
llm:
  openai:
    api_key: "your_api_key"             # ❌ Placeholder value
    api_key: "sk-123"                   # ⚠️ Too short
    api_key: ""                         # ⚠️ Empty (check environment)
```

**Model Configuration Issues**
```yaml
llm:
  openai:
    model: 123                          # ❌ Should be string
    temperature: "hot"                  # ❌ Should be number
```

## Best Practices

### Configuration Organization

1. **Logical Grouping**: Group related settings in appropriate sections
2. **Environment Variables**: Use environment variables for sensitive data
3. **Default Values**: Rely on system defaults for optional settings
4. **Documentation**: Comment complex configurations

### Development Environment

1. **Local Configuration**: Keep local config separate from version control
2. **Environment-Specific**: Use different configs for dev/staging/production
3. **Validation First**: Always validate before deployment
4. **Secret Management**: Never commit API keys to version control

### Production Deployment

1. **Complete Validation**: Run full validation before deployment
2. **Environment Variables**: Use environment variables for production secrets
3. **Path Verification**: Ensure all paths are accessible in production environment
4. **Monitoring Setup**: Configure tracing for production monitoring

## Advanced Configuration

### Multiple LLM Providers

```yaml
llm:
  openai:
    api_key: "sk-..."
    model: "gpt-4"
    temperature: 0.7
  anthropic:
    api_key: "sk-ant-..."  
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.5
  google:
    api_key: "AIza..."
    model: "gemini-1.5-pro-latest"
```

### Custom Path Configuration

```yaml
paths:
  custom_agents: "./agents"
  functions: "./functions"  
  compiled_graphs: "./build/graphs"
  logs: "./logs"
  cache: "./cache"
```

### Advanced Execution Policies

```yaml
execution:
  timeout_seconds: 300
  retry_attempts: 3
  success_policy:
    type: "critical_nodes"
    critical_nodes: ["validation", "approval", "finalization"]
  failure_policy:
    type: "custom"
    custom_function: "handle_workflow_failure"
```

### Comprehensive Tracing Setup

```yaml
tracing:
  enabled: true
  mode: "langsmith"
  project: "production_agentmap"
  langsmith_api_key: "ls_..."
  tags: ["production", "v2.1"]
  metadata:
    environment: "prod"
    version: "2.1.0"
```

## Related Documentation

- **[Validation System Overview](./validation)**: Complete validation system architecture
- **[Configuration Reference](/docs/reference/configuration)**: Complete configuration options
- **[Environment Variables](/docs/reference/configuration/environment-variables)**: Environment setup guide
- **[CLI Validation Commands](/docs/deployment/08-cli-validation)**: Command-line validation tools
- **[LLM Service Configuration](/docs/reference/services/llm-service)**: LLM provider setup details

## Next Steps

1. **Validate Your Config**: Run `agentmap validate config --config your_config.yaml`
2. **Fix Configuration Issues**: Address errors and warnings systematically
3. **Set Up Environment**: Configure environment variables for production
4. **Complete Validation**: Use [validation cache](./validation-cache) for optimal performance
