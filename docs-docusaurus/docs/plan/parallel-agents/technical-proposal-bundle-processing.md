# Technical Proposal: Bundle Processing for Parallel Execution

## Overview

This proposal details changes to the bundle system (`GraphBundleService` and `StaticBundleAnalyzer`) to support serialization, analysis, and caching of parallel edge metadata. The implementation ensures bundle integrity while maintaining backward compatibility with existing single-target bundles.

---

## Current State Analysis

### GraphBundleService Current Behavior

**File:** `src/agentmap/services/graph/graph_bundle_service.py`

**Current Serialization (Lines 512-526):**
```python
def _serialize_metadata_bundle(self, bundle: GraphBundle) -> Dict[str, Any]:
    """Serialize enhanced metadata bundle to dictionary format."""
    nodes_data = {}
    for name, node in bundle.nodes.items():
        nodes_data[name] = {
            "name": node.name,
            "agent_type": node.agent_type,
            "context": node.context,
            "inputs": node.inputs,
            "output": node.output,
            "prompt": node.prompt,
            "description": node.description,
            "edges": node.edges,  # <-- Currently Dict[str, str]
            "tool_source": node.tool_source,
            "available_tools": node.available_tools,
        }
    # ...
```

**Problem:** Serialization assumes `node.edges` values are always strings. With parallel routing, edges may be lists.

**Current Deserialization (Lines 605-620):**
```python
def _deserialize_metadata_bundle(self, data: Dict[str, Any]) -> Optional[GraphBundle]:
    """Deserialize enhanced metadata bundle from dictionary format."""
    # Reconstruct nodes
    nodes = {}
    for name, node_data in data["nodes"].items():
        node = Node(
            name=node_data["name"],
            agent_type=node_data.get("agent_type"),
            # ...
        )
        node.edges = node_data.get("edges", {})  # <-- Expects Dict[str, str]
        nodes[name] = node
```

**Problem:** Deserialization doesn't handle list-valued edges.

### StaticBundleAnalyzer Current Behavior

**File:** `src/agentmap/services/static_bundle_analyzer.py`

**Current Analysis (Lines 261-303):**
```python
def _analyze_graph_structure(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
    """Analyze graph structure for optimization hints."""
    # ...
    structure = {
        "node_count": len(nodes),
        "edge_count": edge_count,
        "has_conditional_routing": has_conditional,
        "max_depth": self._calculate_max_depth(nodes),
        "is_dag": self._check_dag(nodes),
        "parallel_opportunities": self._identify_parallel_nodes(nodes),  # <-- Currently returns []
    }
```

**Problem:** `_identify_parallel_nodes()` is stubbed out and doesn't detect parallel edges.

---

## Proposed Changes

### Change 1: Bundle Serialization with Parallel Support

**File:** `src/agentmap/services/graph/graph_bundle_service.py`

**Update `_serialize_metadata_bundle()` (lines 512-526):**
```python
def _serialize_metadata_bundle(self, bundle: GraphBundle) -> Dict[str, Any]:
    """Serialize enhanced metadata bundle to dictionary format.
    
    Handles both single-target (str) and multi-target (list[str]) edges
    for parallel execution support.
    """
    nodes_data = {}
    for name, node in bundle.nodes.items():
        # Serialize edges with proper type handling
        # Edge values may be str (single target) or list[str] (parallel)
        serialized_edges = {}
        for condition, targets in node.edges.items():
            # Preserve type: str remains str, list remains list
            serialized_edges[condition] = targets
        
        nodes_data[name] = {
            "name": node.name,
            "agent_type": node.agent_type,
            "context": node.context,
            "inputs": node.inputs,
            "output": node.output,
            "prompt": node.prompt,
            "description": node.description,
            "edges": serialized_edges,  # Now supports Union[str, List[str]]
            "tool_source": node.tool_source,
            "available_tools": node.available_tools,
        }
    
    # Helper function to convert sets to sorted lists for JSON serialization
    def set_to_list(s):
        return sorted(list(s)) if s is not None else []
    
    return {
        "format": "metadata",
        "bundle_format": bundle.bundle_format,
        "created_at": bundle.created_at,
        # Core graph data
        "graph_name": bundle.graph_name,
        "entry_point": bundle.entry_point,
        "nodes": nodes_data,
        # ... rest unchanged ...
    }
```

**Rationale:**
- No type conversion needed - JSON supports both strings and arrays
- Preserves exact edge structure (str vs list)
- Backward compatible: existing bundles have only strings

---

### Change 2: Bundle Deserialization with Parallel Support

**Update `_deserialize_metadata_bundle()` (lines 596-665):**
```python
def _deserialize_metadata_bundle(
    self, data: Dict[str, Any]
) -> Optional[GraphBundle]:
    """Deserialize enhanced metadata bundle from dictionary format.
    
    Handles both legacy bundles (single-target edges) and new bundles
    (parallel-target edges) with backward compatibility.
    """
    try:
        # Validate format
        if data.get("format") != "metadata":
            raise ValueError("Not a metadata bundle format")
        
        # Reconstruct nodes with parallel edge support
        nodes = {}
        for name, node_data in data["nodes"].items():
            node = Node(
                name=node_data["name"],
                agent_type=node_data.get("agent_type"),
                context=node_data.get("context", {}),
                inputs=node_data.get("inputs", []),
                output=node_data.get("output"),
                prompt=node_data.get("prompt"),
                description=node_data.get("description"),
                tool_source=node_data.get("tool_source"),
                available_tools=node_data.get("available_tools"),
            )
            
            # Restore edges - now supports Union[str, List[str]]
            # JSON deserialization preserves types (str or list)
            edges_data = node_data.get("edges", {})
            for condition, targets in edges_data.items():
                # Targets may be str or list[str] - both supported by Node.add_edge()
                node.add_edge(condition, targets)
            
            nodes[name] = node
        
        # Helper function to convert lists to sets, handling None values
        def list_to_set(lst):
            return set(lst) if lst is not None else set()
        
        # Extract all fields with backwards compatibility
        bundle = GraphBundle.create_metadata(
            graph_name=data["graph_name"],
            entry_point=data.get("entry_point"),
            nodes=nodes,
            # ... rest unchanged ...
        )
        
        # Set format metadata if available
        if "bundle_format" in data:
            bundle.bundle_format = data["bundle_format"]
        if "created_at" in data:
            bundle.created_at = data["created_at"]
        
        bundle_format = data.get("bundle_format", "legacy")
        self.logger.debug(
            f"Loaded metadata GraphBundle with format: {bundle_format}"
        )
        return bundle
        
    except Exception as e:
        self.logger.error(f"Failed to deserialize metadata bundle: {e}")
        return None
```

**Rationale:**
- JSON naturally preserves string vs array types
- `Node.add_edge()` already accepts both types (from parsing changes)
- No special conversion logic needed
- Backward compatible: old bundles only have strings

---

### Change 3: Static Bundle Analyzer - Parallel Detection

**File:** `src/agentmap/services/static_bundle_analyzer.py`

**Update `create_static_bundle()` to include parallel metadata (lines 163-202):**
```python
# Create validation metadata
validation_metadata = {
    "csv_path": str(csv_path),
    "node_count": len(nodes),
    "agent_type_count": len(agent_types),
    "created_via": "static_analysis",
    "has_missing": len(missing_declarations) > 0,
    "has_parallel_routing": self._has_parallel_routing(nodes),  # NEW
    "parallel_edge_count": self._count_parallel_edges(nodes),   # NEW
}
```

**Add new helper methods (after line 337):**
```python
def _has_parallel_routing(self, nodes: dict[str, Node]) -> bool:
    """Check if graph contains any parallel routing edges.
    
    Args:
        nodes: Dictionary of node name to Node objects
        
    Returns:
        True if any node has parallel edges, False otherwise
    """
    for node in nodes.values():
        for condition, targets in node.edges.items():
            if isinstance(targets, list) and len(targets) > 1:
                return True
    return False

def _count_parallel_edges(self, nodes: dict[str, Node]) -> int:
    """Count number of parallel edges in the graph.
    
    Args:
        nodes: Dictionary of node name to Node objects
        
    Returns:
        Count of edges with multiple targets
    """
    count = 0
    for node in nodes.values():
        for condition, targets in node.edges.items():
            if isinstance(targets, list) and len(targets) > 1:
                count += 1
    return count

def _analyze_parallel_patterns(self, nodes: dict[str, Node]) -> Dict[str, Any]:
    """Analyze parallel routing patterns in the graph.
    
    Identifies fan-out, fan-in, and parallel opportunities for optimization.
    
    Args:
        nodes: Dictionary of node name to Node objects
        
    Returns:
        Dictionary with parallel pattern analysis:
        - fan_out_nodes: Nodes that route to multiple targets
        - fan_in_nodes: Nodes that receive from multiple sources
        - parallel_groups: Groups of nodes that execute in parallel
        - max_parallelism: Maximum number of parallel branches
    """
    fan_out_nodes = []
    fan_in_count = {}
    parallel_groups = []
    max_parallelism = 1
    
    # Find fan-out nodes (nodes with parallel edges)
    for node_name, node in nodes.items():
        for condition, targets in node.edges.items():
            if isinstance(targets, list) and len(targets) > 1:
                fan_out_nodes.append({
                    "node": node_name,
                    "condition": condition,
                    "targets": targets,
                    "parallelism": len(targets)
                })
                parallel_groups.append(targets)
                max_parallelism = max(max_parallelism, len(targets))
                
                # Track fan-in (nodes receiving from parallel source)
                for target in targets:
                    fan_in_count[target] = fan_in_count.get(target, 0) + 1
    
    # Identify actual fan-in nodes (nodes with multiple incoming edges)
    fan_in_nodes = [
        {"node": node, "incoming_count": count}
        for node, count in fan_in_count.items()
        if count > 1
    ]
    
    return {
        "fan_out_nodes": fan_out_nodes,
        "fan_in_nodes": fan_in_nodes,
        "parallel_groups": parallel_groups,
        "max_parallelism": max_parallelism,
        "has_parallel": len(fan_out_nodes) > 0
    }
```

**Rationale:**
- Provides rich metadata about parallel patterns
- Enables optimization decisions based on parallelism
- Helps with debugging and visualization
- Useful for validation (e.g., detecting conflicting output fields)

---

### Change 4: Enhanced Graph Structure Analysis

**File:** `src/agentmap/services/graph/graph_bundle_service.py`

**Update `_analyze_graph_structure()` method (lines 261-303):**
```python
def _analyze_graph_structure(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
    """Analyze graph structure for optimization hints.
    
    Now includes parallel routing analysis for better metadata.
    
    Args:
        nodes: Dictionary of node name to Node objects
        
    Returns:
        Dictionary containing graph structure analysis including parallel patterns
    """
    try:
        edge_count = sum(len(node.edges) for node in nodes.values())
        has_conditional = any(
            any(condition in node.edges for condition in ["success", "failure"])
            for node in nodes.values()
        )
        
        # NEW: Analyze parallel patterns
        parallel_analysis = self._analyze_parallel_patterns(nodes)
        
        structure = {
            "node_count": len(nodes),
            "edge_count": edge_count,
            "has_conditional_routing": has_conditional,
            "max_depth": self._calculate_max_depth(nodes),
            "is_dag": self._check_dag(nodes),
            "parallel_opportunities": parallel_analysis["parallel_groups"],  # Enhanced
            "has_parallel_routing": parallel_analysis["has_parallel"],       # NEW
            "max_parallelism": parallel_analysis["max_parallelism"],         # NEW
            "fan_out_count": len(parallel_analysis["fan_out_nodes"]),        # NEW
            "fan_in_count": len(parallel_analysis["fan_in_nodes"]),          # NEW
        }
        
        self.logger.debug(
            f"Analyzed graph structure: {structure['node_count']} nodes, "
            f"DAG: {structure['is_dag']}, conditional: {structure['has_conditional_routing']}, "
            f"parallel: {structure['has_parallel_routing']} (max={structure['max_parallelism']})"
        )
        return structure
        
    except Exception as e:
        self.logger.warning(
            f"Failed to analyze graph structure: {e}. Using minimal structure."
        )
        return {
            "node_count": len(nodes),
            "edge_count": 0,
            "has_conditional_routing": False,
            "max_depth": 1,
            "is_dag": True,
            "parallel_opportunities": [],
            "has_parallel_routing": False,
            "max_parallelism": 1,
        }

def _analyze_parallel_patterns(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
    """Analyze parallel routing patterns in the graph.
    
    Same implementation as StaticBundleAnalyzer version for consistency.
    """
    # ... (same implementation as above) ...
```

**Rationale:**
- Consistent analysis across static and dynamic bundle creation
- Rich metadata for debugging and optimization
- Useful for validation and visualization tools

---

### Change 5: Bundle Cache Invalidation

**File:** `src/agentmap/services/graph/graph_registry_service.py` (if exists)

**Bundle cache key should include edge structure:**
```python
def _compute_bundle_hash(self, csv_path: Path, nodes: Dict[str, Node]) -> str:
    """Compute hash for bundle caching.
    
    Includes edge structure to invalidate cache when parallel patterns change.
    
    Args:
        csv_path: Path to CSV file
        nodes: Parsed nodes with edge information
        
    Returns:
        Hash string for cache key
    """
    import hashlib
    
    # Start with CSV content hash
    csv_hash = self._compute_csv_hash(csv_path)
    
    # Add edge structure to hash (NEW)
    edge_structure = []
    for node_name in sorted(nodes.keys()):
        node = nodes[node_name]
        for condition in sorted(node.edges.keys()):
            targets = node.edges[condition]
            # Normalize to string for hashing
            if isinstance(targets, list):
                targets_str = "|".join(sorted(targets))
            else:
                targets_str = targets
            edge_structure.append(f"{node_name}:{condition}:{targets_str}")
    
    # Combine CSV hash with edge structure
    combined = f"{csv_hash}:{'|'.join(edge_structure)}"
    return hashlib.sha256(combined.encode()).hexdigest()
```

**Rationale:**
- Cache invalidation when edge structure changes
- Changing `"A"` to `"A|B|C"` creates new bundle
- Prevents stale bundles with incorrect parallel metadata

---

## Bundle Validation

### Validation 1: Target Existence Check

**Add to bundle validation (new method in GraphBundleService):**
```python
def validate_parallel_targets(self, bundle: GraphBundle) -> List[str]:
    """Validate that all parallel edge targets exist in the graph.
    
    Args:
        bundle: GraphBundle to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    node_names = set(bundle.nodes.keys())
    
    for node_name, node in bundle.nodes.items():
        for condition, targets in node.edges.items():
            # Handle both single and parallel targets
            target_list = targets if isinstance(targets, list) else [targets]
            
            for target in target_list:
                if target not in node_names:
                    errors.append(
                        f"Node '{node_name}' edge '{condition}' references "
                        f"nonexistent target '{target}'"
                    )
    
    return errors
```

### Validation 2: Output Field Conflict Detection

**Add validation for parallel branches:**
```python
def validate_parallel_output_fields(self, bundle: GraphBundle) -> List[str]:
    """Validate that parallel branches don't have conflicting output fields.
    
    Parallel agents should write to different output fields to avoid
    state conflicts during merging.
    
    Args:
        bundle: GraphBundle to validate
        
    Returns:
        List of validation warnings (empty if valid)
    """
    warnings = []
    
    for node_name, node in bundle.nodes.items():
        for condition, targets in node.edges.items():
            # Only check parallel edges
            if isinstance(targets, list) and len(targets) > 1:
                # Collect output fields from parallel branches
                output_fields = {}
                for target_name in targets:
                    target_node = bundle.nodes.get(target_name)
                    if target_node and target_node.output:
                        if target_node.output in output_fields:
                            warnings.append(
                                f"Parallel branches from '{node_name}' have conflicting "
                                f"output field '{target_node.output}': "
                                f"nodes {output_fields[target_node.output]} and {target_name}"
                            )
                        output_fields[target_node.output] = target_name
    
    return warnings
```

---

## Testing Strategy

### Test 1: Bundle Serialization with Parallel Edges
```python
def test_serialize_bundle_with_parallel_edges():
    """Test that bundles with parallel edges serialize correctly."""
    node = Node(name="Start", agent_type="input")
    node.add_edge("success", ["A", "B", "C"])  # Parallel edge
    
    bundle = GraphBundle.create_metadata(
        graph_name="TestGraph",
        nodes={"Start": node},
        # ... other params ...
    )
    
    service = GraphBundleService(...)
    serialized = service._serialize_metadata_bundle(bundle)
    
    # Verify edge structure preserved
    assert serialized["nodes"]["Start"]["edges"]["success"] == ["A", "B", "C"]
    assert isinstance(serialized["nodes"]["Start"]["edges"]["success"], list)
```

### Test 2: Bundle Deserialization Backward Compatibility
```python
def test_deserialize_legacy_bundle():
    """Test that legacy bundles (single-target only) load correctly."""
    legacy_data = {
        "format": "metadata",
        "graph_name": "LegacyGraph",
        "nodes": {
            "Start": {
                "name": "Start",
                "edges": {"success": "Next"}  # String (legacy)
            }
        },
        # ... other fields ...
    }
    
    service = GraphBundleService(...)
    bundle = service._deserialize_metadata_bundle(legacy_data)
    
    # Verify single-target edge remains string
    assert bundle.nodes["Start"].edges["success"] == "Next"
    assert isinstance(bundle.nodes["Start"].edges["success"], str)
```

### Test 3: Parallel Pattern Detection
```python
def test_analyze_parallel_patterns():
    """Test parallel pattern analysis in StaticBundleAnalyzer."""
    nodes = {
        "Start": Node(name="Start", agent_type="input"),
        "A": Node(name="A", agent_type="default"),
        "B": Node(name="B", agent_type="default"),
        "C": Node(name="C", agent_type="default"),
        "End": Node(name="End", agent_type="summary"),
    }
    nodes["Start"].add_edge("success", ["A", "B", "C"])
    nodes["A"].add_edge("success", "End")
    nodes["B"].add_edge("success", "End")
    nodes["C"].add_edge("success", "End")
    
    analyzer = StaticBundleAnalyzer(...)
    analysis = analyzer._analyze_parallel_patterns(nodes)
    
    # Verify fan-out detected
    assert len(analysis["fan_out_nodes"]) == 1
    assert analysis["fan_out_nodes"][0]["node"] == "Start"
    assert analysis["max_parallelism"] == 3
    
    # Verify fan-in detected
    assert len(analysis["fan_in_nodes"]) == 1
    assert analysis["fan_in_nodes"][0]["node"] == "End"
```

### Test 4: Bundle Cache Invalidation
```python
def test_bundle_cache_invalidation_on_parallel_change():
    """Test that changing edge structure invalidates bundle cache."""
    # Create initial CSV with single target
    csv_v1 = "GraphName,Node,Success_Next\nTest,Start,Next"
    bundle_v1 = create_bundle_from_csv(csv_v1)
    cache_key_v1 = compute_cache_key(bundle_v1)
    
    # Modify CSV to add parallel targets
    csv_v2 = "GraphName,Node,Success_Next\nTest,Start,A|B|C"
    bundle_v2 = create_bundle_from_csv(csv_v2)
    cache_key_v2 = compute_cache_key(bundle_v2)
    
    # Cache keys should differ
    assert cache_key_v1 != cache_key_v2
```

### Test 5: Parallel Target Validation
```python
def test_validate_parallel_targets_exist():
    """Test validation detects nonexistent parallel targets."""
    node = Node(name="Start", agent_type="input")
    node.add_edge("success", ["A", "B", "Nonexistent"])
    
    bundle = GraphBundle.create_metadata(
        graph_name="TestGraph",
        nodes={"Start": node, "A": node, "B": node},  # Missing "Nonexistent"
    )
    
    service = GraphBundleService(...)
    errors = service.validate_parallel_targets(bundle)
    
    assert len(errors) == 1
    assert "Nonexistent" in errors[0]
```

---

## Acceptance Criteria

### Functional Requirements
- ✅ Bundles serialize multi-target edges as JSON arrays
- ✅ Bundles deserialize multi-target edges correctly
- ✅ Legacy bundles (single-target only) load without errors
- ✅ Static analyzer detects parallel routing patterns
- ✅ Graph structure analysis includes parallel metadata
- ✅ Bundle validation checks parallel target existence
- ✅ Bundle validation warns about output field conflicts

### Performance Requirements
- ✅ Serialization/deserialization overhead <10ms for parallel bundles
- ✅ Parallel pattern analysis completes in <50ms for typical graphs
- ✅ No performance regression for single-target bundles

### Backward Compatibility
- ✅ Existing bundles load correctly
- ✅ Bundle format version preserved
- ✅ No breaking changes to bundle API

### Code Quality
- ✅ >95% code coverage for bundle serialization
- ✅ Comprehensive validation error messages
- ✅ Clear logging for parallel pattern detection

---

## Implementation Checklist

- [ ] Update `_serialize_metadata_bundle()` to handle list edges
- [ ] Update `_deserialize_metadata_bundle()` to restore list edges
- [ ] Add `_has_parallel_routing()` to StaticBundleAnalyzer
- [ ] Add `_count_parallel_edges()` to StaticBundleAnalyzer
- [ ] Add `_analyze_parallel_patterns()` to StaticBundleAnalyzer
- [ ] Update `_analyze_graph_structure()` in GraphBundleService
- [ ] Add `validate_parallel_targets()` validation method
- [ ] Add `validate_parallel_output_fields()` validation method
- [ ] Update bundle cache key calculation (if applicable)
- [ ] Write unit tests for serialization/deserialization
- [ ] Write unit tests for parallel pattern analysis
- [ ] Write integration tests for bundle lifecycle
- [ ] Update bundle validation in graph building pipeline
- [ ] Update documentation with bundle metadata examples

---

## Related Files

### Modified Files
- `src/agentmap/services/graph/graph_bundle_service.py` - Bundle serialization
- `src/agentmap/services/static_bundle_analyzer.py` - Static analysis

### Test Files to Create
- `tests/unit/test_bundle_parallel_serialization.py` - Serialization tests
- `tests/unit/test_bundle_parallel_analysis.py` - Analysis tests
- `tests/integration/test_bundle_parallel_lifecycle.py` - End-to-end tests

---

## Next Steps

1. Implement serialization changes
2. Implement deserialization changes
3. Add parallel pattern analysis methods
4. Update validation methods
5. Write comprehensive unit tests
6. Write integration tests
7. Verify backward compatibility with legacy bundles
8. Update documentation
