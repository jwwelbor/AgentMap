---
---

# CSV Column Alias Support

As of this update, AgentMap now supports multiple column name aliases for CSV files, making it more flexible when working with CSVs from different sources or following different naming conventions.

## Supported Column Aliases

The following column aliases are now supported (case-insensitive):

### Required Columns

**GraphName** (primary name):
- `graph_name`
- `Graph`
- `WorkflowName`
- `workflow_name`
- `workflow`

**Node** (primary name):
- `node_name`
- `NodeName`
- `Step`
- `StepName`
- `name`

### Optional Columns

**AgentType** (primary name):
- `agent_type`
- `Agent`
- `Type`

**Prompt** (primary name):
- `prompt`
- `Instructions`
- `Template`
- `prompt_template`

**Description** (primary name):
- `description`
- `desc`
- `Details`

**Input_Fields** (primary name):
- `input_fields`
- `Inputs`
- `InputFields`

**Output_Field** (primary name):
- `output_field`
- `Output`
- `OutputField`

**Edge** (primary name):
- `edge`
- `next_node`
- `NextNode`
- `Target`
- `next`

**Success_Next** (primary name):
- `success_next`
- `next_on_success`
- `SuccessTarget`
- `on_success`

**Failure_Next** (primary name):
- `failure_next`
- `next_on_failure`
- `FailureTarget`
- `on_failure`

**Context** (primary name):
- `context`
- `Config`
- `Configuration`

## Case-Insensitive Matching

All column names are matched case-insensitively, so these are all equivalent:
- `GraphName`, `graphname`, `GRAPHNAME`, `graph_name`, `Graph_Name`

## Example

Instead of the standard format:
```csv
GraphName,Node,AgentType,Prompt,Success_Next,Failure_Next
MyWorkflow,Start,input,Enter data:,Process,Error
```

You can now use various aliases:
```csv
workflow_name,node_name,type,instructions,on_success,on_failure
MyWorkflow,Start,input,Enter data:,Process,Error
```

Or mix different styles:
```csv
graph_name,Step,agent,prompt_template,next_on_success,FailureTarget
MyWorkflow,Start,input,Enter data:,Process,Error
```

## Implementation Details

The column normalization is handled automatically by:
- `CSVGraphParserService` - When parsing CSV files into graph specifications
- `CSVValidationService` - When validating CSV file structure

The normalization happens transparently before any validation or parsing, so all downstream code continues to use the canonical column names.

## Benefits

1. **Flexibility** - Work with CSVs from different sources without renaming columns
2. **Backward Compatible** - Existing CSVs with standard column names continue to work
3. **User-Friendly** - Use column names that make sense for your domain
4. **Case-Insensitive** - No need to worry about exact capitalization

## Notes

- Only the listed aliases are supported; other column names will be treated as unexpected
- The canonical names (e.g., `GraphName`, `Node`) are still used internally
- Warning messages about unexpected columns will still appear for truly unknown columns
