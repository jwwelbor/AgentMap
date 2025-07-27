---
title: Troubleshooting Guide
sidebar_position: 10
description: Comprehensive troubleshooting guide for AgentMap installation, dependency issues, and system problems
keywords: [troubleshooting, dependencies, installation, system health, diagnostics, errors]
---

# Troubleshooting Guide

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <strong>Troubleshooting</strong></span>
</div>

This comprehensive troubleshooting guide helps you diagnose and resolve common AgentMap issues using the built-in diagnostic tools, advanced error handling capabilities, and dependency management system.

## Advanced Error Handling and Recovery

### Workflow Execution Errors

**Problem**: Workflow execution fails with unclear error messages.

**Diagnosis**: Use the comprehensive exception hierarchy to understand the error domain:

```bash
# Check for specific error types in logs
grep -E "(LLMServiceError|StorageConnectionError|AgentExecutionError)" /var/log/agentmap/

# Run graph inspection for detailed analysis
agentmap inspect-graph YOUR_GRAPH --resolution
```

**Solutions by Exception Type**:

**LLM Service Errors**:
```python
# Check LLM provider status
from agentmap.core.cli.diagnostic_commands import diagnose_command
diagnostic_data = diagnose_command()
print(diagnostic_data['llm'])

# Test specific provider
python -c "import openai; client = openai.OpenAI(); print('OpenAI connection OK')"
```

**Agent Execution Errors**:
```bash
# Verify custom agents are properly implemented
ls -la custom_agents/
python -c "from custom_agents.your_agent import YourAgent; print('Agent import OK')"

# Check agent service injection
agentmap inspect-graph YOUR_GRAPH --services
```

**Storage Connection Errors**:
```bash
# Test storage connectivity
agentmap diagnose | grep -A 5 "Storage Dependencies"

# Check specific storage backend
python -c "import firebase_admin; print('Firebase OK')"  # For Firebase
python -c "import chromadb; print('ChromaDB OK')"      # For vector storage
```

### Thread Management and Recovery

**Problem**: Workflow execution interrupted or stuck in paused state.

**Diagnosis**:
```bash
# List all execution threads
agentmap threads --status all

# Get specific thread details
agentmap thread-info THREAD_ID --detailed

# Check for pending interactions
agentmap interactions --status pending
```

**Solutions**:

**Resume Interrupted Workflows**:
```bash
# Resume with approval
agentmap resume THREAD_ID approve

# Resume with data
agentmap resume THREAD_ID respond --data '{"response": "Continue processing"}'

# Resume from file
echo '{"choice": 1, "reason": "Best option"}' > response.json
agentmap resume THREAD_ID choose --data-file response.json
```

**Handle Timed-Out Interactions**:
```bash
# Check for timed-out threads
agentmap threads --status timed_out

# Reset timed-out thread
agentmap reset-thread THREAD_ID --reason "Timeout recovery"

# Resume with default action
agentmap resume THREAD_ID timeout --data '{"action": "default"}'
```

**Clear Stuck Threads**:
```bash
# Force complete stuck threads
agentmap complete-thread THREAD_ID --force

# Clean up orphaned interactions
agentmap cleanup-interactions --older-than 24h
```

### Human Interaction Issues

**Problem**: Human interaction requests not displayed or resume commands fail.

**Diagnosis**:
```bash
# Check interaction handler status
agentmap diagnose | grep -A 3 "Interaction Handler"

# Verify storage backend for interactions
agentmap storage-test --collection interactions

# List pending interactions
agentmap interactions --pending
```

**Solutions**:

**Fix Interaction Display Issues**:
```python
# Test CLI interaction handler
from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler
from agentmap.di import initialize_di

container = initialize_di()
storage_service = container.storage_service()
handler = CLIInteractionHandler(storage_service)

# Test handler functionality
print("CLI handler initialized successfully")
```

**Resolve Resume Command Failures**:
```bash
# Verify thread exists
agentmap thread-info THREAD_ID

# Check interaction request format
agentmap interaction-info REQUEST_ID

# Validate response data format
echo '{"test": "data"}' | jq .  # Validate JSON syntax

# Resume with verbose logging
agentmap resume THREAD_ID approve --verbose
```

**Handle Invalid Response Data**:
```bash
# Check required response format for interaction type
agentmap interaction-info REQUEST_ID --format-help

# Examples of correct formats:
# Approval: {"reason": "explanation"} (optional)
# Choice: {"choice": 1} or {"choice": "option_name"}
# Edit: {"edited": "new_content"}
# Text: {"text": "response"} or {"response": "text"}
```

## Quick Diagnostic Commands

Start with these essential diagnostic commands to identify issues:

```bash
# Run comprehensive system diagnostics
agentmap diagnose

# Check validation cache health
agentmap validate-cache --stats

# Inspect specific graph
agentmap inspect-graph YOUR_GRAPH_NAME

# Validate configuration
agentmap config
```

## Installation and Setup Issues

### Problem: AgentMap Installation Fails

**Symptoms**: `pip install agentmap` fails with dependency conflicts or build errors.

**Diagnosis**:
```bash
# Check Python version (3.8+ required)
python --version

# Check pip and setuptools
pip --version
pip install --upgrade pip setuptools wheel
```

**Solutions**:

**Option 1: Clean Installation**
```bash
# Create fresh virtual environment
python -m venv agentmap_env
source agentmap_env/bin/activate  # Linux/Mac
# or
agentmap_env\Scripts\activate     # Windows

# Install with all dependencies
pip install agentmap[llm,storage]
```

**Option 2: Resolve Dependency Conflicts**
```bash
# Install with no dependencies first
pip install agentmap --no-deps

# Install core dependencies manually
pip install pydantic typer pyyaml pandas

# Check what's missing
agentmap diagnose
```

### Problem: Missing Dependencies After Installation

**Symptoms**: `agentmap diagnose` shows missing packages despite successful installation.

**Diagnosis**:
```bash
agentmap diagnose
```

**Example Output**:
```
LLM Dependencies:
  Anthropic: ❌ Not available (Missing: langchain_anthropic) [Registry: reg=True, val=False, avail=False]
  OpenAI: ❌ Not available (Missing: langchain_openai) [Registry: reg=True, val=False, avail=False]
```

**Solutions**:

**Option 1: Bundle Installation (Recommended)**
```bash
# Install complete LLM bundle
pip install agentmap[llm]

# Install complete storage bundle
pip install agentmap[storage]

# Install everything
pip install agentmap[llm,storage]
```

**Option 2: Individual Package Installation**
```bash
# Based on diagnose output, install specific packages
pip install anthropic langchain_anthropic
pip install openai langchain_openai
pip install google-generativeai langchain_google_genai

# Verify installation
agentmap diagnose
```

## Dependency Management Issues

### Problem: Registry Inconsistencies

**Symptoms**: Providers show dependencies are available but marked as unavailable.

**Example Output**:
```
Google: ⚠️ Dependencies OK but provider not available (Registration issue) [Registry: reg=True, val=True, avail=False]
```

**Diagnosis**:
This indicates a synchronization issue between the dependency checker and features registry.

**Solutions**:

**Option 1: Automatic Resolution**
```bash
# The next diagnose run will typically resolve this
agentmap diagnose
```

**Option 2: Force Registry Refresh**
```python
# Run this Python code to force registry update
from agentmap.di import initialize_di
container = initialize_di()
dependency_checker = container.dependency_checker_service()

# This will refresh all provider validations
for provider in ["openai", "anthropic", "google"]:
    dependency_checker.check_llm_dependencies(provider)

print("Registry refreshed")
```

### Problem: Feature Enablement Issues

**Symptoms**: Features show as disabled despite configuration.

**Example Output**:
```
LLM Dependencies:
LLM feature enabled: False
```

**Diagnosis**:
Check your configuration file format and feature enablement.

**Solutions**:

**Check Configuration Syntax**:
```yaml
# agentmap_config.yaml - Correct format
features:
  llm: true      # Boolean, not string
  storage: true  # Boolean, not string

# Alternative format
llm:
  enabled: true
storage:
  enabled: true
```

**Common Configuration Mistakes**:
```yaml
# ❌ Wrong - strings instead of booleans
features:
  llm: "true"     # String, not boolean
  storage: "yes"  # Invalid value

# ❌ Wrong - missing features section
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
# Missing: features.llm: true

# ✅ Correct
features:
  llm: true
  storage: true
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
```

### Problem: Version Compatibility Issues

**Symptoms**: Package conflicts or incompatible versions.

**Diagnosis**:
```bash
# Check installed versions
agentmap diagnose | grep "Package Versions"
pip list | grep -E "(openai|anthropic|langchain)"
```

**Solutions**:

**Option 1: Use Compatible Versions**
```bash
# Install known compatible versions
pip install "openai>=1.0.0,<2.0.0"
pip install "anthropic>=0.18.0"
pip install "langchain>=0.1.0,<0.2.0"
pip install "langchain_openai>=0.0.5"
pip install "langchain_anthropic>=0.1.0"
```

**Option 2: Fresh Installation with Bundles**
```bash
# Remove all related packages
pip uninstall -y agentmap openai anthropic langchain langchain_openai langchain_anthropic

# Install with bundles (ensures compatibility)
pip install agentmap[llm,storage]

# Verify
agentmap diagnose
```

## Storage and File System Issues

### Problem: Vector Storage Not Available

**Symptoms**: Vector storage shows as unavailable despite installation.

**Example Output**:
```
Storage Dependencies:
  vector: ❌ Not available (Missing: chromadb) [Registry: reg=True, val=False, avail=False]
```

**Solutions**:

**Install ChromaDB**:
```bash
# Install ChromaDB
pip install chromadb

# For additional vector database support
pip install weaviate-client  # Weaviate
pip install pinecone-client  # Pinecone

# Verify installation
agentmap diagnose
```

**ChromaDB Installation Issues**:
```bash
# If ChromaDB fails to install
pip install --upgrade pip setuptools wheel
pip install chromadb --no-cache-dir

# On Windows, may need Visual C++ Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

### Problem: Firebase Storage Configuration

**Symptoms**: Firebase storage unavailable despite having credentials.

**Example Output**:
```
Storage Dependencies:
  firebase: ❌ Not available (Missing: firebase_admin) [Registry: reg=True, val=False, avail=False]
```

**Solutions**:

**Install Firebase Dependencies**:
```bash
pip install firebase-admin google-cloud-firestore
```

**Configure Firebase Credentials**:
```yaml
# agentmap_storage_config.yaml
firebase:
  credentials_path: "path/to/serviceAccountKey.json"
  project_id: "your-project-id"
  database_url: "https://your-project.firebaseio.com"
```

### Problem: Cloud Storage Authentication

**Symptoms**: Cloud storage providers show as unavailable.

**Solutions**:

**AWS S3 Setup**:
```bash
# Install AWS SDK
pip install boto3

# Configure credentials (choose one method)
aws configure  # AWS CLI method
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
```

**Google Cloud Storage Setup**:
```bash
# Install Google Cloud SDK
pip install google-cloud-storage

# Authenticate (choose one method)
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
```

**Azure Blob Storage Setup**:
```bash
# Install Azure SDK
pip install azure-storage-blob

# Configure connection string
export AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
```

## LLM Provider Issues

### Problem: OpenAI API Key Issues

**Symptoms**: OpenAI provider unavailable despite having API key.

**Diagnosis**:
```bash
# Check if API key is properly configured
echo $OPENAI_API_KEY

# Test API key directly
python -c "
import openai
openai.api_key = 'your-api-key'
print('API key is valid')
"
```

**Solutions**:

**Environment Variable Configuration**:
```bash
# Set environment variable
export OPENAI_API_KEY="sk-your-api-key-here"

# Or in .env file
echo "OPENAI_API_KEY=sk-your-api-key-here" >> .env
```

**Configuration File Setup**:
```yaml
# agentmap_config.yaml
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"  # Reference to environment variable
    model: "gpt-4-turbo"
    temperature: 0.7
```

### Problem: Anthropic Claude API Issues

**Symptoms**: Anthropic provider shows dependencies but fails to connect.

**Solutions**:

**Check API Key Format**:
```bash
# Anthropic API keys start with 'sk-ant-'
export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
```

**Test Connection**:
```python
# Test Anthropic connection
import anthropic
client = anthropic.Anthropic(api_key="your-api-key")
print("Anthropic API connection successful")
```

**Configuration Example**:
```yaml
# agentmap_config.yaml
llm:
  anthropic:
    api_key: "env:ANTHROPIC_API_KEY"
    model: "claude-3-sonnet-20240229"
    temperature: 0.7
```

### Problem: Google Gemini API Setup

**Symptoms**: Google provider dependencies available but connection fails.

**Solutions**:

**Install Google Dependencies**:
```bash
pip install google-generativeai langchain_google_genai
```

**Configure API Key**:
```bash
# Google API key configuration
export GOOGLE_API_KEY="your-google-api-key"
```

**Configuration Example**:
```yaml
# agentmap_config.yaml
llm:
  google:
    api_key: "env:GOOGLE_API_KEY"
    model: "gemini-pro"
    temperature: 0.7
```

## Performance and Cache Issues

### Problem: Slow Validation Performance

**Symptoms**: AgentMap commands run slowly, especially validation.

**Diagnosis**:
```bash
# Check cache statistics
agentmap validate-cache --stats
```

**Example Output Indicating Issues**:
```
Validation Cache Statistics:
==============================
Total files: 450
Valid files: 400
Expired files: 45    # High number of expired files
Corrupted files: 5   # Corrupted cache files
```

**Solutions**:

**Clean Up Cache**:
```bash
# Remove expired entries
agentmap validate-cache --cleanup

# If problems persist, clear all cache
agentmap validate-cache --clear

# Verify improvement
agentmap validate-cache --stats
```

### Problem: Memory Issues with Large Graphs

**Symptoms**: Out of memory errors or very slow performance with large workflows.

**Solutions**:

**Optimize Graph Structure**:
- Break large graphs into smaller sub-graphs
- Use compiled graphs for production
- Implement streaming for large data processing

**Cache Management**:
```bash
# Compile graphs for better performance
agentmap compile --graph LargeWorkflow

# Monitor cache usage
agentmap validate-cache --stats
```

## Configuration Issues

### Problem: Configuration File Not Found

**Symptoms**: AgentMap can't locate configuration file.

**Solutions**:

**Specify Configuration Explicitly**:
```bash
# Use specific config file
agentmap run --config /path/to/agentmap_config.yaml --graph MyGraph

# Set environment variable
export AGENTMAP_CONFIG_PATH="/path/to/agentmap_config.yaml"
```

**Create Default Configuration**:
```bash
# Create config in current directory
cat > agentmap_config.yaml << EOF
csv_path: "workflows/"
autocompile: true

features:
  llm: true
  storage: true

llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-4-turbo"
EOF
```

### Problem: Path Configuration Issues

**Symptoms**: AgentMap can't find CSV files or custom agents.

**Diagnosis**:
```bash
# Check current configuration
agentmap config
```

**Solutions**:

**Use Absolute Paths**:
```yaml
# agentmap_config.yaml - Use absolute paths
csv_path: "/full/path/to/workflows/"
custom_agents_path: "/full/path/to/custom_agents/"
compiled_graphs_path: "/full/path/to/compiled/"
```

**Verify Path Accessibility**:
```bash
# Check if paths exist and are accessible
ls -la "$(agentmap config | grep 'CSV Path' | cut -d: -f2 | xargs)"
```

## Graph Execution Issues

### Problem: Graph Fails to Execute

**Symptoms**: Graph execution fails with unclear errors.

**Diagnosis**:
```bash
# Inspect graph structure and dependencies
agentmap inspect-graph MyGraph --resolution

# Check for missing agents
agentmap inspect-graph MyGraph --config-details
```

**Solutions**:

**Resolve Missing Agents**:
```bash
# Generate missing custom agents
agentmap scaffold --graph MyGraph

# Check what agents are available
agentmap inspect-graph MyGraph
```

**Validate Graph Structure**:
```bash
# Validate CSV structure
agentmap validate-csv --csv workflow.csv

# Compile graph to catch issues early
agentmap compile --graph MyGraph
```

## Development and Custom Agent Issues

### Problem: Custom Agents Not Loading

**Symptoms**: Custom agents show as missing despite being in the directory.

**Diagnosis**:
```bash
# Check custom agents directory
ls -la custom_agents/

# Verify agent imports
python -c "import sys; sys.path.append('custom_agents'); import your_agent"
```

**Solutions**:

**Fix Import Issues**:
```python
# Ensure proper base class inheritance
from agentmap.agents.base_agent import BaseAgent

class YourAgent(BaseAgent):
    def process(self, inputs):
        # Your implementation
        return result
```

**Check Directory Structure**:
```
custom_agents/
├── __init__.py          # Required for Python package
├── your_agent.py
└── another_agent.py
```

### Problem: Service Integration Issues

**Symptoms**: Custom agents can't access LLM or storage services.

**Solutions**:

**Implement Service Protocols**:
```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent

class MyAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent):
    def process(self, inputs):
        # Access LLM service
        if hasattr(self, 'llm_service') and self.llm_service:
            response = self.llm_service.call_llm(
                provider="openai",
                messages=[{"role": "user", "content": "Hello"}]
            )
        
        # Access storage service
        if hasattr(self, 'storage_service') and self.storage_service:
            data = self.storage_service.read("csv", "data.csv")
        
        return response
```

## Network and Connectivity Issues

### Problem: API Rate Limiting

**Symptoms**: Requests fail with rate limit errors.

**Solutions**:

**Configure Rate Limiting**:
```yaml
# agentmap_config.yaml
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    rate_limit:
      requests_per_minute: 60
      tokens_per_minute: 40000
```

**Implement Retry Logic**:
```python
# Custom agent with retry logic
import time
from agentmap.agents.base_agent import BaseAgent

class ResilientAgent(BaseAgent):
    def process(self, inputs, max_retries=3):
        for attempt in range(max_retries):
            try:
                # Your API call here
                return result
            except RateLimitError:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise
```

### Problem: Proxy or Firewall Issues

**Symptoms**: API calls timeout or fail to connect.

**Solutions**:

**Configure Proxy Settings**:
```bash
# Set proxy environment variables
export HTTP_PROXY="http://proxy.company.com:8080"
export HTTPS_PROXY="https://proxy.company.com:8080"
export NO_PROXY="localhost,127.0.0.1"
```

**Test Connectivity**:
```bash
# Test direct connection to API endpoints
curl -I https://api.openai.com/v1/models
curl -I https://api.anthropic.com/v1/messages
```

## Emergency Recovery Procedures

### Complete System Reset

If you encounter persistent issues that can't be resolved:

```bash
# 1. Backup your workflows and configuration
cp -r workflows/ workflows_backup/
cp agentmap_config.yaml agentmap_config_backup.yaml

# 2. Completely remove AgentMap and dependencies
pip uninstall -y agentmap
pip uninstall -y openai anthropic google-generativeai langchain langchain_openai langchain_anthropic langchain_google_genai chromadb

# 3. Clean up cache and temporary files
rm -rf ~/.agentmap/cache/
rm -rf .agentmap/

# 4. Fresh installation
pip install --upgrade pip setuptools wheel
pip install agentmap[llm,storage]

# 5. Verify installation
agentmap diagnose

# 6. Restore configuration
cp agentmap_config_backup.yaml agentmap_config.yaml
```

### Factory Reset Configuration

```bash
# Create minimal working configuration
cat > agentmap_config.yaml << EOF
# Minimal working configuration
csv_path: "workflows/"
autocompile: true

features:
  llm: true
  storage: true

llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
    model: "gpt-3.5-turbo"  # Use basic model first

logging:
  level: "INFO"
EOF

# Test with simple workflow
echo "graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field
Test,start,input,end,,,user_input
Test,end,echo,,,user_input,result" > test_workflow.csv

agentmap run --graph Test --csv test_workflow.csv --state '{"user_input": "Hello"}'
```

## Getting Additional Help

### Diagnostic Information for Support

When seeking help, provide this diagnostic information:

```bash
# Collect comprehensive diagnostic information
echo "=== AgentMap Diagnostics ===" > agentmap_debug.log
agentmap diagnose >> agentmap_debug.log 2>&1
echo -e "\n=== Cache Statistics ===" >> agentmap_debug.log
agentmap validate-cache --stats >> agentmap_debug.log 2>&1
echo -e "\n=== Configuration ===" >> agentmap_debug.log
agentmap config >> agentmap_debug.log 2>&1
echo -e "\n=== Python Environment ===" >> agentmap_debug.log
python --version >> agentmap_debug.log
pip list | grep -E "(agentmap|openai|anthropic|langchain)" >> agentmap_debug.log

# Share agentmap_debug.log when requesting support
```

### Community Resources

- **GitHub Issues**: [Report bugs and get help](https://github.com/jwwelbor/AgentMap/issues)
- **Discussions**: [Community discussions](https://github.com/jwwelbor/AgentMap/discussions)
- **Documentation**: [Complete documentation](/docs/)

## Related Documentation

### 🔧 **Diagnostic Tools**
- **[Diagnostic Commands](/docs/deployment/cli-diagnostics)**: Complete diagnostic command reference
- **[CLI Commands](/docs/deployment/cli-commands)**: All CLI commands and options
- **[Graph Inspector](/docs/deployment/cli-graph-inspector)**: Advanced graph analysis tools

### 🛠️ **Error Handling & Recovery**
- **[Advanced Error Handling](/docs/guides/development/error-handling)**: Comprehensive error handling guide
- **[Human Interaction Workflows](/docs/guides/development/human-interaction)**: Human-in-the-loop patterns
- **[CLI Resume Commands](/docs/deployment/cli-resume)**: Workflow resumption and recovery

### 🏗️ **Setup and Configuration**
- **[Getting Started](/docs/getting-started)**: Installation and setup guide
- **[Dependency Management Guide](/docs/guides/dependency-management)**: Comprehensive dependency management
- **[Configuration Reference](/docs/reference/configuration/)**: Complete configuration options

### 🚀 **Advanced Topics**
- **[System Health Monitoring](/docs/guides/system-health)**: Production monitoring setup
- **[Custom Agent Development](/docs/guides/development/agents/)**: Building custom agents
- **[Service Integration](/docs/guides/development/services/)**: Advanced service integration
