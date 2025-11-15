# Parallel Agent Execution Implementation Documentation

This directory contains comprehensive implementation plans and technical proposals for adding parallel agent execution support to AgentMap.

## Overview

These documents provide detailed, actionable plans for implementing parallel routing using pipe-separated syntax (`ProcessA|ProcessB|ProcessC`) in CSV files, leveraging LangGraph's native list-based routing for parallel superstep execution.

## Documentation Structure

### 1. [PRD: Parallel Agent Execution](./prd.md)
**Product Requirements Document** defining the feature scope, user stories, and acceptance criteria.

**Key Sections:**
- Problem statement and solution overview
- User personas and use cases
- Functional and non-functional requirements
- Acceptance criteria and success metrics

**Read this first** to understand the "what" and "why" of the feature.

---

### 2. [Implementation Plan](./implementation-plan.md)
**Master implementation plan** breaking down the work into phases with timelines and dependencies.

**Key Sections:**
- Executive summary with goals and success criteria
- Architecture changes overview
- Phase-by-phase implementation breakdown (6 phases over 3 weeks)
- Risk assessment and mitigation strategies
- Testing and validation strategy
- Migration path for existing code

**Read this second** to understand the overall implementation approach and timeline.

---

### 3. [Technical Proposal: Parsing](./technical-proposal-parsing.md)
**Detailed proposal for CSV parsing and domain model changes.**

**Key Changes:**
- `NodeSpec` dataclass updates for `Union[str, List[str]]` edges
- `Node` model updates with parallel edge support
- CSV parser pipe delimiter detection (`_parse_edge_targets()`)
- Helper methods for parallel edge queries

**Covers:**
- Current state analysis
- Proposed code changes with examples
- Migration strategy for backward compatibility
- Comprehensive test cases
- Implementation checklist

---

### 4. [Technical Proposal: Assembly](./technical-proposal-assembly.md)
**Detailed proposal for graph assembly changes to support parallel routing.**

**Key Changes:**
- `GraphAssemblyService` parallel edge detection
- New `_add_parallel_success_failure_edge()` method
- Routing functions that return lists for parallel execution
- Enhanced logging for parallel routing decisions

**Covers:**
- LangGraph integration patterns
- Parallel vs sequential routing logic
- Edge case handling
- Performance considerations
- Test cases for all routing scenarios

---

### 5. [Technical Proposal: Bundle Processing](./technical-proposal-bundle-processing.md)
**Detailed proposal for bundle system changes to serialize and cache parallel metadata.**

**Key Changes:**
- Bundle serialization/deserialization with `Union[str, List[str]]` edges
- `StaticBundleAnalyzer` parallel pattern detection
- Enhanced graph structure analysis
- Bundle validation for parallel targets

**Covers:**
- JSON serialization of list-valued edges
- Backward compatibility with legacy bundles
- Parallel pattern analysis algorithms
- Bundle cache invalidation strategies
- Validation for target existence and output field conflicts

---

### 6. [Technical Proposal: Scaffolding](./technical-proposal-scaffolding.md)
**Detailed proposal for scaffolding system to generate parallel-aware code.**

**Key Changes:**
- `FunctionScaffolder` parallel pattern detection
- Template variable preparation with parallel metadata
- Function templates that return lists for parallel routing
- Enhanced documentation in generated code

**Covers:**
- Automatic parallel detection from edge data
- Template selection and rendering logic
- Generated function examples
- Service requirement analysis (no changes needed)

---

## Implementation Order

Follow this sequence for implementation:

1. **Phase 1:** Start with [Parsing Proposal](./technical-proposal-parsing.md)
   - Update domain models (`Node`, `NodeSpec`)
   - Implement pipe delimiter parsing
   - Write unit tests for edge storage

2. **Phase 2:** Continue with [Assembly Proposal](./technical-proposal-assembly.md)
   - Update `GraphAssemblyService` routing logic
   - Implement parallel edge handlers
   - Write tests for LangGraph integration

3. **Phase 3:** Implement [Bundle Proposal](./technical-proposal-bundle-processing.md)
   - Update serialization/deserialization
   - Add parallel pattern analysis
   - Implement bundle validation

4. **Phase 4:** Complete with [Scaffolding Proposal](./technical-proposal-scaffolding.md)
   - Update function scaffolder
   - Create/update templates
   - Test generated code execution

5. **Phase 5:** Integration and testing per [Implementation Plan](./implementation-plan.md)

---

## Quick Reference

### Key Files to Modify

| Component | File | Primary Changes |
|-----------|------|----------------|
| **Parsing** | `csv_graph_parser_service.py` | Add `_parse_edge_targets()`, pipe splitting |
| **Models** | `node.py`, `graph_spec.py` | `Union[str, List[str]]` types, helper methods |
| **Assembly** | `graph_assembly_service.py` | Parallel routing detection, list-returning functions |
| **Bundles** | `graph_bundle_service.py` | Serialize/deserialize lists, validation |
| **Bundles** | `static_bundle_analyzer.py` | Parallel pattern analysis |
| **Scaffolding** | `function_scaffolder.py` | Parallel detection, template selection |
| **Scaffolding** | `indented_template_composer.py` | Template variables for parallel |

### Key Test Scenarios

1. **Backward Compatibility:**
   - Existing CSV files parse unchanged
   - Single-target edges remain strings
   - All existing tests pass

2. **Parallel Routing:**
   - `"A|B|C"` parsed as `["A", "B", "C"]`
   - Routing functions return lists
   - LangGraph executes in parallel

3. **Bundle Lifecycle:**
   - Bundles serialize/deserialize lists
   - Legacy bundles load correctly
   - Cache invalidation on edge changes

4. **Scaffolding:**
   - Functions return lists for parallel targets
   - Functions return strings for single targets
   - Generated code includes documentation

---

## Success Criteria Summary

### Functional
- ✅ All PRD user stories pass acceptance criteria
- ✅ Pipe syntax works in Edge, Success_Next, Failure_Next
- ✅ Parallel execution verified with LangGraph
- ✅ State synchronization works (fan-in)

### Backward Compatibility
- ✅ 100% existing tests pass without modification
- ✅ Single-target workflows unchanged
- ✅ Legacy bundles load correctly

### Performance
- ✅ 10 parallel tasks complete in ~1x time (vs 10x sequential)
- ✅ <50ms parsing overhead
- ✅ No regression for single-target workflows

### Quality
- ✅ >90% code coverage for new paths
- ✅ Comprehensive documentation
- ✅ Clear error messages

---

## Timeline

**Total Duration:** 17 days (~3 weeks)

- **Week 1:** Data models + CSV parsing + Graph assembly (7 days)
- **Week 2:** Bundle system + Scaffolding (5 days)
- **Week 3:** Integration testing + Documentation (5 days)

---

## Related PRs and Issues

*To be added as implementation progresses*

---

## Questions or Feedback

For questions about these proposals or the implementation:

1. Review the specific technical proposal for detailed analysis
2. Check the [Implementation Plan](./implementation-plan.md) for phasing and dependencies
3. Refer to the [PRD](./prd.md) for requirements and acceptance criteria

---

## Document Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| PRD | ✅ Complete | 2025-01-15 |
| Implementation Plan | ✅ Complete | 2025-01-15 |
| Parsing Proposal | ✅ Complete | 2025-01-15 |
| Assembly Proposal | ✅ Complete | 2025-01-15 |
| Bundle Proposal | ✅ Complete | 2025-01-15 |
| Scaffolding Proposal | ✅ Complete | 2025-01-15 |

All documents are ready for review and implementation.
