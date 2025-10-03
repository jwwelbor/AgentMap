---
sidebar_position: 4
title: CLI Pretty Output
description: Enhanced output formatting for AgentMap CLI graph execution with detailed execution summaries and debugging information
keywords: [CLI output, pretty printing, debugging, execution tracking, development tools]
---

# CLI Pretty Output Feature

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>CLI Pretty Output</strong></span>
</div>

## Overview

The `--pretty` flag leverages AgentMap's **CLI Presenter Architecture** to format graph execution output for better readability during development and testing. This feature uses the standardized `cli_presenter.py` utilities that provide consistent output formatting across all CLI commands.

## CLI Presenter Architecture

AgentMap uses a sophisticated presentation layer built around the `cli_presenter.py` module that ensures consistent output formatting and error handling across all CLI commands.

### Core Components

**JSON Output Management:**
```python
from agentmap.deployment.cli.utils.cli_presenter import print_json, print_err, map_exception_to_exit_code

# Standardized JSON output with custom encoding
print_json(result)  # Handles AgentMap objects, datetime, dataclasses

# Consistent error output
print_err("Error message")  # Outputs to stderr

# Exception to exit code mapping
exit_code = map_exception_to_exit_code(exception)
```

**Custom JSON Encoder:**
The CLI presenter includes an `AgentMapJSONEncoder` that handles:
- DateTime objects (converted to ISO format)
- StorageResult objects (uses `to_dict()` method)
- Dataclass objects like `ExecutionSummary` and `NodeExecution`
- Nested structures with recursive datetime processing

**Error Handling Integration:**
```python
# Standard pattern used across all commands
try:
    result = runtime_api_function(args...)
    print_json(result)
except Exception as e:
    print_err(str(e))
    exit_code = map_exception_to_exit_code(e)
    raise typer.Exit(code=exit_code)
```

### Exit Code Mapping

The CLI presenter maps runtime exceptions to standard exit codes:

| Exception Type | Exit Code | Description |
|----------------|-----------|-------------|
| `InvalidInputs` | 2 | Invalid command arguments or input data |
| `GraphNotFound` | 3 | Specified graph does not exist |
| `AgentMapNotInitialized` | 4 | Runtime system not properly initialized |
| Other exceptions | 1 | General error condition |
| Success | 0 | Operation completed successfully |

## Usage

### Basic pretty output:
```bash
agentmap run --graph gm_orchestration --pretty
```

### Detailed output with node execution timeline:
```bash
agentmap run --graph gm_orchestration --pretty --verbose
```

## Example Output

### Without --pretty (default behavior):
```
✅ Graph execution completed successfully
✅ Output: {'input': 'end', '__next_node': 'EndNode', 'orchestrator_result': 'EndNode', 'exploration_result': {'processed': True, 'agent_type': 'exploration_router', 'node': 'EnvironmentInteraction', 'timestamp': 'placeholder'}, 'combat_result': {'processed': True, 'agent_type': 'combat_router', 'node': 'CombatTurn', 'timestamp': 'placeholder'}, '__execution_summary': ExecutionSummary(...), '__policy_success': True}
```

### With --pretty:
```
✅ Graph execution completed successfully
================================================================================
GRAPH EXECUTION SUMMARY
================================================================================

Graph Name: gm_orchestration
Status: COMPLETED
Success: ✅ Yes
Total Duration: 4032.04 seconds
Start Time: 2025-07-02 02:07:50
End Time: 2025-07-02 03:15:02

Nodes Executed: 12

================================================================================
NODE EXECUTION ORDER
================================================================================
 1. UserInput                       29.8s ✅  → "run for cover"
 2. Orchestrator                     2.0s ✅  → EnvironmentInteraction
 3. EnvironmentInteraction           0.0s ✅
 4. UserInput                     3899.6s ✅  → "climb the tree"
 5. Orchestrator                     2.9s ✅  → EnvironmentInteraction
 6. EnvironmentInteraction           0.0s ✅
 7. UserInput                       83.0s ✅  → "punch the zombie"
 8. Orchestrator                     0.8s ✅  → CombatTurn
 9. CombatTurn                       0.0s ✅
10. UserInput                       13.4s ✅  → "end"
11. Orchestrator                     0.6s ✅  → EndNode
12. EndNode                          0.0s ✅

================================================================================
FINAL STATE
================================================================================
Orchestrator Decision: EndNode
Exploration Result: EnvironmentInteraction
Combat Result: CombatTurn

Policy Success: ✅ Yes

Last Input: end
Next Node: EndNode

ℹ️  Use --pretty --verbose to see detailed node execution info
```

### With --pretty --verbose:
Includes detailed node-by-node execution timeline with:
- Node names and execution order
- Success/failure status
- Execution duration
- Time window (start → end)
- Output preview for each node

## Implementation Details

### Facade Pattern Integration

The pretty output feature is integrated into the runtime facade pattern:

1. **Runtime Facade**: The `run_command` uses `runtime_api.run_workflow()` for execution
2. **CLI Presenter**: Uses `cli_presenter.print_json()` for formatted output
3. **Custom Encoding**: Leverages `AgentMapJSONEncoder` for complex object serialization
4. **Error Handling**: Integrates with `map_exception_to_exit_code()` for consistent error handling

### Implementation Architecture

```python
# In run_command.py
from agentmap.runtime_api import run_workflow
from agentmap.deployment.cli.utils.cli_presenter import print_json

def run_command(pretty: bool = False, verbose: bool = False, **kwargs):
    try:
        # Execute via runtime facade
        result = run_workflow(...)
        
        if pretty:
            # Enhanced formatting for development
            format_pretty_output(result, verbose)
        else:
            # Standard JSON for scripting
            print_json(result)
            
    except Exception as e:
        # Consistent error handling via CLI presenter
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
```

### Service Layer Integration

1. **ExecutionFormatterService**: Handles complex object formatting within the service layer
2. **DI Container Integration**: Service registered in `ApplicationContainer` following established patterns
3. **No Production Impact**: Pretty formatting is presentation-only and doesn't affect workflow execution
4. **Backward Compatibility**: Raw JSON output remains the default for script compatibility

## Notes

- This is a development/testing feature
- No impact on graph execution or performance
- Output formatting is purely for human readability
- Raw output is still available without the flag
- Basic `--pretty` mode shows node execution order with timing
- Verbose mode adds detailed output and timestamps for each node
