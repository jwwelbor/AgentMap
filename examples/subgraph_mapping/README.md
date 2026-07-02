# GraphAgent Subgraph Mapping Examples

Runnable examples showing how parent and child graph state move through the
`graph` agent.

## Files

```text
subgraph_mapping/
├── agentmap_config.yaml
├── agentmap_config_storage.yaml
├── run_example.py
├── README.md
└── workflows/
    ├── ChildInputPassThrough.csv
    ├── DirectSubgraphState.csv
    ├── RemappedChildInput.csv
    └── OutputRemapExample.csv
```

## What Each Example Shows

### 1. `DirectSubgraphState`

`Output_Field: inner_result`

The parent stores the entire child graph final state under `inner_result`.
This is the simplest pattern when the parent wants the whole child result as a
nested object.

Relevant fields:

```python
{
    "inner_result": {
        "raw_data": "hello from parent",
        "child_value": "hello from parent",
        "child_final": "hello from parent",
    },
    "final_result": {
        "raw_data": "hello from parent",
        "child_value": "hello from parent",
        "child_final": "hello from parent",
    },
}
```

### 2. `ChildInputPassThrough`

`Input_Fields: text|request_id`

The GraphAgent forwards exactly the listed parent fields into the child graph.
The child sees `text` and `request_id` in its own initial state and returns a
snapshot of those values.

Relevant fields:

```python
{
    "child_result": {
        "text": "passed straight into child text",
        "request_id": "req-42",
        "child_snapshot": {
            "text": "passed straight into child text",
            "request_id": "req-42",
        },
    }
}
```

### 3. `RemappedChildInput`

`Input_Fields: text=raw_data|request_id`

The GraphAgent remaps a parent state key into a different child state key
before the subgraph runs. The parent keeps `raw_data`; the child starts with
`text`.

Relevant fields:

```python
{
    "child_result": {
        "text": "hello through child remap",
        "request_id": "req-42",
        "child_snapshot": {
            "text": "hello through child remap",
            "request_id": "req-42",
        },
    }
}
```

### 4. `OutputRemapExample`

`Output_Field: selected_parent=child_final`

The child produces `child_final`, and the GraphAgent writes that value into the
parent field `selected_parent`. The next parent node reads `selected_parent`
like any other top-level state key.

Relevant fields:

```python
{
    "selected_parent": "mapped back to parent",
    "echoed_parent": "mapped back to parent",
}
```

## Run

From the repository root:

```bash
uv run python examples/subgraph_mapping/run_example.py
```

Or from this directory:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python run_example.py
```

## Mapping Rules

- Standard framework input remap: `state_key:param_name`
- GraphAgent child input selection: `field_a|field_b`
- GraphAgent child input remap: `child_key=parent_key`
- GraphAgent output remap: `parent_key=child_key`

The GraphAgent `=` remaps use `target=source`, which is the reverse of the
framework-wide `:` input mapping syntax.
