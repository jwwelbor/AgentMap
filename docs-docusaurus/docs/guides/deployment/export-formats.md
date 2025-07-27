---
sidebar_position: 1
title: Export Formats Guide
description: Complete guide to AgentMap's export formats for development, production, and sharing workflows
keywords: [export, python, source, debug, documentation, deployment, CI/CD]
---

# Export Formats Guide

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <strong>Export Formats</strong></span>
</div>

AgentMap provides four distinct export formats, each optimized for specific use cases in the development and deployment lifecycle. Understanding when and how to use each format is crucial for effective workflow management.

## Overview of Export Formats

| Format | Purpose | Output | Use Cases |
|--------|---------|--------|-----------|
| **python** | Production deployment | Executable Python code with imports | Production systems, Docker containers, standalone scripts |
| **source** | Development scaffolding | Basic code template | Quick prototyping, code scaffolding, learning |
| **debug** | Development & troubleshooting | Enhanced code with metadata | Debugging, development analysis, code review |
| **documentation** | Sharing & collaboration | Markdown or HTML docs | Documentation, sharing, team communication |

## Python Format

The **python** format generates fully executable Python code ready for production deployment. This format includes all necessary imports, proper StateGraph construction, and complete agent implementations.

### Features

- **Complete executable code** with all required imports
- **LangGraph StateGraph construction** with proper initialization
- **Custom state schema support** (dict, Pydantic models, custom classes)
- **Automatic agent and function imports** from your custom implementations
- **Production-ready structure** suitable for deployment

### Usage

```bash
# Basic python export
agentmap export --graph MyWorkflow --format python --output workflow.py

# With custom state schema
agentmap export --graph MyWorkflow --format python \  
  --state-schema "pydantic:MyStateModel" --output workflow.py

# Using custom module path
agentmap export --graph MyWorkflow --format python \
  --state-schema "myapp.schemas.WorkflowState" --output workflow.py
```

### Example Output

```python
from langgraph.graph import StateGraph
from agentmap.agents.builtins.openai_agent import OpenAIAgent
from agentmap.agents.builtins.anthropic_agent import AnthropicAgent
from agentmap.agents.custom.data_analyzer_agent import DataAnalyzerAgent
from agentmap.functions.route_by_confidence import route_by_confidence
from myapp.schemas.workflow_state import WorkflowState

# Graph: CustomerAnalysisWorkflow
builder = StateGraph(WorkflowState)

# Add nodes with full configuration
builder.add_node("validate_input", 
    DataAnalyzerAgent(
        name="validate_input",
        prompt="Validate customer data for completeness and accuracy",
        context={"input_fields": ["customer_data"], "output_field": "validation_result"}
    ))

builder.add_node("process_analysis", 
    OpenAIAgent(
        name="process_analysis",
        prompt="Analyze customer behavior patterns and generate insights",
        context={"input_fields": ["customer_data", "validation_result"], "output_field": "analysis_report"}
    ))

builder.set_entry_point("validate_input")
graph = builder.compile()
```

### State Schema Options

**Dict Schema (Default):**
```bash
agentmap export --graph MyWorkflow --format python --state-schema "dict"
```

**Pydantic Models:**
```bash
agentmap export --graph MyWorkflow --format python --state-schema "pydantic:CustomerState"
```

**Custom Classes:**
```bash
agentmap export --graph MyWorkflow --format python --state-schema "myapp.models.WorkflowState"
```

### Production Deployment

The python format is ideal for production deployments:

```dockerfile
# Dockerfile example
FROM python:3.11-slim

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY exported_workflow.py .
COPY custom_agents/ ./custom_agents/
COPY custom_functions/ ./custom_functions/

CMD ["python", "exported_workflow.py"]
```

## Source Format

The **source** format generates basic code templates suitable for scaffolding and prototyping. This format provides the essential graph structure without full implementation details.

### Features

- **Minimal code structure** with core graph building
- **Basic StateGraph construction** 
- **Node definitions** with agent types
- **Entry point configuration**
- **Lightweight output** for quick iteration

### Usage

```bash
# Basic source export
agentmap export --graph MyWorkflow --format source --output scaffold.py

# Alternative syntax
agentmap export --graph MyWorkflow --format src --output scaffold.py
```

### Example Output

```python
builder = StateGraph(dict)
builder.add_node("validate_input", DataAnalyzerAgent())
builder.add_node("process_analysis", OpenAIAgent())
builder.add_node("generate_report", DefaultAgent())
builder.set_entry_point("validate_input")
graph = builder.compile()
```

### Use Cases

- **Rapid prototyping** when you need quick graph structure
- **Code scaffolding** for new implementations
- **Learning and exploration** of graph architectures
- **Template generation** for similar workflows

## Debug Format (Advanced)

The **debug** format is a powerful development tool that combines executable code with comprehensive metadata and debugging information. This format is **completely undocumented** in current CLI help but fully supported.

### Features

- **Complete graph metadata** with node details, agent types, and relationships
- **Prompt inspection** with truncated display for long prompts
- **Edge mapping** showing all graph connections
- **Executable code section** with full Python implementation
- **Development insights** for troubleshooting workflows

### Usage

```bash
# Export with debug information
agentmap export --graph MyWorkflow --format debug --output debug_analysis.py
```

### Example Output

```python
# Debug Export for Graph: CustomerAnalysisWorkflow
# State Schema: dict
# Generated by GraphOutputService

# === GRAPH STRUCTURE ===

# Node: validate_input
#   Agent Type: DataAnalyzerAgent
#   Inputs: ['customer_data']
#   Output: validation_result
#   Prompt: Validate customer data for completeness and accuracy. Check for required fields...
#   Edges: {'success': 'process_analysis', 'failure': 'handle_error'}

# Node: process_analysis
#   Agent Type: OpenAIAgent
#   Inputs: ['customer_data', 'validation_result']
#   Output: analysis_report
#   Prompt: Analyze customer behavior patterns using the validated data. Generate insights...
#   Edges: {'success': 'generate_report', 'failure': 'retry_analysis'}

# === EXECUTABLE CODE ===

from langgraph.graph import StateGraph
from agentmap.agents.builtins.openai_agent import OpenAIAgent
# ... full executable implementation follows
```

### Development Workflow

Use debug format for:

1. **Understanding complex workflows** before modification
2. **Code review preparation** with full context
3. **Troubleshooting node relationships** and edge configurations
4. **Documentation generation** for development teams

## Documentation Format (Advanced)

The **documentation** format generates human-readable documentation in Markdown or HTML. This format is also **completely undocumented** but provides powerful documentation capabilities.

### Features

- **Structured documentation** with node descriptions and relationships
- **Multiple output formats** (Markdown, HTML)
- **Prompt documentation** with code formatting
- **Edge relationship mapping**
- **Professional presentation** suitable for sharing

### Usage

```bash
# Generate Markdown documentation
agentmap export --graph MyWorkflow --format documentation --output workflow_docs.md

# Generate HTML documentation  
agentmap export --graph MyWorkflow --format documentation --output workflow_docs.html
```

### Markdown Example Output

```markdown
# Graph: CustomerAnalysisWorkflow

## Overview
This document describes the structure and flow of the `CustomerAnalysisWorkflow` graph.

## Nodes

### validate_input
- **Agent Type**: DataAnalyzerAgent
- **Inputs**: customer_data
- **Output**: validation_result
- **Description**: Validates incoming customer data for completeness

**Prompt:**
```
Validate customer data for completeness and accuracy. 
Check for required fields and data quality issues.
```

**Edges:**
- `success` → `process_analysis`
- `failure` → `handle_error`

### process_analysis
- **Agent Type**: OpenAIAgent
- **Inputs**: customer_data, validation_result
- **Output**: analysis_report
- **Description**: Analyzes customer behavior patterns
```

### HTML Output Features

The HTML format includes:
- **Professional styling** with CSS
- **Structured layout** with proper headings
- **Code syntax highlighting** for prompts
- **Responsive design** for different screen sizes

## Choosing the Right Format

### Development Phase

**Early Development:** Use **source** format for rapid prototyping and experimentation.

```bash
# Quick scaffolding for new workflow
agentmap export --graph ExperimentalFlow --format source --output prototype.py
```

**Active Development:** Use **debug** format to understand and troubleshoot workflows.

```bash
# Detailed analysis for debugging
agentmap export --graph ProductionFlow --format debug --output analysis.py
```

### Production Deployment

**Production Systems:** Use **python** format for complete, deployable code.

```bash
# Production-ready export
agentmap export --graph ProductionFlow --format python \
  --state-schema "pydantic:ProductionState" --output production_workflow.py
```

### Documentation & Sharing

**Team Communication:** Use **documentation** format for sharing workflows.

```bash
# Generate team documentation
agentmap export --graph CustomerFlow --format documentation --output team_docs.md
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Export Workflows
on:
  push:
    branches: [main]

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install AgentMap
        run: pip install agentmap
        
      - name: Export Production Workflows
        run: |
          # Export each production workflow
          agentmap export --graph CustomerOnboarding --format python \
            --output ./dist/customer_onboarding.py
          agentmap export --graph OrderProcessing --format python \
            --output ./dist/order_processing.py
            
      - name: Generate Documentation
        run: |
          # Generate documentation for all workflows
          agentmap export --graph CustomerOnboarding --format documentation \
            --output ./docs/customer_onboarding.md
          agentmap export --graph OrderProcessing --format documentation \
            --output ./docs/order_processing.md
            
      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: exported-workflows
          path: |
            ./dist/
            ./docs/
```

### Docker Build Integration

```dockerfile
# Multi-stage Docker build with workflow export
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Export workflows during build
COPY workflows/ ./workflows/
COPY custom_agents/ ./custom_agents/
COPY custom_functions/ ./custom_functions/

RUN agentmap export --graph ProductionWorkflow --format python \
    --output production_workflow.py

# Production stage
FROM python:3.11-slim as production

WORKDIR /app
COPY --from=builder /app/production_workflow.py .
COPY --from=builder /app/custom_agents/ ./custom_agents/
COPY --from=builder /app/custom_functions/ ./custom_functions/

CMD ["python", "production_workflow.py"]
```

## Advanced Export Options

### State Schema Configuration

**Complex Pydantic Models:**
```python
# Define in schemas/advanced_state.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class AdvancedWorkflowState(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    processing_stage: str = Field(default="initial", description="Current processing stage")
    data_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    error_log: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)
    metadata: Optional[dict] = Field(default=None)
```

```bash
# Export with complex state schema
agentmap export --graph ComplexWorkflow --format python \
  --state-schema "pydantic:AdvancedWorkflowState" \
  --output advanced_workflow.py
```

### Batch Export Operations

```bash
# Export multiple formats for the same workflow
for format in python source debug documentation; do
  agentmap export --graph ProductionFlow --format $format \
    --output "exports/production_flow_${format}.py"
done

# Export all graphs in different formats
for graph in $(agentmap list-graphs); do
  agentmap export --graph $graph --format python \
    --output "dist/${graph,,}.py"
  agentmap export --graph $graph --format documentation \
    --output "docs/${graph,,}.md"
done
```

## Error Handling and Troubleshooting

### Common Export Issues

**Missing Custom Agents:**
```bash
# Error: Custom agent not found
❌ Export failed: Agent type 'CustomAnalyzer' not found

# Solution: Scaffold missing agents first
agentmap scaffold --graph MyWorkflow
agentmap export --graph MyWorkflow --format python --output workflow.py
```

**Invalid State Schema:**
```bash
# Error: Cannot import state schema
❌ Export failed: Failed to import custom schema 'myapp.BadSchema'

# Solution: Verify schema exists and is importable
python -c "from myapp.schemas import GoodSchema; print('Schema valid')"
agentmap export --graph MyWorkflow --format python \
  --state-schema "myapp.schemas.GoodSchema" --output workflow.py
```

**Output Path Issues:**
```bash
# Error: Permission denied
❌ Export failed: Permission denied: /protected/path/

# Solution: Use writable directory or current directory
agentmap export --graph MyWorkflow --format python --output ./workflow.py
```

### Validation Before Export

```bash
# Validate workflow before exporting
agentmap validate-csv --csv workflows.csv
agentmap export --graph ValidatedWorkflow --format python --output production.py
```

## Performance Considerations

### Export Optimization

**Large Workflows:** Use appropriate format for file size:
- **source**: Smallest output, fastest export
- **python**: Medium size, includes all imports
- **debug**: Largest output, comprehensive information
- **documentation**: Variable size, depends on prompt length

**Batch Operations:** Export multiple workflows efficiently:
```bash
# Sequential export (slower)
agentmap export --graph A --format python --output a.py
agentmap export --graph B --format python --output b.py

# Parallel export (faster for many workflows)
parallel -j4 agentmap export --graph {} --format python --output {}.py ::: A B C D
```

### Memory Usage

**Large Prompts:** Debug format includes full prompts, which can be memory-intensive for workflows with very large prompts. Consider using python format for production systems with memory constraints.

**State Schema Complexity:** Complex Pydantic models increase export time and output size. Use dict schema for simple workflows.

## Related Documentation

### 🚀 **Getting Started**
- **[CLI Commands Reference](../../deployment/04-cli-commands)**: Complete CLI command documentation
- **[Quick Start Guide](../../getting-started)**: Build your first workflow
- **[Understanding Workflows](../learning/)**: Core workflow concepts

### 🔧 **Development Tools**
- **[Export Reference](../../reference/export-reference)**: Complete export command reference
- **[CLI Deployment Guide](../../deployment/05-cli-deployment)**: Production deployment strategies
- **[Validation Commands](../../deployment/08-cli-validation)**: Workflow validation tools

### 🏗️ **Production Deployment**
- **[Docker Deployment](../integrations/docker)**: Container deployment strategies
- **[CI/CD Integration](../integrations/cicd)**: Automated deployment pipelines
- **[State Management](../development/state-management)**: Advanced state schema patterns

### 🤖 **Advanced Features**
- **[Service Injection](../../contributing/service-injection)**: Dependency injection patterns
- **[Custom Agent Development](../development/agents/agent-development)**: Building custom agents
- **[Function Development](../development/functions/)**: Custom function implementation
