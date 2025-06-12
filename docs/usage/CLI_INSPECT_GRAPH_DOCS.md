# AgentMap inspect-graph Command Documentation

## Overview

The `agentmap inspect-graph` command makes `get_service_info()` actually useful by providing detailed debugging information about agent service configuration in your graphs.

## Usage

```bash
agentmap inspect-graph GRAPH_NAME [OPTIONS]
```

## Examples

### Basic Inspection
```bash
# Inspect all agents in a graph
agentmap inspect-graph customer_workflow

# Inspect specific node only
agentmap inspect-graph customer_workflow --node validate_user
```

### Detailed Information
```bash
# Show detailed configuration
agentmap inspect-graph customer_workflow --config-details

# Show agent resolution details  
agentmap inspect-graph customer_workflow --resolution

# Use custom CSV file
agentmap inspect-graph my_graph --csv /path/to/custom.csv
```

### Filtering Options
```bash
# Hide protocol information
agentmap inspect-graph customer_workflow --no-protocols

# Hide service information
agentmap inspect-graph customer_workflow --no-services
```

## Sample Output

```
🔍 Inspecting Graph: customer_workflow
==================================================

📊 Graph Overview:
   Resolved Name: customer_workflow
   Total Nodes: 3
   Unique Agent Types: 2
   All Resolvable: ✅
   Resolution Rate: 100.0%

🤖 Node: validate_customer
   Agent Type: LLMAgent
   Description: Validate customer information using LLM
   📋 Services:
      logger_available: ✅
      execution_tracker_available: ✅
      state_adapter_available: ✅
      prompt_manager_available: ✅
      llm_service_configured: ❌ (will be configured at runtime)
      storage_service_configured: ❌
   🔌 Protocols:
      implements_llm_capable: ✅
      implements_storage_capable: ❌
      implements_prompt_capable: ✅
   📝 Configuration:
      Input Fields: ['customer_data']
      Output Field: validation_result

🤖 Node: lookup_database
   Agent Type: DatabaseAgent
   Description: Look up customer in database
   📋 Services:
      logger_available: ✅
      execution_tracker_available: ✅
      state_adapter_available: ✅
      storage_service_configured: ✅
   🔌 Protocols:
      implements_storage_capable: ✅
   📝 Configuration:
      Input Fields: ['customer_id']
      Output Field: customer_record

✅ No issues found - all agents properly configured!

💡 Helpful Commands:
   agentmap diagnose                    # Check system dependencies
   agentmap inspect-graph customer_workflow --config-details  # Show detailed config
   agentmap inspect-graph customer_workflow --node NODE_NAME  # Inspect specific node
```

## Troubleshooting Output

When issues are found:

```
⚠️  Issues Found (1):
   lookup_database: missing_dependencies
      Missing: psycopg2-binary (for PostgreSQL support)
      Error: Cannot resolve agent type 'DatabaseAgent'

💡 Troubleshooting:
   • Check that graph 'customer_workflow' exists in the CSV file
   • Verify CSV file path: /path/to/graphs.csv
   • Run 'agentmap diagnose' to check system dependencies
```

## Integration with Custom Agents

When you create custom agents using the scaffolding template, they automatically include the `_get_child_service_info()` hook:

```python
def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
    """Provide agent-specific service information for debugging."""
    return {
        "services": {
            "my_custom_service_available": self.my_service is not None,
            "api_configured": self.api_key is not None,
        },
        "protocols": {
            "implements_custom_protocol": True
        },
        "custom_configuration": {
            "api_endpoint": self.api_endpoint,
            "timeout": self.timeout,
            "retry_count": self.retry_count
        }
    }
```

This allows the `inspect-graph` command to show your custom service information:

```
🤖 Node: my_custom_node
   Agent Type: MyCustomAgent
   📋 Services:
      logger_available: ✅
      my_custom_service_available: ✅
      api_configured: ✅
   ⚙️  Custom Configuration:
      api_endpoint: https://api.example.com
      timeout: 30
      retry_count: 3
```

## Use Cases

### 1. Debugging Agent Configuration Issues
```bash
# Check why an agent isn't working
agentmap inspect-graph my_graph --node problematic_agent --config-details
```

### 2. Verifying Service Injection
```bash
# Ensure all agents have required services
agentmap inspect-graph my_graph --services
```

### 3. Understanding Agent Capabilities
```bash
# See what protocols each agent implements
agentmap inspect-graph my_graph --protocols
```

### 4. Pre-deployment Validation
```bash
# Check all agents resolve correctly before running
agentmap inspect-graph production_workflow --resolution
```

### 5. Troubleshooting Dependencies
```bash
# Find missing dependencies
agentmap inspect-graph my_graph --resolution
agentmap diagnose  # Follow up with system-level diagnostics
```

## Options Reference

| Option | Description |
|--------|-------------|
| `--csv`, `-c` | Path to CSV file (default: from config) |
| `--config` | Path to custom config file |
| `--node`, `-n` | Inspect specific node only |
| `--services/--no-services` | Show/hide service availability (default: show) |
| `--protocols/--no-protocols` | Show/hide protocol implementations (default: show) |
| `--config-details` | Show detailed configuration information |
| `--resolution` | Show agent resolution details and issues |

## Related Commands

- `agentmap diagnose` - Check system-level dependencies
- `agentmap validate-csv` - Validate CSV file structure
- `agentmap config` - Show configuration values
- `agentmap run GRAPH_NAME` - Run the graph after inspection
