# State Management and Data Flow

AgentMap uses a shared state object to pass data between nodes. Understanding how state is managed and flows through the graph is crucial for effective workflow design.

## State Structure

The state is a dictionary that contains:

- Input fields from the initial state
- Output fields from each node's execution
- System fields like `last_action_success`
- Optional memory fields

Example state evolution:
```python
### Initial state
state = {"input": "Hello, world!"}

### After Node1 (Echo)
state = {
    "input": "Hello, world!",
    "echoed": "Hello, world!",  # output_field from Node1
    "last_action_success": True
}

### After Node2 (OpenAI)
state = {
    "input": "Hello, world!",
    "echoed": "Hello, world!",
    "response": "Greetings, human!",  # output_field from Node2
    "last_action_success": True
}
```

## State Adapter

The `StateAdapter` class handles different state formats:

- Dictionary state (default)
- Pydantic models
- Custom state objects

It provides methods for getting and setting values regardless of state type:

```python
### Get a value
value = StateAdapter.get_value(state, "field_name", default="default value")

### Set a value
new_state = StateAdapter.set_value(state, "field_name", "new value")
```

## State Flow in an Agent's Lifecycle

1. **Input Extraction**:
   - Agent's `run` method extracts input fields from state
   - Only fields listed in `Input_Fields` are accessible

2. **Processing**:
   - Agent's `process` method transforms inputs to output
   - Custom logic determines the result

3. **Output Setting**:
   - Output is stored in the field specified by `Output_Field`
   - `last_action_success` flag is set based on execution result

4. **Routing**:
   - Next node is determined based on routing rules and `last_action_success`

## Memory Management

For agents with memory (like LLM agents), there's additional state handling:

1. **Memory Serialization/Deserialization**:
   - Memory objects are serialized when stored in state
   - They're deserialized when retrieved by an agent

2. **Memory Flow**:
   - Memory is passed between nodes via a designated memory field (e.g., `chat_memory`)
   - Agents can add to the memory during processing

Example with memory:
```python
### After LLM agent with memory
state = {
    "input": "Hello",
    "response": "Hi there!",
    "chat_memory": {
        "_type": "langchain_memory",
        "memory_type": "buffer",
        "messages": [
            {"type": "human", "content": "Hello"},
            {"type": "ai", "content": "Hi there!"}
        ]
    },
    "last_action_success": True
}
```

## Execution Tracking

Execution tracking is handled via LangSmith

This tracking is useful for:
- Debugging workflow execution
- Monitoring performance
- Understanding the execution path

## Error Handling

If an agent encounters an error:

1. The error is logged
2. `last_action_success` is set to `False`
3. An `error` field may be added to state
4. Routing follows the `Failure_Next` path

Custom error handling can be implemented in agents' `process` method.


---
