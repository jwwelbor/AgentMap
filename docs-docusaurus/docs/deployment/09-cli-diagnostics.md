---
sidebar_position: 7
title: Diagnostic Commands
description: Comprehensive system diagnostics, dependency checking, and troubleshooting tools for AgentMap deployments
keywords: [CLI commands, diagnostics, troubleshooting, system health, dependencies, validation, registry]
---

# Diagnostic Commands

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>Diagnostic Commands</strong></span>
</div>

AgentMap provides comprehensive diagnostic tools built on the **runtime facade pattern** for system health monitoring, dependency validation, and troubleshooting. These commands leverage the sophisticated **DependencyCheckerService** and **FeaturesRegistryService** through the runtime API to provide enterprise-grade system validation and installation guidance.

## Diagnostic Architecture

### Facade Pattern Implementation

The diagnostic commands follow AgentMap's consistent facade pattern, using `runtime_api.py` for business logic:

```python
# Diagnostic command pattern
from agentmap.runtime_api import ensure_initialized, diagnose_system
from agentmap.deployment.cli.utils.cli_presenter import print_json, print_err, map_exception_to_exit_code

def diagnose_command(args):
    try:
        # Ensure runtime is initialized
        ensure_initialized(config_file=args.config)
        
        # Use runtime facade for diagnostic logic
        result = diagnose_system(config_file=args.config)
        
        # Use CLI presenter for consistent output
        print_json(result)
        
    except Exception as e:
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
```

### Runtime API Integration

Diagnostic commands use these runtime facade functions:

| Function | Purpose | Commands Using |
|----------|---------|----------------|
| `diagnose_system()` | Comprehensive system health check | `diagnose` |
| `validate_cache()` | Cache integrity validation | `validate-cache` |
| `refresh_cache()` | Cache management operations | `refresh` |
| `get_config()` | Configuration display | `config` |
| `ensure_initialized()` | Runtime initialization check | All diagnostic commands |

### CLI Presenter Integration

All diagnostic commands benefit from the standardized CLI presenter utilities:

- **Structured Output**: JSON format for automation and human-readable options
- **Exception Mapping**: Runtime exceptions mapped to appropriate exit codes for scripting
- **Custom Encoding**: Handles diagnostic objects, timestamps, and complex data structures

### Service Integration Architecture

The diagnostic commands integrate with AgentMap's sophisticated service layer:

```python
# Diagnostic command implementation
def diagnose_command(config_file):
    try:
        # Initialize runtime system via facade
        ensure_initialized(config_file=config_file)
        
        # Use facade to access DependencyCheckerService and FeaturesRegistryService
        result = diagnose_system(config_file=config_file)
        
        # Service layer provides:
        # - LLM provider validation (OpenAI, Anthropic, Google)
        # - Storage system validation (CSV, JSON, Vector, etc.)
        # - Registry status coordination
        # - Installation guidance
        
        # CLI presenter handles complex service objects
        print_json(result)
        
    except Exception as e:
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
```

### Enterprise-Grade Validation Features

**Multi-Layer Validation:**
- **Feature Policy**: Checks if features are enabled in configuration
- **Technical Dependencies**: Validates package installations and versions
- **Registry Coordination**: Ensures feature registry matches technical state
- **Inconsistency Detection**: Identifies mismatches between layers

**Installation Guidance System:**
- **Bundle Suggestions**: Recommends `agentmap[llm]` style installations
- **Individual Packages**: Provides specific pip install commands
- **Provider-Specific**: Tailored instructions for each service provider
- **Dependency Resolution**: Helps resolve complex conflicts

## System Diagnostics

The `diagnose` command performs comprehensive dependency validation and system health checking using AgentMap's enterprise-grade **DependencyCheckerService** and **FeaturesRegistryService**.

```bash
agentmap diagnose [OPTIONS]
```

### Options
- `--config`, `-c`: Path to custom config file

### Core Functionality

The diagnose command provides:

1. **LLM Provider Validation**: Checks dependencies and registry status for OpenAI, Anthropic, and Google
2. **Storage System Validation**: Validates CSV, JSON, File, Vector, Firebase, and Blob storage dependencies
3. **Registry Status Coordination**: Shows feature enablement vs dependency availability
4. **Inconsistency Detection**: Identifies mismatches between registry and actual dependencies
5. **Installation Guidance**: Provides specific pip install commands for missing dependencies
6. **Environment Information**: Shows Python version, paths, and package versions

### Example Usage

```bash
# Run comprehensive system diagnostics
agentmap diagnose

# Use specific configuration file
agentmap diagnose --config configs/production.yaml
```

### Sample Output

```
AgentMap Dependency Diagnostics
=============================

LLM Dependencies:
LLM feature enabled: True
  Openai: ✅ Available [Registry: reg=True, val=True, avail=True]
  Anthropic: ❌ Not available (Missing: langchain_anthropic) [Registry: reg=True, val=False, avail=False]
  Google: ⚠️ Dependencies OK but provider not available (Registration issue) [Registry: reg=True, val=True, avail=False]

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
  For vector storage: pip install chromadb
  For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai

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

### Dependency Validation Architecture

The diagnostic system uses a sophisticated multi-layer validation approach:

#### 1. Feature Policy Validation
- **Feature Enablement**: Checks if LLM and Storage features are enabled
- **Policy Coordination**: Coordinates feature flags with technical validation
- **Feature Registry**: Maintains centralized feature availability status

#### 2. Technical Dependency Checking
- **Package Validation**: Validates specific package dependencies for each provider
- **Version Requirements**: Checks minimum version requirements (e.g., openai>=1.0.0)
- **Import Testing**: Attempts actual imports to verify package functionality
- **Missing Dependency Tracking**: Provides specific lists of missing packages

#### 3. Registry Status Coordination
- **Registration Status**: Shows if providers are registered in the features registry
- **Validation Status**: Indicates if providers have passed dependency validation
- **Availability Status**: Shows final provider availability for use
- **Inconsistency Detection**: Identifies mismatches between technical validation and registry status

#### 4. Installation Guidance System
- **Bundle Installation**: Suggests comprehensive bundle installs (e.g., `agentmap[llm]`)
- **Individual Packages**: Provides specific package installation commands
- **Provider-Specific**: Tailored installation instructions for each LLM/storage provider
- **Dependency Resolution**: Helps resolve complex dependency conflicts

## Diagnostic Scenarios

### Dependency Installation Issues

**Scenario**: Missing LLM provider dependencies

```bash
agentmap diagnose
```

**Example Output**:
```
LLM Dependencies:
  Anthropic: ❌ Not available (Missing: langchain_anthropic) [Registry: reg=True, val=False, avail=False]
  
Installation Suggestions:
  For Anthropic support: pip install agentmap[anthropic] or pip install anthropic
```

**Resolution**:
```bash
# Install using bundle (recommended)
pip install agentmap[anthropic]

# Or install specific package
pip install anthropic

# Verify installation
agentmap diagnose
```

### Registry Inconsistency Detection

**Scenario**: Provider has dependencies but isn't available

```bash
agentmap diagnose
```

**Example Output**:
```
LLM Dependencies:
  Google: ⚠️ Dependencies OK but provider not available (Registration issue) [Registry: reg=True, val=True, avail=False]
```

**Resolution**: This indicates a registry synchronization issue. The dependency checker service will automatically resolve this on next validation cycle.

### Storage System Validation

**Scenario**: Checking vector storage availability

```bash
agentmap diagnose
```

**Example Output**:
```
Storage Dependencies:
  vector: ❌ Not available (Missing: chromadb) [Registry: reg=True, val=False, avail=False]
  
Installation Suggestions:
  For vector storage: pip install chromadb
```

**Resolution**:
```bash
# Install vector storage dependencies
pip install chromadb

# Verify vector storage is now available
agentmap diagnose
```

### Feature Enablement Issues

**Scenario**: Features disabled in configuration

```bash
agentmap diagnose
```

**Example Output**:
```
LLM Dependencies:
LLM feature enabled: False
```

**Resolution**: Check feature enablement in your configuration file:
```yaml
# agentmap_config.yaml
llm:
  enabled: true  # Ensure this is set to true
```

## Cache Management Commands

AgentMap provides sophisticated validation caching to improve performance. The cache management commands help maintain optimal system performance.

### Validation Cache Commands

```bash
agentmap validate-cache [OPTIONS]
```

**Options:**
- `--clear`: Clear all validation cache
- `--cleanup`: Remove expired cache entries
- `--stats`: Show cache statistics (default)
- `--file FILE_PATH`: Clear cache for specific file only

### Cache Statistics

```bash
# View cache statistics
agentmap validate-cache --stats
```

**Example Output:**
```
Validation Cache Statistics:
==============================
Total files: 45
Valid files: 42
Expired files: 2
Corrupted files: 1

💡 Run 'agentmap validate-cache --cleanup' to remove expired entries
⚠️  Found 1 corrupted cache files
```

### Cache Management Operations

```bash
# Clean up expired cache entries
agentmap validate-cache --cleanup

# Clear all cache
agentmap validate-cache --clear

# Clear cache for specific file
agentmap validate-cache --clear --file workflow.csv
```

## Graph Inspection Commands

The `inspect-graph` command provides detailed analysis of agent service configuration and graph structure.

### Graph Inspection

```bash
agentmap inspect-graph GRAPH_NAME [OPTIONS]
```

**Options:**
- `--csv FILE_PATH`: Path to CSV file
- `--config CONFIG_FILE`: Path to custom config file  
- `--node NODE_NAME`: Inspect specific node only
- `--services/--no-services`: Show service availability (default: true)
- `--protocols/--no-protocols`: Show protocol implementations (default: true)
- `--config-details`: Show detailed configuration
- `--resolution`: Show agent resolution details

### Graph Inspection Example

```bash
# Inspect entire graph
agentmap inspect-graph MyWorkflow

# Inspect specific node with detailed resolution info
agentmap inspect-graph MyWorkflow --node ProcessData --resolution
```

**Example Output:**
```
🔍 Inspecting Graph: MyWorkflow
==================================================

📊 Graph Overview:
   Resolved Name: MyWorkflow
   Total Nodes: 5
   Unique Agent Types: 3
   All Resolvable: ✅
   Resolution Rate: 100.0%

🤖 Node: ProcessData
   Agent Type: DataAnalyzer
   Description: Analyze data using LLM
   🔧 Resolution:
      Resolvable: ✅
      Source: Custom Agent
   📋 Services:
      llm: ✅
      storage: ✅
   🔌 Protocols:
      LLMCapableAgent: ✅
      StorageCapableAgent: ✅
   📝 Configuration:
      Input Fields: ['data', 'query']
      Output Field: analysis

✅ No issues found - all agents properly configured!

💡 Helpful Commands:
   agentmap diagnose                    # Check system dependencies
   agentmap inspect-graph MyWorkflow --config-details  # Show detailed config
   agentmap inspect-graph MyWorkflow --node NODE_NAME  # Inspect specific node
```

## Programmatic Diagnostic Access

For automation and monitoring integration, AgentMap provides programmatic access to diagnostic information:

```python
from deployment.http import diagnose_command, cache_info_command

# Get structured diagnostic data
diagnostic_data = diagnose_command()
print(diagnostic_data['llm']['openai']['available'])  # True/False
print(diagnostic_data['installation_suggestions'])  # List of suggestions

# Get cache statistics
cache_data = cache_info_command()
print(cache_data['cache_statistics']['total_files'])  # Number
```

## Production Monitoring Integration

The diagnostic commands can be integrated into production monitoring systems for automated health checking:

### Automated Health Check Script

```bash
#!/bin/bash
# health_check.sh - Production health monitoring script

echo "Running AgentMap health check..."

# Run comprehensive diagnostics
agentmap diagnose > /tmp/agentmap_health.log 2>&1

# Check for critical failures
if grep -q "LLM feature enabled: False" /tmp/agentmap_health.log; then
    echo "CRITICAL: LLM feature disabled"
    exit 2
fi

# Check for missing dependencies
missing_deps=$(grep -c "Not available" /tmp/agentmap_health.log)
if [ "$missing_deps" -gt 5 ]; then
    echo "WARNING: Multiple dependencies missing ($missing_deps)"
    exit 1
fi

# Check cache health
agentmap validate-cache --stats | grep "Corrupted files: [1-9]" && {
    echo "WARNING: Corrupted cache files detected"
    agentmap validate-cache --cleanup
}

echo "AgentMap health check passed"
exit 0
```

### Monitoring Integration Examples

**Nagios/Icinga Integration:**
```bash
# /etc/nagios/commands.cfg
define command {
    command_name    check_agentmap_health
    command_line    /usr/local/bin/agentmap_health_check.sh
}
```

**Prometheus Monitoring:**

```python
# agentmap_exporter.py
from prometheus_client import Gauge, generate_latest
from deployment.http import diagnose_command

# Create metrics
llm_providers_available = Gauge('agentmap_llm_providers_available', 'Number of available LLM providers')
storage_providers_available = Gauge('agentmap_storage_providers_available', 'Number of available storage providers')


def collect_metrics():
    data = diagnose_command()

    # Count available providers
    llm_available = sum(1 for provider in data['llm'].values() if provider['available'])
    storage_available = sum(1 for provider in data['storage'].values() if provider['available'])

    llm_providers_available.set(llm_available)
    storage_providers_available.set(storage_available)

    return generate_latest()
```

## Best Practices for System Health

### 1. Regular Dependency Validation
- **Daily Monitoring**: Run `agentmap diagnose` as part of daily operational procedures
- **Automated Scheduling**: Set up cron jobs or scheduled tasks for regular health checks
- **Dependency Drift Detection**: Monitor for changes in dependency availability over time

### 2. Pre-Deployment Validation
- **CI/CD Integration**: Include `agentmap diagnose` in deployment pipelines
- **Environment Validation**: Verify all dependencies in staging before production deployment
- **Registry Consistency**: Ensure feature registry state matches actual system capabilities

### 3. Cache Management
- **Regular Cleanup**: Schedule `agentmap validate-cache --cleanup` to remove expired entries
- **Performance Monitoring**: Monitor cache hit rates and validation performance
- **Storage Management**: Keep cache directories under 80% capacity

### 4. Dependency Management Strategy
- **Bundle Installations**: Use `agentmap[bundle]` syntax for consistent dependency management
- **Version Pinning**: Pin critical dependency versions in production environments
- **Incremental Updates**: Test dependency updates in staging environments first

### 5. Monitoring and Alerting
- **Provider Availability**: Alert on LLM or storage provider availability changes
- **Registry Inconsistencies**: Monitor for mismatches between technical validation and registry status
- **Performance Degradation**: Track validation cache performance and diagnostic command execution times

## Troubleshooting Common Issues

### Dependency Installation Problems

**Issue**: Package installation fails or dependencies not detected
```bash
# Check current status
agentmap diagnose

# Common solutions
pip install --upgrade pip setuptools wheel
pip install agentmap[llm,storage] --force-reinstall

# Verify installation
python -c "import openai, anthropic; print('LLM dependencies OK')"
```

### Registry Inconsistency Issues

**Issue**: Provider shows as having dependencies but unavailable
```bash
# Example output showing inconsistency
# Google: ⚠️ Dependencies OK but provider not available (Registration issue)

# Solution: Force registry refresh
python -c "from agentmap.di import initialize_di; c = initialize_di(); c.dependency_checker_service().validate_all_dependencies()"
```

### Feature Enablement Problems

**Issue**: Features show as disabled despite correct configuration
```yaml
# Check configuration format in agentmap_config.yaml
features:
  llm: true      # Ensure this is a boolean, not string
  storage: true  # Ensure this is a boolean, not string
```

### Cache Performance Issues

**Issue**: Slow validation or corrupted cache
```bash
# Check cache health
agentmap validate-cache --stats

# Clean up if needed
agentmap validate-cache --cleanup  # Remove expired entries
agentmap validate-cache --clear    # Clear all cache if corrupted
```

### Version Compatibility Problems

**Issue**: Package version conflicts
```bash
# Check installed versions
agentmap diagnose | grep "Package Versions"

# Fix version conflicts
pip install "openai>=1.0.0,<2.0.0" "langchain>=0.1.0,<0.2.0"

# Use bundle for compatibility
pip uninstall agentmap
pip install agentmap[llm,storage]  # Installs compatible versions
```

## Related Documentation

### 🔧 **CLI Tools & Operations**
- **[CLI Commands Reference](./04-cli-commands)**: Complete CLI command reference
- **[Validation Commands](./08-cli-validation)**: Workflow and configuration validation
- **[Graph Inspector](./06-cli-graph-inspector)**: Advanced graph analysis tools

### 📚 **Configuration & Setup**
- **[Getting Started](/docs/getting-started)**: Installation and initial setup
- **[Dependency Management Guide](/docs/guides/dependency-management)**: Comprehensive dependency management
- **[Troubleshooting Guide](/docs/guides/troubleshooting)**: Step-by-step issue resolution

### 🏗️ **Advanced Topics**
- **[System Health Monitoring](/docs/guides/system-health)**: Production health monitoring
- **[Configuration Reference](/docs/reference/configuration/)**: Complete configuration options
- **[Service Architecture](/docs/reference/services/)**: Understanding the service layer
