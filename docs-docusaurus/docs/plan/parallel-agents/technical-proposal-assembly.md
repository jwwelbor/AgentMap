# Technical Proposal: Graph Assembly Changes for Parallel Execution

## Overview

This proposal details changes to `GraphAssemblyService` to support parallel agent execution using LangGraph's native list-based routing. The implementation generates conditional edges that return lists of node names to trigger LangGraph's parallel superstep execution.

---

## Current State Analysis

### GraphAssemblyService Current Behavior

**File:** `src/agentmap/services/graph/graph_assembly_service.py`

**Current Edge Processing (Lines 285-358):**
```python
def process_node_edges(self, node_name: str, edges: Dict[str, str]) -> None:
    """Process edges for a node and add them to the graph."""
    # ... orchestrator handling ...
    
    # Check for function-based routing first
    if self._try_add_function_edge(node_name, edges):
        return
    
    # Handle standard edge types
    self._add_standard_edges(node_name, edges)

def _add_standard_edges(self, node_name: str, edges: Dict[str, str]) -> None:
    """Add standard edge types (success/failure/default)."""
    has_success = "success" in edges
    has_failure = "failure" in edges
    
    if has_success and has_failure:
        self._add_success_failure_edge(
            node_name, edges["success"], edges["failure"]
        )
    elif has_success:
        self._add_conditional_edge(
            node_name,
            lambda state: (
                edges["success"] if state.get("last_action_success", True) else None
            ),
        )
    # ... other cases ...

def _add_success_failure_edge(
    self, source: str, success: str, failure: str
) -> None:
    """Add success/failure conditional edges."""
    
    def branch(state):
        return success if state.get("last_action_success", True) else failure
    
    self.builder.add_conditional_edges(source, branch)
```

**Problem:** All routing functions return single strings, cannot trigger parallel execution.

---

## Proposed Changes

### Change 1: Type-Aware Edge Processing

**Add new method to detect edge types (after line 313):**
```python
def _is_parallel_edge(self, edge_value) -> bool:
    """Check if edge value represents parallel targets.
    
    Args:
        edge_value: Edge value from node.edges (str or list[str])
        
    Returns:
        True if edge has multiple targets for parallel execution
    """
    return isinstance(edge_value, list) and len(edge_value) > 1

def _normalize_edge_value(self, edge_value) -> tuple[bool, Union[str, List[str]]]:
    """Normalize edge value and determine if parallel.
    
    Args:
        edge_value: Edge value from node.edges
        
    Returns:
        Tuple of (is_parallel, normalized_value)
        - is_parallel: True if multiple targets
        - normalized_value: The edge value (str or list)
    """
    if edge_value is None:
        return False, None
    elif isinstance(edge_value, str):
        return False, edge_value
    elif isinstance(edge_value, list):
        if len(edge_value) == 0:
            return False, None
        elif len(edge_value) == 1:
            return False, edge_value[0]  # Single item list -> string
        else:
            return True, edge_value  # Multiple items -> parallel
    else:
        # Unexpected type, treat as single
        self.logger.warning(
            f"Unexpected edge value type: {type(edge_value)}. Treating as single target."
        )
        return False, str(edge_value)
```

---

### Change 2: Enhanced Standard Edge Handler

**Update `_add_standard_edges()` method (lines 331-358):**
```python
def _add_standard_edges(self, node_name: str, edges: Dict[str, Union[str, List[str]]]) -> None:
    """Add standard edge types with parallel support.
    
    Handles success/failure/default edges and detects parallel targets.
    
    Args:
        node_name: Source node name
        edges: Dictionary of edge conditions to targets (str or list[str])
    """
    has_success = "success" in edges
    has_failure = "failure" in edges
    has_default = "default" in edges
    
    # Analyze edge types for parallel routing
    success_parallel = False
    failure_parallel = False
    success_targets = None
    failure_targets = None
    
    if has_success:
        success_parallel, success_targets = self._normalize_edge_value(edges["success"])
    if has_failure:
        failure_parallel, failure_targets = self._normalize_edge_value(edges["failure"])
    
    # Route to appropriate handler based on parallel detection
    if has_success and has_failure:
        # Both success and failure paths
        if success_parallel or failure_parallel:
            self._add_parallel_success_failure_edge(
                node_name, 
                success_targets, success_parallel,
                failure_targets, failure_parallel
            )
        else:
            # Both single targets (existing behavior)
            self._add_success_failure_edge(
                node_name, success_targets, failure_targets
            )
    elif has_success:
        # Only success path
        if success_parallel:
            self._add_conditional_edge(
                node_name,
                lambda state, targets=success_targets: (
                    targets if state.get("last_action_success", True) else None
                )
            )
            self.logger.debug(
                f"[{node_name}] → parallel success → {success_targets}"
            )
        else:
            # Single success target (existing behavior)
            self._add_conditional_edge(
                node_name,
                lambda state, target=success_targets: (
                    target if state.get("last_action_success", True) else None
                ),
            )
    elif has_failure:
        # Only failure path
        if failure_parallel:
            self._add_conditional_edge(
                node_name,
                lambda state, targets=failure_targets: (
                    targets if not state.get("last_action_success", True) else None
                )
            )
            self.logger.debug(
                f"[{node_name}] → parallel failure → {failure_targets}"
            )
        else:
            # Single failure target (existing behavior)
            self._add_conditional_edge(
                node_name,
                lambda state, target=failure_targets: (
                    target if not state.get("last_action_success", True) else None
                ),
            )
    elif has_default:
        # Unconditional edge (default)
        default_parallel, default_targets = self._normalize_edge_value(edges["default"])
        if default_parallel:
            # Parallel default edge - return list directly
            self.logger.debug(
                f"[{node_name}] → parallel default → {default_targets}"
            )
            # For default parallel, we need a routing function that always returns the list
            self._add_conditional_edge(
                node_name,
                lambda state, targets=default_targets: targets
            )
        else:
            # Single default edge (existing behavior)
            self.builder.add_edge(node_name, default_targets)
            self.logger.debug(f"[{node_name}] → default → {default_targets}")
```

**Rationale:**
- Detects parallel routing for all edge types
- Uses normalization to handle single-item lists
- Preserves exact existing behavior for single targets
- Lambda capture ensures correct target binding

---

### Change 3: New Parallel Success/Failure Handler

**Add new method (after line 374):**
```python
def _add_parallel_success_failure_edge(
    self, 
    source: str, 
    success_targets: Union[str, List[str]], 
    success_parallel: bool,
    failure_targets: Union[str, List[str]], 
    failure_parallel: bool
) -> None:
    """Add success/failure edges with parallel support.
    
    Generates routing function that returns either:
    - Single target (str) for sequential routing
    - Multiple targets (list[str]) for parallel routing
    
    LangGraph's superstep architecture handles parallel execution automatically
    when the routing function returns a list.
    
    Args:
        source: Source node name
        success_targets: Target(s) for success path (str or list[str])
        success_parallel: True if success has multiple targets
        failure_targets: Target(s) for failure path (str or list[str])
        failure_parallel: True if failure has multiple targets
    """
    
    def branch(state):
        """Routing function that may return str or list[str]."""
        last_action_success = state.get("last_action_success", True)
        
        if last_action_success:
            # Success path
            result = success_targets  # May be str or list[str]
            if success_parallel:
                self.logger.debug(
                    f"[{source}] Routing to parallel success targets: {result}"
                )
            return result
        else:
            # Failure path
            result = failure_targets  # May be str or list[str]
            if failure_parallel:
                self.logger.debug(
                    f"[{source}] Routing to parallel failure targets: {result}"
                )
            return result
    
    self.builder.add_conditional_edges(source, branch)
    
    # Enhanced logging for parallel edges
    success_display = (
        f"{success_targets} (parallel)" if success_parallel 
        else success_targets
    )
    failure_display = (
        f"{failure_targets} (parallel)" if failure_parallel 
        else failure_targets
    )
    self.logger.debug(
        f"[{source}] → success → {success_display} / failure → {failure_display}"
    )
```

**Rationale:**
- Single method handles all combinations (single/parallel success/failure)
- Returns appropriate type (str or list) based on configuration
- LangGraph automatically handles parallel execution for list returns
- Enhanced logging distinguishes parallel from sequential routing

---

### Change 4: Update Existing Success/Failure Handler

**Update `_add_success_failure_edge()` to maintain clarity (lines 365-374):**
```python
def _add_success_failure_edge(
    self, source: str, success: str, failure: str
) -> None:
    """Add single-target success/failure conditional edges.
    
    This is the existing behavior for single-target routing.
    For parallel routing, use _add_parallel_success_failure_edge().
    
    Args:
        source: Source node name
        success: Single success target
        failure: Single failure target
    """
    
    def branch(state):
        return success if state.get("last_action_success", True) else failure
    
    self.builder.add_conditional_edges(source, branch)
    self.logger.debug(f"[{source}] → success → {success} / failure → {failure}")
```

**Rationale:**
- Preserves existing behavior exactly
- Clear documentation distinguishes from parallel version
- No performance overhead for single-target routing

---

### Change 5: Update Function-Based Routing

**Update `_add_function_edge()` to support parallel returns (lines 376-390):**
```python
def _add_function_edge(
    self,
    source: str,
    func_name: str,
    success: Optional[Union[str, List[str]]],
    failure: Optional[Union[str, List[str]]],
) -> None:
    """Add function-based routing edge with parallel support.
    
    The routing function may return str or list[str], enabling parallel
    routing when the function logic determines multiple targets.
    
    Args:
        source: Source node name
        func_name: Name of routing function to load
        success: Success target(s) - may be str or list[str]
        failure: Failure target(s) - may be str or list[str]
    """
    func = self.function_resolution.load_function(func_name)
    
    def wrapped(state):
        # Function may return str or list[str]
        result = func(state, success, failure)
        
        # Log parallel routing if function returns list
        if isinstance(result, list) and len(result) > 1:
            self.logger.debug(
                f"[{source}] Function '{func_name}' returned parallel targets: {result}"
            )
        
        return result
    
    self.builder.add_conditional_edges(source, wrapped)
    self.logger.debug(
        f"[{source}] → routed by function '{func_name}' "
        f"(success={success}, failure={failure})"
    )
```

**Rationale:**
- Routing functions can now return lists for parallel execution
- Backward compatible with functions returning strings
- Logging shows when parallel routing occurs

---

## LangGraph Integration

### How LangGraph Handles Parallel Execution

**From LangGraph Documentation:**
> When `add_conditional_edges()` routing functions return a list of node names, all those nodes will be run in parallel as part of the next superstep.

**Example:**
```python
# Single-target routing (existing behavior)
def route_single(state):
    return "NextNode"  # str -> sequential execution

graph.add_conditional_edges("Start", route_single)

# Multi-target routing (new behavior)
def route_parallel(state):
    return ["NodeA", "NodeB", "NodeC"]  # list -> parallel execution

graph.add_conditional_edges("Start", route_parallel)
```

**State Synchronization:**
- LangGraph automatically waits for all parallel branches to complete
- State updates from all branches are merged before next node executes
- Each parallel agent updates its own output_field (no conflicts if designed correctly)

**Fan-In Pattern:**
```python
# All three parallel nodes route to same consolidator
# LangGraph automatically synchronizes at the consolidator
ProcessA → Consolidate
ProcessB → Consolidate
ProcessC → Consolidate
```

---

## Edge Case Handling

### Case 1: Empty Edge List
```python
# Parser ensures empty lists become None
edges = {"success": []}  # Invalid, filtered by parser
# GraphAssemblyService sees: edges = {}
```

### Case 2: Single-Item List
```python
# Normalization converts to string for efficiency
edges = {"success": ["OnlyNode"]}
# Normalized to: edges = {"success": "OnlyNode"}
# Uses existing single-target code path
```

### Case 3: Mixed Parallel and Single
```python
edges = {
    "success": ["A", "B", "C"],  # Parallel
    "failure": "ErrorHandler"     # Single
}
# Supported! Uses _add_parallel_success_failure_edge
```

### Case 4: All Default (Unconditional Parallel)
```python
edges = {"default": ["X", "Y", "Z"]}
# Supported! Uses conditional edge with always-list function
```

---

## Testing Strategy

### Test 1: Single-Target Backward Compatibility
```python
def test_single_target_routing_unchanged():
    """Verify single-target routing behavior is unchanged."""
    graph = create_test_graph()
    assembly_service = create_assembly_service()
    
    node = Node(name="Start", agent_type="input")
    node.add_edge("success", "Next")  # Single target
    
    agent_instances = {"Start": mock_agent, "Next": mock_agent}
    
    compiled = assembly_service.assemble_graph(
        graph, agent_instances
    )
    
    # Verify routing function returns string, not list
    # (internal test of routing logic)
```

### Test 2: Parallel Success Edge
```python
def test_parallel_success_routing():
    """Test parallel routing on success path."""
    node = Node(name="Start", agent_type="input")
    node.add_edge("success", ["A", "B", "C"])  # Parallel
    
    # ... assemble and execute ...
    
    # Verify all three nodes execute concurrently
    # Verify state contains updates from all three
```

### Test 3: Mixed Parallel and Single
```python
def test_mixed_parallel_single_routing():
    """Test mix of parallel success and single failure."""
    node = Node(name="Process", agent_type="default")
    node.add_edge("success", ["A", "B", "C"])  # Parallel
    node.add_edge("failure", "Error")            # Single
    
    # Test success path (parallel)
    # Test failure path (single)
```

### Test 4: Parallel Default Edge
```python
def test_parallel_default_edge():
    """Test unconditional parallel routing."""
    node = Node(name="Start", agent_type="input")
    node.add_edge("default", ["X", "Y", "Z"])
    
    # Verify routing function always returns list
```

### Test 5: Function-Based Parallel Routing
```python
def test_function_returns_parallel_targets():
    """Test routing function that returns list."""
    # Create routing function that returns list based on state
    def dynamic_router(state, success, failure):
        if state.get("branch_count") > 2:
            return ["A", "B", "C"]  # Parallel
        else:
            return "Single"  # Sequential
    
    # Test both paths
```

---

## Performance Considerations

### Overhead Analysis

**Single-Target Path (Existing):**
- Type check: `isinstance(edge_value, str)` → **~0.1μs**
- No additional overhead

**Multi-Target Path (New):**
- Type check: `isinstance(edge_value, list)` → **~0.1μs**
- List length check: `len(edge_value) > 1` → **~0.1μs**
- Total overhead: **~0.2μs** (negligible)

**Conclusion:** No measurable performance impact for either path.

---

## Acceptance Criteria

### Functional Requirements
- ✅ Assembly detects when edge has multiple targets
- ✅ Routing functions return list for parallel execution
- ✅ Routing functions return str for single-target (existing)
- ✅ Success/failure edges support parallel targets
- ✅ Default edges support parallel targets
- ✅ Function-based routing supports parallel returns
- ✅ Enhanced logging shows parallel routing decisions

### LangGraph Integration
- ✅ Parallel targets execute concurrently (LangGraph superstep)
- ✅ State synchronization works (fan-in)
- ✅ State updates from parallel branches merge correctly

### Backward Compatibility
- ✅ Single-target routing unchanged
- ✅ All existing tests pass without modification
- ✅ No performance regression

### Code Quality
- ✅ >95% code coverage for new routing logic
- ✅ Clear separation between single and parallel handlers
- ✅ Comprehensive edge case handling

---

## Implementation Checklist

- [ ] Add `_is_parallel_edge()` helper method
- [ ] Add `_normalize_edge_value()` helper method
- [ ] Update `_add_standard_edges()` with parallel detection
- [ ] Add `_add_parallel_success_failure_edge()` method
- [ ] Update `_add_success_failure_edge()` documentation
- [ ] Update `_add_function_edge()` for parallel returns
- [ ] Update type hints for edges: `Dict[str, Union[str, List[str]]]`
- [ ] Add enhanced logging for parallel routing
- [ ] Write unit tests for parallel edge detection
- [ ] Write unit tests for parallel routing functions
- [ ] Write integration tests for parallel execution
- [ ] Verify LangGraph parallel execution with test graph
- [ ] Update documentation with parallel routing examples

---

## Code Examples

### Example 1: Simple Parallel Routing
```python
# CSV:
# Node,Success_Next
# Start,ProcessA|ProcessB|ProcessC

# Generated routing function:
def route_success(state):
    if state.get("last_action_success", True):
        return ["ProcessA", "ProcessB", "ProcessC"]  # Parallel!
    else:
        return None
```

### Example 2: Mixed Routing
```python
# CSV:
# Node,Success_Next,Failure_Next
# Process,A|B|C,ErrorHandler

# Generated routing function:
def route_mixed(state):
    if state.get("last_action_success", True):
        return ["A", "B", "C"]  # Parallel on success
    else:
        return "ErrorHandler"  # Sequential on failure
```

### Example 3: Conditional Parallel
```python
# Routing function that returns list or str based on state
def smart_router(state, success, failure):
    branch_count = state.get("branch_count", 1)
    
    if branch_count > 5:
        # Many branches - use parallel
        return ["Handler1", "Handler2", "Handler3"]
    else:
        # Few branches - use sequential
        return "SingleHandler"
```

---

## Related Files

### Modified Files
- `src/agentmap/services/graph/graph_assembly_service.py` - Core assembly logic

### Test Files to Create
- `tests/unit/test_assembly_parallel_routing.py` - Unit tests for routing
- `tests/integration/test_parallel_execution.py` - Integration tests with LangGraph

### Example Files to Create
- `examples/parallel_fanout.csv` - Fan-out pattern example
- `examples/parallel_mixed.csv` - Mixed sequential/parallel example

---

## Next Steps

1. Implement helper methods for parallel detection
2. Update `_add_standard_edges()` with parallel logic
3. Implement `_add_parallel_success_failure_edge()`
4. Update function-based routing
5. Write comprehensive unit tests
6. Write LangGraph integration tests
7. Verify state synchronization
8. Update documentation with examples
