---
title: Input Field Mapping
sidebar_position: 1
---

# Input Field Mapping

AgentMap supports three binding modes for mapping CSV `Input_Fields` to agent parameters: **direct mode**, **mapped binding mode**, and **positional binding mode**. This guide explains each mode, when to use it, and how the framework selects the appropriate mode automatically.

## Direct Mode (Default)

Direct mode is the default, backward-compatible behavior. Each field name in `Input_Fields` is used as both the state key and the parameter name passed to the agent.

### CSV Example

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,Prompt
my_graph,calculator,default,foo_count | bar_count,result,done,Add the inputs
```

### How It Works

The framework reads `foo_count` and `bar_count` from the state and passes them to the agent's `process()` method as:

```python
inputs = {"foo_count": 8, "bar_count": 3}
```

### When Direct Mode Is Used

Direct mode activates when:
- No field contains `:` (colon) syntax
- The agent does not declare `expected_params`

**No changes are needed for existing workflows.** All CSVs and agents created before input field mapping continue to work without modification.

## Mapped Binding Mode

Mapped binding mode lets you decouple state key names from agent parameter names using `state_key:param_name` syntax in the `Input_Fields` column.

### CSV Example

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,Prompt
my_graph,calculator,custom_adder,foo_count:addend_a | bar_count:addend_b,result,done,Add the inputs
```

### How It Works

The framework reads `foo_count` from the state but passes it to the agent as `addend_a`. Similarly, `bar_count` is passed as `addend_b`:

```python
# State:  {"foo_count": 8, "bar_count": 3}
# Agent receives:
inputs = {"addend_a": 8, "addend_b": 3}
```

### Agent Code

```python
class CustomAdder(BaseAgent):
    def process(self, inputs):
        a = inputs.get("addend_a", 0)
        b = inputs.get("addend_b", 0)
        return a + b
```

### When Mapped Mode Is Used

Mapped mode activates when any field in `Input_Fields` contains a `:` character. Fields without `:` in the same node still use direct mode for their individual resolution.

### Mixed Fields

You can mix mapped and direct fields in the same node:

```csv
Input_Fields
foo_count:addend_a | bonus_type
```

Here `foo_count` is remapped to `addend_a`, while `bonus_type` passes through as-is (direct mode).

**Important:** When any field uses `:` syntax, positional binding is disabled for the entire node.

## Positional Binding Mode

Positional binding mode maps CSV input fields to agent parameters by index position. This is useful when an agent has well-defined parameter names that differ from the state key names, and you want to avoid repeating the mapping in every CSV row.

### Agent Code

Declare `expected_params` as a class attribute on your agent:

```python
from agentmap.agents.base_agent import BaseAgent

class DiceAdder(BaseAgent):
    expected_params = ["addend_a", "addend_b"]

    def process(self, inputs):
        a = inputs.get("addend_a", 0)
        b = inputs.get("addend_b", 0)
        return a + b
```

### CSV Example

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,Prompt
my_graph,calculator,dice_adder,foo_count | bar_count,result,done,Add the inputs
```

### How It Works

The framework matches fields to `expected_params` by position:
- Position 0: `foo_count` (state key) maps to `addend_a` (param name)
- Position 1: `bar_count` (state key) maps to `addend_b` (param name)

The agent receives:

```python
inputs = {"addend_a": 8, "addend_b": 3}
```

### When Positional Mode Is Used

Positional mode activates when:
1. The agent declares a non-empty `expected_params` list
2. No field in `Input_Fields` contains `:` syntax
3. The field index is within the bounds of `expected_params`

### Overflow Behavior

If there are more input fields than `expected_params` entries, the extra fields fall through to direct mode:

```python
expected_params = ["addend_a", "addend_b"]
# Input_Fields: foo_count | bar_count | bonus_type
# Result:
inputs = {
    "addend_a": 8,        # positional (index 0)
    "addend_b": 3,        # positional (index 1)
    "bonus_type": "fire",  # overflow -> direct mode (index 2, no matching param)
}
```

## Mode Detection Decision Tree

The framework selects the binding mode for each node automatically:

```
1. Does ANY field in Input_Fields contain ':'?
   |
   +-- YES --> Mapped mode for fields with ':', direct mode for others.
   |           Positional binding is DISABLED for this node.
   |
   +-- NO --> Does the agent declare non-empty expected_params?
              |
              +-- YES --> Positional mode for fields within expected_params bounds.
              |           Overflow fields use direct mode.
              |
              +-- NO --> Direct mode for all fields.
```

Key rules:
- **Mapped syntax takes priority.** If any field uses `:`, the entire node cannot use positional binding.
- **Positional requires expected_params.** Without the class attribute, positional binding never activates.
- **Direct mode is always the fallback.** It handles overflow fields and nodes with no special syntax.

## Backward Compatibility

**Zero changes are required for existing workflows.**

- All existing CSV files continue to produce identical results.
- All 46 built-in agents work without modification (none declare `expected_params`).
- The `expected_params` parameter on `get_inputs()` defaults to `None`, preserving all existing call sites.
- No existing test fixtures, example files, or agent source files are modified.

## Edge Cases

### Empty Input_Fields

Nodes with empty or absent `Input_Fields` produce an empty inputs dictionary. No binding mode is triggered.

### State Key Not Found

When a field references a state key that does not exist, the value resolves to `None` (existing behavior, unchanged by input field mapping).

### Underflow (Fewer Fields Than expected_params)

If there are fewer input fields than `expected_params` entries, only the available fields are mapped positionally. No error is raised for unmatched `expected_params` entries.
