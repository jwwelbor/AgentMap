# Technical Proposal: Scaffolding for Parallel-Aware Code Generation

## Overview

This proposal details changes to the scaffolding system (`AgentScaffolder`, `FunctionScaffolder`, and `IndentedTemplateComposer`) to generate parallel-aware routing functions and agent code. The implementation ensures scaffolded code properly handles list returns for parallel execution while maintaining backward compatibility.

---

## Current State Analysis

### FunctionScaffolder Current Behavior

**File:** `src/agentmap/services/graph/scaffold/function_scaffolder.py`

**Current Implementation (Lines 13-32):**
```python
def scaffold(
    self,
    func_name: str,
    info: Dict[str, Any],
    output_path: Path,
    overwrite: bool = False,
) -> Optional[Path]:
    file_name = f"{func_name}.py"
    file_path = output_path / file_name
    
    if file_path.exists() and not overwrite:
        return None
    
    code = self.templates.render_function(func_name, info)
    
    with file_path.open("w") as out:
        out.write(code)
    
    self.logger.debug(f"[FunctionScaffolder] ✅ Scaffolded function: {file_path}")
    return file_path
```

**Problem:** No detection of parallel routing patterns. Generated functions always return strings.

### IndentedTemplateComposer Current Behavior

**File:** `src/agentmap/services/indented_template_composer.py`

**Current Template Variables (Lines 786-824):**
```python
def _prepare_function_template_variables(
    self, func_name: str, info: Dict[str, Any]
) -> Dict[str, str]:
    """Prepare comprehensive template variables for function template substitution."""
    template_vars = {
        "func_name": func_name,
        "context": info.get("context", "") or "No context provided",
        "context_fields": context_fields,
        "success_node": info.get("success_next", "") or "None",
        "failure_node": info.get("failure_next", "") or "None",
        # ...
    }
```

**Problem:** Template variables don't include information about parallel routing (whether targets are lists).

### Current Function Template

**File:** `src/agentmap/templates/system/scaffold/function_template.txt` (inferred)

**Current Structure:**
```python
def {func_name}(state, success_node, failure_node):
    """
    Routing function for {node_name}.
    # ...
    """
    
    # Routing logic
    if state.get("last_action_success", True):
        return success_node  # Always returns string
    else:
        return failure_node  # Always returns string
```

**Problem:** Template doesn't support returning lists for parallel execution.

---

## Proposed Changes

### Change 1: Parallel Pattern Detection in FunctionScaffolder

**File:** `src/agentmap/services/graph/scaffold/function_scaffolder.py`

**Add helper method (after line 11):**
```python
def _detect_parallel_routing(self, info: Dict[str, Any]) -> Dict[str, bool]:
    """Detect whether routing targets are parallel (list-based).
    
    Args:
        info: Function information dictionary containing edge targets
        
    Returns:
        Dictionary with 'success_parallel' and 'failure_parallel' flags
    """
    success_next = info.get("success_next")
    failure_next = info.get("failure_next")
    
    return {
        "success_parallel": isinstance(success_next, list) and len(success_next) > 1,
        "failure_parallel": isinstance(failure_next, list) and len(failure_next) > 1,
        "has_parallel": (
            (isinstance(success_next, list) and len(success_next) > 1) or
            (isinstance(failure_next, list) and len(failure_next) > 1)
        )
    }
```

**Update `scaffold()` method (lines 13-32):**
```python
def scaffold(
    self,
    func_name: str,
    info: Dict[str, Any],
    output_path: Path,
    overwrite: bool = False,
) -> Optional[Path]:
    """Scaffold routing function with parallel execution support.
    
    Detects whether routing targets are parallel (list-based) and
    generates appropriate code that returns lists for parallel execution.
    """
    file_name = f"{func_name}.py"
    file_path = output_path / file_name
    
    if file_path.exists() and not overwrite:
        return None
    
    # NEW: Detect parallel routing patterns
    parallel_info = self._detect_parallel_routing(info)
    
    # NEW: Add parallel detection to info for template rendering
    info_with_parallel = {**info, **parallel_info}
    
    code = self.templates.render_function(func_name, info_with_parallel)
    
    with file_path.open("w") as out:
        out.write(code)
    
    # Enhanced logging for parallel functions
    if parallel_info["has_parallel"]:
        self.logger.debug(
            f"[FunctionScaffolder] ✅ Scaffolded PARALLEL routing function: {file_path}"
        )
    else:
        self.logger.debug(
            f"[FunctionScaffolder] ✅ Scaffolded function: {file_path}"
        )
    
    return file_path
```

**Rationale:**
- Automatic detection of parallel patterns from edge data
- No manual configuration needed
- Clear logging distinguishes parallel from sequential

---

### Change 2: Enhanced Template Variable Preparation

**File:** `src/agentmap/services/indented_template_composer.py`

**Update `_prepare_function_template_variables()` (lines 786-824):**
```python
def _prepare_function_template_variables(
    self, func_name: str, info: Dict[str, Any]
) -> Dict[str, str]:
    """Prepare comprehensive template variables for function template substitution.
    
    Now includes parallel routing metadata for generating list-returning functions.
    """
    # Generate context fields documentation
    context_fields = self._generate_context_fields(
        info.get("input_fields", []), info.get("output_field", "")
    )
    
    # NEW: Extract parallel routing flags
    success_parallel = info.get("success_parallel", False)
    failure_parallel = info.get("failure_parallel", False)
    has_parallel = info.get("has_parallel", False)
    
    # NEW: Format targets for display and code generation
    success_next = info.get("success_next", "")
    failure_next = info.get("failure_next", "")
    
    # Format success target(s)
    if success_parallel:
        success_display = f"{success_next} (parallel)"
        success_code = repr(success_next)  # Generates ["A", "B", "C"]
    else:
        success_display = success_next or "None"
        success_code = repr(success_next) if success_next else "None"
    
    # Format failure target(s)
    if failure_parallel:
        failure_display = f"{failure_next} (parallel)"
        failure_code = repr(failure_next)  # Generates ["A", "B", "C"]
    else:
        failure_display = failure_next or "None"
        failure_code = repr(failure_next) if failure_next else "None"
    
    # Prepare all template variables
    template_vars = {
        "func_name": func_name,
        "context": info.get("context", "") or "No context provided",
        "context_fields": context_fields,
        "success_node": success_display,           # For documentation
        "failure_node": failure_display,           # For documentation
        "success_code": success_code,              # NEW: For code generation
        "failure_code": failure_code,              # NEW: For code generation
        "success_parallel": str(success_parallel), # NEW: Template flag
        "failure_parallel": str(failure_parallel), # NEW: Template flag
        "has_parallel": str(has_parallel),         # NEW: Template flag
        "node_name": info.get("node_name", "") or "Unknown",
        "description": info.get("description", "") or "No description provided",
        "output_field": info.get("output_field", "") or "None",
    }
    
    self.logger.debug(
        f"[IndentedTemplateComposer] Prepared template variables for {func_name}: "
        f"success={success_display}, failure={failure_display}, "
        f"parallel={has_parallel}"
    )
    
    return template_vars
```

**Rationale:**
- Provides both display strings (docs) and code strings (actual code)
- Uses `repr()` to generate proper Python list syntax
- Flags enable conditional template rendering

---

### Change 3: New Parallel Function Template

**Create new file:** `src/agentmap/templates/system/scaffold/function_template.txt`

**Proposed Template:**
```python
def {func_name}(state, success_node, failure_node):
    """
    Routing function for {node_name}.
    
    Description: {description}
    Context: {context}
    
    Available state fields:
{context_fields}
    
    Routing behavior:
    - Success path: {success_node}
    - Failure path: {failure_node}
    
    Parallel execution: {has_parallel}
    This function returns {'a list' if has_parallel == 'True' else 'a string'} to trigger {'parallel' if has_parallel == 'True' else 'sequential'} execution.
    
    Args:
        state: Current workflow state dictionary
        success_node: Target node(s) for success path
        failure_node: Target node(s) for failure path
        
    Returns:
        {'List[str] or str' if has_parallel == 'True' else 'str'}: Next node(s) to execute, or None to terminate
    """
    
    # Extract relevant state values for routing decision
    last_action_success = state.get("last_action_success", True)
    
    # TODO: Add custom routing logic here
    # You can access any state field to make routing decisions
    # Example: route based on output value, error conditions, etc.
    
    # Default routing based on success/failure
    if last_action_success:
        # Success path
        next_node = {success_code}
        
        # Log routing decision
        if isinstance(next_node, list):
            print(f"[{func_name}] Routing to parallel success targets: {{next_node}}")
        else:
            print(f"[{func_name}] Routing to success: {{next_node}}")
        
        return next_node
    else:
        # Failure path
        next_node = {failure_code}
        
        # Log routing decision
        if isinstance(next_node, list):
            print(f"[{func_name}] Routing to parallel failure targets: {{next_node}}")
        else:
            print(f"[{func_name}] Routing to failure: {{next_node}}")
        
        return next_node
```

**Rationale:**
- Template automatically generates correct return type (str or list)
- Clear documentation about parallel execution
- Logging shows routing decisions
- TODO comment guides customization

---

### Change 4: Alternative - Dedicated Parallel Template

**Option B: Create separate template for parallel routing**

**File:** `src/agentmap/templates/system/scaffold/parallel_function_template.txt`

```python
def {func_name}(state, success_node, failure_node):
    """
    PARALLEL routing function for {node_name}.
    
    This function returns lists of node names to trigger LangGraph's
    parallel superstep execution. All nodes in the returned list will
    execute concurrently.
    
    Description: {description}
    Context: {context}
    
    Available state fields:
{context_fields}
    
    Routing behavior:
    - Success path (parallel): {success_node}
    - Failure path: {failure_node}
    
    Args:
        state: Current workflow state dictionary
        success_node: List of target nodes for parallel success path
        failure_node: Target node(s) for failure path
        
    Returns:
        List[str] or str: List for parallel execution, string for sequential
    """
    
    # Extract state values for routing decision
    last_action_success = state.get("last_action_success", True)
    
    if last_action_success:
        # PARALLEL SUCCESS PATH
        # All nodes in this list will execute concurrently
        parallel_targets = {success_code}
        
        print(f"[{func_name}] Routing to {{len(parallel_targets)}} parallel targets: {{parallel_targets}}")
        
        # LangGraph will execute all these nodes in parallel
        return parallel_targets
    else:
        # Failure path (sequential or parallel)
        next_node = {failure_code}
        
        if isinstance(next_node, list):
            print(f"[{func_name}] Routing to parallel failure targets: {{next_node}}")
        else:
            print(f"[{func_name}] Routing to failure: {{next_node}}")
        
        return next_node
```

**Template Selection Logic:**
```python
def compose_function_template(self, func_name: str, info: Dict[str, Any]) -> str:
    """Compose function template with parallel execution support."""
    # Determine which template to use
    has_parallel = info.get("has_parallel", False)
    
    if has_parallel:
        template_name = "parallel_function_template.txt"
        self.logger.debug(
            f"Using parallel function template for {func_name}"
        )
    else:
        template_name = "function_template.txt"
    
    # Load appropriate template
    template_content = self._load_template_internal(template_name)
    
    # Prepare variables and render
    template_vars = self._prepare_function_template_variables(func_name, info)
    return self._apply_variable_substitution(template_content, template_vars)
```

**Rationale:**
- Dedicated templates for clarity
- Easier to maintain separate logic
- Clear indication of parallel vs sequential
- More specialized documentation

---

### Change 5: Agent Template Updates (Optional)

**File:** `src/agentmap/templates/system/scaffold/modular/process_method.txt`

**Add comments about parallel execution (optional enhancement):**
```python
def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process inputs and generate outputs.
    
    This agent may be part of a parallel execution pattern.
    Ensure that:
    1. Output field is unique (doesn't conflict with parallel siblings)
    2. Processing is stateless or handles partial state correctly
    3. No side effects that assume sequential execution
    
    Args:
        inputs: State dictionary from the graph
        
    Returns:
        Dictionary with updates to merge into state
    """
    # ... existing template code ...
```

**Rationale:**
- Educates developers about parallel execution constraints
- Prevents common pitfalls (conflicting output fields)
- No functional changes, just better documentation

---

## Service Requirement Detection

### No Changes Needed

**Analysis:** Parallel routing doesn't change service requirements.

**Rationale:**
- Parallel agents use same services as sequential
- Service injection happens per-agent, not per-routing
- Protocol requirements unchanged

**Example:**
```python
# Whether ProcessA, ProcessB, ProcessC execute sequentially or in parallel,
# they still need the same services
ProcessA: requires ["logging_service", "state_adapter_service"]
ProcessB: requires ["logging_service", "state_adapter_service"]
ProcessC: requires ["logging_service", "state_adapter_service"]
```

**Validation:** The existing `ServiceRequirementsParser` continues to work without modifications.

---

## Testing Strategy

### Test 1: Parallel Pattern Detection
```python
def test_detect_parallel_routing():
    """Test detection of parallel routing patterns."""
    scaffolder = FunctionScaffolder(...)
    
    # Parallel success
    info_parallel = {
        "success_next": ["A", "B", "C"],
        "failure_next": "Error"
    }
    result = scaffolder._detect_parallel_routing(info_parallel)
    assert result["success_parallel"] == True
    assert result["failure_parallel"] == False
    assert result["has_parallel"] == True
    
    # All sequential
    info_sequential = {
        "success_next": "Next",
        "failure_next": "Error"
    }
    result = scaffolder._detect_parallel_routing(info_sequential)
    assert result["success_parallel"] == False
    assert result["failure_parallel"] == False
    assert result["has_parallel"] == False
```

### Test 2: Template Variable Preparation
```python
def test_prepare_parallel_template_variables():
    """Test template variable preparation with parallel routing."""
    composer = IndentedTemplateComposer(...)
    
    info = {
        "func_name": "test_router",
        "success_next": ["A", "B", "C"],
        "failure_next": "Error",
        "success_parallel": True,
        "failure_parallel": False,
        "has_parallel": True,
        # ... other fields ...
    }
    
    vars = composer._prepare_function_template_variables("test_router", info)
    
    # Check code generation strings
    assert vars["success_code"] == "['A', 'B', 'C']"
    assert vars["failure_code"] == "'Error'"
    
    # Check display strings
    assert "parallel" in vars["success_node"]
    
    # Check flags
    assert vars["has_parallel"] == "True"
```

### Test 3: Generated Function Returns List
```python
def test_scaffolded_parallel_function_returns_list():
    """Test that scaffolded parallel function returns list."""
    scaffolder = FunctionScaffolder(...)
    
    info = {
        "func_name": "parallel_router",
        "node_name": "Start",
        "success_next": ["A", "B", "C"],
        "failure_next": "Error",
        "description": "Test parallel routing"
    }
    
    # Scaffold function
    output_path = Path("/tmp/test_scaffold")
    file_path = scaffolder.scaffold("parallel_router", info, output_path, overwrite=True)
    
    # Import and test the generated function
    import sys
    sys.path.insert(0, str(output_path))
    from parallel_router import parallel_router
    
    # Test success path returns list
    state = {"last_action_success": True}
    result = parallel_router(state, ["A", "B", "C"], "Error")
    assert result == ["A", "B", "C"]
    assert isinstance(result, list)
    
    # Test failure path returns string
    state = {"last_action_success": False}
    result = parallel_router(state, ["A", "B", "C"], "Error")
    assert result == "Error"
    assert isinstance(result, str)
```

### Test 4: Sequential Function Unchanged
```python
def test_scaffolded_sequential_function_unchanged():
    """Test that non-parallel functions generate as before."""
    scaffolder = FunctionScaffolder(...)
    
    info = {
        "func_name": "sequential_router",
        "node_name": "Process",
        "success_next": "Next",
        "failure_next": "Error",
        "description": "Test sequential routing"
    }
    
    # Scaffold and verify returns strings
    # ... similar to above test ...
```

---

## Documentation Updates

### Generated Code Comments

**Example generated function with parallel routing:**
```python
def process_documents(state, success_node, failure_node):
    """
    Routing function for DocumentProcessor.
    
    Description: Route to parallel document analyzers
    
    Routing behavior:
    - Success path: ['SentimentAnalyzer', 'TopicAnalyzer', 'SummaryAgent'] (parallel)
    - Failure path: ErrorHandler
    
    Parallel execution: True
    This function returns a list to trigger parallel execution.
    
    PARALLEL EXECUTION NOTES:
    - All agents in the success list execute concurrently
    - Each should write to a unique output field
    - LangGraph synchronizes before next node
    - State updates are merged automatically
    """
    # ... generated code ...
```

---

## Acceptance Criteria

### Functional Requirements
- ✅ FunctionScaffolder detects parallel routing patterns
- ✅ Generated functions return list for parallel targets
- ✅ Generated functions return str for single targets
- ✅ Template variables include parallel routing metadata
- ✅ Generated code includes parallel execution documentation
- ✅ Logging distinguishes parallel from sequential scaffolding

### Backward Compatibility
- ✅ Non-parallel functions generate identically to existing
- ✅ No breaking changes to scaffold API
- ✅ Existing templates work without modification

### Code Quality
- ✅ >95% code coverage for scaffolding changes
- ✅ Clear documentation in generated code
- ✅ Examples demonstrate parallel patterns

---

## Implementation Checklist

- [ ] Add `_detect_parallel_routing()` to FunctionScaffolder
- [ ] Update `FunctionScaffolder.scaffold()` with parallel detection
- [ ] Update `_prepare_function_template_variables()` with parallel metadata
- [ ] Create/update function template with parallel support
- [ ] (Optional) Create dedicated parallel function template
- [ ] (Optional) Update agent templates with parallel comments
- [ ] Write unit tests for parallel detection
- [ ] Write unit tests for template variable preparation
- [ ] Write integration tests for scaffolded function execution
- [ ] Create example CSV files with parallel routing
- [ ] Generate example functions and verify output
- [ ] Update scaffolding documentation

---

## Related Files

### Modified Files
- `src/agentmap/services/graph/scaffold/function_scaffolder.py` - Parallel detection
- `src/agentmap/services/indented_template_composer.py` - Template variables

### New Template Files
- `src/agentmap/templates/system/scaffold/function_template.txt` - Updated template
- `src/agentmap/templates/system/scaffold/parallel_function_template.txt` - (Optional) Dedicated parallel template

### Test Files to Create
- `tests/unit/test_scaffolder_parallel_detection.py` - Detection tests
- `tests/integration/test_scaffolder_parallel_generation.py` - Generation tests

### Example Files to Create
- `examples/scaffolded_parallel_router.py` - Example generated function
- `examples/parallel_scaffold_demo.csv` - CSV for scaffolding demo

---

## Next Steps

1. Implement parallel detection in FunctionScaffolder
2. Update template variable preparation
3. Create/update function template
4. Write unit tests for detection logic
5. Write tests for generated code execution
6. Create example workflows
7. Update documentation
8. Verify integration with graph assembly

---

## Design Decision: Single vs Dual Templates

**Recommendation:** Use single template with conditional rendering

**Rationale:**
- Simpler maintenance (one template to update)
- Automatic adaptation to routing pattern
- Less cognitive load for developers
- Template can handle both cases cleanly

**Alternative:** If conditional logic becomes complex, split into two templates for clarity.
