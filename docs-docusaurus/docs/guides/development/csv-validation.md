---
sidebar_position: 9
title: CSV Validation Guide
description: Comprehensive guide to CSV workflow validation including structure, graph consistency, and agent validation
keywords: [CSV validation, workflow validation, graph consistency, agent types, routing validation]
---

# CSV Validation Guide

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <a href="/docs/guides/development">Development</a> → <strong>CSV Validation</strong></span>
</div>

The CSV validation system ensures your workflow definition files are structurally correct, logically consistent, and ready for compilation. This guide covers all aspects of CSV validation from basic structure to advanced graph topology checks.

## Validation Overview

CSV validation operates at multiple levels to ensure comprehensive workflow integrity:

1. **Structure Validation**: Column presence, naming, and basic format
2. **Row-level Validation**: Individual row data using Pydantic models
3. **Graph Consistency**: Workflow topology and node relationships
4. **Agent Validation**: Agent type availability and configuration
5. **Routing Logic**: Edge definitions and navigation paths

## Column Validation

### Required Columns

Every CSV workflow file must contain these essential columns:

- **`GraphName`**: Name of the workflow graph
- **`Node`**: Unique identifier for each node within the graph

### Optional Columns

Additional columns provide functionality and configuration:

- **`AgentType`**: Specifies which agent handles the node
- **`Prompt`**: Instructions or template for the agent
- **`Description`**: Human-readable description of the node
- **`Context`**: Additional context or configuration data
- **`Input_Fields`**: Pipe-separated list of input field names
- **`Output_Field`**: Name of the output field produced
- **`Edge`**: Direct routing to next node
- **`Success_Next`**: Node to route to on successful execution
- **`Failure_Next`**: Node to route to on failure

### Column Alias Support

The system supports flexible column naming with case-insensitive matching:

```csv
# These are all equivalent to "GraphName"
GraphName, graph_name, Graph, WorkflowName, workflow_name, workflow

# These are all equivalent to "Node"  
Node, node_name, NodeName, Step, StepName, name

# These are all equivalent to "AgentType"
AgentType, agent_type, Agent, Type
```

**Normalization Process**:
1. Column names are matched case-insensitively
2. Aliases are automatically converted to canonical names
3. Validation proceeds with normalized column names

## Row-Level Validation

Each CSV row is validated using a Pydantic model to ensure data integrity:

### Required Field Validation

```python
# Required fields cannot be empty or whitespace-only
GraphName: "customer_onboarding"  # ✅ Valid
Node: "validate_email"            # ✅ Valid

GraphName: ""                     # ❌ Error: cannot be empty
Node: "   "                       # ❌ Error: cannot be whitespace only
```

### Input Fields Validation

Input fields must follow pipe-separated format with valid field names:

```csv
# Valid input field formats
Input_Fields: "email|name|phone"           # ✅ Multiple fields
Input_Fields: "user_data"                  # ✅ Single field  
Input_Fields: "customer-info|preferences" # ✅ With dashes
Input_Fields: ""                           # ✅ Empty (optional)

# Invalid formats
Input_Fields: "field with spaces"         # ❌ Spaces not allowed
Input_Fields: "field@domain"              # ❌ Special characters not allowed
```

### Output Field Validation

Output fields must be valid identifiers:

```csv
# Valid output field names
Output_Field: "processed_email"    # ✅ Valid identifier
Output_Field: "result"             # ✅ Simple name
Output_Field: "customer-data"      # ✅ With dash

# Invalid output field names  
Output_Field: "result data"        # ❌ Spaces not allowed
Output_Field: "result@processed"   # ❌ Special characters not allowed
```

### Routing Logic Validation

The system validates routing configurations to prevent conflicts:

```csv
# Valid: Direct routing
GraphName,Node,Edge
workflow1,start,process_data

# Valid: Conditional routing  
GraphName,Node,Success_Next,Failure_Next
workflow1,validate,approved,rejected

# Invalid: Conflicting routing
GraphName,Node,Edge,Success_Next
workflow1,node1,next_node,success_node  # ❌ Cannot use both Edge and Success/Failure_Next
```

## Graph Consistency Validation

### Duplicate Node Detection

Each node name must be unique within its graph:

```csv
GraphName,Node
customer_flow,validate_email    # ✅ First instance
customer_flow,process_payment   # ✅ Different node
customer_flow,validate_email    # ❌ Error: Duplicate node in same graph

# Valid: Same node name in different graphs
customer_flow,validate_email    # ✅ Valid
admin_flow,validate_email       # ✅ Valid (different graph)
```

### Node Reference Validation

All edge targets must reference existing nodes within the same graph:

```csv
# Valid references
GraphName,Node,Edge
workflow1,start,process_data
workflow1,process_data,end

# Invalid reference
GraphName,Node,Edge  
workflow1,start,nonexistent_node  # ❌ Error: Target node doesn't exist
```

### Entry Point Detection

The system identifies potential workflow entry points:

- **Entry Points**: Nodes with no incoming edges from other nodes
- **Multiple Entry Points**: Warning if multiple nodes could be starting points
- **No Entry Points**: Warning if all nodes have incoming edges (potential cycle)

```csv
# Clear entry point example
GraphName,Node,Edge
workflow1,start,middle     # start = entry point (no incoming edges)
workflow1,middle,end       # middle has incoming edge from start
workflow1,end,             # end = terminal point (no outgoing edges)
```

### Terminal Node Detection

The system identifies workflow endpoints:

- **Terminal Nodes**: Nodes with no outgoing edges
- **No Terminal Nodes**: Warning if all nodes have outgoing edges (potential infinite loop)

## Agent Type Validation

### Agent Registry Check

The system validates agent types against the available agent registry:

```csv
# Valid agent types (if registered)
AgentType: "GPTAgent"           # ✅ Valid if registered
AgentType: "HumanAgent"         # ✅ Built-in agent type
AgentType: "CustomEmailAgent"   # ✅ Valid if custom agent exists

# Unknown agent types
AgentType: "NonexistentAgent"   # ⚠️ Warning: Unknown agent type
AgentType: "GPTAgnet"           # ⚠️ Warning: Possible typo
```

### Agent Availability Verification

The validator checks if agent classes can be instantiated:

- **Built-in Agents**: Always available
- **Custom Agents**: Must be in the custom agents directory
- **Function-based Agents**: Must be in the functions directory

## Function Reference Validation

The system handles function references in routing:

```csv
# Function reference in routing
GraphName,Node,Edge
workflow1,decision,func:determine_next_node(result)

# Validation behavior:
# ✅ Function reference detected and noted
# ℹ️ Info: Cannot validate target nodes (determined at runtime)
# ⚠️ Warning: If function is not found in functions directory
```

## Validation Output Examples

### Successful Validation

```bash
🔍 Validating CSV file: workflows/customer_onboarding.csv
✅ CSV file format is valid
ℹ️ CSV contains 8 rows and 6 columns  
ℹ️ Found 1 graph(s): 'customer_onboarding' (8 nodes)
ℹ️ Found 3 unique agent types: GPTAgent, HumanAgent, EmailAgent
ℹ️ Graph 'customer_onboarding' has multiple potential entry points: 'start', 'manual_entry'
ℹ️ Node 'final_approval' has no outgoing edges (terminal node)
✅ Validation completed successfully
```

### Validation with Errors

```bash
🔍 Validating CSV file: workflows/broken_workflow.csv
❌ CSV Validation Errors:
  1. Required column missing: 'Node'
  2. Duplicate node 'validate_email' in graph 'customer_flow'
     Line 5
  3. Node 'process_payment' references non-existent target 'send_confirmtion' in Edge
     Line 6, Field: Edge, Value: send_confirmtion
     Suggestion: Valid targets: validate_email, process_payment, send_confirmation

⚠️ CSV Validation Warnings:
  1. Unknown agent type: 'GPTAgnet'
     Line 3, Field: AgentType, Value: GPTAgnet
     Suggestion: Check spelling or ensure agent is properly registered/available
```

## Common Validation Errors

### Structural Errors

**Missing Required Columns**
```
❌ Required column missing: 'GraphName'
Solution: Add GraphName column to your CSV
```

**Empty Required Fields**
```  
❌ Row validation error: Field cannot be empty or just whitespace
Line 3, Field: Node
Solution: Provide a non-empty node name
```

### Graph Consistency Errors

**Duplicate Nodes**
```
❌ Duplicate node 'process_data' in graph 'workflow1'  
Line 5, Field: Node
Solution: Use unique node names within each graph
```

**Invalid Node References**
```
❌ Node 'start' references non-existent target 'proces_data' in Edge
Line 2, Field: Edge, Value: proces_data
Suggestion: Valid targets: process_data, validate_input, end
Solution: Fix typo in target node name
```

### Routing Logic Errors

**Conflicting Edge Definitions**
```
❌ Cannot have both Edge and Success/Failure_Next defined
Solution: Use either direct routing (Edge) or conditional routing (Success/Failure_Next)
```

## Best Practices

### CSV Structure

1. **Consistent Naming**: Use consistent column names throughout your project
2. **Clear Node Names**: Use descriptive, unique node names
3. **Logical Grouping**: Group related nodes in the same graph
4. **Documentation**: Use Description column for complex nodes

### Graph Design

1. **Clear Entry Points**: Design workflows with obvious starting points
2. **Defined Endpoints**: Ensure workflows have clear termination conditions  
3. **Error Handling**: Use Success/Failure routing for robust error handling
4. **Function Usage**: Leverage function references for dynamic routing

### Development Workflow

1. **Validate Early**: Run validation after structural changes
2. **Fix Errors First**: Address errors before warnings
3. **Review Warnings**: Investigate warnings to prevent future issues
4. **Use Cache**: Let caching speed up repeated validations

## Advanced Features

### Graph Statistics

The validator provides insights about your workflow structure:

```
ℹ️ Found 2 graph(s): 'main_flow' (12 nodes), 'error_handler' (4 nodes)
ℹ️ Graph 'main_flow' has multiple potential entry points: 'start', 'resume'  
ℹ️ Found 5 unique agent types: GPTAgent, HumanAgent, EmailAgent, ValidationAgent, ProcessorAgent
```

### Performance Optimization

The validator can identify potential performance issues:

```
⚠️ Node 'complex_analysis' has a large prompt (500+ characters)
Line 8, Field: Prompt
Suggestion: Consider breaking into smaller, focused prompts
```

## Related Documentation

- **[Validation System Overview](./validation)**: Complete validation system architecture  
- **[CSV Schema Reference](/docs/reference/csv-schema)**: Detailed CSV format specification
- **[CLI Validation Commands](/docs/deployment/08-cli-validation)**: Command-line validation tools
- **[Agent Development](/docs/guides/development/agents/agent-development)**: Creating custom agents
- **[Best Practices](./validation-best-practices)**: Development workflow integration

## Next Steps

1. **Validate Your CSV**: Run `agentmap validate csv --csv your_workflow.csv`
2. **Fix Any Issues**: Address errors and warnings systematically
3. **Configure Validation**: Set up [config validation](./config-validation) for complete workflow validation
4. **Integrate Cache**: Use [cache management](./validation-cache) for optimal performance
