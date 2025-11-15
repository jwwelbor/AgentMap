# Parallel Agent Execution for AgentMap

## Epic
This feature is part of the **AgentMap Core Features Enhancement** initiative to align implementation with documented capabilities and LangGraph best practices.

## Goal

### Problem
AgentMap's documentation (README.md, architecture.md, features.md) advertises support for parallel agent execution using pipe-separated CSV syntax (e.g., `ProcessA|ProcessB|ProcessC`), but the actual implementation only supports sequential, single-target routing. This creates a critical gap between what users expect based on documentation and what the system actually delivers.

**Current State:**
- Documentation shows examples like: `Success_Next: ProcessA|ProcessB|ProcessC`
- CSV parser in `csv_graph_parser_service.py:540-546` treats pipe characters as literal strings
- Graph assembly creates single conditional edges that return one node name
- Users cannot leverage LangGraph's native parallel execution capabilities

**Impact on Users:**
- Developers following documentation examples receive runtime errors or unexpected behavior
- Map-reduce patterns require workarounds instead of declarative CSV configuration
- Performance optimization through parallel processing is unavailable
- Documentation credibility is undermined by implementation gaps

### Solution
Implement full support for parallel agent execution following LangGraph's native patterns:

1. **Parse pipe-separated targets** in Edge, Success_Next, and Failure_Next CSV columns
2. **Return lists from conditional edges** to trigger LangGraph's parallel superstep execution
3. **Provide a consolidation agent** (e.g., `summary` or new `join` agent) for fan-in patterns
4. **Maintain backward compatibility** with existing single-target workflows
5. **Align with LangGraph conventions** for state management and synchronization

**LangGraph Foundation:**
According to LangGraph documentation, when `add_conditional_edges()` routing functions return a list of node names, "all those nodes will be run in parallel as part of the next superstep." This native capability requires no special parallel execution logic—just proper list-based routing.

### Impact

**Quantitative:**
- **100% documentation alignment**: All documented parallel routing examples will function correctly
- **10-100x performance improvement**: Parallel execution for independent tasks (e.g., processing 10 items concurrently vs. sequentially)
- **Zero breaking changes**: Existing single-target workflows continue unchanged

**Qualitative:**
- **Developer productivity**: Declarative parallel workflows replace custom implementation code
- **System reliability**: Leverages battle-tested LangGraph parallelization
- **Feature completeness**: Closes critical gap between promise and delivery
- **User confidence**: Documentation examples work as written

**Success Metrics:**
- All documentation examples with pipe-separated targets execute successfully
- Parallel execution test suite passes with 100% coverage
- No regression in existing single-target workflow execution
- Performance benchmarks show expected parallel speedup for independent tasks

## User Personas

### Primary: Platform Engineer (Sarah)
- **Role**: Backend engineer building AI workflow orchestration systems
- **Experience**: 3-5 years software engineering, intermediate LangGraph knowledge
- **Goals**: Build scalable, high-performance agent workflows with minimal code
- **Pain Points**:
  - Cannot implement parallel processing without dropping to raw LangGraph
  - CSV examples in docs don't work, causing confusion and lost time
  - Performance bottlenecks from sequential processing of independent tasks
- **Use Cases**: Document processing pipelines, multi-modal analysis, concurrent API calls

### Secondary: Data Scientist (Marcus)
- **Role**: ML engineer creating AI agent experiments and prototypes
- **Experience**: 2-3 years Python, new to AgentMap and LangGraph
- **Goals**: Rapidly prototype complex agent workflows using declarative config
- **Pain Points**:
  - Expects documentation examples to work out-of-the-box
  - Lacks deep LangGraph knowledge to implement parallel patterns manually
  - Needs simple consolidation of parallel results for analysis
- **Use Cases**: A/B testing multiple models, parallel sentiment analysis, batch processing

### Tertiary: DevOps Engineer (Alex)
- **Role**: Infrastructure engineer deploying AgentMap workflows to production
- **Experience**: 5+ years ops, minimal AI/ML background
- **Goals**: Deploy reliable, performant workflows with predictable resource usage
- **Pain Points**:
  - Needs to understand concurrency behavior for capacity planning
  - Requires clear error handling for partial failures in parallel execution
  - Must debug workflows using logs and traces
- **Use Cases**: Production deployment, monitoring, cost optimization

## User Stories

### Must-Have (P0)

**US-1: Basic Parallel Routing**
- **As a** Platform Engineer
- **I want to** specify multiple target nodes using pipe syntax in Success_Next
- **So that I can** execute independent agents in parallel for performance

**Acceptance Criteria:**
```gherkin
Given a CSV with Success_Next: "ProcessA|ProcessB|ProcessC"
When the source node completes successfully
Then ProcessA, ProcessB, and ProcessC execute in parallel
And all three receive the complete state
And execution continues when all three complete
```

**US-2: Parallel Routing on All Edge Types**
- **As a** Platform Engineer
- **I want to** use pipe-separated targets in Edge, Success_Next, and Failure_Next
- **So that I can** route to parallel agents conditionally or unconditionally

**Acceptance Criteria:**
```gherkin
Given Edge: "NodeA|NodeB" (unconditional parallel)
When the node executes
Then NodeA and NodeB execute in parallel

Given Success_Next: "SuccessA|SuccessB" and Failure_Next: "FailureA|FailureB"
When the node succeeds
Then SuccessA and SuccessB execute in parallel
When the node fails
Then FailureA and FailureB execute in parallel
```

**US-3: State Synchronization for Parallel Agents**
- **As a** Platform Engineer
- **I want to** have parallel agents automatically synchronize before continuing
- **So that I can** ensure all parallel work completes before downstream nodes execute

**Acceptance Criteria:**
```gherkin
Given Success_Next: "ParallelA|ParallelB" with next node "Consolidate"
When ParallelA completes in 1s and ParallelB completes in 3s
Then Consolidate waits for both and starts at t=3s
And Consolidate receives state with updates from both agents
```

**US-4: Backward Compatibility**
- **As a** Platform Engineer
- **I want to** keep existing single-target workflows unchanged
- **So that I can** adopt parallel routing incrementally without breaking production

**Acceptance Criteria:**
```gherkin
Given an existing CSV with Success_Next: "SingleNode" (no pipe)
When the workflow executes
Then behavior is identical to current implementation
And no performance regression occurs
And existing tests pass without modification
```

### Should-Have (P1)

**US-5: Result Consolidation with Summary Agent**
- **As a** Data Scientist
- **I want to** consolidate parallel results using the summary agent
- **So that I can** aggregate outputs without custom code

**Acceptance Criteria:**
```gherkin
Given Success_Next: "AnalyzerA|AnalyzerB|AnalyzerC" with Input_Fields: "resultA|resultB|resultC"
And the next node uses agent_type: "summary"
When all parallel agents complete
Then the summary agent receives all three results
And produces a consolidated summary output
```

**US-6: Validation of Parallel Targets**
- **As a** Platform Engineer
- **I want to** receive clear validation errors for invalid parallel targets
- **So that I can** debug configuration issues quickly

**Acceptance Criteria:**
```gherkin
Given Success_Next: "ValidNode|NonexistentNode"
When the CSV is validated
Then validation fails with error: "Target 'NonexistentNode' not found in graph"
And the error identifies the source node and edge type
```

**US-7: Execution Tracking for Parallel Nodes**
- **As a** DevOps Engineer
- **I want to** see parallel execution in execution tracking output
- **So that I can** debug and monitor parallel workflows

**Acceptance Criteria:**
```gherkin
Given Success_Next: "TaskA|TaskB|TaskC"
When execution tracking is enabled
Then execution_steps shows all three tasks with parallel indicator
And timing shows concurrent execution (not sequential sum)
And execution_path reflects fan-out and fan-in structure
```

### Could-Have (P2)

**US-8: Mixed Single and Parallel Routing**
- **As a** Platform Engineer
- **I want to** combine single-target and parallel-target routing in one workflow
- **So that I can** optimize only the portions that benefit from parallelism

**Acceptance Criteria:**
```gherkin
Given a workflow with both "EdgeA" and "EdgeB|EdgeC|EdgeD" routing
When the workflow executes
Then sequential and parallel sections execute correctly
And state management works seamlessly between patterns
```

**US-9: Configurable Parallel Execution Limits**
- **As a** DevOps Engineer
- **I want to** set max concurrency for parallel execution
- **So that I can** prevent resource exhaustion in production

**Acceptance Criteria:**
```gherkin
Given agentmap_config.yaml with execution.max_parallel_nodes: 5
When Success_Next: "N1|N2|N3|N4|N5|N6|N7|N8"
Then only 5 nodes execute concurrently
And remaining 3 execute in a subsequent batch
```

**US-10: Error Handling Policies for Partial Failures**
- **As a** Platform Engineer
- **I want to** configure how partial failures in parallel execution are handled
- **So that I can** choose between fail-fast and continue-on-error strategies

**Acceptance Criteria:**
```gherkin
Given parallel_failure_policy: "fail_fast" in config
When ParallelA succeeds but ParallelB fails
Then execution stops and routes to Failure_Next

Given parallel_failure_policy: "continue_on_error"
When ParallelA succeeds but ParallelB fails
Then execution continues with ParallelA results
And error is logged but doesn't halt workflow
```

## Requirements

### Functional Requirements

#### FR-1: CSV Parsing for Parallel Targets
1. The CSV parser MUST detect pipe characters (`|`) in Edge, Success_Next, and Failure_Next columns
2. The parser MUST split pipe-separated values into a list of target node names
3. The parser MUST trim whitespace from each target node name
4. The parser MUST preserve single-target behavior when no pipe character is present
5. The parser MUST handle empty targets gracefully (e.g., `NodeA||NodeB` treats empty string as invalid)

#### FR-2: Node Model Extension
6. The Node model MUST support storing multiple targets per edge condition
7. The Node.add_edge() method MUST accept both string and list[string] target values
8. The Node model MUST provide a method to query whether an edge has multiple targets
9. The Node model MUST maintain backward compatibility with existing single-target edge storage

#### FR-3: Graph Assembly for Parallel Execution
10. GraphAssemblyService MUST detect when an edge has multiple targets
11. For edges with multiple targets, the service MUST create conditional edges that return lists
12. The conditional edge function MUST return a list of all target node names for parallel execution
13. For single-target edges, the service MUST continue using current string-return behavior
14. The service MUST log parallel routing decisions with all target nodes
15. The service MUST support parallel targets in default, success, and failure edge types

#### FR-4: LangGraph Integration
16. Parallel edges MUST use LangGraph's `add_conditional_edges()` method
17. The routing function MUST return a Python list for parallel execution
18. The system MUST rely on LangGraph's superstep architecture for synchronization
19. The system MUST NOT implement custom parallel execution logic
20. Fan-in MUST happen automatically when multiple parallel nodes route to the same target

#### FR-5: State Management
21. All parallel agents MUST receive the complete graph state
22. Parallel agents MUST update state using their configured output_field
23. State updates from parallel agents MUST be merged before the next node executes
24. The system MUST use LangGraph's state reducer functions for merging parallel updates
25. Parallel agents MUST NOT overwrite each other's outputs (unique output_field enforcement)

#### FR-6: Result Consolidation
26. The existing `summary` agent MUST support consolidating multiple input fields
27. The summary agent MUST accept pipe-separated input_fields (e.g., `result1|result2|result3`)
28. The summary agent MUST provide a default consolidation strategy (concatenation with separator)
29. Users MUST be able to customize consolidation logic via Context configuration
30. Documentation MUST provide examples of fan-out followed by fan-in with summary agent

#### FR-7: Error Handling
31. If any parallel target does not exist, CSV validation MUST fail with a descriptive error
32. If parallel agents have conflicting output_field values, validation MUST warn or fail
33. If a parallel agent fails, the system MUST follow existing success_policy behavior
34. Execution tracking MUST record failures in parallel branches individually
35. Error messages MUST identify which parallel branch failed

#### FR-8: Backward Compatibility
36. Existing CSV workflows with single targets MUST execute without modification
37. No changes to CSV schema or column names are required
38. Performance for single-target workflows MUST NOT degrade
39. All existing tests MUST pass without modification
40. Migration from single to parallel targets requires only CSV changes (no code changes)

### Non-Functional Requirements

#### NFR-1: Performance
- **Parallel Speedup**: For N independent agents, execution time should approach 1/N of sequential time (accounting for overhead)
- **Overhead**: Parallel execution overhead MUST be <100ms for parsing and setup
- **Scalability**: The system MUST support up to 50 parallel target nodes per edge
- **Memory**: Memory usage should scale linearly with parallel branches (no exponential growth)

#### NFR-2: Reliability
- **Error Isolation**: Errors in one parallel branch MUST NOT crash other branches
- **Deterministic Execution**: Given the same input, parallel execution MUST produce the same state updates (order-independent)
- **State Consistency**: State merging MUST be atomic and consistent
- **Recovery**: Failed parallel executions MUST be retryable

#### NFR-3: Observability
- **Execution Tracking**: Parallel execution MUST be visible in execution_steps with timing data
- **Logging**: Debug logs MUST show which nodes execute in parallel
- **Metrics**: Execution summary MUST include parallel execution count and timing
- **Visualization**: Execution path MUST represent fan-out and fan-in structure clearly

#### NFR-4: Usability
- **Documentation Quality**: All parallel execution patterns MUST have working examples
- **Error Messages**: Validation errors MUST explain what's wrong and how to fix it
- **Migration Path**: Existing single-target workflows MUST be easily convertible to parallel
- **Learning Curve**: Developers familiar with pipe syntax (bash, Linux) should understand immediately

#### NFR-5: Maintainability
- **Code Quality**: Parallel execution logic MUST follow existing AgentMap service patterns
- **Test Coverage**: Parallel execution MUST have >90% code coverage
- **Separation of Concerns**: CSV parsing, node modeling, and graph assembly remain separate services
- **Extensibility**: Design MUST support future enhancements (e.g., Send API for map-reduce)

#### NFR-6: Compliance
- **LangGraph Compatibility**: MUST work with LangGraph versions 0.2.x and later
- **Python Compatibility**: MUST support Python 3.11+
- **Dependency Constraints**: MUST NOT introduce new external dependencies
- **License Compliance**: All code MUST comply with MIT license

## Acceptance Criteria

### AC-1: Documentation Examples Work
- [ ] All parallel routing examples in README.md execute successfully
- [ ] All parallel routing examples in architecture.md are technically accurate
- [ ] All parallel routing examples in features.md execute successfully
- [ ] New examples demonstrate fan-out, fan-in, and mixed patterns

### AC-2: Core Functionality
- [ ] CSV with `Success_Next: "A|B|C"` triggers parallel execution of A, B, C
- [ ] CSV with `Edge: "X|Y"` triggers unconditional parallel execution of X, Y
- [ ] CSV with `Failure_Next: "E1|E2"` triggers parallel execution on failure
- [ ] Single-target edges (no pipe) continue working identically
- [ ] Parallel agents receive complete state
- [ ] Parallel agents update state via their output_field
- [ ] Next node after parallel execution waits for all branches to complete
- [ ] Summary agent consolidates results from parallel branches

### AC-3: Validation and Error Handling
- [ ] Validation detects nonexistent nodes in parallel targets
- [ ] Validation warns about duplicate output_field values in parallel branches
- [ ] Runtime errors in one parallel branch don't crash other branches
- [ ] Error messages identify which parallel branch failed
- [ ] Execution tracking shows all parallel branches and their status

### AC-4: Performance and Scalability
- [ ] 10 parallel agents complete in ~1x time vs ~10x for sequential
- [ ] 50 parallel agents execute without memory issues
- [ ] Parsing overhead for parallel targets is <50ms
- [ ] No performance regression for single-target workflows

### AC-5: Integration and Compatibility
- [ ] All existing AgentMap tests pass without modification
- [ ] Parallel execution works with all agent types (openai, claude, csv_reader, etc.)
- [ ] Parallel execution works with all edge types (default, success, failure)
- [ ] Parallel execution integrates with existing execution policies
- [ ] Bundle caching works correctly with parallel workflows

### AC-6: Developer Experience
- [ ] Parallel execution tutorial added to documentation
- [ ] Migration guide for converting sequential to parallel workflows
- [ ] Example workflows demonstrate common parallel patterns
- [ ] CLI validation command detects parallel configuration issues
- [ ] Debug logs clearly show parallel routing decisions

## Out of Scope

### Explicitly Excluded Features
1. **Send API for Map-Reduce**: Dynamic parallel execution where the number of branches is determined at runtime (future enhancement)
2. **Custom Synchronization Logic**: Partial joins, conditional waits, or custom fan-in logic beyond LangGraph defaults
3. **Parallel Execution Limits**: Configuration for max concurrent nodes (could-have for future release)
4. **Parallel Failure Policies**: Advanced error handling strategies like "continue on partial failure" (could-have for future)
5. **Distributed Execution**: Parallel nodes executing on different machines/containers
6. **Progress Streaming**: Real-time updates as parallel branches complete
7. **Priority-Based Execution**: Ordering or prioritizing parallel branches
8. **Resource Pools**: Shared resource management across parallel branches

### Alternative Approaches Considered
1. **Custom Parallel Agent Type**: Rejected in favor of leveraging LangGraph's native capabilities
2. **Separate Parallel Syntax**: Rejected to maintain consistency with documentation examples
3. **Explicit Join Nodes**: Rejected because LangGraph handles fan-in automatically
4. **Thread Pools**: Rejected because LangGraph manages parallelism internally

### Implementation Details (Out of Scope for PRD)
- Specific function signatures and class methods
- Internal data structure choices for storing parallel targets
- Logging format and level details
- Unit test implementation strategies
- Performance optimization techniques

### Future Enhancements
- Send API integration for dynamic map-reduce patterns
- Visual workflow editor with parallel execution preview
- Parallel execution profiling and optimization tools
- Automatic parallel opportunity detection
- Cloud-native distributed parallel execution

### Assumptions and Constraints
- **Assumption**: LangGraph's superstep architecture handles synchronization correctly
- **Assumption**: All parallel agents are independent (no inter-agent communication required)
- **Assumption**: State updates from parallel agents don't conflict (different output_fields)
- **Constraint**: Parallel execution requires LangGraph 0.2.x+ for list-based routing
- **Constraint**: Implementation must work within existing AgentMap service architecture
- **Constraint**: No breaking changes to CSV schema or public APIs

---

## Metadata

**Feature Complexity**: Ikea Furniture ⭐⭐
**Priority**: P0 (Documentation alignment is critical for user trust)
**Estimated Effort**: 2-3 weeks (Medium complexity, well-defined scope)
**Dependencies**: None (uses existing LangGraph and AgentMap infrastructure)
**Target Release**: Next minor version (0.x.0 - new feature, backward compatible)

**Document Status**: ✅ Ready for Review
**Last Updated**: 2025-01-15
**Author**: Product Requirements Team
**Reviewers**: Engineering Lead, Architecture Team

---

## Related Documentation
- [LangGraph Graph API - Conditional Edges](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [AgentMap Architecture - Multi-Agent Coordination](/docs-docusaurus/docs/reference/architecture.md)
- [AgentMap Features - Advanced Routing Patterns](/docs-docusaurus/docs/reference/features.md)
- [AgentMap README - CSV Schema Reference](/README.md#csv-schema-reference)
