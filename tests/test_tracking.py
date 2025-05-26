"""
Example script demonstrating execution tracking in AgentMap.
"""
import json
import yaml
from pathlib import Path

from agentmap.cli import initialize_di

# Configure tracking in config file
SAMPLE_CONFIG = """
csv_path: examples/MultiNodeGraph.csv
execution:
  tracking:
    enabled: true   # Enable detailed tracking
    track_outputs: true
    track_inputs: true
  success_policy:
    type: critical_nodes
    critical_nodes:
      - inputNode
      - processNode
"""

def setup_config():
    """Setup sample configuration."""
    config_path = Path("agentmap_config.yaml")
    initialize_di(config_path)

    with open(config_path, "w") as f:
        f.write(SAMPLE_CONFIG)
    print(f"Created sample config at {config_path}")

def run_sample_workflow():
    """Run a sample workflow with tracking."""
    from agentmap.runner import run_graph
    
    # Initial state
    initial_state = {
        "input": "Sample input data"
    }
    
    # Run graph
    print("\nRunning graph with execution tracking...")
    result = run_graph("SampleGraph", initial_state)
    
    # Check if tracking data is present
    if "__execution_summary" in result:
        summary = result["__execution_summary"]
        policy_success = result.get("__policy_success", False)
        
        print("\nExecution Summary:")
        print(f"- Overall success: {summary['overall_success']}")
        print(f"- Policy success: {summary['graph_success']}")
        
        print("\nTo check success status mid-execution:")
        print('    if result["graph_success"]:')
        print('        print("Graph still on successful path!")')
        print('    else:')
        print('        print("Graph has deviated from successful path!")')
        print(f"- Total duration: {summary['total_duration']:.2f}s")
        print(f"- Execution path: {summary['execution_path']}")
        
        print("\nNode Results:")
        for node, data in summary["node_results"].items():
            status = "✅ Success" if data["success"] else "❌ Failed"
            duration = data["duration"] * 1000 if data["duration"] else 0  # Convert to ms
            print(f"- {node}: {status} ({duration:.2f}ms)")
            if not data["success"] and data.get("error"):
                print(f"  Error: {data['error']}")
    else:
        print("No execution tracking data found in result.")
    
    print("\nFull Result:")
    # Filter out large tracking data from the print output
    filtered_result = {k: v for k, v in result.items() if k not in ["__execution_summary"]}
    print(json.dumps(filtered_result, indent=2))
    
    return result

def main():
    """Run the example script."""
    setup_config()
    run_sample_workflow()

if __name__ == "__main__":
    main()
