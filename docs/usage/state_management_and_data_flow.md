# State Management and Data Flow

AgentMap uses a service-based architecture for state management, with the StateAdapterService handling different state formats and the ExecutionTrackingService monitoring state evolution through the workflow.

## State Management Architecture

### Clean Architecture Approach

State management is handled by specialized services:

1. **StateAdapterService**: Adapts between different state formats
2. **ExecutionTrackingService**: Tracks state changes during execution
3. **GraphRunnerService**: Orchestrates state flow through the graph

## State Structure

The state is typically a dictionary that contains:

- Input fields from the initial state
- Output fields from each node's execution
- System fields like `last_action_success`
- Optional memory fields for conversational agents

Example state evolution:
```python
# Initial state
state = {"input": "Hello, world!"}

# After Node1 (Echo)
state = {
    "input": "Hello, world!",
    "echoed": "Hello, world!",  # output_field from Node1
    "last_action_success": True
}

# After Node2 (OpenAI)  
state = {
    "input": "Hello, world!",
    "echoed": "Hello, world!",
    "response": "Greetings, human!",  # output_field from Node2
    "last_action_success": True
}
```

## StateAdapterService

The StateAdapterService provides a clean interface for state operations:

### Service Interface

```python
class StateAdapterService:
    """Service for adapting state between different formats"""
    
    def adapt_initial_state(self, state: Any, schema: Type = None) -> Dict[str, Any]:
        """Adapt initial state to required format"""
        if isinstance(state, dict):
            return state
        elif hasattr(state, 'dict'):  # Pydantic model
            return state.dict()
        else:
            return {"input": state}  # Wrap simple values
    
    def extract_value(self, state: Any, key: str, default: Any = None) -> Any:
        """Extract value from state regardless of format"""
        if isinstance(state, dict):
            return state.get(key, default)
        elif hasattr(state, '__getattribute__'):
            return getattr(state, key, default)
        return default
    
    def update_state(self, state: Any, key: str, value: Any) -> Any:
        """Update state value maintaining format"""
        if isinstance(state, dict):
            state[key] = value
            return state
        # Handle other formats as needed
```

### Usage in Services

```python
class GraphRunnerService:
    def __init__(self, state_adapter_service: StateAdapterService, ...):
        self.state_adapter = state_adapter_service
        # ... other dependencies
    
    def run_graph(self, graph_name: str, initial_state: Any) -> ExecutionResult:
        # Adapt state to standard format
        adapted_state = self.state_adapter.adapt_initial_state(
            initial_state, 
            self.get_state_schema(graph_name)
        )
        
        # Execute with adapted state
        result = self.execute(adapted_state)
        return result
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

## ExecutionTrackingService

The ExecutionTrackingService provides comprehensive tracking of state evolution:

### Service Interface

```python
class ExecutionTrackingService:
    """Service for tracking workflow execution"""
    
    def create_tracker(self, graph_name: str) -> ExecutionTracker:
        """Create a new execution tracker"""
        return ExecutionTracker(
            graph_name=graph_name,
            track_outputs=self.config.track_outputs,
            track_inputs=self.config.track_inputs
        )

class ExecutionTracker:
    """Tracks execution of a single workflow"""
    
    def track_node_start(self, node_name: str, inputs: Dict[str, Any]):
        """Track when a node starts executing"""
        
    def track_node_complete(self, node_name: str, outputs: Any, success: bool):
        """Track when a node completes"""
        
    def get_summary(self) -> ExecutionSummary:
        """Get execution summary with all tracking data"""
```

### Tracking Configuration

```yaml
# In agentmap_config.yaml
execution:
  tracking:
    enabled: true              # Enable tracking
    track_outputs: false       # Track output values (can be large)
    track_inputs: false        # Track input values
    track_duration: true       # Track execution times
```

### Using Execution Tracking

```python
# The GraphRunnerService automatically tracks execution
result = runner.run_graph("MyWorkflow", {"input": "data"})

# Access tracking data
summary = result.execution_summary
print(f"Total duration: {summary.total_duration}s")
print(f"Execution path: {' → '.join(summary.execution_path)}")

# Check node-level details
for node, details in summary.node_results.items():
    print(f"{node}: {'✓' if details.success else '✗'} ({details.duration}s)")
```

Execution tracking is useful for:
- Debugging workflow execution
- Monitoring performance bottlenecks
- Understanding the execution path
- Identifying failing nodes

## Error Handling

If an agent encounters an error:

1. The error is logged
2. `last_action_success` is set to `False`
3. An `error` field may be added to state
4. Routing follows the `Failure_Next` path

Custom error handling can be implemented in agents' `process` method.


---
