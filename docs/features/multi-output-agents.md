# Multi-Output Feature Guide

## Overview

The multi-output feature enables agents to produce multiple output fields from a single execution, allowing complex workflows where data is processed and distributed across multiple state variables. Instead of writing complex transformation logic to split a single output, agents can directly declare and return multiple fields.

### What is Multi-Output?

In AgentMap workflows, each agent node traditionally produces a single output field that gets added to the workflow state. The multi-output feature allows agents to declare and return **multiple output fields** in a single execution.

**Before (Single Output):**
```
Agent returns: "processed_result"
State receives: {"output": "processed_result"}
```

**After (Multi-Output):**
```
Agent returns: {"result": [...], "status": "success", "count": 42}
State receives: {"result": [...], "status": "success", "count": 42}
```

## Why Use Multi-Output?

### Key Benefits

1. **Reduced Complexity**: No need for downstream agents just to split outputs
2. **Better State Design**: Each field becomes a first-class state variable
3. **Clearer Intent**: The CSV definition shows exactly what the agent produces
4. **Easier Debugging**: Each output field is independently available in state
5. **Improved Composition**: Downstream agents can depend on any combination of outputs
6. **Data Integrity**: Status, counts, and results travel together through the workflow

### Use Cases

- **Data Processing**: ParseData returns `parsed|row_count|parse_status`
- **Validation**: ValidateData returns `valid_rows|errors|validation_status`
- **ETL Workflows**: Transform returns `transformed|transform_count` and status
- **Error Handling**: Methods return both `result|error|error_code` for comprehensive feedback

## Declaring Multi-Output in CSV

### Syntax

Use pipe-delimited (`|`) field names in the `Output_Field` column:

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge
pipeline,ParseData,ParseAgent,raw_data|config,parsed|row_count|parse_status,ValidateData
pipeline,ValidateData,ValidateAgent,parsed|row_count,valid_rows|errors|validation_status,TransformData
pipeline,TransformData,TransformAgent,valid_rows,transformed|transform_count,SaveResults
```

### Key Rules

1. **Field Names**: Each output field name must be a valid Python identifier (letters, numbers, underscores)
2. **Delimiter**: Use pipe character (`|`) to separate multiple fields - no spaces around pipes
3. **Spaces**: Field names are automatically trimmed, so spaces around pipes are optional:
   - `result|status|count` (preferred)
   - `result | status | count` (also valid, trimmed automatically)
4. **Single Output**: Traditional single-output syntax still works:
   - `Output_Field: save_result` (backward compatible)
   - `Output_Field: single_field` (will be treated as list with one element)

### Examples

```csv
# Multi-output example
Output_Field: parsed|row_count|parse_status

# Single output (backward compatible)
Output_Field: result

# With spaces (automatically trimmed)
Output_Field: field1 | field2 | field3
```

## Implementing Multi-Output Agents

### Return Type Requirements

When declaring multiple outputs, your agent's `process()` method **must return a dictionary** where keys match your declared output fields.

### Valid Returns

```python
class ParseAgent(BaseAgent):
    def process(self, inputs):
        # Correct: Return dict with all declared fields
        return {
            "parsed": parsed_data,
            "row_count": len(parsed_data),
            "parse_status": "success"
        }
```

### Single Output (Still Valid)

```python
class SaveAgent(BaseAgent):
    def process(self, inputs):
        # Valid: Single output can return string directly
        return "Saved 100 records"

        # Or return dict with single field
        return {"result": "Saved 100 records"}
```

### Complete Example

```python
from agentmap.agents.base_agent import BaseAgent
from typing import Any, Dict, List

class DataParserAgent(BaseAgent):
    """Parse CSV data and return multiple outputs."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse input data and return multiple fields.

        Declared outputs: parsed|row_count|parse_status
        """
        try:
            raw_data = inputs.get("raw_data", "")
            config = inputs.get("config", {})

            # Parse data
            parsed = self._parse_csv(raw_data, config)

            # Return all declared output fields
            return {
                "parsed": parsed,
                "row_count": len(parsed),
                "parse_status": "success"
            }
        except Exception as e:
            # Return error status
            return {
                "parsed": [],
                "row_count": 0,
                "parse_status": f"error: {str(e)}"
            }

    def _parse_csv(self, raw_data: str, config: Dict) -> List[Dict]:
        """Parse CSV string into list of dicts."""
        lines = raw_data.strip().split('\n')
        if not lines:
            return []

        headers = [h.strip() for h in lines[0].split(',')]
        rows = []

        for line in lines[1:]:
            values = [v.strip() for v in line.split(',')]
            rows.append(dict(zip(headers, values)))

        return rows
```

## Validation Modes

When you declare multiple outputs but the agent returns unexpected data, AgentMap applies **output validation** according to the agent's configured validation mode.

### Three Validation Modes

#### 1. **ignore** Mode (Silent)
- Missing fields: Silently omitted from state
- Extra fields: Silently filtered out
- Wrong type: Silently wrapped in first field
- **Use when**: You trust agent implementation, want zero logging overhead
- **Effect**: Degraded but continuing

```python
# Config for ignore mode
output_validation: ignore
```

**Example:**
```python
# Agent declares: result|status|count
# Agent returns: "error occurred"  (scalar instead of dict)
# Result: {result: "error occurred"} in state
# Log: Nothing
```

#### 2. **warn** Mode (Logged but Continues - DEFAULT)
- Missing fields: Warning logged, continue with available fields
- Extra fields: Warning logged, filtered from state
- Wrong type: Warning logged, wrapped in first field
- **Use when**: Development/testing, want visibility into issues
- **Effect**: Problems logged but workflow continues
- **This is the default if not specified**

```python
# Config for warn mode (default)
output_validation: warn

# Or omit the setting entirely - warn is default
```

**Example:**
```python
# Agent declares: result|status|count
# Agent returns: {result: "data"}  (missing status, count)
# Result: {result: "data"} in state
# Log: WARNING - Agent MissingFields missing declared output fields: ['status', 'count']
```

#### 3. **error** Mode (Strict)
- Missing fields: Exception raised, agent execution fails
- Extra fields: Exception raised, agent execution fails
- Wrong type: Exception raised, agent execution fails
- **Use when**: Production/enforcement, need strict contracts
- **Effect**: Workflow stops on validation failures
- **Fails fast**

```python
# Config for error mode
output_validation: error
```

**Example:**
```python
# Agent declares: result|status|count
# Agent returns: {result: "data"}  (missing status, count)
# Result: ValueError raised
# Workflow: Stops immediately with clear error
```

### Configuring Validation Mode

#### In CSV Graph Definition

Add `output_validation` to agent context (via CSV Extra column or agent config):

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Extra
pipeline,ParseData,ParseAgent,raw_data,parsed|row_count|parse_status,"{""output_validation"": ""error""}"
```

#### In Agent Implementation

```python
class StrictParseAgent(BaseAgent):
    def __init__(self, name, prompt, context=None, **kwargs):
        context = context or {}
        # Set validation mode in context
        context["output_validation"] = "error"
        super().__init__(name, prompt, context, **kwargs)
```

#### In Configuration File

```yaml
agents:
  ParseAgent:
    output_validation: error
    prompt: "Parse the following data..."
```

### Validation Error Messages

When validation issues occur, you'll see clear messages:

**Missing Fields:**
```
Agent ParseData missing declared output fields: ['row_count', 'parse_status'].
Returned keys: ['parsed']
```

**Extra Fields (auto-filtered):**
```
Agent TransformData declared output fields ['transformed', 'count'] but returned
['transformed', 'count', 'metadata', 'timing']. Extra fields filtered: ['metadata', 'timing']
```

**Wrong Return Type:**
```
Agent ValidateData declares multiple outputs ['valid_rows', 'errors', 'status'] but returned
<class 'str'> instead of dict. Assigning to first output field 'valid_rows'.
```

## Backward Compatibility

The multi-output feature is **fully backward compatible**:

### Single Output Still Works
```csv
# Traditional single output - still works
Output_Field: result
```

Agents returning scalars continue to work:
```python
def process(self, inputs):
    return "Done"  # Single scalar return
```

### Automatic Detection
- Single field name → treated as traditional single output
- Pipe-delimited names → treated as multi-output
- No code changes needed to existing workflows

### Migration Path
To convert a single-output agent to multi-output:

1. **Update CSV Declaration** (add pipe-delimited fields):
   ```csv
   # Before
   Output_Field: result

   # After
   Output_Field: result|status|count
   ```

2. **Update Agent Implementation** (return dict):
   ```python
   # Before
   def process(self, inputs):
       return "Done"

   # After
   def process(self, inputs):
       return {
           "result": "Done",
           "status": "success",
           "count": 1
       }
   ```

3. **Test** (verify workflow still works)

4. **Update Downstream Agents** (adjust input field dependencies if needed)

## Common Patterns

### Pattern 1: Data + Metadata

Return both the processed data and information about the processing:

```python
def process(self, inputs):
    data = process_input(inputs)
    return {
        "data": data,
        "processed_count": len(data),
        "timestamp": datetime.now().isoformat()
    }
```

**CSV Declaration:**
```csv
Output_Field: data|processed_count|timestamp
```

### Pattern 2: Result + Status

Return both the result and a status indicator for downstream routing:

```python
def process(self, inputs):
    try:
        result = risky_operation(inputs)
        return {
            "result": result,
            "status": "success",
            "error": None
        }
    except Exception as e:
        return {
            "result": None,
            "status": "failed",
            "error": str(e)
        }
```

**CSV Declaration:**
```csv
Output_Field: result|status|error
```

### Pattern 3: Split Processing

Return multiple branches of processed data:

```python
def process(self, inputs):
    data = inputs.get("data", [])

    valid = [item for item in data if validate(item)]
    invalid = [item for item in data if not validate(item)]

    return {
        "valid_items": valid,
        "invalid_items": invalid,
        "validation_report": {
            "total": len(data),
            "valid": len(valid),
            "invalid": len(invalid)
        }
    }
```

**CSV Declaration:**
```csv
Output_Field: valid_items|invalid_items|validation_report
```

### Pattern 4: Conditional Status

Use multi-output to make conditional routing data:

```python
def process(self, inputs):
    result = heavy_computation(inputs)

    if is_valid(result):
        next_step = "continue"
    else:
        next_step = "review"

    return {
        "result": result,
        "next_step": next_step,
        "is_valid": is_valid(result)
    }
```

Then use `next_step` in the CSV for routing:
```csv
Node,Edge,Condition
Transform,Review,next_step == 'review'
Transform,Continue,next_step == 'continue'
```

## Error Handling Best Practices

### Always Include Status Field

```python
def process(self, inputs):
    try:
        result = do_work(inputs)
        return {
            "result": result,
            "status": "success",
            "error_code": None,
            "error_message": None
        }
    except ValidationError as e:
        return {
            "result": None,
            "status": "validation_error",
            "error_code": e.code,
            "error_message": str(e)
        }
    except Exception as e:
        return {
            "result": None,
            "status": "unexpected_error",
            "error_code": "UNKNOWN",
            "error_message": str(e)
        }
```

### Provide Recovery Information

```python
def process(self, inputs):
    try:
        return {
            "data": fetch_data(inputs),
            "status": "success",
            "retry_possible": False
        }
    except TemporaryError as e:
        return {
            "data": None,
            "status": "temporary_error",
            "retry_possible": True
        }
    except PermanentError as e:
        return {
            "data": None,
            "status": "permanent_error",
            "retry_possible": False
        }
```

## Performance Considerations

### Dictionary Return Overhead

Returning dictionaries with multi-output is negligible:
- Parsing: < 1ms for typical workflows
- Validation: < 1ms even in strict mode
- State merge: Native Python dict merge, no serialization overhead

### State Size

Multi-output doesn't increase state size differently than traditional approaches:
- Single field with complex data: Same as multi-output with same data
- No additional overhead for the pipe-delimited syntax

### Optimization Tips

1. **Lazy computation**: Only compute fields you're declaring
   ```python
   # Good: Only compute what's declared
   return {
       "result": computed_result,
       "count": len(result)
   }

   # Bad: Computing extra data that's not used
   return {
       "result": computed_result,
       "debug_info": expensive_debug_computation(),
       "timing": expensive_timing_analysis()
   }
   ```

2. **Early returns**: Fail fast when possible
   ```python
   if not is_valid(inputs):
       return {
           "result": None,
           "status": "invalid_input",
           "error": "..."
       }
   ```

3. **Batching**: Process multiple items if possible
   ```python
   # Efficient: Process batch
   items = [parse_item(i) for i in inputs.get("batch", [])]

   # Inefficient: Single at a time
   item = parse_item(inputs.get("single"))
   ```

## Complete Workflow Example

Here's a complete end-to-end example of a multi-output workflow:

### CSV Definition

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,output_validation
data_pipeline,Ingest,IngestAgent,file_path,raw_data|file_size|read_status,Parse,warn
data_pipeline,Parse,ParseAgent,raw_data|file_size,parsed|row_count|parse_status,Validate,warn
data_pipeline,Validate,ValidateAgent,parsed|row_count,valid_rows|errors|validation_status,Transform,error
data_pipeline,Transform,TransformAgent,valid_rows,transformed|transform_count,Save,warn
data_pipeline,Save,SaveAgent,transformed|transform_count|validation_status,save_result,,
```

### Agent Implementations

```python
class IngestAgent(BaseAgent):
    def process(self, inputs):
        file_path = inputs.get("file_path")
        try:
            with open(file_path, 'r') as f:
                raw_data = f.read()
            return {
                "raw_data": raw_data,
                "file_size": len(raw_data),
                "read_status": "success"
            }
        except Exception as e:
            return {
                "raw_data": None,
                "file_size": 0,
                "read_status": f"error: {str(e)}"
            }

class ParseAgent(BaseAgent):
    def process(self, inputs):
        raw_data = inputs.get("raw_data", "")
        try:
            lines = raw_data.strip().split('\n')
            headers = lines[0].split(',')
            rows = []
            for line in lines[1:]:
                rows.append(dict(zip(headers, line.split(','))))
            return {
                "parsed": rows,
                "row_count": len(rows),
                "parse_status": "success"
            }
        except Exception as e:
            return {
                "parsed": [],
                "row_count": 0,
                "parse_status": f"error: {str(e)}"
            }

class ValidateAgent(BaseAgent):
    def process(self, inputs):
        parsed = inputs.get("parsed", [])
        errors = []
        valid_rows = []

        for i, row in enumerate(parsed):
            if self._validate_row(row):
                valid_rows.append(row)
            else:
                errors.append({"row": i, "issue": "validation failed"})

        return {
            "valid_rows": valid_rows,
            "errors": errors,
            "validation_status": "passed" if not errors else "has_errors"
        }

    def _validate_row(self, row):
        # Implement validation logic
        return True

class TransformAgent(BaseAgent):
    def process(self, inputs):
        valid_rows = inputs.get("valid_rows", [])
        transformed = [self._transform_row(row) for row in valid_rows]

        return {
            "transformed": transformed,
            "transform_count": len(transformed)
        }

    def _transform_row(self, row):
        # Implement transformation logic
        return row

class SaveAgent(BaseAgent):
    def process(self, inputs):
        transformed = inputs.get("transformed", [])
        count = len(transformed)

        # Save to database, file, etc.
        try:
            save_records(transformed)
            return f"Saved {count} records successfully"
        except Exception as e:
            return f"Failed to save {count} records: {str(e)}"
```

### Workflow Execution

The workflow automatically:
1. **Ingests** file → produces `raw_data|file_size|read_status`
2. **Parses** raw data → produces `parsed|row_count|parse_status`
3. **Validates** parsed data → produces `valid_rows|errors|validation_status`
4. **Transforms** valid rows → produces `transformed|transform_count`
5. **Saves** transformed data → produces `save_result`

Each agent receives **all declared input fields** in its inputs dict, and can access any combination of state variables for downstream decision-making.

## Troubleshooting

### Agent Returns Scalar Instead of Dict

**Error:**
```
Agent MyAgent declares multiple outputs [...] but returned <class 'str'> instead of dict.
```

**Solution:**
```python
# Wrong
def process(self, inputs):
    return "result"

# Right
def process(self, inputs):
    return {"output_field": "result"}
```

### Missing Declared Output Fields

**Error:**
```
Agent MyAgent missing declared output fields: ['field2', 'field3']. Returned keys: ['field1']
```

**Solution:**
Ensure all declared fields are returned:
```python
# Declare: field1|field2|field3
# Must return all three:
return {
    "field1": value1,
    "field2": value2,
    "field3": value3
}
```

### Downstream Agent Can't Find Field

**Error:**
```
KeyError: 'expected_field' when trying to access inputs
```

**Solution:**
Verify the upstream agent declares the field and the downstream agent requests it:
```csv
# Upstream must declare it
Output_Field: field1|expected_field

# Downstream must request it
Input_Fields: field1|expected_field
```

## See Also

- [CSV Reference Guide](../architecture/csv-reference.md) - Complete CSV syntax
- [Agent Development Guide](./agent-development.md) - Writing agents
- [Migration Guide](#migration-guide) - Converting existing workflows
