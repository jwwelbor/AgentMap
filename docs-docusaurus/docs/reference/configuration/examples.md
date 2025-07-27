---
title: Configuration Examples
sidebar_position: 5
description: Complete configuration examples for AgentMap including local development, production deployment, and cloud integration scenarios.
keywords: [configuration examples, deployment scenarios, local development, production setup, cloud integration]
---

# Configuration Examples

This guide provides complete, working configuration examples for different AgentMap deployment scenarios. Each example includes both the main configuration file and environment variable setup.

## 🏃‍♂️ Quick Start: Minimal Configuration

Perfect for getting started with AgentMap in under 5 minutes.

### Minimal Configuration Files

**agentmap_config.yaml:**
```yaml
# Minimal configuration for quick start
csv_path: "examples/HelloWorld.csv"
autocompile: true

llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-3.5-turbo"
    temperature: 0.7
```

**.env:**
```bash
# Basic environment variables
OPENAI_API_KEY=sk-your-openai-key-here
```

**Quick Start Usage:**
```bash
# 1. Save the configuration files
# 2. Set your OpenAI API key in .env
# 3. Run your first workflow
agentmap run --graph HelloWorld --state '{"input": "Hello, AgentMap!"}'
```

## 🏠 Local Development Configuration

Comprehensive setup for local development with multiple LLM providers and local storage.

### Development Configuration Files

**agentmap_config.yaml:**
```yaml
# Development configuration with multiple providers
csv_path: "examples/DevelopmentWorkflow.csv"
autocompile: true
storage_config_path: "agentmap_dev_storage.yaml"

# Directory paths for development
paths:
  custom_agents: "dev/custom_agents"
  functions: "dev/custom_functions"
  compiled_graphs: "dev/compiled"
  csv_repository: "dev/workflows"

# Multiple LLM providers for testing
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-3.5-turbo"
    temperature: 0.7
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-haiku-20240307"
    temperature: 0.7
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-1.0-pro"
    temperature: 0.7

# Basic routing for development
routing:
  enabled: true
  routing_matrix:
    anthropic:
      low: "claude-3-haiku-20240307"
      medium: "claude-3-sonnet-20240229"
    openai:
      low: "gpt-3.5-turbo"
      medium: "gpt-4-turbo"

# Memory for stateful testing
memory:
  enabled: true
  default_type: "buffer"
  buffer_window_size: 5
  max_token_limit: 1000

# Development execution tracking
execution:
  tracking:
    enabled: true
    track_outputs: true
    track_inputs: true
  success_policy:
    type: "all_nodes"

# Local tracing for debugging
tracing:
  enabled: true
  mode: "local"
  local_exporter: "file"
  local_directory: "./dev_traces"
  trace_all: true

# Development logging
logging:
  version: 1
  disable_existing_loggers: false
  formatters:
    detailed:
      format: "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(name)s: %(message)s"
  handlers:
    console:
      class: logging.StreamHandler
      formatter: detailed
      level: DEBUG
  root:
    level: DEBUG
    handlers: [console]

# Environment overrides for development
environment_overrides:
  routing_enabled: ${AGENTMAP_ROUTING_ENABLED:true}
  debug_mode: ${DEBUG_MODE:true}
```

**agentmap_dev_storage.yaml:**
```yaml
# Development storage configuration
csv:
  default_directory: "dev/data/csv"
  collections:
    users: "dev/data/csv/users.csv"
    products: "dev/data/csv/products.csv"
    test_data: "dev/data/csv/test_data.csv"

json:
  default_directory: "dev/data/json"
  collections:
    config: "dev/data/json/config.json"
    user_profiles: "dev/data/json/profiles.json"
    test_documents: "dev/data/json/test_docs.json"

kv:
  default_provider: "local"
  collections:
    cache:
      provider: "local"
      path: "dev/data/kv/cache.json"
    session:
      provider: "memory"
      ttl: 1800

file:
  default_directory: "dev/data/files"
  allow_binary: true
  collections:
    documents: "dev/data/files/docs"
    uploads: "dev/data/files/uploads"

memory:
  default_ttl: 1800
  max_size: 1000
  cleanup_interval: 300
```

**.env:**
```bash
# Development environment variables
# LLM Provider Keys (development/limited keys)
OPENAI_API_KEY=sk-your-dev-openai-key
ANTHROPIC_API_KEY=sk-ant-api03-your-dev-anthropic-key
GOOGLE_API_KEY=AIzaSy-your-dev-google-key

# Development Settings
ENVIRONMENT=development
DEBUG_MODE=true
LOG_LEVEL=DEBUG

# Routing Configuration
AGENTMAP_ROUTING_ENABLED=true
AGENTMAP_DEFAULT_TASK_TYPE=general
AGENTMAP_COST_OPTIMIZATION=false

# Development Features
FEATURE_EXPERIMENTAL_ROUTING=true
FEATURE_ADVANCED_MEMORY=true
```

## 🚀 Production Deployment Configuration

Enterprise-ready configuration with security, monitoring, and performance optimization.

### Production Configuration Files

**agentmap_config.yaml:**
```yaml
# Production configuration with full optimization
csv_path: "workflows/production.csv"
autocompile: true
storage_config_path: "agentmap_production_storage.yaml"

# Production paths
paths:
  custom_agents: "production/agents"
  functions: "production/functions"
  compiled_graphs: "production/compiled"
  csv_repository: "production/workflows"

# Multi-provider LLM configuration
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-4-turbo"
    temperature: 0.3
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-sonnet-20240229"
    temperature: 0.3
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-1.5-pro"
    temperature: 0.3

# Advanced routing with cost optimization
routing:
  enabled: true
  
  routing_matrix:
    anthropic:
      low: "claude-3-haiku-20240307"
      medium: "claude-3-sonnet-20240229"
      high: "claude-3-opus-20240229"
      critical: "claude-3-opus-20240229"
    openai:
      low: "gpt-3.5-turbo"
      medium: "gpt-4-turbo"
      high: "gpt-4"
      critical: "gpt-4"
    google:
      low: "gemini-1.0-pro"
      medium: "gemini-1.5-pro"
      high: "gemini-1.5-pro"
      critical: "gemini-1.5-pro"
  
  task_types:
    general:
      provider_preference: ["anthropic", "openai", "google"]
      default_complexity: "medium"
    code_analysis:
      provider_preference: ["openai", "anthropic"]
      default_complexity: "medium"
    creative_writing:
      provider_preference: ["anthropic", "openai"]
      default_complexity: "high"
    data_analysis:
      provider_preference: ["openai", "google", "anthropic"]
      default_complexity: "medium"
  
  cost_optimization:
    enabled: true
    prefer_cost_effective: true
    max_cost_tier: "high"
  
  performance:
    enable_routing_cache: true
    cache_ttl: 600
    max_cache_size: 5000

# Production memory configuration
memory:
  enabled: true
  default_type: "buffer_window"
  buffer_window_size: 10
  max_token_limit: 4000
  memory_key: "conversation_memory"

# Comprehensive execution tracking
execution:
  tracking:
    enabled: true
    track_outputs: true
    track_inputs: true
  success_policy:
    type: "all_nodes"

# LangSmith integration for monitoring
tracing:
  enabled: true
  mode: "langsmith"
  project: "production-workflows"
  langsmith_api_key: "env:LANGSMITH_API_KEY"
  trace_all: true

# Production logging with file output
logging:
  version: 1
  disable_existing_loggers: false
  file_path: "/var/log/agentmap/app.log"
  formatters:
    production:
      format: "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
    detailed:
      format: "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(name)s: %(message)s"
  handlers:
    console:
      class: logging.StreamHandler
      formatter: production
      level: WARNING
    file:
      class: logging.handlers.RotatingFileHandler
      filename: "/var/log/agentmap/app.log"
      formatter: detailed
      level: INFO
      maxBytes: 104857600  # 100MB
      backupCount: 5
  root:
    level: INFO
    handlers: [console, file]

# Production authentication
authentication:
  jwt:
    secret_key: "env:JWT_SECRET_KEY"
    algorithm: "HS256"
    expiration_hours: 24
  api_keys:
    enabled: true
    header_name: "X-API-Key"
    keys:
      - "env:API_KEY_PROD"
      - "env:API_KEY_BACKUP"

# Performance optimization
performance:
  connection_pool:
    max_connections: 200
    pool_timeout: 30
    retry_attempts: 3
  cache:
    enabled: true
    type: "redis"
    ttl: 7200
    max_size: 10000
  rate_limiting:
    enabled: true
    requests_per_minute: 120
    burst_size: 20
  timeouts:
    llm_request: 45
    storage_operation: 15
    workflow_execution: 600

# Environment overrides
environment_overrides:
  routing_enabled: ${AGENTMAP_ROUTING_ENABLED:true}
  cost_optimization: ${AGENTMAP_COST_OPTIMIZATION:true}
  max_concurrent: ${AGENTMAP_MAX_CONCURRENT:50}
  request_timeout: ${AGENTMAP_REQUEST_TIMEOUT:45}
```

**agentmap_production_storage.yaml:**
```yaml
# Production storage with cloud providers
csv:
  default_directory: "/app/data/csv"
  collections:
    users: "/app/data/csv/users.csv"
    transactions: "/app/data/csv/transactions.csv"
    analytics: "/app/data/csv/analytics.csv"

json:
  default_directory: "/app/data/json"
  
  # Cloud storage providers
  providers:
    azure:
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
      default_container: "production-documents"
    aws:
      region: "us-west-2"
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      default_bucket: "agentmap-production"
  
  collections:
    config: "/app/data/json/config.json"
    user_profiles: "azure://users/profiles.json"
    analytics_data: "s3://analytics/data.json"

vector:
  default_provider: "pinecone"
  collections:
    documents:
      provider: "pinecone"
      index_name: "production-docs"
      namespace: "general"
      dimension: 1536
      metric: "cosine"
      api_key: "env:PINECONE_API_KEY"
      environment: "env:PINECONE_ENVIRONMENT"
    embeddings:
      provider: "supabase"
      table: "embeddings"
      connection_string: "env:SUPABASE_URL"
      api_key: "env:SUPABASE_KEY"

kv:
  default_provider: "redis"
  collections:
    cache:
      provider: "redis"
      connection: "env:REDIS_URL"
      prefix: "agentmap:prod:"
      ttl: 7200
    sessions:
      provider: "redis"
      connection: "env:REDIS_URL"
      prefix: "session:prod:"
      ttl: 3600

firebase:
  default_project: "env:FIREBASE_PROJECT_ID"
  auth:
    service_account_key: "env:FIREBASE_SERVICE_ACCOUNT"
  firestore:
    collections:
      user_data:
        collection_path: "users"
      audit_logs:
        collection_path: "audit/logs"

file:
  default_directory: "/app/data/files"
  allow_binary: true
  options:
    max_file_size: "50MB"
  collections:
    documents: "/app/data/files/documents"
    uploads: "/app/data/files/uploads"
    archives: "/app/data/files/archives"
```

**.env.production:**
```bash
# Production environment variables
# LLM Provider Keys (production/full access)
OPENAI_API_KEY=sk-production-openai-key-with-full-access
ANTHROPIC_API_KEY=sk-ant-api03-production-anthropic-key
GOOGLE_API_KEY=AIzaSy-production-google-key
LANGSMITH_API_KEY=ls-production-langsmith-key

# Cloud Storage Credentials
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
PINECONE_API_KEY=12345678-1234-1234-1234-123456789abc
PINECONE_ENVIRONMENT=us-west1-gcp

# Database Credentials
REDIS_URL=redis://production-redis-cluster:6379/0
SUPABASE_URL=https://production-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Firebase Configuration
FIREBASE_PROJECT_ID=agentmap-production
FIREBASE_SERVICE_ACCOUNT=/app/config/firebase-service-account.json

# Security Settings
JWT_SECRET_KEY=production-jwt-secret-key-very-secure
API_KEY_PROD=ak-production-api-key-secure
API_KEY_BACKUP=ak-backup-api-key-secure

# Production Settings
ENVIRONMENT=production
DEBUG_MODE=false
LOG_LEVEL=INFO

# Routing & Performance
AGENTMAP_ROUTING_ENABLED=true
AGENTMAP_COST_OPTIMIZATION=true
AGENTMAP_MAX_CONCURRENT=50
AGENTMAP_REQUEST_TIMEOUT=45

# Monitoring
METRICS_ENABLED=true
HEALTH_CHECK_ENABLED=true
```

## ☁️ Multi-Cloud Integration Configuration

Advanced setup with multiple cloud providers and sophisticated routing.

### Multi-Cloud Configuration Files

**agentmap_config.yaml:**
```yaml
# Multi-cloud enterprise configuration
csv_path: "workflows/enterprise.csv"
autocompile: true
storage_config_path: "agentmap_multicloud_storage.yaml"

# Enterprise paths
paths:
  custom_agents: "enterprise/agents"
  functions: "enterprise/functions"
  compiled_graphs: "enterprise/compiled"
  csv_repository: "enterprise/workflows"

# All LLM providers configured
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-4"
    temperature: 0.2
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-opus-20240229"
    temperature: 0.2
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-1.5-pro"
    temperature: 0.2

# Sophisticated routing with all task types
routing:
  enabled: true
  
  routing_matrix:
    anthropic:
      low: "claude-3-haiku-20240307"
      medium: "claude-3-sonnet-20240229"
      high: "claude-3-opus-20240229"
      critical: "claude-3-opus-20240229"
    openai:
      low: "gpt-3.5-turbo"
      medium: "gpt-4-turbo"
      high: "gpt-4"
      critical: "gpt-4"
    google:
      low: "gemini-1.0-pro"
      medium: "gemini-1.5-pro"
      high: "gemini-1.5-pro"
      critical: "gemini-1.5-pro"
  
  task_types:
    general:
      provider_preference: ["anthropic", "openai", "google"]
      default_complexity: "medium"
    creative_writing:
      provider_preference: ["anthropic", "openai"]
      default_complexity: "high"
    code_analysis:
      provider_preference: ["openai", "anthropic"]
      default_complexity: "medium"
    customer_service:
      provider_preference: ["anthropic", "openai"]
      default_complexity: "medium"
    data_analysis:
      provider_preference: ["openai", "google", "anthropic"]
      default_complexity: "medium"
  
  complexity_analysis:
    prompt_length_thresholds:
      low: 150
      medium: 400
      high: 1000
    methods:
      prompt_length: true
      keyword_analysis: true
      context_analysis: true
      memory_analysis: true
  
  cost_optimization:
    enabled: true
    prefer_cost_effective: true
    max_cost_tier: "critical"
  
  performance:
    enable_routing_cache: true
    cache_ttl: 900
    max_cache_size: 10000

# Advanced memory management
memory:
  enabled: true
  default_type: "token_buffer"
  buffer_window_size: 15
  max_token_limit: 8000
  memory_key: "enterprise_memory"

# Comprehensive execution control
execution:
  tracking:
    enabled: true
    track_outputs: true
    track_inputs: true
  success_policy:
    type: "critical_nodes"
    critical_nodes: ["validation", "security_check", "final_output"]

# Enterprise tracing
tracing:
  enabled: true
  mode: "langsmith"
  project: "enterprise-workflows"
  langsmith_api_key: "env:LANGSMITH_API_KEY"
  trace_all: true

# Enterprise logging
logging:
  version: 1
  disable_existing_loggers: false
  file_path: "/var/log/agentmap/enterprise.log"
  formatters:
    enterprise:
      format: "[%(asctime)s] [%(levelname)s] [%(process)d] %(name)s: %(message)s"
    audit:
      format: "[%(asctime)s] [AUDIT] [%(process)d] %(message)s"
  handlers:
    console:
      class: logging.StreamHandler
      formatter: enterprise
      level: ERROR
    file:
      class: logging.handlers.RotatingFileHandler
      filename: "/var/log/agentmap/enterprise.log"
      formatter: enterprise
      level: INFO
      maxBytes: 209715200  # 200MB
      backupCount: 10
    audit:
      class: logging.handlers.RotatingFileHandler
      filename: "/var/log/agentmap/audit.log"
      formatter: audit
      level: INFO
      maxBytes: 104857600  # 100MB
      backupCount: 20
  root:
    level: INFO
    handlers: [console, file]
  loggers:
    agentmap.audit:
      level: INFO
      handlers: [audit]
      propagate: false

# Enterprise authentication and security
authentication:
  jwt:
    secret_key: "env:JWT_SECRET_KEY"
    algorithm: "HS256"
    expiration_hours: 8
  api_keys:
    enabled: true
    header_name: "X-API-Key"
    keys:
      - "env:API_KEY_ENTERPRISE"
      - "env:API_KEY_INTEGRATION"
      - "env:API_KEY_MONITORING"
  supabase:
    url: "env:SUPABASE_URL"
    api_key: "env:SUPABASE_API_KEY"
    jwt_secret: "env:SUPABASE_JWT_SECRET"
  permissions:
    require_auth: true
    default_permissions: ["read"]
    admin_permissions: ["read", "write", "delete", "admin"]

# Enterprise performance optimization
performance:
  connection_pool:
    max_connections: 500
    pool_timeout: 60
    retry_attempts: 5
    connection_lifetime: 7200
  cache:
    enabled: true
    type: "redis"
    ttl: 14400  # 4 hours
    max_size: 50000
  rate_limiting:
    enabled: true
    requests_per_minute: 300
    burst_size: 50
  timeouts:
    llm_request: 60
    storage_operation: 30
    workflow_execution: 1800  # 30 minutes

# Host application integration
host_application:
  service_discovery:
    enabled: true
    protocol: "http"
    discovery_interval: 60
  services:
    enterprise_db:
      type: "database"
      connection_string: "env:ENTERPRISE_DB_URL"
      pool_size: 20
    analytics_service:
      type: "http"
      endpoint: "env:ANALYTICS_SERVICE_URL"
      authentication:
        type: "bearer"
        token: "env:ANALYTICS_SERVICE_TOKEN"

# Environment overrides
environment_overrides:
  routing_enabled: ${AGENTMAP_ROUTING_ENABLED:true}
  cost_optimization: ${AGENTMAP_COST_OPTIMIZATION:true}
  max_concurrent: ${AGENTMAP_MAX_CONCURRENT:100}
  enterprise_features: ${AGENTMAP_ENTERPRISE_FEATURES:true}
```

**agentmap_multicloud_storage.yaml:**
```yaml
# Multi-cloud storage configuration
csv:
  default_directory: "/app/data/csv"
  collections:
    enterprise_data: "/app/data/csv/enterprise.csv"
    analytics: "s3://analytics-bucket/data.csv"
    backup_data: "azure://backup-container/data.csv"

json:
  default_directory: "/app/data/json"
  
  providers:
    azure:
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
      default_container: "enterprise-docs"
      containers:
        primary: "primary-container"
        backup: "backup-container"
        archive: "archive-container"
    
    aws:
      region: "us-west-2"
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      default_bucket: "enterprise-primary"
      buckets:
        analytics: "analytics-bucket"
        logs: "logs-bucket"
        backups: "backup-bucket"
    
    gcp:
      project_id: "env:GCP_PROJECT_ID"
      credentials_file: "env:GCP_SERVICE_ACCOUNT_FILE"
      default_bucket: "enterprise-gcp"
      buckets:
        ml_data: "ml-training-data"
        archives: "long-term-archives"
  
  collections:
    # Multi-cloud distribution
    config: "/app/data/json/config.json"
    user_profiles: "azure://primary/users.json"
    analytics_results: "s3://analytics-bucket/results.json"
    ml_models: "gs://ml-data/models.json"
    backup_config: "azure://backup/config.json"

vector:
  default_provider: "pinecone"
  collections:
    primary_docs:
      provider: "pinecone"
      index_name: "enterprise-primary"
      namespace: "production"
      dimension: 1536
      metric: "cosine"
      api_key: "env:PINECONE_API_KEY"
      environment: "env:PINECONE_ENVIRONMENT"
    
    customer_data:
      provider: "supabase"
      table: "customer_embeddings"
      connection_string: "env:SUPABASE_URL"
      api_key: "env:SUPABASE_KEY"
      dimension: 1536
    
    local_cache:
      provider: "local"
      path: "/app/data/vector/cache"
      dimension: 768
      index_type: "hnsw"

kv:
  default_provider: "redis"
  collections:
    primary_cache:
      provider: "redis"
      connection: "env:REDIS_PRIMARY_URL"
      prefix: "enterprise:primary:"
      ttl: 14400
    
    session_store:
      provider: "redis"
      connection: "env:REDIS_SESSION_URL"
      prefix: "session:enterprise:"
      ttl: 28800
    
    backup_cache:
      provider: "redis"
      connection: "env:REDIS_BACKUP_URL"
      prefix: "enterprise:backup:"
      ttl: 86400

firebase:
  default_project: "env:FIREBASE_PROJECT_ID"
  auth:
    service_account_key: "env:FIREBASE_SERVICE_ACCOUNT"
  
  firestore:
    collections:
      enterprise_users:
        collection_path: "enterprise/users"
        query_limit: 1000
      audit_logs:
        collection_path: "audit/enterprise_logs"
        query_limit: 10000
      compliance_data:
        collection_path: "compliance/data"
  
  realtime_db:
    collections:
      live_analytics:
        db_url: "env:FIREBASE_RTDB_URL"
        path: "analytics/live"
        query_limit: 1000
  
  storage:
    collections:
      enterprise_files:
        bucket: "env:FIREBASE_STORAGE_BUCKET"
        path: "enterprise/files"
        max_file_size: "100MB"
      compliance_docs:
        bucket: "env:FIREBASE_COMPLIANCE_BUCKET"
        path: "compliance/documents"

file:
  default_directory: "/app/data/files"
  allow_binary: true
  
  options:
    max_file_size: "500MB"
    encryption: true
    encryption_key: "env:FILE_ENCRYPTION_KEY"
  
  collections:
    enterprise_docs: "/app/data/files/enterprise"
    secure_files: "/app/secure/files"
    temp_uploads: "/tmp/agentmap/uploads"

memory:
  default_ttl: 7200
  max_size: 100000
  cleanup_interval: 600
  
  collections:
    enterprise_cache:
      ttl: 14400
      max_size: 50000
      compression: true
    session_data:
      ttl: 3600
      max_size: 10000
```

**.env.enterprise:**
```bash
# Enterprise multi-cloud environment variables

# LLM Provider Keys (enterprise/unlimited)
OPENAI_API_KEY=sk-enterprise-openai-unlimited-access
ANTHROPIC_API_KEY=sk-ant-api03-enterprise-anthropic-key
GOOGLE_API_KEY=AIzaSy-enterprise-google-unlimited
LANGSMITH_API_KEY=ls-enterprise-langsmith-monitoring

# Azure Cloud Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=enterprisestorage;AccountKey=...

# AWS Cloud Storage
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7ENTERPRISE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYENTERPRISE
AWS_DEFAULT_REGION=us-west-2

# Google Cloud Platform
GCP_PROJECT_ID=agentmap-enterprise-12345
GCP_SERVICE_ACCOUNT_FILE=/app/config/gcp-service-account.json

# Vector Databases
PINECONE_API_KEY=12345678-enterprise-pinecone-key
PINECONE_ENVIRONMENT=us-west1-gcp-enterprise

# Supabase
SUPABASE_URL=https://enterprise-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.enterprise...
SUPABASE_JWT_SECRET=enterprise-jwt-secret

# Redis Clusters
REDIS_PRIMARY_URL=redis://enterprise-redis-primary:6379/0
REDIS_SESSION_URL=redis://enterprise-redis-sessions:6379/0
REDIS_BACKUP_URL=redis://enterprise-redis-backup:6379/0

# Firebase
FIREBASE_PROJECT_ID=agentmap-enterprise
FIREBASE_SERVICE_ACCOUNT=/app/config/firebase-enterprise.json
FIREBASE_RTDB_URL=https://agentmap-enterprise-rtdb.firebaseio.com
FIREBASE_STORAGE_BUCKET=agentmap-enterprise.appspot.com
FIREBASE_COMPLIANCE_BUCKET=agentmap-compliance.appspot.com

# Enterprise Databases
ENTERPRISE_DB_URL=postgresql://enterprise-cluster:5432/agentmap

# External Services
ANALYTICS_SERVICE_URL=https://analytics.enterprise.com/api
ANALYTICS_SERVICE_TOKEN=bearer-token-for-analytics

# Security & Authentication
JWT_SECRET_KEY=enterprise-jwt-secret-ultra-secure
API_KEY_ENTERPRISE=ak-enterprise-primary-key
API_KEY_INTEGRATION=ak-enterprise-integration-key
API_KEY_MONITORING=ak-enterprise-monitoring-key
FILE_ENCRYPTION_KEY=enterprise-file-encryption-key

# Enterprise Settings
ENVIRONMENT=enterprise
DEBUG_MODE=false
LOG_LEVEL=INFO

# Performance & Scaling
AGENTMAP_ROUTING_ENABLED=true
AGENTMAP_COST_OPTIMIZATION=true
AGENTMAP_MAX_CONCURRENT=100
AGENTMAP_REQUEST_TIMEOUT=60
AGENTMAP_ENTERPRISE_FEATURES=true

# Monitoring & Observability
METRICS_ENABLED=true
HEALTH_CHECK_ENABLED=true
TRACING_ENABLED=true
AUDIT_LOGGING_ENABLED=true
```

## 🧪 Testing and Staging Configuration

Configuration optimized for testing and staging environments.

### Testing Configuration Files

**agentmap_test_config.yaml:**
```yaml
# Testing configuration with mocked services
csv_path: "tests/test_workflow.csv"
autocompile: false  # Disable for testing
storage_config_path: "agentmap_test_storage.yaml"

# Test paths
paths:
  custom_agents: "tests/mock_agents"
  functions: "tests/mock_functions"
  compiled_graphs: "tests/compiled"
  csv_repository: "tests/workflows"

# Limited LLM providers for testing
llm:
  openai:
    api_key: "env:OPENAI_TEST_KEY"
    model: "gpt-3.5-turbo"
    temperature: 0.0  # Deterministic for testing

# Simple routing for testing
routing:
  enabled: false  # Disable complex routing in tests

# Test memory configuration
memory:
  enabled: false  # Disable for stateless tests

# Test execution
execution:
  tracking:
    enabled: true
    track_outputs: true
    track_inputs: true
  success_policy:
    type: "all_nodes"

# No tracing in tests
tracing:
  enabled: false

# Test logging
logging:
  version: 1
  disable_existing_loggers: false
  handlers:
    console:
      class: logging.StreamHandler
      level: INFO
  root:
    level: INFO
    handlers: [console]
```

**agentmap_test_storage.yaml:**
```yaml
# Testing storage with in-memory providers
csv:
  default_directory: "tests/data/csv"
  collections:
    test_users: "tests/data/csv/users.csv"
    test_data: "tests/data/csv/test.csv"

json:
  default_directory: "tests/data/json"
  collections:
    test_config: "tests/data/json/config.json"

kv:
  default_provider: "memory"
  collections:
    test_cache:
      provider: "memory"
      ttl: 60

file:
  default_directory: "tests/data/files"
  allow_binary: false

memory:
  default_ttl: 60
  max_size: 100
  cleanup_interval: 30
```

**.env.test:**
```bash
# Test environment variables
OPENAI_TEST_KEY=sk-test-key-for-limited-testing
ENVIRONMENT=test
DEBUG_MODE=true
LOG_LEVEL=INFO
AGENTMAP_ROUTING_ENABLED=false
```

## 📖 Environment File Examples

### Basic .env Template

```bash
# Copy this template and update with your values

# =============================================================================
# LLM PROVIDER API KEYS (Choose one or more)
# =============================================================================
# OpenAI (recommended for getting started)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Anthropic (recommended for advanced reasoning)
# ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key-here

# Google AI (recommended for cost-effective options)
# GOOGLE_API_KEY=AIzaSy-your-google-api-key-here

# =============================================================================
# OPTIONAL: STORAGE PROVIDERS
# =============================================================================
# Redis (for caching and session storage)
# REDIS_URL=redis://localhost:6379/0

# Pinecone (for vector search)
# PINECONE_API_KEY=your-pinecone-api-key
# PINECONE_ENVIRONMENT=us-west1-gcp-free

# Firebase (for document storage)
# FIREBASE_PROJECT_ID=your-project-id
# FIREBASE_SERVICE_ACCOUNT=/path/to/service-account.json

# =============================================================================
# OPTIONAL: MONITORING & DEBUGGING
# =============================================================================
# LangSmith (for tracing and monitoring)
# LANGSMITH_API_KEY=ls-your-langsmith-api-key

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================
ENVIRONMENT=development
DEBUG_MODE=true
LOG_LEVEL=INFO
```

### Docker Compose Integration

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  agentmap:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_URL=redis://redis:6379/0
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    depends_on:
      - redis
    volumes:
      - ./data:/app/data
      - ./config:/app/config

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

## 🔧 Configuration Validation Examples

### Validation Script

```python
#!/usr/bin/env python3
"""
AgentMap Configuration Validator
Run this script to validate your configuration files.
"""

import os
import yaml
from pathlib import Path

def validate_config():
    """Validate AgentMap configuration."""
    
    # Check required files
    config_file = "agentmap_config.yaml"
    storage_file = "agentmap_config_storage.yaml"
    env_file = ".env"
    
    print("🔍 Validating AgentMap Configuration...")
    
    # Check configuration files exist
    if not Path(config_file).exists():
        print(f"❌ {config_file} not found")
        return False
        
    if not Path(storage_file).exists():
        print(f"⚠️  {storage_file} not found (optional)")
    
    # Load and validate YAML syntax
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        print(f"✅ {config_file} has valid YAML syntax")
    except yaml.YAMLError as e:
        print(f"❌ {config_file} has invalid YAML: {e}")
        return False
    
    # Check required configuration fields
    required_fields = ['csv_path', 'llm']
    for field in required_fields:
        if field not in config:
            print(f"❌ Missing required field: {field}")
            return False
    
    # Check LLM provider configuration
    llm_config = config.get('llm', {})
    if not llm_config:
        print("❌ No LLM providers configured")
        return False
    
    # Check environment variables
    if Path(env_file).exists():
        print(f"✅ {env_file} found")
    else:
        print(f"⚠️  {env_file} not found")
    
    # Validate LLM provider keys
    llm_keys = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'google': 'GOOGLE_API_KEY'
    }
    
    for provider, env_var in llm_keys.items():
        if provider in llm_config:
            if not os.getenv(env_var):
                print(f"⚠️  {env_var} not set for {provider} provider")
            else:
                print(f"✅ {env_var} configured for {provider}")
    
    print("\n🎉 Configuration validation complete!")
    return True

if __name__ == "__main__":
    validate_config()
```

## 📖 Next Steps

1. **Choose your deployment scenario** - Select the configuration that matches your needs
2. **Customize for your environment** - Modify paths, credentials, and settings
3. **Test your configuration** - Use the validation script to check everything works
4. **Review [Troubleshooting](troubleshooting)** - Common issues and solutions

Ready to troubleshoot common configuration issues? Continue to the [Troubleshooting](troubleshooting) guide.
