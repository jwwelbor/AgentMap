# AgentMap Execution Tracking

This package provides comprehensive execution tracking for AgentMap graphs, tracking the success/failure
of each node execution, performance metrics, and detailed execution path information.

## Execution Tracking

The AgentMap execution tracking system provides two levels of tracking:

1. **Minimal Tracking (Always On)**: Tracks basic execution information needed for policy-based success evaluation
2. **Detailed Tracking (Optional)**: Records detailed timing, inputs, outputs, and other diagnostic information

The system always maintains the minimal tracking needed to evaluate graph success based on the configured policy, while detailed tracking can be enabled when more information is needed for debugging or analysis.

## Implementation

The tracking system always provides:

- **Policy-Based Success Tracking**: Real-time evaluation of whether the graph is meeting success criteria
- **Execution Path Recording**: Basic tracking of which nodes were executed
- **Graph Success State**: Always-available graph success status using the `graph_success` field

With detailed tracking enabled, you also get:

- **Performance Metrics**: Detailed timing information for each node and overall graph
- **Input/Output Capture**: Optional recording of inputs and outputs for debugging
- **Error Details**: Comprehensive error information for failed nodes
- **Rich Execution Summary**: Complete execution details in the `__execution_summary` field

## Configuration

The execution system can be configured in your `agentmap_config.yaml` file:

```yaml
execution:
  # Tracking configuration
  tracking:
    enabled: true                    # Enable detailed tracking (default: false for minimal tracking)
    track_outputs: false             # Record output values in detailed tracking (default: false)
    track_inputs: false              # Record input values in detailed tracking (default: false)
  
  # Success policy configuration (always active)
  success_policy:
    type: "critical_nodes"           # Policy type (default: "all_nodes")
    critical_nodes:                  # List of critical nodes for "critical_nodes" policy
      - "validateInput" 
      - "processPayment"
    custom_function: ""              # Module path to custom policy function
```

### Available Success Policies

- **all_nodes**: All nodes in the execution path must succeed (default)
- **final_node**: Only the final node must succeed
- **critical_nodes**: All listed critical nodes must succeed
- **custom**: Use a custom policy function

## Usage

The execution tracking system is automatically integrated into the graph execution process.
Policy-based success tracking is always available through the `graph_success` field in the state:

```python
from agentmap.runner import run_graph

result = run_graph("my_workflow", initial_state)

# Access policy-based success
graph_success = result["graph_success"]
if graph_success:
    print("Workflow succeeded according to policy!")
else:
    print("Workflow failed according to policy.")
```

With detailed tracking enabled, you also get access to the full execution summary:

```python
# Access the detailed execution summary
summary = result["__execution_summary"]

# Analyze execution details
print(f"Execution path: {summary['execution_path']}")
print(f"Total duration: {summary['total_duration']:.2f}s")

# Find failing nodes
failing_nodes = [
    node for node, data in summary["node_results"].items() 
    if not data["success"]
]

for node in failing_nodes:
    print(f"Node {node} failed with error: {summary['node_results'][node]['error']}")
```

## Real-time Success Tracking

The execution tracking system provides real-time tracking of graph success according to the configured policy. This allows you to check if the graph is still on a successful path at any point during execution:

```python
# During graph execution (e.g., in a custom agent)
def process(self, inputs):
    # Check if graph is still on successful path
    graph_success = StateAdapter.get_value(state, "graph_success")
    
    if not graph_success:
        # Take corrective action or log warning
        logger.warning("Graph has deviated from successful path!")
```

This real-time success tracking is particularly useful for:

1. **Early Termination**: Stop graph execution early if it's already failed according to policy
2. **Adaptive Execution**: Take different actions based on current success status
3. **Debugging**: Log detailed diagnostics when graph deviates from successful path

## Custom Success Policies

You can define custom success policies by creating a function and specifying its module path in the config:

```python
# In my_module.py
def custom_success_policy(summary):
    """Custom success policy that requires at least 80% of nodes to succeed."""
    nodes = summary["node_results"]
    success_count = sum(1 for data in nodes.values() if data["success"])
    return success_count / len(nodes) >= 0.8 if nodes else False
```

Then configure it in your `agentmap_config.yaml`:

```yaml
execution:
  success_policy:
    type: "custom"
    custom_function: "my_module.custom_success_policy"
```
