---
sidebar_position: 8
title: Export Reference
description: Complete reference for AgentMap export command with all formats, options, and advanced usage patterns
keywords: [export, CLI reference, python, source, debug, documentation, state schema]
---

# Export Reference

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/reference">Reference</a> → <strong>Export Reference</strong></span>
</div>

Complete reference for the `agentmap export` command, covering all supported formats, options, and advanced usage patterns.

## Command Syntax

```bash
agentmap export [OPTIONS]
```

## Required Parameters

### --graph, -g

**Type:** `string`  
**Required:** Yes  
**Description:** Name of the graph to export  

```bash
agentmap export --graph CustomerWorkflow
```

The graph name must match a graph defined in your CSV workflow file.

## Output Options

### --output, -o

**Type:** `string`  
**Default:** `generated_graph.py`  
**Description:** Output file path for the exported graph  

```bash
# Specify output file
agentmap export --graph MyWorkflow --output custom_name.py

# Specify output directory (filename auto-generated)
agentmap export --graph MyWorkflow --output ./exports/

# Full path specification
agentmap export --graph MyWorkflow --output /path/to/exports/workflow.py
```

**Auto-naming Behavior:**
- If output is a directory, filename is `{GraphName}.{extension}`
- Extension is determined by format: `.py` for python/source/debug, `.md` for documentation
- Directories are created automatically if they don't exist

## Format Options

### --format, -f

**Type:** `string`  
**Default:** `python`  
**Valid Values:** `python`, `source`, `src`, `debug`, `documentation`  
**Description:** Export format to generate  

```bash
# Python format (default)
agentmap export --graph MyWorkflow --format python

# Source code template
agentmap export --graph MyWorkflow --format source
agentmap export --graph MyWorkflow --format src  # Alternative syntax

# Debug format with metadata
agentmap export --graph MyWorkflow --format debug

# Documentation format
agentmap export --graph MyWorkflow --format documentation
```

#### Format Details

| Format | Extension | Features | Use Case |
|--------|-----------|----------|----------|
| `python` | `.py` | Complete executable code, full imports | Production deployment |
| `source`/`src` | `.py` | Basic template, minimal code | Prototyping, scaffolding |
| `debug` | `.py` | Metadata + executable code | Development, debugging |
| `documentation` | `.md`/`.html` | Human-readable docs | Sharing, documentation |

## Configuration Options

### --csv

**Type:** `string`  
**Default:** From configuration file  
**Description:** Override CSV file path  

```bash
# Use custom CSV file
agentmap export --graph MyWorkflow --csv ./custom_workflows.csv

# Use CSV from different directory
agentmap export --graph MyWorkflow --csv /path/to/workflows.csv
```

### --config, -c

**Type:** `string`  
**Default:** `agentmap_config.yaml`  
**Description:** Path to custom configuration file  

```bash
# Use custom config file
agentmap export --graph MyWorkflow --config ./configs/production.yaml
```

### --state-schema, -s

**Type:** `string`  
**Default:** `dict`  
**Description:** State schema type for graph construction  

```bash
# Default dict schema
agentmap export --graph MyWorkflow --state-schema dict

# Pydantic model
agentmap export --graph MyWorkflow --state-schema "pydantic:CustomerState"

# Custom class
agentmap export --graph MyWorkflow --state-schema "myapp.schemas.WorkflowState"
```

#### State Schema Formats

**Dict Schema (Default):**
```bash
--state-schema "dict"
```
Generates: `StateGraph(dict)`

**Pydantic Models:**
```bash
--state-schema "pydantic:ModelName"
```
Generates: `StateGraph(ModelName)` with automatic import from `agentmap.schemas.modelname`

**Custom Classes:**
```bash
--state-schema "module.path.ClassName"
```
Generates: `StateGraph(ClassName)` with import from specified module

## Format-Specific Examples

### Python Format

Complete executable code for production deployment:

```bash
# Basic python export
agentmap export \
  --graph ProductionWorkflow \
  --format python \
  --output production.py

# With Pydantic state schema
agentmap export \
  --graph ProductionWorkflow \
  --format python \
  --state-schema "pydantic:ProductionState" \
  --output production.py

# With custom state class
agentmap export \
  --graph ProductionWorkflow \
  --format python \
  --state-schema "myapp.models.WorkflowState" \
  --output production.py
```

**Generated Output:**
```python
from langgraph.graph import StateGraph
from agentmap.agents.builtins.openai_agent import OpenAIAgent
from myapp.models import WorkflowState

# Graph: ProductionWorkflow
builder = StateGraph(WorkflowState)
builder.add_node("process_input", OpenAIAgent(
    name="process_input",
    prompt="Process incoming data",
    context={"input_fields": ["data"], "output_field": "processed_data"}
))
builder.set_entry_point("process_input")
graph = builder.compile()
```

### Source Format

Basic code template for scaffolding:

```bash
# Basic source export
agentmap export \
  --graph PrototypeWorkflow \
  --format source \
  --output prototype.py

# Alternative syntax
agentmap export \
  --graph PrototypeWorkflow \
  --format src \
  --output prototype.py
```

**Generated Output:**
```python
builder = StateGraph(dict)
builder.add_node("process_input", OpenAIAgent())
builder.add_node("generate_output", DefaultAgent())
builder.set_entry_point("process_input")
graph = builder.compile()
```

### Debug Format

Enhanced format with metadata and executable code:

```bash
# Debug export for analysis
agentmap export \
  --graph DevelopmentWorkflow \
  --format debug \
  --output analysis.py
```

**Generated Output:**
```python
# Debug Export for Graph: DevelopmentWorkflow
# State Schema: dict
# Generated by GraphOutputService

# === GRAPH STRUCTURE ===

# Node: process_input
#   Agent Type: OpenAIAgent
#   Inputs: ['user_input']
#   Output: processed_data
#   Prompt: Process user input and extract key information...
#   Edges: {'success': 'generate_output', 'failure': 'handle_error'}

# === EXECUTABLE CODE ===

from langgraph.graph import StateGraph
# ... full implementation follows
```

### Documentation Format

Human-readable documentation in Markdown or HTML:

```bash
# Markdown documentation
agentmap export \
  --graph CustomerWorkflow \
  --format documentation \
  --output workflow_docs.md

# HTML documentation (auto-detected from extension)
agentmap export \
  --graph CustomerWorkflow \
  --format documentation \
  --output workflow_docs.html
```

**Markdown Output:**
```markdown
# Graph: CustomerWorkflow

## Overview
This document describes the structure and flow of the `CustomerWorkflow` graph.

## Nodes

### process_input
- **Agent Type**: OpenAIAgent
- **Inputs**: user_input
- **Output**: processed_data
- **Description**: Processes customer input data

**Prompt:**
```
Process user input and extract key information for analysis
```

**Edges:**
- `success` → `generate_output`
- `failure` → `handle_error`
```

## Advanced Usage Patterns

### Batch Export Operations

Export multiple formats for the same workflow:

```bash
# Export all formats for comprehensive analysis
for format in python source debug documentation; do
  agentmap export \
    --graph ProductionWorkflow \
    --format $format \
    --output "exports/production_${format}.py"
done
```

Export multiple workflows:

```bash
# Export all workflows in production format
for graph in CustomerOnboarding OrderProcessing PaymentFlow; do
  agentmap export \
    --graph $graph \
    --format python \
    --output "dist/${graph,,}_production.py"
done
```

### CI/CD Integration

Production deployment pipeline:

```bash
#!/bin/bash
# deploy.sh - Production deployment script

# Validate workflows
agentmap validate-csv --csv production_workflows.csv

# Export production workflows
agentmap export --graph CustomerOnboarding --format python \
  --state-schema "pydantic:CustomerState" \
  --output ./dist/customer_onboarding.py

agentmap export --graph OrderProcessing --format python \
  --state-schema "pydantic:OrderState" \
  --output ./dist/order_processing.py

# Generate documentation
agentmap export --graph CustomerOnboarding --format documentation \
  --output ./docs/customer_onboarding.md

agentmap export --graph OrderProcessing --format documentation \
  --output ./docs/order_processing.md

echo "✅ All workflows exported successfully"
```

### Docker Build Integration

Multi-stage Dockerfile with export:

```dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy workflow definitions
COPY workflows.csv .
COPY custom_agents/ ./custom_agents/
COPY custom_functions/ ./custom_functions/

# Export workflows during build
RUN agentmap export --graph ProductionWorkflow --format python \
    --state-schema "pydantic:ProductionState" \
    --output production_workflow.py

# Production stage
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /app/production_workflow.py .
COPY --from=builder /app/custom_agents/ ./custom_agents/

CMD ["python", "production_workflow.py"]
```

### Custom State Schema Examples

**Simple Pydantic Model:**
```python
# schemas/customer_state.py
from pydantic import BaseModel

class CustomerState(BaseModel):
    customer_id: str
    processing_stage: str = "initial"
    data: dict = {}
```

```bash
agentmap export --graph CustomerFlow --format python \
  --state-schema "pydantic:CustomerState" --output customer_flow.py
```

**Complex State Schema:**
```python
# myapp/schemas/advanced_state.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class AdvancedWorkflowState(BaseModel):
    workflow_id: str = Field(..., description="Unique workflow identifier")
    current_stage: str = Field(default="initial")
    processing_history: List[str] = Field(default_factory=list)
    error_count: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=datetime.now)
    metadata: Optional[dict] = Field(default=None)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

```bash
agentmap export --graph ComplexWorkflow --format python \
  --state-schema "myapp.schemas.advanced_state.AdvancedWorkflowState" \
  --output complex_workflow.py
```

## Output File Management

### Directory Structure

Recommended directory structure for exports:

```
project/
├── exports/
│   ├── production/
│   │   ├── customer_workflow.py
│   │   └── order_workflow.py
│   ├── development/
│   │   ├── customer_debug.py
│   │   └── order_debug.py
│   └── documentation/
│       ├── customer_docs.md
│       └── order_docs.md
├── workflows.csv
└── custom_agents/
```

### Automated Export Management

```bash
#!/bin/bash
# export_all.sh - Comprehensive export script

# Create directory structure
mkdir -p exports/{production,development,documentation}

# Export production versions
for graph in CustomerWorkflow OrderWorkflow; do
  agentmap export --graph $graph --format python \
    --output "exports/production/${graph,,}.py"
done

# Export debug versions
for graph in CustomerWorkflow OrderWorkflow; do
  agentmap export --graph $graph --format debug \
    --output "exports/development/${graph,,}_debug.py"
done

# Export documentation
for graph in CustomerWorkflow OrderWorkflow; do
  agentmap export --graph $graph --format documentation \
    --output "exports/documentation/${graph,,}_docs.md"
done

echo "✅ All exports completed successfully"
```

## Error Handling

### Common Errors and Solutions

**Graph Not Found:**
```bash
❌ Error: Graph 'NonExistentWorkflow' not found in CSV

# Solution: Check graph name in CSV file
grep "NonExistentWorkflow" workflows.csv
agentmap export --graph ActualWorkflowName --format python
```

**Missing Custom Agents:**
```bash
❌ Error: Agent type 'CustomAnalyzer' not found

# Solution: Scaffold missing agents first
agentmap scaffold --graph MyWorkflow
agentmap export --graph MyWorkflow --format python
```

**Invalid State Schema:**
```bash
❌ Error: Failed to import custom schema 'invalid.module'

# Solution: Verify schema module exists
python -c "from valid.module import ValidSchema"
agentmap export --graph MyWorkflow --format python \
  --state-schema "valid.module.ValidSchema"
```

**Permission Denied:**
```bash
❌ Error: Permission denied: /protected/directory/

# Solution: Use writable directory
agentmap export --graph MyWorkflow --format python \
  --output ./exports/workflow.py
```

**Output Directory Doesn't Exist:**
```bash
❌ Error: No such file or directory: '/path/to/nonexistent/'

# Solution: Export automatically creates directories
agentmap export --graph MyWorkflow --format python \
  --output /path/to/nonexistent/workflow.py  # Creates directory
```

### Validation Before Export

```bash
# Validate CSV structure before export
agentmap validate-csv --csv workflows.csv

# Validate specific graph before export
agentmap validate-csv --csv workflows.csv --graph MyWorkflow

# Export after successful validation
if agentmap validate-csv --csv workflows.csv; then
  agentmap export --graph MyWorkflow --format python --output production.py
  echo "✅ Export completed successfully"
else
  echo "❌ Validation failed, export cancelled"
  exit 1
fi
```

## Performance Optimization

### Export Performance Tips

**Large Workflows:**
- Use `source` format for fastest export (minimal processing)
- Use `python` format for production (moderate processing)
- Use `debug` format only when needed (most processing)

**Batch Operations:**
```bash
# Sequential (slower)
agentmap export --graph A --format python --output a.py
agentmap export --graph B --format python --output b.py

# Parallel (faster for multiple workflows)
export -f export_workflow
export_workflow() {
  agentmap export --graph $1 --format python --output $1.py
}

parallel export_workflow ::: WorkflowA WorkflowB WorkflowC
```

**Memory Usage:**
- `documentation` format with large prompts uses more memory
- `debug` format includes full metadata (higher memory usage)
- `source` format is most memory-efficient

### File Size Considerations

| Format | Typical Size | Factors |
|--------|-------------|---------|
| `source` | 1-5 KB | Minimal code structure |
| `python` | 5-50 KB | Full imports, complete implementation |
| `debug` | 10-100 KB | Metadata + full implementation |
| `documentation` | Variable | Depends on prompt length and descriptions |

## Environment Variables

Export command respects these environment variables:

```bash
# Configuration file override
export AGENTMAP_CONFIG_PATH="/path/to/custom/config.yaml"

# CSV file override
export AGENTMAP_CSV_PATH="/path/to/workflows.csv"

# Output directory override
export AGENTMAP_EXPORT_PATH="/path/to/exports/"

# Logging level for debugging
export AGENTMAP_LOG_LEVEL="DEBUG"

# Run export with environment overrides
agentmap export --graph MyWorkflow --format python
```

## Integration Examples

### Make Integration

```makefile
# Makefile for workflow export automation

GRAPHS := CustomerWorkflow OrderWorkflow PaymentWorkflow
EXPORT_DIR := ./exports

.PHONY: export-all export-production export-docs clean

export-all: export-production export-docs

export-production:
	@mkdir -p $(EXPORT_DIR)/production
	@for graph in $(GRAPHS); do \
		echo "Exporting $$graph..."; \
		agentmap export --graph $$graph --format python \
			--output $(EXPORT_DIR)/production/$$graph.py; \
	done

export-docs:
	@mkdir -p $(EXPORT_DIR)/documentation
	@for graph in $(GRAPHS); do \
		echo "Generating docs for $$graph..."; \
		agentmap export --graph $$graph --format documentation \
			--output $(EXPORT_DIR)/documentation/$$graph.md; \
	done

clean:
	rm -rf $(EXPORT_DIR)

# Usage: make export-all
```

### GitHub Actions Integration

```yaml
name: Export Workflows

on:
  push:
    branches: [main]
    paths: ['workflows.csv', 'custom_agents/**']

jobs:
  export:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install Dependencies
      run: |
        pip install agentmap
        
    - name: Validate Workflows
      run: |
        agentmap validate-csv --csv workflows.csv
        
    - name: Export Production Workflows
      run: |
        mkdir -p dist/
        agentmap export --graph CustomerWorkflow --format python \
          --state-schema "pydantic:CustomerState" \
          --output dist/customer_workflow.py
        agentmap export --graph OrderWorkflow --format python \
          --state-schema "pydantic:OrderState" \
          --output dist/order_workflow.py
          
    - name: Generate Documentation
      run: |
        mkdir -p docs/workflows/
        agentmap export --graph CustomerWorkflow --format documentation \
          --output docs/workflows/customer_workflow.md
        agentmap export --graph OrderWorkflow --format documentation \
          --output docs/workflows/order_workflow.md
          
    - name: Upload Artifacts
      uses: actions/upload-artifact@v3
      with:
        name: exported-workflows
        path: |
          dist/
          docs/workflows/
```

## Related Documentation

### 🚀 **Core Documentation**
- **[Export Formats Guide](../../guides/deployment/export-formats)**: Comprehensive format comparison and usage
- **[CLI Commands Reference](../../deployment/04-cli-commands)**: Complete CLI documentation
- **[CSV Schema Reference](../csv-schema)**: Workflow definition format

### 🔧 **Development Tools**
- **[Validation Commands](../../deployment/08-cli-validation)**: Workflow validation before export
- **[Scaffolding Reference](../scaffolding)**: Generate custom agents and functions
- **[State Management](../../guides/development/state-management)**: Advanced state schema patterns

### 🏗️ **Deployment & Production**
- **[CLI Deployment Guide](../../deployment/05-cli-deployment)**: Production deployment strategies
- **[Docker Integration](../../guides/integrations/docker)**: Container deployment patterns
- **[CI/CD Integration](../../guides/integrations/cicd)**: Automated deployment pipelines

### 🤖 **Advanced Features**
- **[Service Injection](../dependency-injection)**: Dependency injection patterns
- **[Agent Development](../agents/)**: Custom agent implementation
- **[Configuration Reference](../configuration/)**: Advanced configuration options
