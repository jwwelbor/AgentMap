# CSV Reference: Multi-Output Fields

## Quick Reference

| Feature | Syntax | Example | Notes |
|---------|--------|---------|-------|
| Single Output | `field_name` | `result` | Backward compatible |
| Multi-Output | `field1\|field2\|field3` | `parsed\|row_count\|status` | Pipe-delimited |
| Field Names | Valid Python identifier | `valid_rows`, `error_code`, `data_v2` | Letters, numbers, underscores |
| Spacing | Optional around pipes | `a\|b\|c` or `a \| b \| c` | Automatically trimmed |

## Output_Field Column Specification

The `Output_Field` column in CSV graph definitions declares what fields an agent produces.

### Single Output (Backward Compatible)

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge
pipeline,MyNode,MyAgent,input_field,result,NextNode
```

**Result in state:** `{result: "value"}`

### Multi-Output (New)

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge
pipeline,MyNode,MyAgent,input_field,field1|field2|field3,NextNode
```

**Result in state:** `{field1: val1, field2: val2, field3: val3}`

## Complete Field Reference

### Column: Output_Field

**Purpose:** Declares all fields this agent adds to the workflow state

**Format:**
- Single field: `field_name`
- Multiple fields: `field1|field2|field3`

**Parsing Rules:**
1. If contains pipe (`|`): treated as multi-output
2. If no pipe: treated as single output (even if list notation)
3. Each field is trimmed of whitespace
4. Empty strings after split are ignored

**Validation:**
- Each field name must be a valid Python identifier
- No special characters except underscore
- Cannot be Python keywords (e.g., `class`, `def`, `return`)
- Cannot be empty or whitespace-only

### Examples

#### Multi-Output Examples

```csv
# Basic multi-output
Output_Field: parsed|row_count|status

# With status and error handling
Output_Field: result|status|error_code|error_message

# Complex example
Output_Field: valid_rows|invalid_rows|validation_count|validation_errors

# Data + metadata
Output_Field: data|timestamp|source|version
```

#### Single Output Examples

```csv
# Traditional single
Output_Field: result

# Still works (no pipe)
Output_Field: save_result

# With underscore (valid identifier)
Output_Field: processed_data
```

### Invalid Examples (Will Fail Validation)

```csv
# Invalid: spaces in name (no underscores allowed)
Output_Field: field 1|field 2

# Invalid: Python keyword
Output_Field: class|def|return

# Invalid: special characters
Output_Field: field@1|field#2

# Invalid: empty field (extra pipe)
Output_Field: field1||field2
```

## State Integration

### How Output Fields Become State

Each field declared in `Output_Field` is added to the workflow state:

```csv
Node,Output_Field
ParseData,parsed|row_count|parse_status
```

**Agent Process Method:**
```python
def process(self, inputs):
    return {
        "parsed": [...],
        "row_count": 100,
        "parse_status": "success"
    }
```

**Resulting State Update:**
```python
state = {
    # ... existing state ...
    "parsed": [...],
    "row_count": 100,
    "parse_status": "success"
}
```

### Input Field Requirements

Downstream agents request specific fields via `Input_Fields`:

```csv
Node,Input_Fields,Output_Field
ParseData,raw_data|config,parsed|row_count|parse_status
ValidateData,parsed|row_count,valid_rows|errors|validation_status
```

**ValidateData receives:**
```python
inputs = {
    "parsed": [...],
    "row_count": 100
}
```

Notice: `parse_status` is available in state but not requested by this agent.

## Output Validation Configuration

### Validation Mode Settings

Add `output_validation` to control how AgentMap validates agent returns:

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,output_validation
pipeline,ParseData,ParseAgent,raw_data,parsed|row_count|status,warn
pipeline,ValidateData,ValidateAgent,parsed,valid|errors,error
```

**Modes:**

| Mode | Behavior | Default? | Use Case |
|------|----------|----------|----------|
| `ignore` | Silent | No | Trust agent implementation |
| `warn` | Log warnings, continue | **Yes** | Development/debugging |
| `error` | Raise exception, fail | No | Production/strict enforcement |

### How Validation Works

#### ignore Mode
```python
# Agent declares: field1|field2|field3
# Agent returns: {"field1": val1}  (missing field2, field3)
# Result: {"field1": val1} added to state
# Log: Nothing
```

#### warn Mode (Default)
```python
# Agent declares: field1|field2|field3
# Agent returns: {"field1": val1}  (missing field2, field3)
# Result: {"field1": val1} added to state
# Log: WARNING - missing declared output fields: ['field2', 'field3']
```

#### error Mode
```python
# Agent declares: field1|field2|field3
# Agent returns: {"field1": val1}  (missing field2, field3)
# Result: ValueError raised, workflow stops
# Log: ERROR - ValueError with clear message
```

### Extra Fields Filtering

When agent returns fields not declared, they're automatically filtered:

```python
# Agent declares: result|status
# Agent returns: {
#     "result": value,
#     "status": "ok",
#     "debug_info": {...},      # Extra - filtered out
#     "timing": {...}           # Extra - filtered out
# }
# Final state: {"result": value, "status": "ok"}
```

**Logging depends on validation mode:**
- `ignore`: Silent
- `warn`: Logs which extra fields were filtered
- `error`: Raises exception for extra fields

## Type Handling

### Scalar Returns in Multi-Output

When agent declares multi-output but returns scalar:

```csv
# Declared multi-output
Output_Field: result|status|count
```

```python
# Agent returns scalar
def process(self, inputs):
    return "simple string"
```

**Behavior depends on validation mode:**

- `ignore`: `{"result": "simple string"}` (wrapped in first field)
- `warn`: Same as ignore, with warning logged
- `error`: Exception raised

### Dictionary Return in Single-Output

Single-output agents can still return dict:

```csv
Output_Field: result
```

```python
def process(self, inputs):
    return {"result": "value"}  # Still works
```

**Result:** `{"result": "value"}` in state

## Pipe Delimiters in Field Values

Field names cannot contain pipes, but values can:

```python
# Field names (in CSV)
# ✓ Good
Output_Field: data|separator|format

# ✗ Bad - pipe in field name
Output_Field: data|with|pipes|in|name  # Ambiguous!
```

**But values can contain pipes:**
```python
def process(self, inputs):
    return {
        "data": ["a|b", "c|d"],        # OK - pipe in value
        "separator": "|",               # OK - pipe in value
        "format": "field1|field2|field3" # OK - pipe in value
    }
```

## Backward Compatibility

### Single-Output Agent Conversion

**Before:**
```csv
Output_Field: result
```

**After (Multi-Output):**
```csv
Output_Field: result|status|metadata
```

**Agent Code:**
```python
# Before
def process(self, inputs):
    return "done"

# After
def process(self, inputs):
    return {
        "result": "done",
        "status": "success",
        "metadata": {}
    }
```

**State Access:**
```python
# Before
state["result"]  # "done"

# After
state["result"]    # "done"
state["status"]    # "success"
state["metadata"]  # {}
```

### Mixed Workflows

Workflows can mix single and multi-output agents:

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge
pipeline,Node1,Agent1,input,output1|output2|output3,Node2
pipeline,Node2,Agent2,output1,result,Node3
pipeline,Node3,Agent3,result|output2,final_output,
```

Node1 uses multi-output, Node2 and Node3 use single-output.

## CSV Column Definition

### Full CSV Structure with Multi-Output

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,Extra,output_validation
graph_name,NodeName,AgentType,field1|field2,out1|out2|out3,NextNode,"{...}",warn
```

**Columns:**

| Column | Required | Example | Notes |
|--------|----------|---------|-------|
| GraphName | Yes | `pipeline` | Workflow identifier |
| Node | Yes | `ParseData` | Unique node name |
| AgentType | Yes | `ParseAgent` | Agent class or builtin |
| Input_Fields | Yes | `raw_data\|config` | Pipe-delimited list |
| Output_Field | Yes | `parsed\|count\|status` | Pipe-delimited list (new feature) |
| Edge | Yes | `NextNode` or empty | Next node or empty for terminal |
| Extra | No | JSON config | Additional agent configuration |
| output_validation | No | `warn`, `error`, `ignore` | Validation mode (default: `warn`) |

## Parsing Algorithm

### How AgentMap Parses Output_Field

```
Input: "field1|field2|field3"

Step 1: Split by "|"
→ ["field1", "field2", "field3"]

Step 2: Strip whitespace from each
→ ["field1", "field2", "field3"]

Step 3: Filter empty strings
→ ["field1", "field2", "field3"]

Step 4: If one element → single-output, else → multi-output
→ Multi-output with 3 fields

Step 5: Validate field names
→ Check each is valid Python identifier
→ Success if all valid
```

### Edge Cases

```
"field1"           → ["field1"]        → Single output
"field1|"          → ["field1"]        → Single output (trailing pipe removed)
"|field1"          → ["field1"]        → Single output (leading pipe removed)
"field1||field2"   → ["field1", "field2"] → 2 fields (empty middle removed)
"field1 | field2"  → ["field1", "field2"] → 2 fields (spaces trimmed)
" "                → []                → Error (no valid fields)
""                 → []                → Error (no fields)
```

## JSON Extra Column for Validation Mode

Use the `Extra` column to configure output validation per node:

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,Extra
pipeline,ParseData,ParseAgent,raw_data,parsed|count|status,Validate,"{""output_validation"": ""error""}"
```

## Examples by Use Case

### Data Processing Workflow

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,output_validation
etl,Extract,ExtractAgent,source_path,raw_data|extract_count|extract_status,Transform,warn
etl,Transform,TransformAgent,raw_data|extract_count,transformed|transform_count|transform_status,Load,warn
etl,Load,LoadAgent,transformed|transform_count,load_status,
```

### Error Handling Pattern

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,output_validation
process,Main,MainAgent,input,result|success|error_code,Finalize,error
process,Finalize,FinalizeAgent,result|success,output,
```

### Data Validation Pipeline

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,output_validation
validate,CheckSchema,SchemaAgent,data,schema_valid|schema_errors,CheckContent,error
validate,CheckContent,ContentAgent,data|schema_valid,content_valid|content_errors,Report,error
validate,Report,ReportAgent,schema_valid|content_valid|schema_errors|content_errors,report,
```

## Performance Notes

- **Pipe parsing**: O(n) where n = number of fields (typically 1-10)
- **Field validation**: O(n) identifier checks
- **State merge**: Native Python dict merge, negligible overhead
- **No serialization**: Fields stay as Python objects in state

## See Also

- [Multi-Output Feature Guide](../features/multi-output-agents.md) - Complete feature documentation
- [Agent Development](../guides/agent-development.md) - Writing agents
- [Workflow Examples](../examples/workflows.md) - Example workflows
