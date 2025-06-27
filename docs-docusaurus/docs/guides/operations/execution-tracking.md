---
sidebar_position: 1
title: Execution Tracking & Monitoring
description: Comprehensive execution tracking for AgentMap graphs with performance metrics and success evaluation
keywords: [execution tracking, monitoring, performance metrics, policy-based success, debugging, AgentMap operations]
---

# AgentMap Execution Tracking & Monitoring

AgentMap provides comprehensive execution tracking for all graph workflows, enabling you to monitor success/failure states, performance metrics, and detailed execution paths. This system helps you understand workflow behavior, debug issues, and optimize performance.

## Overview

The AgentMap execution tracking system provides two levels of tracking:

1. **Minimal Tracking (Always On)**: Tracks basic execution information needed for policy-based success evaluation
2. **Detailed Tracking (Optional)**: Records detailed timing, inputs, outputs, and diagnostic information

The system always maintains the minimal tracking needed to evaluate graph success based on your configured policy, while detailed tracking can be enabled when more information is needed for debugging or analysis.

## Core Features

### Policy-Based Success Tracking
- **Real-time Success Evaluation**: Continuously evaluates whether the graph is meeting success criteria
- **Multiple Policy Types**: Choose from `all_nodes`, `final_node`, `critical_nodes`, or custom policies
- **Early Detection**: Identify when workflows deviate from the successful path

### Performance Monitoring
- **Node-Level Timing**: Detailed execution time for each node in your workflow
- **Overall Graph Metrics**: Total execution time and resource usage
- **Performance Trends**: Track performance changes over time

### Execution Path Analysis
- **Complete Path Recording**: Track which nodes were executed and in what order
- **Branch Analysis**: Understand decision points and routing in your workflows
- **Error Tracking**: Detailed information about where and why failures occur

## Implementation

### Always-Available Tracking

The tracking system always provides:

- **Policy-Based Success Tracking**: Real-time evaluation of whether the graph is meeting success criteria
- **Execution Path Recording**: Basic tracking of which nodes were executed
- **Graph Success State**: Always-available graph success status using the `graph_success` field

### Detailed Tracking (Optional)

With detailed tracking enabled, you also get:

- **Performance Metrics**: Detailed timing information for each node and overall graph
- **Input/Output Capture**: Optional recording of inputs and outputs for debugging
- **Error Details**: Comprehensive error information for failed nodes
- **Rich Execution Summary**: Complete execution details in the `__execution_summary` field

## Configuration

Configure the execution system in your `agentmap_config.yaml` file:

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

#### All Nodes Policy (Default)
All nodes in the execution path must succeed for the graph to be considered successful.

```yaml
execution:
  success_policy:
    type: "all_nodes"
```

#### Final Node Policy
Only the final node must succeed. Useful for workflows where early failures can be recovered.

```yaml
execution:
  success_policy:
    type: "final_node"
```

#### Critical Nodes Policy
Specific critical nodes must succeed. Other nodes can fail without affecting overall success.

```yaml
execution:
  success_policy:
    type: "critical_nodes"
    critical_nodes:
      - "validatePayment"
      - "processTransaction"
      - "sendConfirmation"
```

#### Custom Policy
Define your own success criteria using a custom function.

```yaml
execution:
  success_policy:
    type: "custom"
    custom_function: "my_module.custom_success_policy"
```

## Usage Examples

### Basic Success Tracking

Policy-based success tracking is automatically integrated into the graph execution process:

```python
from agentmap.runner import run_graph

result = run_graph("customer_workflow", initial_state)

# Access policy-based success (always available)
graph_success = result["graph_success"]
if graph_success:
    print("✅ Workflow succeeded according to policy!")
    # Process successful result
    customer_id = result.get("customer_id")
    print(f"Customer {customer_id} onboarded successfully")
else:
    print("❌ Workflow failed according to policy.")
    # Handle failure case
    print("Initiating error recovery procedures...")
```

### Detailed Execution Analysis

With detailed tracking enabled, access comprehensive execution information:

```python
# Access the detailed execution summary
summary = result["__execution_summary"]

# Analyze execution details
print(f"Execution path: {summary['execution_path']}")
print(f"Total duration: {summary['total_duration']:.2f}s")
print(f"Nodes executed: {len(summary['node_results'])}")

# Performance analysis
for node, data in summary["node_results"].items():
    duration = data["duration"]
    print(f"Node {node}: {duration:.3f}s")

# Find failing nodes
failing_nodes = [
    node for node, data in summary["node_results"].items() 
    if not data["success"]
]

if failing_nodes:
    print(f"Failed nodes: {', '.join(failing_nodes)}")
    for node in failing_nodes:
        error_info = summary['node_results'][node]['error']
        print(f"  {node}: {error_info}")
```

### Real-time Success Monitoring

Monitor graph success during execution for adaptive workflows:

```python
# In a custom agent or function
def process_with_monitoring(self, inputs):
    """Process data with real-time success monitoring."""
    
    # Check if graph is still on successful path
    graph_success = inputs.get("graph_success", True)
    
    if not graph_success:
        # Take corrective action
        self.logger.warning("Graph has deviated from successful path!")
        return self.initiate_recovery_mode(inputs)
    
    # Continue with normal processing
    return self.normal_processing(inputs)
```

### Performance Monitoring

Track and analyze performance patterns:

```python
def analyze_workflow_performance(execution_results):
    """Analyze performance trends across multiple executions."""
    
    performance_data = []
    
    for result in execution_results:
        summary = result.get("__execution_summary", {})
        if summary:
            performance_data.append({
                "total_duration": summary["total_duration"],
                "node_count": len(summary["node_results"]),
                "success": result["graph_success"],
                "timestamp": summary.get("start_time")
            })
    
    # Calculate averages
    avg_duration = sum(p["total_duration"] for p in performance_data) / len(performance_data)
    success_rate = sum(1 for p in performance_data if p["success"]) / len(performance_data)
    
    print(f"Average execution time: {avg_duration:.2f}s")
    print(f"Success rate: {success_rate:.1%}")
    
    return {
        "avg_duration": avg_duration,
        "success_rate": success_rate,
        "total_executions": len(performance_data)
    }
```

## Custom Success Policies

Create custom success policies for complex business logic:

```python
# In my_policies.py
def custom_success_policy(summary):
    """
    Custom success policy that requires at least 80% of nodes to succeed
    and critical business nodes must always succeed.
    """
    nodes = summary["node_results"]
    
    # Critical business nodes that must always succeed
    critical_nodes = ["validateInput", "processPayment", "recordTransaction"]
    
    # Check critical nodes first
    for node in critical_nodes:
        if node in nodes and not nodes[node]["success"]:
            return False  # Critical node failed
    
    # Check overall success rate
    success_count = sum(1 for data in nodes.values() if data["success"])
    success_rate = success_count / len(nodes) if nodes else 0
    
    return success_rate >= 0.8

def payment_workflow_policy(summary):
    """Policy specifically for payment workflows."""
    nodes = summary["node_results"]
    
    # Payment workflows require specific sequence success
    required_sequence = ["validate_card", "authorize_payment", "capture_funds"]
    
    for node in required_sequence:
        if node not in nodes or not nodes[node]["success"]:
            return False
    
    return True
```

Then configure in `agentmap_config.yaml`:

```yaml
execution:
  success_policy:
    type: "custom"
    custom_function: "my_policies.payment_workflow_policy"
```

## Monitoring and Debugging

### Debug Mode Configuration

Enable comprehensive debugging for development:

```yaml
execution:
  tracking:
    enabled: true
    track_outputs: true
    track_inputs: true
    debug_mode: true        # Additional debug information
  logging:
    level: "DEBUG"          # Verbose logging
    include_timestamps: true
```

### Error Diagnosis

Use execution tracking to diagnose workflow issues:

```python
def diagnose_workflow_failure(result):
    """Comprehensive workflow failure diagnosis."""
    
    if result["graph_success"]:
        print("✅ Workflow succeeded - no diagnosis needed")
        return
    
    summary = result.get("__execution_summary", {})
    if not summary:
        print("❌ No execution summary available")
        return
    
    print("🔍 Workflow Failure Diagnosis")
    print(f"Execution Path: {' → '.join(summary['execution_path'])}")
    print(f"Total Duration: {summary['total_duration']:.2f}s")
    
    # Identify failure points
    failed_nodes = []
    for node, data in summary["node_results"].items():
        if not data["success"]:
            failed_nodes.append({
                "node": node,
                "error": data.get("error", "Unknown error"),
                "duration": data.get("duration", 0),
                "inputs": data.get("inputs", {}) if "inputs" in data else "Not tracked"
            })
    
    if failed_nodes:
        print(f"\n❌ Failed Nodes ({len(failed_nodes)}):")
        for failure in failed_nodes:
            print(f"  • {failure['node']}: {failure['error']}")
            print(f"    Duration: {failure['duration']:.3f}s")
            if failure['inputs'] != "Not tracked":
                print(f"    Inputs: {failure['inputs']}")
    
    # Performance analysis
    node_times = [(node, data["duration"]) for node, data in summary["node_results"].items()]
    slowest_nodes = sorted(node_times, key=lambda x: x[1], reverse=True)[:3]
    
    print(f"\n⏱️  Slowest Nodes:")
    for node, duration in slowest_nodes:
        print(f"  • {node}: {duration:.3f}s")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if len(failed_nodes) > len(summary["node_results"]) * 0.5:
        print("  • Multiple node failures suggest input data or configuration issues")
    if summary["total_duration"] > 30:
        print("  • Long execution time - consider workflow optimization")
    if any(d > 10 for _, d in node_times):
        print("  • Some nodes are very slow - review agent implementations")
```

### Monitoring Dashboard Data

Structure execution data for monitoring dashboards:

```python
def format_for_monitoring(execution_results):
    """Format execution data for monitoring systems."""
    
    dashboard_data = {
        "metrics": {
            "total_executions": len(execution_results),
            "success_count": sum(1 for r in execution_results if r["graph_success"]),
            "failure_count": sum(1 for r in execution_results if not r["graph_success"]),
            "avg_duration": 0,
            "error_types": {}
        },
        "recent_executions": [],
        "performance_trends": []
    }
    
    durations = []
    for result in execution_results:
        summary = result.get("__execution_summary", {})
        if summary:
            duration = summary["total_duration"]
            durations.append(duration)
            
            # Track error types
            for node, data in summary["node_results"].items():
                if not data["success"]:
                    error_type = type(data.get("error", "Unknown")).__name__
                    dashboard_data["metrics"]["error_types"][error_type] = \
                        dashboard_data["metrics"]["error_types"].get(error_type, 0) + 1
            
            # Recent execution info
            dashboard_data["recent_executions"].append({
                "timestamp": summary.get("start_time"),
                "duration": duration,
                "success": result["graph_success"],
                "node_count": len(summary["node_results"])
            })
    
    # Calculate averages
    if durations:
        dashboard_data["metrics"]["avg_duration"] = sum(durations) / len(durations)
        dashboard_data["metrics"]["success_rate"] = \
            dashboard_data["metrics"]["success_count"] / len(execution_results)
    
    return dashboard_data
```

## Best Practices

### 1. Choose Appropriate Tracking Levels

- **Development**: Enable detailed tracking with input/output capture
- **Testing**: Use detailed tracking without input/output for performance
- **Production**: Use minimal tracking unless debugging specific issues

### 2. Success Policy Selection

- **Simple Workflows**: Use `all_nodes` for strict success requirements
- **Fault-Tolerant Workflows**: Use `critical_nodes` to allow non-critical failures
- **Complex Business Logic**: Implement custom policies for specific requirements

### 3. Performance Optimization

- Monitor node execution times regularly
- Set thresholds for acceptable performance
- Use execution data to identify optimization opportunities

### 4. Error Recovery

- Use real-time success tracking for early failure detection
- Implement recovery mechanisms based on policy evaluation
- Log detailed error information for post-execution analysis

### 5. Monitoring Integration

- Export execution data to monitoring systems
- Set up alerts based on success rates and performance metrics
- Create dashboards for operational visibility

## Troubleshooting

### Common Issues

#### "Graph success is always False"
- Check your success policy configuration
- Verify critical nodes are spelled correctly
- Ensure custom policy functions are accessible

#### "No execution summary available"
- Enable detailed tracking in configuration
- Check that tracking is not disabled globally
- Verify execution completed successfully

#### "Performance degradation over time"
- Review execution summaries for trends
- Check for increasing node execution times
- Monitor system resource usage during execution

### Debug Commands

```bash
# Validate tracking configuration
agentmap validate-config --section execution

# Run with detailed tracking enabled
agentmap run --graph MyWorkflow --track-detailed

# Analyze execution results
agentmap diagnose --results execution_log.json
```

## Integration with Other Systems

### Logging Integration

```python
import logging
from agentmap.runner import run_graph

# Configure logging for execution tracking
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workflow_monitor")

result = run_graph("my_workflow", initial_state)

# Log execution summary
summary = result.get("__execution_summary", {})
if summary:
    logger.info(f"Workflow completed: success={result['graph_success']}, "
                f"duration={summary['total_duration']:.2f}s, "
                f"nodes={len(summary['node_results'])}")
    
    # Log failures
    if not result["graph_success"]:
        failed_nodes = [node for node, data in summary["node_results"].items() 
                       if not data["success"]]
        logger.error(f"Workflow failed at nodes: {failed_nodes}")
```

### Metrics Export

```python
def export_metrics_to_prometheus(execution_results):
    """Export execution metrics to Prometheus format."""
    
    from prometheus_client import Counter, Histogram, Gauge
    
    # Define metrics
    execution_counter = Counter('agentmap_executions_total', 
                               'Total executions', ['status'])
    execution_duration = Histogram('agentmap_execution_duration_seconds',
                                  'Execution duration')
    node_failures = Counter('agentmap_node_failures_total',
                           'Node failures', ['node_name', 'error_type'])
    
    # Update metrics
    for result in execution_results:
        status = 'success' if result['graph_success'] else 'failure'
        execution_counter.labels(status=status).inc()
        
        summary = result.get("__execution_summary", {})
        if summary:
            execution_duration.observe(summary["total_duration"])
            
            # Track node failures
            for node, data in summary["node_results"].items():
                if not data["success"]:
                    error_type = type(data.get("error", "Unknown")).__name__
                    node_failures.labels(node_name=node, error_type=error_type).inc()
```

The execution tracking system provides comprehensive visibility into your AgentMap workflows, enabling you to monitor success, debug issues, and optimize performance effectively.

## See Also

- [Testing Patterns](testing-patterns.md) - Testing strategies for workflows with execution tracking
- [CLI Commands Reference](../../reference/cli-commands.md) - CLI commands for execution and monitoring
- [Infrastructure Guide](../infrastructure/index.md) - Configuration options for execution tracking
- [Advanced Agent Types](../advanced/advanced-agent-types.md) - Advanced performance patterns and optimization
