# Pretty Output Feature for Graph Execution

## Overview

The `--pretty` flag has been added to the `run` command to format graph execution output for better readability during development and testing.

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

### Without --pretty (current behavior):
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

1. Added `--pretty` boolean flag to the `run` command
2. Added `--verbose` boolean flag for detailed output
3. Created `ExecutionFormatterService` in the services layer following established patterns
4. Added service to DI container (`ApplicationContainer`)
5. No changes to production code paths - only affects display

## Notes

- This is a development/testing feature
- No impact on graph execution or performance
- Output formatting is purely for human readability
- Raw output is still available without the flag
- Basic `--pretty` mode shows node execution order with timing
- Verbose mode adds detailed output and timestamps for each node
