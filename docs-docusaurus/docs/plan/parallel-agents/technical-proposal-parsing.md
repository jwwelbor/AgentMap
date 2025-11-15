# Technical Proposal: CSV Parsing and Node Model Changes

## Overview

This proposal details the changes required for CSV parsing and domain models to support parallel agent execution. The implementation enables pipe-separated target syntax while maintaining 100% backward compatibility with existing single-target workflows.

---

## Current State Analysis

### CSV Parser Current Behavior

**File:** `src/agentmap/services/csv_graph_parser_service.py`

**Current Implementation (Lines 318-320):**
```python
# Parse edge information
edge = self._safe_get_field(row, "Edge").strip() or None
success_next = self._safe_get_field(row, "Success_Next").strip() or None
failure_next = self._safe_get_field(row, "Failure_Next").strip() or None
```

**Problem:** Pipe characters are treated as literal strings. Input like `"ProcessA|ProcessB|ProcessC"` is stored as a single string, not parsed as multiple targets.

### Node Model Current Behavior

**File:** `src/agentmap/models/node.py`

**Current Implementation (Lines 54-66):**
```python
def __init__(self, ...):
    ...
    self.edges: Dict[str, str] = {}  # condition: next_node

def add_edge(self, condition: str, target_node: str) -> None:
    """Store an edge relationship to another node."""
    self.edges[condition] = target_node
```

**Problem:** `edges` dictionary stores `str` values only. Cannot represent multiple target nodes for parallel execution.

### NodeSpec Model Current Behavior

**File:** `src/agentmap/models/graph_spec.py`

**Current Implementation (Lines 27-30):**
```python
@dataclass
class NodeSpec:
    ...
    # Edge information (raw from CSV)
    edge: Optional[str] = None
    success_next: Optional[str] = None
    failure_next: Optional[str] = None
```

**Problem:** Edge fields are typed as `Optional[str]`, cannot hold lists of targets.

---

## Proposed Changes

### Change 1: NodeSpec Data Model

**File:** `src/agentmap/models/graph_spec.py`

**Proposed Implementation:**
```python
from typing import Optional, Union, List

@dataclass
class NodeSpec:
    """Specification for a single node parsed from CSV."""
    
    name: str
    graph_name: str
    agent_type: Optional[str] = None
    prompt: Optional[str] = None
    description: Optional[str] = None
    context: Optional[str] = None
    input_fields: List[str] = field(default_factory=list)
    output_field: Optional[str] = None
    
    # Edge information (raw from CSV)
    # NEW: Support both single target (str) and multiple targets (list[str])
    edge: Optional[Union[str, List[str]]] = None
    success_next: Optional[Union[str, List[str]]] = None
    failure_next: Optional[Union[str, List[str]]] = None
    
    # Tool information
    available_tools: Optional[List[str]] = None
    tool_source: Optional[str] = None
    
    # Metadata
    line_number: Optional[int] = None
    
    # NEW: Helper methods for edge type checking
    def is_parallel_edge(self, edge_type: str) -> bool:
        """Check if specified edge type has multiple targets.
        
        Args:
            edge_type: One of 'edge', 'success_next', 'failure_next'
            
        Returns:
            True if edge has multiple targets, False otherwise
        """
        edge_value = getattr(self, edge_type, None)
        return isinstance(edge_value, list) and len(edge_value) > 1
    
    def get_edge_targets(self, edge_type: str) -> List[str]:
        """Get edge targets as a list (always returns list).
        
        Args:
            edge_type: One of 'edge', 'success_next', 'failure_next'
            
        Returns:
            List of target node names (may be empty, single, or multiple)
        """
        edge_value = getattr(self, edge_type, None)
        if edge_value is None:
            return []
        elif isinstance(edge_value, str):
            return [edge_value]
        else:
            return edge_value
```

**Rationale:**
- `Union[str, List[str]]` allows both single-target (existing) and multi-target (new) edges
- Helper methods provide clean API for type checking
- Backward compatible: existing code reading strings still works

---

### Change 2: Node Domain Model

**File:** `src/agentmap/models/node.py`

**Proposed Implementation:**
```python
from typing import Any, Dict, List, Optional, Union

class Node:
    """Domain entity representing a workflow node."""
    
    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        agent_type: Optional[str] = None,
        inputs: Optional[List[str]] = None,
        output: Optional[str] = None,
        prompt: Optional[str] = None,
        description: Optional[str] = None,
        tool_source: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.context = context
        self.agent_type = agent_type
        self.inputs = inputs or []
        self.output = output
        self.prompt = prompt
        self.description = description
        self.tool_source = tool_source
        self.available_tools = available_tools
        # NEW: Support both str and list[str] for parallel edges
        self.edges: Dict[str, Union[str, List[str]]] = {}
    
    def add_edge(self, condition: str, target_node: Union[str, List[str]]) -> None:
        """Store an edge relationship to another node(s).
        
        Supports both single-target and multi-target (parallel) edges.
        
        Args:
            condition: Routing condition (e.g., 'success', 'failure', 'default')
            target_node: Name of target node (str) or list of target nodes (list[str])
        
        Examples:
            node.add_edge("success", "NextNode")  # Single target (existing)
            node.add_edge("success", ["A", "B", "C"])  # Parallel targets (new)
        """
        self.edges[condition] = target_node
    
    def is_parallel_edge(self, condition: str) -> bool:
        """Check if edge condition routes to multiple parallel nodes.
        
        Args:
            condition: Edge condition to check
            
        Returns:
            True if edge has multiple targets, False otherwise
        """
        edge_value = self.edges.get(condition)
        return isinstance(edge_value, list) and len(edge_value) > 1
    
    def get_edge_targets(self, condition: str) -> List[str]:
        """Get edge targets as a list (normalized view).
        
        Always returns a list for consistent handling, whether edge is
        single-target or multi-target.
        
        Args:
            condition: Edge condition to retrieve
            
        Returns:
            List of target node names (empty if condition not found)
        """
        edge_value = self.edges.get(condition)
        if edge_value is None:
            return []
        elif isinstance(edge_value, str):
            return [edge_value]
        else:
            return list(edge_value)  # Return copy to prevent mutation
    
    def has_conditional_routing(self) -> bool:
        """Check if this node has conditional routing (success/failure paths).
        
        Returns:
            True if node has 'success' or 'failure' edges, False otherwise
        """
        return "success" in self.edges or "failure" in self.edges
    
    def __repr__(self) -> str:
        """String representation of the node."""
        edge_parts = []
        for condition, targets in self.edges.items():
            if isinstance(targets, list):
                targets_str = "|".join(targets)
                edge_parts.append(f"{condition}->{targets_str}")
            else:
                edge_parts.append(f"{condition}->{targets}")
        edge_info = ", ".join(edge_parts)
        return f"<Node {self.name} [{self.agent_type}] → {edge_info}>"
```

**Rationale:**
- `add_edge()` now accepts both `str` and `List[str]` (backward compatible)
- New helper methods provide clean API for parallel edge detection
- `__repr__` shows parallel edges with pipe notation for debugging

---

### Change 3: CSV Parser - Pipe Delimiter Detection

**File:** `src/agentmap/services/csv_graph_parser_service.py`

**Add new helper method (after line 377):**
```python
def _parse_edge_targets(self, edge_value: str) -> Optional[Union[str, List[str]]]:
    """Parse edge target(s) from CSV field value.
    
    Detects pipe-separated targets for parallel execution and returns
    appropriate type (str for single, list for multiple).
    
    Args:
        edge_value: Raw edge value from CSV field
        
    Returns:
        - None if empty/whitespace
        - str if single target
        - list[str] if multiple pipe-separated targets
        
    Examples:
        _parse_edge_targets("")                -> None
        _parse_edge_targets("NextNode")        -> "NextNode"
        _parse_edge_targets("A|B|C")           -> ["A", "B", "C"]
        _parse_edge_targets("Node | Other")    -> ["Node", "Other"]
    """
    if not edge_value or not edge_value.strip():
        return None
    
    # Check for pipe delimiter indicating parallel targets
    if "|" in edge_value:
        # Split on pipe and clean each target
        targets = [
            target.strip() 
            for target in edge_value.split("|")
            if target.strip()  # Filter out empty strings
        ]
        
        # Validate targets
        if not targets:
            self.logger.warning(
                f"Edge value '{edge_value}' contains pipes but no valid targets"
            )
            return None
        
        # Return list for multiple targets (parallel execution)
        if len(targets) > 1:
            self.logger.debug(
                f"Parsed parallel edge targets: {targets}"
            )
            return targets
        
        # Single target after splitting (edge case: "NodeA|")
        return targets[0]
    
    # No pipe delimiter - single target (existing behavior)
    return edge_value.strip()
```

**Update existing parsing logic (lines 318-320):**
```python
# Parse edge information - NOW supports parallel targets
edge = self._parse_edge_targets(self._safe_get_field(row, "Edge"))
success_next = self._parse_edge_targets(self._safe_get_field(row, "Success_Next"))
failure_next = self._parse_edge_targets(self._safe_get_field(row, "Failure_Next"))
```

**Rationale:**
- Single method handles all edge types consistently
- Automatic detection of parallel vs single targets
- Extensive validation and logging for debugging
- Handles edge cases (trailing pipes, whitespace)

---

### Change 4: CSV Parser - Node Conversion

**File:** `src/agentmap/services/csv_graph_parser_service.py`

**Update `_convert_node_specs_to_nodes()` (lines 540-546):**
```python
# Add edge information - NOW supports parallel targets
if node_spec.edge:
    node.add_edge("default", node_spec.edge)
elif node_spec.success_next or node_spec.failure_next:
    if node_spec.success_next:
        node.add_edge("success", node_spec.success_next)
    if node_spec.failure_next:
        node.add_edge("failure", node_spec.failure_next)
```

**No changes needed!** The existing code already passes edge values directly to `node.add_edge()`, which now accepts both `str` and `List[str]`.

---

## Migration Strategy

### Backward Compatibility

**Guaranteed Compatibility:**
1. **Existing CSV files** with single targets work unchanged
2. **Existing code** reading `node.edges` values works for strings
3. **Type checking** allows both `str` and `List[str]`

**Potential Issues:**
1. Code that assumes `edges` values are always `str` may need type guards
2. Code that directly compares edge values may need normalization

**Mitigation:**
- Use new helper methods: `is_parallel_edge()`, `get_edge_targets()`
- Gradual migration: old code continues working, new code uses helpers

### Data Migration

**Bundle Compatibility:**
- New bundles include `Union[str, List[str]]` edge data
- Old bundles deserialize correctly (all strings)
- No migration script needed

**CSV Migration:**
- No migration required for existing CSVs
- Users opt-in to parallel routing by adding pipes

---

## Test Cases

### Test 1: Single Target Parsing (Backward Compatibility)
```python
def test_parse_single_target_edge():
    """Test that single targets are parsed as strings (existing behavior)."""
    parser = CSVGraphParserService(logging_service)
    
    # Single target should remain string, not list
    result = parser._parse_edge_targets("NextNode")
    assert result == "NextNode"
    assert isinstance(result, str)
```

### Test 2: Multiple Target Parsing (New Functionality)
```python
def test_parse_parallel_targets():
    """Test that pipe-separated targets are parsed as list."""
    parser = CSVGraphParserService(logging_service)
    
    # Multiple targets should become list
    result = parser._parse_edge_targets("NodeA|NodeB|NodeC")
    assert result == ["NodeA", "NodeB", "NodeC"]
    assert isinstance(result, list)
```

### Test 3: Whitespace Handling
```python
def test_parse_targets_with_whitespace():
    """Test that whitespace is trimmed from targets."""
    parser = CSVGraphParserService(logging_service)
    
    result = parser._parse_edge_targets(" Node1 | Node2 | Node3 ")
    assert result == ["Node1", "Node2", "Node3"]
```

### Test 4: Edge Cases
```python
def test_parse_edge_cases():
    """Test edge cases in target parsing."""
    parser = CSVGraphParserService(logging_service)
    
    # Empty string
    assert parser._parse_edge_targets("") is None
    assert parser._parse_edge_targets("   ") is None
    
    # Trailing pipe
    assert parser._parse_edge_targets("NodeA|") == "NodeA"
    
    # Empty middle element
    result = parser._parse_edge_targets("A||C")
    assert result == ["A", "C"]  # Empty element filtered out
```

### Test 5: Node Edge Storage
```python
def test_node_stores_parallel_edges():
    """Test that Node correctly stores parallel edges."""
    node = Node(name="TestNode", agent_type="default")
    
    # Single target
    node.add_edge("success", "SingleTarget")
    assert node.edges["success"] == "SingleTarget"
    assert not node.is_parallel_edge("success")
    
    # Multiple targets
    node.add_edge("failure", ["A", "B", "C"])
    assert node.edges["failure"] == ["A", "B", "C"]
    assert node.is_parallel_edge("failure")
```

### Test 6: Node Edge Retrieval
```python
def test_node_get_edge_targets():
    """Test normalized edge target retrieval."""
    node = Node(name="TestNode", agent_type="default")
    
    # No edge
    assert node.get_edge_targets("nonexistent") == []
    
    # Single edge
    node.add_edge("success", "Single")
    assert node.get_edge_targets("success") == ["Single"]
    
    # Multiple edges
    node.add_edge("failure", ["A", "B", "C"])
    assert node.get_edge_targets("failure") == ["A", "B", "C"]
```

### Test 7: Full CSV Parsing Integration
```python
def test_parse_csv_with_parallel_routing():
    """Integration test: Parse CSV with parallel routing."""
    csv_content = """
GraphName,Node,AgentType,Success_Next,Failure_Next
ParallelTest,Start,input,ProcessA|ProcessB|ProcessC,Error
ParallelTest,ProcessA,default,Consolidate,
ParallelTest,ProcessB,default,Consolidate,
ParallelTest,ProcessC,default,Consolidate,
ParallelTest,Consolidate,summary,,
ParallelTest,Error,echo,,
"""
    
    # Write to temp CSV and parse
    graph_spec = parser.parse_csv_to_graph_spec(temp_csv_path)
    nodes = parser._convert_node_specs_to_nodes(
        graph_spec.get_nodes_for_graph("ParallelTest")
    )
    
    # Verify parallel edge
    start_node = nodes["Start"]
    assert start_node.is_parallel_edge("success")
    assert start_node.get_edge_targets("success") == ["ProcessA", "ProcessB", "ProcessC"]
    
    # Verify single edges (backward compatibility)
    assert nodes["ProcessA"].edges["success"] == "Consolidate"
    assert isinstance(nodes["ProcessA"].edges["success"], str)
```

---

## Acceptance Criteria

### Functional Requirements
- ✅ CSV parser detects `|` in Edge, Success_Next, Failure_Next columns
- ✅ Parser splits pipe-separated values into list of strings
- ✅ Parser trims whitespace from each target
- ✅ Parser preserves single-target as string (not single-item list)
- ✅ Node model stores both `str` and `List[str]` edge values
- ✅ Node provides helper methods for parallel edge detection

### Backward Compatibility
- ✅ Existing CSV files parse without errors
- ✅ Single-target edges remain strings
- ✅ All existing tests pass without modification
- ✅ Node API remains compatible

### Code Quality
- ✅ >95% code coverage for new parsing logic
- ✅ Comprehensive edge case handling
- ✅ Clear error messages for invalid input
- ✅ Extensive logging for debugging

---

## Implementation Checklist

- [ ] Update `graph_spec.py` NodeSpec with Union types
- [ ] Add helper methods to NodeSpec
- [ ] Update `node.py` Node with Union types
- [ ] Add helper methods to Node class
- [ ] Update Node.__repr__ for parallel edges
- [ ] Add `_parse_edge_targets()` to CSVGraphParserService
- [ ] Update `_parse_row_to_node_spec()` to use new parser
- [ ] Write unit tests for `_parse_edge_targets()`
- [ ] Write unit tests for Node parallel edge methods
- [ ] Write integration test for CSV parsing with parallel edges
- [ ] Update type hints throughout codebase
- [ ] Run full test suite to verify backward compatibility
- [ ] Update documentation with examples

---

## Related Files

### Modified Files
- `src/agentmap/models/graph_spec.py` - NodeSpec data model
- `src/agentmap/models/node.py` - Node domain model
- `src/agentmap/services/csv_graph_parser_service.py` - CSV parsing logic

### Test Files to Create
- `tests/unit/test_node_parallel_edges.py` - Node model tests
- `tests/unit/test_csv_parser_parallel.py` - Parser tests
- `tests/integration/test_parallel_csv_parsing.py` - Integration tests

### Example Files to Create
- `examples/parallel_routing_simple.csv` - Basic parallel example
- `examples/parallel_routing_mixed.csv` - Mixed sequential/parallel

---

## Next Steps

1. Implement NodeSpec changes in `graph_spec.py`
2. Implement Node changes in `node.py`
3. Write unit tests for Node helper methods
4. Implement CSV parser changes
5. Write unit tests for parser
6. Create integration tests
7. Verify backward compatibility
8. Update documentation

---

## Questions and Assumptions

### Questions
1. Should we support nested parallel routing (parallel within parallel)?
   - **Answer:** No, out of scope for initial implementation
2. Should we validate that all parallel targets exist during parsing?
   - **Answer:** Yes, but as a warning not an error (validation happens in assembly)
3. How to handle conflicting output_field in parallel branches?
   - **Answer:** Validation in bundle system, not parser

### Assumptions
1. LangGraph handles state merging from parallel branches
2. Pipe `|` is the correct delimiter (matches documentation)
3. Whitespace trimming is always desired
4. Empty targets (e.g., `A||B`) should be filtered out
