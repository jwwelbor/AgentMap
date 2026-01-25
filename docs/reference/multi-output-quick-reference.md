# Multi-Output Quick Reference Card

## One-Minute Overview

Multi-output allows agents to produce multiple fields at once.

**CSV:**
```csv
Output_Field: field1|field2|field3
```

**Python:**
```python
def process(self, inputs):
    return {
        "field1": value1,
        "field2": value2,
        "field3": value3
    }
```

**Result in state:** Three separate fields available to downstream agents.

## Common Syntax

### Declaring Outputs

| Use Case | Syntax | Example |
|----------|--------|---------|
| Single output | `field_name` | `result` |
| Multiple outputs | `field1\|field2\|field3` | `parsed\|count\|status` |
| With spaces | `field1 \| field2` | `result \| status` |

### Spaces and Delimiters

- Spaces around pipes are optional and trimmed automatically
- All of these are equivalent:
  - `field1|field2|field3`
  - `field1 | field2 | field3`
  - `field1\| field2\|field3`

### Invalid Examples

```
# ❌ Wrong - spaces in field name
field1 |field 2|field3

# ❌ Wrong - special characters
field@1|field#2

# ❌ Wrong - Python keywords
class|def|return

# ❌ Wrong - empty fields
field1||field3
```

## Validation Modes

```csv
output_validation: ignore    # Silent (no logging)
output_validation: warn      # Log warnings (DEFAULT)
output_validation: error     # Raise exceptions (strict)
```

### What Each Mode Does

| Mode | Missing Fields | Wrong Type | Extra Fields |
|------|---|---|---|
| `ignore` | Omitted silently | Wrapped in first field | Filtered silently |
| `warn` | Logged + omitted | Logged + wrapped | Logged + filtered |
| `error` | Exception raised | Exception raised | Exception raised |

## Agent Implementation

### Return All Declared Fields

```python
def process(self, inputs):
    return {
        "field1": compute1(inputs),
        "field2": compute2(inputs),
        "field3": compute3(inputs)
    }
```

### Handle Errors

```python
def process(self, inputs):
    try:
        return {
            "result": do_work(inputs),
            "status": "success"
        }
    except Exception as e:
        return {
            "result": None,
            "status": f"error: {str(e)}"
        }
```

### Access Inputs

```python
def process(self, inputs):
    # Safe access (recommended)
    field1 = inputs.get("field1", default_value)
    field2 = inputs.get("field2", default_value)

    # Or unpack
    field1, field2 = inputs.get("field1"), inputs.get("field2")
```

## CSV Examples

### Data Processing

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,output_validation
etl,Parse,ParseAgent,raw_data,parsed|row_count|status,Validate,warn
etl,Validate,ValidateAgent,parsed|row_count,valid|errors|status,Transform,warn
etl,Transform,TransformAgent,valid,transformed|count,Save,error
etl,Save,SaveAgent,transformed|count,result,
```

### Error Handling

```csv
Node,Input_Fields,Output_Field,Edge,output_validation
Process,input,result|status|error,Next,error
Next,result|status,output,
```

### Conditional Routing

```csv
Node,Input_Fields,Output_Field,Edge,output_validation
Analyze,data,score|category|next_step,Route,warn
Route,next_step,decision,FinalNode
```

## Common Patterns

### Result + Status
```python
{
    "result": computed_value,
    "status": "success" | "failure" | "partial"
}
```

### Data + Count
```python
{
    "data": items,
    "count": len(items)
}
```

### Multiple Categories
```python
{
    "valid": valid_items,
    "invalid": invalid_items,
    "summary": {"valid": 10, "invalid": 2}
}
```

### Result + Error Info
```python
{
    "result": value,
    "error_code": None | "ERROR_X",
    "error_message": None | "User-friendly message"
}
```

## Testing

### Unit Test Template

```python
def test_multi_output_agent():
    agent = MyAgent("test", "prompt", logger=MagicMock())
    inputs = {"input_field": "value"}

    result = agent.process(inputs)

    # Verify all fields present
    assert "field1" in result
    assert "field2" in result
    assert "field3" in result

    # Verify values
    assert result["field1"] == expected_value
    assert result["status"] == "success"
```

## Debugging

### Agent Returns Wrong Type

**Error:**
```
Agent MyAgent declares multiple outputs [...] but returned <class 'str'>
```

**Fix:**
```python
# Wrong
return "result"

# Right
return {"output_field": "result"}
```

### Missing Declared Fields

**Error:**
```
Agent MyAgent missing declared output fields: ['field2']
```

**Fix:**
Ensure all declared fields are in return dict:
```python
# Declare: field1|field2|field3
return {
    "field1": val1,
    "field2": val2,      # Must include all
    "field3": val3
}
```

### Downstream Can't Find Field

**Error:**
```
KeyError: 'expected_field'
```

**Check:**
1. Upstream declares the field: `Output_Field: ... | expected_field`
2. Downstream requests the field: `Input_Fields: ... | expected_field`

## Performance Notes

- Negligible overhead (< 1ms even for 10+ fields)
- No serialization overhead (stays as Python objects)
- Early returns recommended for performance
- Don't compute fields you're not declaring

## Backward Compatibility

✅ **Fully backward compatible**
- Single-output agents still work
- Existing workflows unaffected
- Mixed single/multi-output workflows OK
- Automatic detection based on pipe delimiter

## CSV Column Structure

```
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,Extra,output_validation
name,NodeName,AgentClass,in1|in2,out1|out2|out3,NextNode,{...},warn
```

## Field Naming Rules

✅ Valid:
- `result`, `status`, `count`
- `field_1`, `field_2_a`
- `valid_rows`, `error_code`
- `data`, `DATA`, `data_v2`

❌ Invalid:
- `field 1` (spaces)
- `field-1` (hyphens)
- `field@1` (special chars)
- `class`, `def`, `return` (keywords)

## Accessing State After Execution

All output fields become available in state:

```python
state = {
    "original_field": original_value,
    # From Agent1
    "field1": value1,
    "field2": value2,
    "field3": value3,
    # From Agent2
    "field4": value4
}

# Access any field
print(state["field1"])
print(state["field3"])
print(state["field4"])
```

## Configuration Examples

### Per-Agent Configuration

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Extra
etl,Parse,ParseAgent,raw_data,parsed|count,"{""strict"": true}"
```

### Global Configuration

In agent config file:
```yaml
agents:
  ParseAgent:
    output_validation: error
    strict: true
```

### CSV Configuration

```csv
Node,AgentType,Input_Fields,Output_Field,output_validation
Parse,ParseAgent,raw_data,parsed|count|status,error
```

## Error Messages Reference

| Error | Meaning | Fix |
|-------|---------|-----|
| `missing declared output fields` | Agent didn't return all fields | Return all declared fields |
| `but returned <type>` | Wrong return type for multi-output | Return dict, not scalar |
| `Extra fields filtered` | Agent returned undeclared fields | Declare all fields or don't return them |
| `Invalid field name` | Field name is Python keyword | Choose different field name |

## Validation Mode Decision Tree

```
Is it production/critical?
├─ Yes → Use "error"
└─ No → Is it development?
        ├─ Yes → Use "warn" (default)
        └─ No → Is it resilient system?
                ├─ Yes → Use "ignore"
                └─ No → Use "warn"
```

## Cheat Sheet: Single to Multi-Output Migration

**CSV Before:**
```csv
Output_Field: result
```

**CSV After:**
```csv
Output_Field: result|status|count
```

**Code Before:**
```python
def process(self, inputs):
    return compute()
```

**Code After:**
```python
def process(self, inputs):
    result = compute()
    return {
        "result": result,
        "status": "success",
        "count": len(result)
    }
```

## Links

- **Feature Guide**: [Multi-Output Agents](../features/multi-output-agents.md)
- **CSV Reference**: [CSV Reference](./csv-multi-output-reference.md)
- **Agent Development**: [Agent Guide](../guides/agent-development-multi-output.md)
- **Migration**: [Migration Guide](../guides/migration-to-multi-output.md)
- **Troubleshooting**: [Feature Guide - Troubleshooting](../features/multi-output-agents.md#troubleshooting)

## Version Info

- **Feature Available**: AgentMap v0.8+
- **Backward Compatible**: Yes
- **Performance Impact**: Negligible (< 1ms overhead)
