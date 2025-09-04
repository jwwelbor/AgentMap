---
title: Environment Variables
sidebar_position: 4
description: Complete reference of AgentMap environment variables for API keys, storage credentials, system overrides, and security settings.
keywords: [environment variables, API keys, credentials, configuration overrides, security]
---

# Environment Variables

AgentMap uses environment variables for secure credential management, runtime configuration overrides, and deployment-specific settings. This guide provides a complete reference of all supported environment variables with examples and security best practices.

## 🔐 Security First: Why Environment Variables?

Environment variables provide secure, deployment-specific configuration by:

- **Separating credentials from code** - No sensitive data in configuration files
- **Supporting multiple environments** - Different values for dev/staging/production
- **Enabling CI/CD integration** - Automated deployment with secure credential injection
- **Following security best practices** - Industry-standard approach to secrets management

## 📋 Environment Variable Categories

### LLM Provider API Keys
Essential credentials for language model providers

### Storage Provider Credentials  
Authentication for databases and cloud storage services

### System Configuration Overrides
Runtime modification of application behavior

### Authentication & Security
JWT secrets, API keys, and security settings

### Monitoring & Tracing
LangSmith, logging, and debugging configuration

### Performance & Optimization
Connection limits, timeouts, and resource settings

## 🤖 LLM Provider API Keys

### OpenAI Configuration

```bash
# Required: OpenAI API key
OPENAI_API_KEY=sk-1234567890abcdef1234567890abcdef12345678

# Optional: Organization ID (for organization-specific usage)
OPENAI_ORG_ID=org-1234567890abcdef

# Optional: Default model override
OPENAI_DEFAULT_MODEL=gpt-4-turbo

# Optional: API base URL (for custom endpoints)
OPENAI_API_BASE=https://api.openai.com/v1
```

### Anthropic Configuration

```bash
# Required: Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-1234567890abcdef1234567890abcdef12345678

# Optional: Default model override
ANTHROPIC_DEFAULT_MODEL=claude-3-5-sonnet-20241022

# Optional: API base URL
ANTHROPIC_API_BASE=https://api.anthropic.com
```

### Google AI Configuration

```bash
# Required: Google AI API key
GOOGLE_API_KEY=AIzaSy1234567890abcdef1234567890abcdef123

# Optional: Default model override  
GOOGLE_DEFAULT_MODEL=gemini-1.5-pro

# Optional: Project ID (for Vertex AI)
GOOGLE_PROJECT_ID=my-project-123456
```

### LLM Configuration Usage

```yaml
# In agentmap_config.yaml
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "env:OPENAI_DEFAULT_MODEL:gpt-3.5-turbo"  # With fallback
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "env:ANTHROPIC_DEFAULT_MODEL:claude-3-5-sonnet-20241022"
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "env:GOOGLE_DEFAULT_MODEL:gemini-1.0-pro"
```

## 🗄️ Storage Provider Credentials

### Vector Database Credentials

```bash
# Pinecone
PINECONE_API_KEY=12345678-1234-1234-1234-123456789abc
PINECONE_ENVIRONMENT=us-west1-gcp-free

# Supabase Vector
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-key
```

### Cloud Storage Credentials

```bash
# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_ACCOUNT=yourstorageaccount
AZURE_STORAGE_KEY=abcdef1234567890abcdef1234567890...

# AWS S3
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_SESSION_TOKEN=temporary-session-token-for-assumed-roles
AWS_DEFAULT_REGION=us-west-2

# Google Cloud Storage
GCP_PROJECT_ID=my-project-123456
GCP_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### Database Credentials

```bash
# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password
REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_DB=0

# PostgreSQL (for Supabase or custom databases)
DATABASE_URL=postgresql://user:password@localhost:5432/agentmap
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=agentmap_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=agentmap

# MongoDB (if using custom storage)
MONGODB_URI=mongodb://user:password@localhost:27017/agentmap
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_USER=agentmap_user
MONGODB_PASSWORD=secure_password
```

### Firebase Credentials

```bash
# Firebase project configuration
FIREBASE_DEFAULT_PROJECT=my-project-12345
FIREBASE_PROJECT_ID=my-project-12345
FIREBASE_API_KEY=AIzaSy1234567890abcdef1234567890abcdef123

# Firebase authentication
FIREBASE_SERVICE_ACCOUNT=/path/to/firebase-service-account.json
FIREBASE_EMAIL=service-account@my-project.iam.gserviceaccount.com
FIREBASE_PASSWORD=service-account-password

# Firebase Realtime Database
FIREBASE_RTDB_URL=https://my-project-12345-default-rtdb.firebaseio.com

# Firebase Storage
FIREBASE_STORAGE_BUCKET=my-project-12345.appspot.com
```

## ⚙️ System Configuration Overrides

### Routing System Configuration

```bash
# Enable/disable intelligent routing
AGENTMAP_ROUTING_ENABLED=true

# Default task type for routing decisions
AGENTMAP_DEFAULT_TASK_TYPE=general

# Cost optimization settings
AGENTMAP_COST_OPTIMIZATION=true
AGENTMAP_MAX_COST_TIER=high

# Routing cache settings
AGENTMAP_ROUTING_CACHE=true
AGENTMAP_ROUTING_CACHE_TTL=300
AGENTMAP_ROUTING_CACHE_SIZE=1000

# Fallback configuration
AGENTMAP_FALLBACK_PROVIDER=anthropic
AGENTMAP_FALLBACK_MODEL=claude-3-haiku-20240307
```

### Memory Configuration

```bash
# Memory system enable/disable
AGENTMAP_MEMORY_ENABLED=false

# Memory type configuration
AGENTMAP_MEMORY_TYPE=buffer
AGENTMAP_MEMORY_BUFFER_SIZE=5
AGENTMAP_MEMORY_TOKEN_LIMIT=2000

# Memory key configuration
AGENTMAP_MEMORY_KEY=conversation_memory
```

### Execution Configuration

```bash
# Execution tracking
AGENTMAP_TRACKING_ENABLED=true
AGENTMAP_TRACK_OUTPUTS=true
AGENTMAP_TRACK_INPUTS=true

# Success policy configuration
AGENTMAP_SUCCESS_POLICY=all_nodes
AGENTMAP_CRITICAL_NODES=node1,node2,node3

# Workflow compilation
AGENTMAP_AUTOCOMPILE=true
AGENTMAP_COMPILE_ON_STARTUP=true
```

### Path Configuration

```bash
# Custom directory paths
AGENTMAP_CUSTOM_AGENTS_PATH=custom/agents
AGENTMAP_CUSTOM_FUNCTIONS_PATH=custom/functions
AGENTMAP_COMPILED_GRAPHS_PATH=compiled/graphs
AGENTMAP_CSV_REPOSITORY_PATH=workflows
AGENTMAP_STORAGE_CONFIG_PATH=config/storage.yaml
```

## 🔒 Authentication & Security

### JWT Configuration

```bash
# JWT secret key (required for JWT authentication)
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-here

# JWT configuration
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
JWT_ISSUER=agentmap
JWT_AUDIENCE=agentmap-api
```

### API Key Authentication

```bash
# API keys for service authentication
API_KEY_1=ak-1234567890abcdef1234567890abcdef
API_KEY_2=ak-fedcba0987654321fedcba0987654321
API_KEY_ADMIN=ak-admin-1234567890abcdef1234567890ab

# API key configuration
API_KEY_HEADER=X-API-Key
API_KEY_EXPIRATION_DAYS=90
```

### Security Settings

```bash
# Encryption settings
ENCRYPTION_KEY=your-32-byte-encryption-key-here
FILE_ENCRYPTION_KEY=file-specific-encryption-key

# CORS configuration
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://myapp.com
CORS_ALLOWED_METHODS=GET,POST,PUT,DELETE
CORS_ALLOWED_HEADERS=Content-Type,Authorization,X-API-Key

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=10
```

## 📊 Monitoring & Tracing

### LangSmith Configuration

```bash
# LangSmith tracing
LANGSMITH_API_KEY=ls_1234567890abcdef1234567890abcdef
LANGSMITH_PROJECT=production-workflows
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# Tracing configuration
AGENTMAP_TRACING_ENABLED=true
AGENTMAP_TRACING_MODE=langsmith
AGENTMAP_TRACE_ALL=true
```

### Logging Configuration

```bash
# Bootstrap logging (before main config loads)
AGENTMAP_CONFIG_LOG_LEVEL=INFO

# Application logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/agentmap/app.log
LOG_FORMAT=json
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=5

# Debug settings
DEBUG_MODE=false
VERBOSE_LOGGING=false
```

### Performance Monitoring

```bash
# Performance settings
AGENTMAP_MAX_CONCURRENT=10
AGENTMAP_REQUEST_TIMEOUT=30
AGENTMAP_CONNECTION_TIMEOUT=10

# Monitoring endpoints
METRICS_ENABLED=true
METRICS_PORT=8081
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_PORT=8082
```

## 🚀 Performance & Optimization

### Connection & Resource Limits

```bash
# Connection pooling
MAX_CONNECTIONS=100
POOL_TIMEOUT=30
CONNECTION_LIFETIME=3600
RETRY_ATTEMPTS=3

# Resource limits
MAX_MEMORY_MB=2048
MAX_CPU_CORES=4
MAX_FILE_SIZE_MB=100

# Timeout settings
LLM_REQUEST_TIMEOUT=30
STORAGE_OPERATION_TIMEOUT=10
WORKFLOW_EXECUTION_TIMEOUT=300
```

### Caching Configuration

```bash
# Cache settings
CACHE_ENABLED=true
CACHE_TYPE=memory
CACHE_TTL=3600
CACHE_MAX_SIZE=1000

# Redis cache (if using Redis for caching)
CACHE_REDIS_URL=redis://localhost:6379/1
CACHE_REDIS_PREFIX=agentmap:cache:
```

### Batch Processing

```bash
# Batch operation settings
BATCH_PROCESSING_ENABLED=true
BATCH_SIZE=100
BATCH_TIMEOUT=5
PARALLEL_BATCHES=4
```

## 🌍 Deployment Environment Variables

### Environment Detection

```bash
# Environment identification
ENVIRONMENT=production  # development, staging, production
DEPLOYMENT_ID=prod-v1.2.3
BUILD_VERSION=1.2.3
GIT_COMMIT=abc123def456

# Feature flags
FEATURE_ROUTING_V2=true
FEATURE_ADVANCED_MEMORY=false
FEATURE_EXPERIMENTAL_STORAGE=false
```

### Service Discovery

```bash
# Host application integration
HOST_SERVICE_DISCOVERY=true
HOST_SERVICE_PROTOCOL=http
HOST_SERVICE_DISCOVERY_INTERVAL=30

# Service endpoints
CUSTOM_SERVICE_ENDPOINT=http://localhost:8080/api
CUSTOM_SERVICE_TOKEN=bearer-token-for-custom-service
DATABASE_SERVICE_URL=postgresql://localhost:5432/app
```

## 🔧 Environment Variable Syntax in Configuration

### Basic Environment Variable Reference

```yaml
# Simple environment variable reference
api_key: "env:OPENAI_API_KEY"

# Environment variable with default value
model: "env:OPENAI_DEFAULT_MODEL:gpt-3.5-turbo"

# Boolean environment variables
enabled: "env:FEATURE_ENABLED:true"

# Numeric environment variables  
port: "env:PORT:8080"
timeout: "env:REQUEST_TIMEOUT:30"
```

### Advanced Environment Variable Usage

```yaml
# Complex interpolation (using environment_overrides section)
environment_overrides:
  routing_enabled: ${AGENTMAP_ROUTING_ENABLED:true}
  max_concurrent: ${AGENTMAP_MAX_CONCURRENT:10}
  debug_mode: ${DEBUG_MODE:false}

# List values from environment
task_types: ${AGENTMAP_TASK_TYPES:general,code_analysis,creative_writing}

# JSON values from environment (parsed automatically)
routing_matrix: ${AGENTMAP_ROUTING_MATRIX:{}}
```

## 📄 Environment File Management

### Development Environment (.env)

```bash
# .env file for local development
# LLM Provider Keys
OPENAI_API_KEY=sk-your-development-key-here
ANTHROPIC_API_KEY=sk-ant-api03-your-dev-key-here

# Local Storage
REDIS_URL=redis://localhost:6379/0

# Development Settings
ENVIRONMENT=development
DEBUG_MODE=true
LOG_LEVEL=DEBUG
AGENTMAP_ROUTING_ENABLED=false
```

### Staging Environment (.env.staging)

```bash
# .env.staging file
# Production-like keys but limited access
OPENAI_API_KEY=sk-staging-key-with-limits
ANTHROPIC_API_KEY=sk-ant-staging-key

# Staging Resources
REDIS_URL=redis://staging-redis:6379/0
DATABASE_URL=postgresql://staging-db:5432/agentmap

# Staging Settings
ENVIRONMENT=staging
DEBUG_MODE=false
LOG_LEVEL=INFO
AGENTMAP_ROUTING_ENABLED=true
```

### Production Environment (.env.production)

```bash
# .env.production file
# Full production keys
OPENAI_API_KEY=sk-production-key-full-access
ANTHROPIC_API_KEY=sk-ant-production-key

# Production Resources
REDIS_URL=redis://prod-redis-cluster:6379/0
DATABASE_URL=postgresql://prod-db-cluster:5432/agentmap

# Production Settings
ENVIRONMENT=production
DEBUG_MODE=false
LOG_LEVEL=WARNING
AGENTMAP_ROUTING_ENABLED=true
AGENTMAP_COST_OPTIMIZATION=true
```

## 🛡️ Security Best Practices

### Credential Security

**✅ Do:**
- Use strong, unique keys for each environment
- Rotate credentials regularly (90-day cycle recommended)
- Use dedicated service accounts with minimal permissions
- Store credentials in secure environment variable systems
- Use different credentials for development/staging/production

**❌ Don't:**
- Put credentials in configuration files
- Commit `.env` files to version control
- Share production credentials across environments
- Use default or weak passwords
- Log credential values

### Environment File Security

```bash
# Secure file permissions
chmod 600 .env
chmod 600 .env.production
chmod 600 .env.staging

# Ensure .env files are in .gitignore
echo ".env*" >> .gitignore
```

### Environment Variable Validation

```python
# Example validation in your application
import os
from typing import Optional

def get_required_env(key: str) -> str:
    """Get required environment variable with validation."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value

def get_optional_env(key: str, default: str) -> str:
    """Get optional environment variable with default."""
    return os.getenv(key, default)

# Usage examples
OPENAI_API_KEY = get_required_env("OPENAI_API_KEY")
LOG_LEVEL = get_optional_env("LOG_LEVEL", "INFO")
```

## 🐳 Container & Deployment Integration

### Docker Environment

```dockerfile
# Dockerfile environment variable declaration
ENV ENVIRONMENT=production
ENV LOG_LEVEL=INFO

# Runtime environment variables (set during container run)
# docker run -e OPENAI_API_KEY=sk-... -e REDIS_URL=redis://... agentmap
```

### Kubernetes Deployment

```yaml
# kubernetes-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentmap
spec:
  template:
    spec:
      containers:
      - name: agentmap
        image: agentmap:latest
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: agentmap-secrets
              key: openai-api-key
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: agentmap-config
              key: redis-url
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Deploy to Production
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    REDIS_URL: ${{ secrets.REDIS_URL }}
    ENVIRONMENT: production
  run: |
    python -m agentmap deploy
```

## 🔍 Troubleshooting Environment Variables

### Common Issues

**Missing Environment Variables:**
```bash
# Check if variable is set
echo $OPENAI_API_KEY

# List all AgentMap-related environment variables
env | grep AGENTMAP

# Validate required variables
python -c "import os; print('OPENAI_API_KEY' in os.environ)"
```

**Invalid Credential Format:**
```bash
# OpenAI API keys should start with 'sk-'
echo $OPENAI_API_KEY | grep '^sk-'

# Anthropic API keys should start with 'sk-ant-api03-'
echo $ANTHROPIC_API_KEY | grep '^sk-ant-api03-'
```

**Environment File Loading:**
```python
# Test environment file loading
from dotenv import load_dotenv
import os

load_dotenv()  # Load .env file
print(f"OpenAI Key: {os.getenv('OPENAI_API_KEY', 'Not found')}")
```

### Debugging Environment Configuration

```yaml
# Enable debug logging for environment variable resolution
logging:
  loggers:
    agentmap.config:
      level: DEBUG
      
# Add environment validation to configuration
validation:
  validate_environment: true
  required_variables:
    - OPENAI_API_KEY
    - ANTHROPIC_API_KEY
  optional_variables:
    - REDIS_URL
    - LANGSMITH_API_KEY
```

## 📖 Next Steps

1. **Set up your [.env file](examples#environment-file-examples)** - Configure for your environment
2. **Review [Configuration Examples](examples)** - See complete setups with environment variables
3. **Test your configuration** - Validate all credentials and connections
4. **Implement [security best practices](#security-best-practices)** - Secure your deployment

Ready to see complete configuration examples? Continue to the [Configuration Examples](examples) guide.
