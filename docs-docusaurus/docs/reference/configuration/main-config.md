---
title: Main Configuration
sidebar_position: 2
description: Complete YAML configuration reference for AgentMap core settings including LLM providers, routing, memory, and execution policies.
keywords: [YAML configuration, LLM providers, routing, memory management, execution policies]
---

# Main Configuration

The main configuration file (`agentmap_config.yaml`) contains all core AgentMap settings including LLM providers, intelligent routing, memory management, execution policies, and performance optimization. This guide covers every configuration option with examples and best practices.

## 📁 Configuration File Loading

AgentMap uses **automatic configuration discovery** with the following precedence order:

### 1. Explicit `--config` flag (Highest Priority)
```bash
agentmap run --config /path/to/custom_config.yaml
```
Explicitly specified config files take absolute precedence.

### 2. `agentmap_config.yaml` in current directory (Auto-Discovered)
```bash
# Place agentmap_config.yaml in your working directory
cd /your/project
agentmap run  # Automatically discovers and uses ./agentmap_config.yaml
```
If no explicit config is provided, AgentMap automatically checks for `agentmap_config.yaml` in the current working directory.

### 3. System defaults (Lowest Priority)
```bash
# If no config file found, uses built-in defaults
agentmap run
```
When no config file is found, AgentMap uses sensible system defaults.

### Configuration Discovery Logging
AgentMap always logs which configuration source is being used:
```
[2024-08-06 10:30:15] INFO: Using configuration from: auto-discovered: /project/agentmap_config.yaml
```

### Quick Setup
1. **Initialize config template**:
   ```bash
   agentmap init-config
   ```

2. **Edit the generated `agentmap_config.yaml`**

3. **Run commands without `--config` flag**:
   ```bash
   agentmap run --csv examples/lesson1.csv
   ```

## 📋 Complete Configuration Structure

```yaml
# Core configuration
csv_path: "examples/SingleNodeGraph.csv"
autocompile: true
storage_config_path: "agentmap_config_storage.yaml"

# Directory paths
paths:
  custom_agents: "agentmap/custom_agents"
  functions: "agentmap/custom_functions"
  compiled_graphs: "agentmap/compiled_graphs"
  csv_repository: "workflows"

# LLM configuration with multiple providers
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
    model: "gemini-1.0-pro"
    temperature: 0.7

# Intelligent routing system
routing:
  enabled: true
  routing_matrix:
    # Provider × Complexity matrix
  task_types:
    # Application-specific task definitions
  complexity_analysis:
    # Automatic complexity detection
  cost_optimization:
    # Cost management settings
  fallback:
    # Error handling and defaults

# Memory configuration
memory:
  enabled: false
  default_type: "buffer"
  buffer_window_size: 5
  max_token_limit: 2000
  memory_key: "conversation_memory"

# Execution tracking and success policies
execution:
  tracking:
    enabled: true
    track_outputs: true
    track_inputs: true
  success_policy:
    type: "all_nodes"
    critical_nodes: []
    custom_function: ""

# Tracing and debugging
tracing:
  enabled: false
  mode: "local"
  project: "your_project_name"
  langsmith_api_key: "env:LANGSMITH_API_KEY"

# Logging configuration
logging:
  version: 1
  file_path: null
  formatters:
    # Custom formatters
  handlers:
    # Log handlers
  root:
    level: INFO
    handlers: [console]

# Environment variable overrides
environment_overrides:
  routing_enabled: ${AGENTMAP_ROUTING_ENABLED:true}
  default_task_type: ${AGENTMAP_DEFAULT_TASK_TYPE:general}
```

## 🔧 Core Configuration

### Basic Settings

```yaml
# Required: Path to your main workflow CSV file
csv_path: "examples/SingleNodeGraph.csv"

# Optional: Automatically compile graphs on startup (default: true)
autocompile: true

# Optional: Path to storage configuration file (default: "storage_config.yaml")
storage_config_path: "agentmap_config_storage.yaml"
```

**Configuration Details:**
- `csv_path`: Must end with `.csv` extension, validated by Pydantic
- `autocompile`: Enables automatic workflow compilation for faster execution
- `storage_config_path`: Separate file for storage provider configurations

## 📁 Paths Configuration

```yaml
paths:
  # Directory for custom agent implementations
  custom_agents: "agentmap/custom_agents"
  
  # Directory for custom function implementations  
  functions: "agentmap/custom_functions"
  
  # Directory for compiled workflow graphs (performance optimization)
  compiled_graphs: "agentmap/compiled_graphs"
  
  # Repository directory for storing workflow CSV files
  csv_repository: "workflows"
```

**Path Configuration Best Practices:**
- Use relative paths for portability across environments
- Ensure directories exist or AgentMap will create them automatically
- Consider using environment-specific paths for different deployments

## 🤖 LLM Provider Configuration

### Multi-Provider Setup

```yaml
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"    # Environment variable reference
    model: "gpt-3.5-turbo"           # Default model
    temperature: 0.7                 # Creativity parameter (0.0-2.0)
    
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.7
    
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-1.0-pro"
    temperature: 0.7
```

### Provider-Specific Models

**OpenAI Models:**
- `gpt-3.5-turbo` - Fast, cost-effective for simple tasks
- `gpt-4-turbo` - Balanced performance and capabilities
- `gpt-4` - Highest capability for complex reasoning

**Anthropic Models:**
- `claude-3-haiku-20240307` - Ultra-fast, cost-effective
- `claude-3-5-sonnet-20241022` - Balanced performance
- `claude-3-opus-20240229` - Highest capability

**Google Models:**
- `gemini-1.0-pro` - General purpose model
- `gemini-1.5-pro` - Enhanced capabilities

### Temperature Settings

```yaml
temperature: 0.0    # Deterministic, focused responses
temperature: 0.7    # Balanced creativity and coherence (recommended)
temperature: 1.0    # More creative, varied responses
temperature: 2.0    # Maximum creativity (use carefully)
```

## 🎯 LLM Routing Configuration

AgentMap's intelligent routing system automatically selects the optimal LLM provider and model based on task complexity, cost optimization, and performance requirements.

### Routing Matrix

```yaml
routing:
  enabled: true
  
  # Core routing table: (provider, complexity) → model
  routing_matrix:
    anthropic:
      low: "claude-3-haiku-20240307"
      medium: "claude-3-5-sonnet-20241022"
      high: "claude-3-opus-20240229"
      critical: "claude-3-opus-20240229"
    
    openai:
      low: "gpt-3.5-turbo"
      medium: "gpt-4-turbo"
      high: "gpt-4"
      critical: "gpt-4"
    
    google:
      low: "gemini-1.0-pro"
      medium: "gemini-1.0-pro"
      high: "gemini-1.5-pro"
      critical: "gemini-1.5-pro"
```

### Task Types

Define application-specific task categories with routing preferences:

```yaml
routing:
  task_types:
    # General purpose tasks
    general:
      description: "General purpose tasks"
      provider_preference: ["anthropic", "openai", "google"]
      default_complexity: "medium"
      complexity_keywords:
        high: ["analyze", "complex", "detailed", "comprehensive"]
        critical: ["urgent", "critical", "important", "decision"]
    
    # Creative content generation
    creative_writing:
      description: "Creative content generation and storytelling"
      provider_preference: ["anthropic", "openai"]
      default_complexity: "high"
      complexity_keywords:
        medium: ["write", "create", "story"]
        high: ["creative", "narrative", "imaginative", "artistic"]
        critical: ["masterpiece", "publication", "professional"]
    
    # Technical analysis and coding
    code_analysis:
      description: "Code review, analysis, and technical documentation"
      provider_preference: ["openai", "anthropic"]
      default_complexity: "medium"
      complexity_keywords:
        low: ["simple", "basic", "review"]
        medium: ["analyze", "refactor", "optimize"]
        high: ["architecture", "design", "complex algorithm"]
        critical: ["security", "production", "critical bug"]
    
    # Customer service interactions
    customer_service:
      description: "Customer service interactions and support"
      provider_preference: ["anthropic", "openai"]
      default_complexity: "medium"
      complexity_keywords:
        low: ["greeting", "simple question", "faq"]
        medium: ["support", "help", "issue"]
        high: ["complaint", "escalation", "complex problem"]
        critical: ["urgent", "emergency", "executive"]
    
    # Data analysis and insights
    data_analysis:
      description: "Data processing, analysis, and insights"
      provider_preference: ["openai", "google", "anthropic"]
      default_complexity: "medium"
      complexity_keywords:
        low: ["simple", "summary", "basic stats"]
        medium: ["analyze", "trends", "patterns"]
        high: ["deep analysis", "insights", "correlations"]
        critical: ["predictive", "strategic", "business critical"]
```

### Complexity Analysis

Automatic complexity detection based on multiple factors:

```yaml
routing:
  complexity_analysis:
    # Prompt length thresholds (characters)
    prompt_length_thresholds:
      low: 100      # < 100 chars = low complexity
      medium: 300   # 100-300 chars = medium complexity
      high: 800     # 300-800 chars = high complexity
      # > 800 chars = critical complexity
    
    # Enable different analysis methods
    methods:
      prompt_length: true
      keyword_analysis: true
      context_analysis: true
      memory_analysis: true
    
    # Keyword weighting for complexity calculation
    keyword_weights:
      complexity_keywords: 0.4
      task_specific_keywords: 0.3
      prompt_structure: 0.3
    
    # Context analysis settings
    context_analysis:
      memory_size_threshold: 10
      input_field_count_threshold: 5
```

### Cost Optimization

```yaml
routing:
  cost_optimization:
    enabled: true
    # Prefer cheaper models when complexity allows
    prefer_cost_effective: true
    # Maximum cost tier (low, medium, high, critical)
    max_cost_tier: "high"
```

### Fallback Configuration

```yaml
routing:
  fallback:
    # Default provider when preferences unavailable
    default_provider: "anthropic"
    # Default model when routing fails
    default_model: "claude-3-haiku-20240307"
    # Retry with lower complexity if model unavailable
    retry_with_lower_complexity: true
```

### Performance Settings

```yaml
routing:
  performance:
    # Cache routing decisions for identical inputs
    enable_routing_cache: true
    # Cache TTL in seconds
    cache_ttl: 300
    # Maximum cache size
    max_cache_size: 1000
```

## 🧠 Memory Configuration

Configure conversation memory for stateful workflows:

```yaml
memory:
  # Enable/disable memory functionality
  enabled: false
  
  # Memory type: "buffer", "buffer_window", "summary", "token_buffer"
  default_type: "buffer"
  
  # Number of previous messages to remember (buffer_window type)
  buffer_window_size: 5
  
  # Maximum tokens before summarization (token_buffer type)
  max_token_limit: 2000
  
  # Key name for memory in workflow state
  memory_key: "conversation_memory"
```

### Memory Types

**Buffer Memory:**
- Stores all conversation history
- Best for: Short conversations, complete context needed

**Buffer Window Memory:**
- Stores last N messages
- Best for: Ongoing conversations, limited context

**Summary Memory:**
- Automatically summarizes old messages
- Best for: Long conversations, key information retention

**Token Buffer Memory:**
- Manages memory based on token count
- Best for: Cost-sensitive applications, token limits

## ⚙️ Execution Configuration

Control workflow execution behavior and tracking:

```yaml
execution:
  # What to record during execution
  tracking:
    enabled: true
    track_outputs: true    # Record node outputs
    track_inputs: true     # Record node inputs
  
  # How to determine workflow success
  success_policy:
    type: "all_nodes"      # "all_nodes", "final_node", "critical_nodes", "custom"
    critical_nodes: []     # List of critical node names
    custom_function: ""    # Custom success evaluation function
```

### Success Policy Types

**all_nodes (default):**
- Workflow succeeds only if all nodes complete successfully
- Best for: Critical workflows, data processing pipelines

**final_node:**
- Workflow succeeds if the final node completes successfully
- Best for: Output-focused workflows, reporting systems

**critical_nodes:**
- Workflow succeeds if specified critical nodes complete successfully
- Best for: Complex workflows with optional steps

**custom:**
- Use custom function to evaluate success
- Best for: Complex business logic, custom success criteria

## 📊 Tracing Configuration

Configure debugging and monitoring:

```yaml
tracing:
  enabled: false
  
  # Tracing mode: "local" or "langsmith"
  mode: "local"
  
  # Local tracing settings
  local_exporter: "file"    # "file" or "csv"
  local_directory: "./traces"
  
  # LangSmith integration
  project: "your_project_name"
  langsmith_api_key: "env:LANGSMITH_API_KEY"
  
  # What to trace
  trace_all: true           # Trace all workflows
  trace_graphs: []          # Specific workflows to trace
```

### Local Tracing

**File Export:**
- Creates detailed trace files in JSON format
- Best for: Development, detailed debugging

**CSV Export:**
- Creates CSV files with execution data
- Best for: Data analysis, performance monitoring

### LangSmith Integration

```yaml
tracing:
  enabled: true
  mode: "langsmith"
  project: "production-workflows"
  langsmith_api_key: "env:LANGSMITH_API_KEY"
  trace_all: true
```

## 📝 Logging Configuration

Comprehensive logging setup using Python's logging configuration:

```yaml
logging:
  version: 1
  disable_existing_loggers: false
  
  # Optional: Log to file
  file_path: "/var/log/agentmap/app.log"
  
  # Log formatters
  formatters:
    default:
      format: "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
    detailed:
      format: "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(name)s: %(message)s"
  
  # Log handlers
  handlers:
    console:
      class: logging.StreamHandler
      formatter: default
      level: DEBUG
    
    file:
      class: logging.FileHandler
      filename: "/var/log/agentmap/app.log"
      formatter: detailed
      level: INFO
  
  # Root logger configuration
  root:
    level: INFO
    handlers: [console, file]
  
  # Logger-specific settings
  loggers:
    agentmap.routing:
      level: DEBUG
      handlers: [console]
      propagate: false
    
    agentmap.storage:
      level: WARNING
      handlers: [file]
      propagate: false
```

### Log Levels

- `TRACE`: Most detailed, development only
- `DEBUG`: Detailed debugging information
- `INFO`: General operational information
- `WARNING`: Warning messages, potential issues
- `ERROR`: Error messages, failures

## 🌍 Environment Variable Overrides

Use environment variables to override configuration at runtime:

```yaml
environment_overrides:
  # Routing system
  routing_enabled: ${AGENTMAP_ROUTING_ENABLED:true}
  default_task_type: ${AGENTMAP_DEFAULT_TASK_TYPE:general}
  cost_optimization: ${AGENTMAP_COST_OPTIMIZATION:true}
  routing_cache_enabled: ${AGENTMAP_ROUTING_CACHE:true}
  
  # Performance settings
  max_concurrent_requests: ${AGENTMAP_MAX_CONCURRENT:10}
  request_timeout: ${AGENTMAP_REQUEST_TIMEOUT:30}
  
  # Development settings
  debug_mode: ${AGENTMAP_DEBUG:false}
  verbose_logging: ${AGENTMAP_VERBOSE:false}
```

### Environment Variable Syntax

```yaml
# With default value
setting: ${ENV_VAR:default_value}

# Without default (required)
setting: ${ENV_VAR}

# Boolean values
enabled: ${ENABLE_FEATURE:true}

# Numeric values
port: ${PORT:8080}
```

## 🔒 Authentication Configuration

Configure authentication and authorization:

```yaml
authentication:
  # JWT configuration
  jwt:
    secret_key: "env:JWT_SECRET_KEY"
    algorithm: "HS256"
    expiration_hours: 24
  
  # API key authentication
  api_keys:
    enabled: true
    header_name: "X-API-Key"
    keys:
      - "env:API_KEY_1"
      - "env:API_KEY_2"
  
  # Supabase integration
  supabase:
    url: "env:SUPABASE_URL"
    api_key: "env:SUPABASE_API_KEY"
    jwt_secret: "env:SUPABASE_JWT_SECRET"
  
  # Permission system
  permissions:
    require_auth: true
    default_permissions: ["read"]
    admin_permissions: ["read", "write", "delete", "admin"]
```

## 🚀 Performance Optimization

Configure performance and resource management:

```yaml
performance:
  # Connection pooling
  connection_pool:
    max_connections: 100
    pool_timeout: 30
    retry_attempts: 3
  
  # Caching
  cache:
    enabled: true
    type: "memory"      # "memory", "redis", "file"
    ttl: 3600          # Time to live in seconds
    max_size: 1000     # Maximum cache entries
  
  # Rate limiting
  rate_limiting:
    enabled: false
    requests_per_minute: 60
    burst_size: 10
  
  # Timeouts
  timeouts:
    llm_request: 30    # LLM request timeout
    storage_operation: 10    # Storage operation timeout
    workflow_execution: 300  # Total workflow timeout
```

## 🏢 Host Application Configuration

Configure integration with host applications:

```yaml
host_application:
  # Service discovery
  service_discovery:
    enabled: true
    protocol: "http"
    discovery_interval: 30
  
  # Service injection
  services:
    custom_service:
      type: "http"
      endpoint: "http://localhost:8080/api"
      authentication:
        type: "bearer"
        token: "env:CUSTOM_SERVICE_TOKEN"
    
    database_service:
      type: "database"
      connection_string: "env:DATABASE_URL"
      pool_size: 10
  
  # Protocol configuration
  protocols:
    http:
      timeout: 30
      retry_attempts: 3
      headers:
        User-Agent: "AgentMap/1.0"
    
    grpc:
      timeout: 15
      keepalive_interval: 30
```

## ✅ Configuration Validation

AgentMap automatically validates configuration using Pydantic models:

### Validation Rules

- **Required Fields**: `csv_path` must be provided and end with `.csv`
- **Numeric Ranges**: `temperature` must be between 0.0 and 2.0
- **Enum Values**: `tracing.mode` must be "local" or "langsmith"
- **Default Values**: All optional fields have sensible defaults

### Validation Examples

```yaml
# ✅ Valid configuration
temperature: 0.7

# ❌ Invalid configuration
temperature: 3.0  # Error: temperature must be <= 2.0

# ✅ Valid success policy
success_policy:
  type: "all_nodes"

# ❌ Invalid success policy  
success_policy:
  type: "invalid_type"  # Error: must be one of: all_nodes, final_node, critical_nodes, custom
```

## 🔄 Hot Reloading

Some configuration changes can be applied without restart:

### Hot Reloadable Settings
- Environment variable overrides
- Logging levels
- Routing preferences
- Cache settings

### Restart Required Settings
- Core paths configuration
- Storage provider settings
- Authentication configuration
- LLM provider credentials

## 📖 Next Steps

1. **Configure [Storage](storage-config)** - Set up your data persistence layer
2. **Set [Environment Variables](environment-variables)** - Secure your credentials  
3. **Review [Examples](examples)** - See complete configuration examples
4. **Test Configuration** - Validate your setup before deployment

Ready to configure storage providers? Continue to the [Storage Configuration](storage-config) guide.
