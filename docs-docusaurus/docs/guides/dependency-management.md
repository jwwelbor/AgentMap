---
title: Dependency Management Guide
sidebar_position: 8
description: Comprehensive guide to AgentMap's dependency management system, provider configuration, and installation strategies
keywords: [dependency management, providers, LLM, storage, features registry, installation, configuration]
---

# Dependency Management Guide

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <strong>Dependency Management</strong></span>
</div>

AgentMap features a sophisticated dependency management system that coordinates feature policies, technical validation, and provider availability through the **DependencyCheckerService** and **FeaturesRegistryService**. This guide covers the complete dependency management architecture and best practices.

## Overview

### Dependency Management Architecture

AgentMap's dependency management operates on multiple coordinated layers:

1. **Feature Policy Layer**: Controls which features are enabled/disabled
2. **Technical Validation Layer**: Validates actual package availability and imports
3. **Registry Coordination Layer**: Maintains centralized provider status
4. **Installation Guidance Layer**: Provides specific installation recommendations

### Core Components

**DependencyCheckerService**: Performs technical validation of package dependencies
- Validates package imports and version requirements
- Checks provider-specific dependencies (OpenAI, Anthropic, Google, etc.)
- Provides detailed missing dependency tracking
- Generates installation suggestions

**FeaturesRegistryService**: Manages feature enablement and provider availability
- Maintains registration status for all providers
- Coordinates validation status with technical checks
- Provides unified availability status
- Detects inconsistencies between policy and technical state

## Provider Dependencies

### LLM Providers

AgentMap supports multiple LLM providers with specific dependency requirements:

#### OpenAI
```python
# Required packages
DEPENDENCIES = ["langchain_openai"]

# Installation options
pip install agentmap[openai]
# or
pip install openai>=1.0.0 langchain_openai
```

#### Anthropic (Claude)
```python
# Required packages  
DEPENDENCIES = ["langchain_anthropic"]

# Installation options
pip install agentmap[anthropic]
# or
pip install anthropic langchain_anthropic
```

#### Google (Gemini)
```python
# Required packages
DEPENDENCIES = ["langchain_google_genai"]

# Installation options
pip install agentmap[google]
# or
pip install google-generativeai langchain-google-genai
```

### Storage Providers

AgentMap supports various storage backends with different dependency requirements:

#### Core Storage (Always Available)
```python
# Built-in storage types
CORE_STORAGE = ["csv", "json", "file"]
# Dependencies: pandas (included with AgentMap)
```

#### Vector Storage
```python
# Required packages
DEPENDENCIES = ["langchain", "chromadb"]

# Installation
pip install chromadb
# or
pip install agentmap[vector]
```

#### Cloud Storage

**Firebase**
```python
# Required packages
DEPENDENCIES = ["firebase_admin"]

# Installation
pip install firebase-admin google-cloud-firestore
```

**Azure Blob Storage**
```python
# Required packages
DEPENDENCIES = ["azure-storage-blob"]

# Installation
pip install azure-storage-blob
```

**AWS S3**
```python
# Required packages
DEPENDENCIES = ["boto3"]

# Installation
pip install boto3
```

**Google Cloud Storage**
```python
# Required packages
DEPENDENCIES = ["google-cloud-storage"]

# Installation
pip install google-cloud-storage
```

## Installation Strategies

### Bundle Installation (Recommended)

Bundle installations ensure compatible versions and include all necessary dependencies:

```bash
# Install all LLM providers
pip install agentmap[llm]

# Install all storage providers
pip install agentmap[storage]

# Install specific provider bundles
pip install agentmap[openai]      # OpenAI only
pip install agentmap[anthropic]   # Anthropic only
pip install agentmap[google]      # Google only

# Install complete bundle
pip install agentmap[llm,storage]
```

### Individual Package Installation

For fine-grained control or specific environments:

```bash
# Core AgentMap without optional dependencies
pip install agentmap

# Add specific packages as needed
pip install openai>=1.0.0 langchain_openai
pip install anthropic langchain_anthropic
pip install google-generativeai langchain_google_genai
pip install chromadb
```

### Development Installation

For development environments with all capabilities:

```bash
# Install development dependencies
pip install agentmap[llm,storage,dev]

# Or install from source with all extras
git clone https://github.com/jwwelbor/AgentMap.git
cd AgentMap
pip install -e .[llm,storage,dev]
```

## Feature Configuration

### Feature Enablement

Control which features are available through configuration:

```yaml
# agentmap_config.yaml
features:
  llm: true      # Enable LLM providers
  storage: true  # Enable storage providers

# Alternative configuration format
llm:
  enabled: true
storage:
  enabled: true
```

### Provider-Specific Configuration

Configure individual providers while maintaining dependency coordination:

```yaml
# agentmap_config.yaml
features:
  llm: true
  storage: true

llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-4-turbo"
    enabled: true  # Provider-specific enablement
  
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-5-sonnet-20241022"
    enabled: true
  
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-pro"
    enabled: false  # Disable specific provider

storage:
  default_backend: "csv"
  vector:
    enabled: true
    backend: "chromadb"
  firebase:
    enabled: true
    credentials_path: "serviceAccountKey.json"
```

## Dependency Validation Workflow

### Validation Process

The dependency validation follows a specific workflow:

1. **Feature Policy Check**: Is the feature enabled in configuration?
2. **Technical Dependency Validation**: Are required packages available?
3. **Registry Status Update**: Update provider availability in registry
4. **Inconsistency Detection**: Flag mismatches between policy and technical state
5. **Installation Suggestion Generation**: Provide specific remediation steps

### Validation Commands

```bash
# Run comprehensive dependency validation
agentmap diagnose

# Check specific provider dependencies programmatically
python -c "
from agentmap.di import initialize_di
container = initialize_di()
checker = container.dependency_checker_service()

# Check LLM dependencies
for provider in ['openai', 'anthropic', 'google']:
    has_deps, missing = checker.check_llm_dependencies(provider)
    print(f'{provider}: {has_deps}, missing: {missing}')
"
```

### Registry Status Interpretation

Understanding registry status indicators:

```
Provider: ✅ Available [Registry: reg=True, val=True, avail=True]
```

- **reg=True**: Provider is registered in the system
- **val=True**: Provider has passed dependency validation
- **avail=True**: Provider is available for use

```
Provider: ⚠️ Dependencies OK but provider not available (Registration issue) [Registry: reg=True, val=True, avail=False]
```

- Indicates registry synchronization issue
- Will typically resolve on next validation cycle

```
Provider: ❌ Not available (Missing: package_name) [Registry: reg=True, val=False, avail=False]
```

- Missing technical dependencies
- Installation suggestions provided

## Version Management

### Compatible Versions

AgentMap maintains compatibility matrices for optimal package versions:

```python
# Recommended version ranges
COMPATIBLE_VERSIONS = {
    "openai": ">=1.0.0,<2.0.0",
    "anthropic": ">=0.18.0",
    "langchain": ">=0.1.0,<0.2.0",
    "langchain_openai": ">=0.0.5",
    "langchain_anthropic": ">=0.1.0",
    "langchain_google_genai": ">=0.0.6",
    "chromadb": ">=0.4.0"
}
```

### Version Conflict Resolution

When experiencing version conflicts:

```bash
# Check current versions
agentmap diagnose | grep "Package Versions"
pip list | grep -E "(openai|anthropic|langchain)"

# Install compatible versions
pip install "openai>=1.0.0,<2.0.0" "langchain>=0.1.0,<0.2.0"

# Or use bundle installation for automatic compatibility
pip uninstall agentmap openai anthropic langchain
pip install agentmap[llm,storage]  # Installs compatible versions
```

### Version Pinning for Production

For production environments, pin specific versions:

```bash
# requirements.txt
agentmap==1.4.2
openai==1.12.0
anthropic==0.18.1
langchain==0.1.11
langchain_openai==0.0.8
langchain_anthropic==0.1.4
chromadb==0.4.22
```

## Registry Management

### Registry Coordination

The features registry coordinates between policy and technical validation:

```python
# Programmatic registry management
from agentmap.di import initialize_di

container = initialize_di()
features_service = container.features_registry_service()
dependency_checker = container.dependency_checker_service()

# Check provider availability
available = features_service.is_provider_available("llm", "openai")
registered = features_service.is_provider_registered("llm", "openai")
validated = features_service.is_provider_validated("llm", "openai")

print(f"OpenAI - Available: {available}, Registered: {registered}, Validated: {validated}")

# Force validation update
has_deps, missing = dependency_checker.check_llm_dependencies("openai")
print(f"Technical validation - Has deps: {has_deps}, Missing: {missing}")
```

### Provider Aliases

The registry supports provider aliases for convenient access:

```python
# Supported aliases
PROVIDER_ALIASES = {
    "gpt": "openai",
    "claude": "anthropic", 
    "gemini": "google"
}

# Can use aliases in configuration and commands
# "gpt" automatically resolves to "openai"
```

## Installation Guidance System

### Automated Installation Suggestions

The dependency checker provides specific installation guidance:

```bash
# Example suggestions from agentmap diagnose
Installation Suggestions:
  To enable LLM agents: pip install agentmap[llm]
  For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0
  For Anthropic support: pip install agentmap[anthropic] or pip install anthropic
  For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai
  For vector storage: pip install chromadb
```

### Installation Patterns

**Progressive Installation**: Start minimal, add as needed
```bash
# Start with core
pip install agentmap

# Add LLM capability
pip install agentmap[openai]

# Add storage capability  
pip install chromadb

# Verify each addition
agentmap diagnose
```

**Complete Installation**: Install everything upfront
```bash
# One-command installation
pip install agentmap[llm,storage]

# Verify complete installation
agentmap diagnose
```

### Environment-Specific Installation

**Development Environment**:
```bash
# Development with all providers
pip install agentmap[llm,storage,dev]
```

**Production Environment**:
```bash
# Minimal production install
pip install agentmap[openai]  # Only needed provider

# Or specific packages for production
pip install agentmap openai==1.12.0 langchain_openai==0.0.8
```

**CI/CD Environment**:
```bash
# Install with cache and verification
pip install agentmap[llm] --cache-dir=/tmp/pip-cache
agentmap diagnose  # Verify in CI pipeline
```

## Advanced Dependency Management

### Custom Dependency Checking

Extend the dependency checker for custom providers:

```python
from agentmap.services.dependency_checker_service import DependencyCheckerService

class CustomDependencyChecker(DependencyCheckerService):
    CUSTOM_DEPENDENCIES = {
        "custom_llm": ["custom_llm_package>=1.0.0"],
        "custom_storage": ["custom_storage_package"]
    }
    
    def check_custom_dependencies(self, provider: str) -> tuple[bool, list[str]]:
        """Check custom provider dependencies."""
        if provider not in self.CUSTOM_DEPENDENCIES:
            return False, [f"Unknown provider: {provider}"]
        
        missing = []
        for dep in self.CUSTOM_DEPENDENCIES[provider]:
            if not self.check_dependency(dep):
                missing.append(dep)
        
        return len(missing) == 0, missing
```

### Dependency Monitoring

Monitor dependency changes in production:

```python
# dependency_monitor.py
from agentmap.core.cli.diagnostic_commands import diagnose_command
import json
import time

def monitor_dependencies():
    """Monitor dependency status and alert on changes."""
    previous_state = None
    
    while True:
        current_state = diagnose_command()
        
        if previous_state:
            # Check for changes in provider availability
            for category in ['llm', 'storage']:
                for provider, status in current_state[category].items():
                    prev_status = previous_state[category][provider]
                    if status['available'] != prev_status['available']:
                        print(f"ALERT: {category}.{provider} availability changed: "
                              f"{prev_status['available']} -> {status['available']}")
        
        previous_state = current_state
        time.sleep(300)  # Check every 5 minutes

if __name__ == "__main__":
    monitor_dependencies()
```

### Dependency Caching

Optimize dependency checking performance:

```bash
# Cache validation results
agentmap validate-cache --stats

# Clean up expired cache
agentmap validate-cache --cleanup

# Clear all cache for fresh validation
agentmap validate-cache --clear
```

## Production Best Practices

### Pre-Deployment Validation

```bash
# Comprehensive pre-deployment check
#!/bin/bash
echo "Pre-deployment dependency validation..."

# Check all dependencies
agentmap diagnose > deployment_check.log 2>&1

# Verify no critical failures
if grep -q "LLM feature enabled: False" deployment_check.log; then
    echo "FAIL: LLM feature disabled"
    exit 1
fi

# Count missing dependencies
missing_count=$(grep -c "Not available" deployment_check.log)
if [ "$missing_count" -gt 2 ]; then
    echo "FAIL: Too many missing dependencies ($missing_count)"
    exit 1
fi

echo "PASS: Dependency validation complete"
```

### Dependency Health Monitoring

```yaml
# monitoring.yaml - Example monitoring configuration
dependency_checks:
  interval: "5m"
  alerts:
    - condition: "llm_providers_available < 1"
      severity: "critical"
      message: "No LLM providers available"
    
    - condition: "registry_inconsistencies > 0"
      severity: "warning"
      message: "Registry inconsistencies detected"
    
    - condition: "cache_corrupted_files > 5"
      severity: "warning"
      message: "Cache corruption detected"
```

### Rollback Procedures

```bash
# dependency_rollback.sh - Rollback to known good state
#!/bin/bash

echo "Rolling back to known good dependency state..."

# Backup current state
pip freeze > current_requirements.txt

# Restore from known good requirements
pip install -r production_requirements.txt --force-reinstall

# Verify rollback
agentmap diagnose

echo "Rollback complete. Check agentmap diagnose output."
```

## Troubleshooting Dependency Issues

### Common Issues and Solutions

**Issue: Bundle installation fails**
```bash
# Clear pip cache and retry
pip cache purge
pip install agentmap[llm] --no-cache-dir
```

**Issue: Version conflicts**
```bash
# Check for conflicts
pip check

# Resolve with compatible versions
pip install "openai>=1.0.0,<2.0.0" "langchain>=0.1.0,<0.2.0"
```

**Issue: Registry inconsistencies persist**
```python
# Force registry refresh
from agentmap.di import initialize_di
container = initialize_di()
checker = container.dependency_checker_service()

# Re-validate all dependencies
for provider in ["openai", "anthropic", "google"]:
    checker.check_llm_dependencies(provider)

print("Registry refreshed")
```

### Diagnostic Commands

```bash
# Full dependency analysis
agentmap diagnose

# Cache analysis
agentmap validate-cache --stats

# Configuration verification
agentmap config

# Graph-specific dependency check
agentmap inspect-graph MyGraph --resolution
```

## Integration Examples

### CI/CD Pipeline Integration

```yaml
# .github/workflows/test.yml
name: Test with Dependency Validation
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install AgentMap
        run: pip install agentmap[llm,storage]
      
      - name: Validate Dependencies
        run: |
          agentmap diagnose
          # Fail if critical dependencies missing
          agentmap diagnose | grep -q "LLM feature enabled: True" || exit 1
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Run Tests
        run: pytest
```

### Docker Integration

```dockerfile
# Dockerfile with dependency management
FROM python:3.11-slim

# Install AgentMap with dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Verify dependencies in container
RUN agentmap diagnose

COPY . /app
WORKDIR /app

# Health check using dependency validation
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD agentmap diagnose --quiet || exit 1

CMD ["python", "app.py"]
```

## Related Documentation

### 🔧 **System Tools**
- **[Diagnostic Commands](/docs/deployment/cli-diagnostics)**: Complete diagnostic command reference
- **[Troubleshooting Guide](/docs/guides/troubleshooting)**: Detailed issue resolution
- **[CLI Commands](/docs/deployment/cli-commands)**: All command-line tools

### 🏗️ **Configuration**
- **[Getting Started](/docs/getting-started)**: Installation and setup
- **[Configuration Reference](/docs/reference/configuration/)**: Complete configuration options
- **[System Health Monitoring](/docs/guides/system-health)**: Production monitoring

### 🚀 **Advanced Topics**
- **[Service Architecture](/docs/reference/services/)**: Understanding services and protocols
- **[Custom Agent Development](/docs/guides/development/agents/)**: Building custom agents
- **[Production Deployment](/docs/deployment/)**: Production deployment strategies
