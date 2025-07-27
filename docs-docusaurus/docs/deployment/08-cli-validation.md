---
sidebar_position: 8
title: CLI Validation Commands
description: Complete reference for AgentMap CLI validation commands with examples, options, and best practices
keywords: [CLI commands, validation, workflow validation, CSV validation, configuration validation, cache management]
---

# CLI Validation Commands

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>CLI Validation Commands</strong></span>
</div>

AgentMap provides comprehensive CLI validation commands to ensure your workflows, configuration files, and system setup are correct before execution. These commands integrate seamlessly with development workflows and CI/CD pipelines.

## Command Overview

The validation system provides several specialized commands:

- **`agentmap validate csv`**: Validate CSV workflow files with graph consistency checks
- **`agentmap validate config`**: Validate YAML configuration files with schema validation
- **`agentmap validate all`**: Comprehensive validation of both CSV and config files
- **`agentmap validate cache`**: Manage validation cache for performance optimization

## CSV Validation Command

Validate CSV workflow definition files with comprehensive structure and logic checks.

### Basic Usage

```bash
agentmap validate csv [OPTIONS]
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--csv` | `-c` | Path to CSV file to validate | Uses config default |
| `--no-cache` | | Skip cache and force re-validation | `false` |
| `--config` | | Path to custom config file | `agentmap_config.yaml` |

### Examples

**Validate Specific CSV File**:
```bash
agentmap validate csv --csv workflows/customer_onboarding.csv
```

**Force Fresh Validation (Bypass Cache)**:
```bash
agentmap validate csv --csv workflows/customer_onboarding.csv --no-cache
```

**Use Custom Configuration**:
```bash
agentmap validate csv --csv workflows/flow.csv --config configs/development.yaml
```

**Validate Default CSV (from config)**:
```bash
agentmap validate csv
```

### Sample Output

**Successful Validation**:
```
🔍 Validating CSV file: workflows/customer_onboarding.csv
✅ CSV file format is valid
ℹ️ CSV contains 12 rows and 7 columns
ℹ️ Found 1 graph(s): 'customer_onboarding' (12 nodes)
ℹ️ Found 4 unique agent types: GPTAgent, HumanAgent, EmailAgent, ValidationAgent
ℹ️ Graph 'customer_onboarding' has multiple potential entry points: 'start', 'manual_entry'
ℹ️ Node 'final_approval' has no outgoing edges (terminal node)
✅ CSV validation passed!
```

**Validation with Issues**:
```
🔍 Validating CSV file: workflows/broken_workflow.csv

❌ CSV Validation Errors:
  1. Duplicate node 'validate_email' in graph 'customer_flow'
     Line 5
  2. Node 'process_payment' references non-existent target 'send_confirmtion' in Edge
     Line 6, Field: Edge, Value: send_confirmtion
     Suggestion: Valid targets: validate_email, process_payment, send_confirmation

⚠️ CSV Validation Warnings:
  1. Unknown agent type: 'GPTAgnet'
     Line 3, Field: AgentType, Value: GPTAgnet
     Suggestion: Check spelling or ensure agent is properly registered/available
  2. Node 'complex_analysis' has a large prompt (500+ characters)
     Line 8, Field: Prompt
     Suggestion: Consider breaking into smaller, focused prompts

ℹ️ Validation complete with 2 errors and 2 warnings
```

### Validation Checks Performed

**Structure Validation**:
- Required columns presence (`GraphName`, `Node`)
- Optional columns recognition
- Column alias support and normalization
- Data format and consistency

**Row-Level Validation**:
- Required field completeness
- Input/Output field format validation
- Routing logic consistency
- Field value constraints

**Graph Consistency**:
- Duplicate node detection within graphs
- Node reference validation
- Entry and terminal point identification
- Routing path verification

**Agent Validation**:
- Agent type availability checking
- Agent registry verification
- Custom agent accessibility

## Config Validation Command

Validate YAML configuration files with comprehensive schema and environment checks.

### Basic Usage

```bash
agentmap validate config [OPTIONS]
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config` | `-c` | Path to config file to validate | `agentmap_config.yaml` |
| `--no-cache` | | Skip cache and force re-validation | `false` |

### Examples

**Validate Default Configuration**:
```bash
agentmap validate config
```

**Validate Specific Configuration**:
```bash
agentmap validate config --config configs/production.yaml
```

**Force Fresh Validation**:
```bash
agentmap validate config --config configs/staging.yaml --no-cache
```

### Sample Output

**Successful Validation**:
```
🔍 Validating configuration file: agentmap_config.yaml
✅ Configuration file format is valid
ℹ️ Found 5 configuration sections: paths, llm, execution, tracing, memory
✅ Configuration schema validation passed
ℹ️ Custom agents directory will be created: ./custom_agents
ℹ️ OpenAI API key found in environment variable OPENAI_API_KEY
ℹ️ LLM providers configured: openai, anthropic
✅ Config validation passed!
```

**Validation with Issues**:
```
🔍 Validating configuration file: configs/production.yaml

❌ Config Validation Errors:
  1. Schema validation error: Expected boolean, got string
     Field: execution.parallel_execution, Value: "true"
  2. OpenAI API key appears to be a placeholder
     Field: llm.openai.api_key, Value: your_api_key_here
     Suggestion: Replace with your actual API key

⚠️ Config Validation Warnings:
  1. No API key configured for anthropic
     Field: llm.anthropic.api_key
     Suggestion: Set api_key in config or ANTHROPIC_API_KEY environment variable
  2. Tracing enabled but project name not configured
     Field: tracing.project
     Suggestion: Set a meaningful project name for tracing

ℹ️ Validation complete with 2 errors and 2 warnings
```

### Validation Checks Performed

**YAML Structure**:
- Valid YAML syntax
- Root-level dictionary format
- Section organization and naming
- Common typo detection

**Schema Validation**:
- Pydantic model compliance
- Type checking and constraints
- Required field validation
- Field format verification

**Path Validation**:
- File and directory existence
- Path accessibility and permissions
- Parent directory validation
- Extension consistency checking

**LLM Configuration**:
- API key format and presence
- Environment variable checking
- Model name validation
- Provider-specific settings

**Cross-Reference Validation**:
- Tracing configuration completeness
- Execution policy consistency
- Inter-section dependency verification

## Comprehensive Validation Command

Validate both CSV and configuration files in a single comprehensive check.

### Basic Usage

```bash
agentmap validate all [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--csv` | Path to CSV file to validate | Uses config default |
| `--config` | Path to config file to validate | `agentmap_config.yaml` |
| `--no-cache` | Skip cache and force re-validation | `false` |
| `--fail-on-warnings` | Treat warnings as errors (exit code 1) | `false` |
| `--config-file` | Path to initialization config file | None |

### Examples

**Validate All with Defaults**:
```bash
agentmap validate all
```

**Specify Both Files**:
```bash
agentmap validate all --csv workflows/main.csv --config configs/prod.yaml
```

**Strict Validation (Fail on Warnings)**:
```bash
agentmap validate all --fail-on-warnings
```

**CI/CD Pipeline Usage**:
```bash
agentmap validate all --no-cache --fail-on-warnings
```

### Sample Output

**Successful Validation**:
```
🔍 Running complete validation
Files:
  CSV: workflows/customer_flow.csv
  Config: agentmap_config.yaml

🔍 CSV validation completed successfully
✅ CSV file format is valid
ℹ️ Found 1 graph(s): 'customer_onboarding' (8 nodes)

🔍 Config validation completed successfully  
✅ Configuration schema validation passed
ℹ️ LLM providers configured: openai

✅ All validation passed!
```

**Validation with Mixed Results**:
```
🔍 Running complete validation

🔍 CSV validation completed successfully
✅ All CSV checks passed

❌ Config Validation Errors:
  1. CSV path does not exist: ./missing_workflow.csv
     Field: csv_path

⚠️ Config Validation Warnings:
  1. No API key configured for anthropic
     Field: llm.anthropic.api_key

ℹ️ Complete validation finished with 1 error and 1 warning
```

### Exit Codes

| Exit Code | Condition |
|-----------|-----------|
| `0` | All validation passed, or warnings only (without `--fail-on-warnings`) |
| `1` | Validation errors found, or warnings with `--fail-on-warnings` |

## Cache Management Command

Manage the validation cache system for optimal performance and troubleshooting.

### Basic Usage

```bash
agentmap validate cache [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--stats` | Show cache statistics and performance metrics |
| `--clear` | Clear all validation cache files |
| `--cleanup` | Remove expired cache entries only |
| `--file PATH` | Clear cache for specific file only |

### Examples

**View Cache Statistics**:
```bash
agentmap validate cache --stats
```

**Clear All Cache**:
```bash
agentmap validate cache --clear
```

**Remove Expired Entries**:
```bash
agentmap validate cache --cleanup
```

**Clear Cache for Specific File**:
```bash
agentmap validate cache --file workflows/customer_flow.csv
```

### Sample Output

**Cache Statistics**:
```
📊 Validation Cache Statistics
Total cache entries: 23
Valid cache entries: 18
Expired cache entries: 3
Corrupted cache entries: 2
Cache directory: ~/.agentmap/validation_cache
Total cache size: 256 KB

Cache performance:
Recent cache hits: 85%
Average cache age: 4.2 hours
Oldest valid entry: 18 hours ago

Recent activity:
✅ workflows/main.csv (cached 2 hours ago)
✅ agentmap_config.yaml (cached 4 hours ago)
⏰ workflows/old_flow.csv (expired 26 hours ago)
❌ workflows/broken.csv (corrupted cache)
```

**Cache Operations**:
```bash
# Clear all cache
agentmap validate cache --clear
# Cleared 23 cache entries

# Cleanup expired only  
agentmap validate cache --cleanup
# Removed 3 expired cache entries

# Clear specific file
agentmap validate cache --file workflows/test.csv
# Cleared cache for workflows/test.csv
```

## Command Integration and Workflows

### Development Workflow

**Typical Development Cycle**:
```bash
# 1. Start development - validate existing state
agentmap validate all

# 2. Make changes to CSV workflow
# Edit workflows/customer_flow.csv

# 3. Validate changes immediately  
agentmap validate csv --csv workflows/customer_flow.csv

# 4. Update configuration if needed
# Edit agentmap_config.yaml

# 5. Validate configuration changes
agentmap validate config

# 6. Final comprehensive validation
agentmap validate all

# 7. Commit changes (validation passing)
git commit -m "Updated customer workflow"
```

### CI/CD Integration

**Build Pipeline Integration**:
```bash
# Pre-deployment validation script
#!/bin/bash
set -e

echo "🔍 Starting comprehensive validation..."

# Clear cache for fresh validation
agentmap validate cache --clear

# Run strict validation
agentmap validate all --no-cache --fail-on-warnings

if [ $? -eq 0 ]; then
    echo "✅ Validation passed - deployment authorized"
else
    echo "❌ Validation failed - deployment blocked"
    exit 1
fi
```

**Environment-Specific Validation**:
```bash
# Development: Allow warnings
agentmap validate all || echo "Review warnings before proceeding"

# Staging: Warn about issues but don't block
agentmap validate all --fail-on-warnings || echo "Address issues before production"

# Production: Strict validation required
agentmap validate all --no-cache --fail-on-warnings
```

### Performance Optimization

**Cache-Aware Development**:
```bash
# During active development (use cache)
agentmap validate csv --csv current_workflow.csv

# For critical validations (bypass cache)
agentmap validate all --no-cache

# Regular maintenance
agentmap validate cache --cleanup
```

**Batch Validation**:
```bash
# Validate multiple workflows efficiently
for workflow in workflows/*.csv; do
    agentmap validate csv --csv "$workflow"
done

# Comprehensive project validation
agentmap validate all --config configs/development.yaml
agentmap validate all --config configs/staging.yaml  
agentmap validate all --config configs/production.yaml
```

## Troubleshooting Common Issues

### Cache-Related Issues

**Cache Performance Problems**:
```bash
# Check cache effectiveness
agentmap validate cache --stats

# If hit rate is low, clear and rebuild cache
agentmap validate cache --clear
agentmap validate all  # Rebuild cache
```

**Stale Cache Issues**:
```bash
# Force fresh validation
agentmap validate all --no-cache

# Clear cache for specific problematic file
agentmap validate cache --file problematic_workflow.csv
```

### Validation Errors

**File Not Found Errors**:
```bash
# Check current directory and file paths
ls -la workflows/
ls -la configs/

# Use absolute paths if needed
agentmap validate csv --csv /full/path/to/workflow.csv
```

**Permission Errors**:
```bash
# Check file permissions
ls -la workflows/workflow.csv

# Check cache directory permissions
ls -la ~/.agentmap/validation_cache/
```

### Environment Issues

**Missing Dependencies**:
```bash
# Verify AgentMap installation
agentmap --version

# Check Python environment
python --version
pip list | grep agentmap
```

**Environment Variable Issues**:
```bash
# Check required environment variables
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Validate configuration with environment setup
agentmap validate config --config configs/production.yaml
```

## Best Practices for CLI Usage

### Command Selection

**Use Specific Commands During Development**:
```bash
# When working on CSV files
agentmap validate csv --csv specific_workflow.csv

# When updating configuration
agentmap validate config --config specific_config.yaml

# For comprehensive pre-commit checks
agentmap validate all
```

### Flag Usage Guidelines

**Cache Management**:
- **Default behavior**: Use cache for faster development iterations
- **`--no-cache`**: Use in CI/CD pipelines and for troubleshooting
- **Cache commands**: Use for maintenance and performance monitoring

**Error Handling**:
- **Default behavior**: Allow warnings during development
- **`--fail-on-warnings`**: Use for production deployments and strict validation
- **Exit codes**: Integrate with scripts and automation

### Performance Optimization

**Development Speed**:
```bash
# Fast iteration during development
agentmap validate csv --csv current_file.csv  # Uses cache

# Comprehensive validation before commits  
agentmap validate all  # Uses cache

# Clean validation for deployments
agentmap validate all --no-cache --fail-on-warnings
```

**Resource Management**:
```bash
# Regular maintenance
agentmap validate cache --cleanup  # Weekly
agentmap validate cache --clear    # Monthly or after major updates
```

## Related Documentation

- **[Validation System Overview](/docs/guides/development/validation)**: Complete validation system architecture
- **[CSV Validation Guide](/docs/guides/development/csv-validation)**: Detailed CSV validation capabilities
- **[Config Validation Guide](/docs/guides/development/config-validation)**: Configuration validation specifics
- **[Validation Cache Management](/docs/guides/development/validation-cache)**: Cache system details
- **[Validation Best Practices](/docs/guides/development/validation-best-practices)**: Development workflow integration
- **[CSV Schema Reference](/docs/reference/csv-schema)**: Complete CSV format specification
- **[Configuration Reference](/docs/reference/configuration)**: Configuration file format and options

## Next Steps

1. **Start Validating**: Begin using validation commands in your development workflow
2. **Integrate with CI/CD**: Add validation to your deployment pipeline
3. **Optimize Performance**: Use cache management for faster development
4. **Learn Best Practices**: Review [validation best practices](/docs/guides/development/validation-best-practices) for optimal workflows
