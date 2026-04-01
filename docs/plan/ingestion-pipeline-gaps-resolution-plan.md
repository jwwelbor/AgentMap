# Ingestion Pipeline Gaps Resolution Plan

## Overview

The AgentMap ingestion pipeline transforms CSV workflow definitions into executable LangGraph graphs through a multi-stage process: CSV parsing → domain model creation → bundle assembly → bootstrap/execution. This plan identifies concrete gaps in validation, performance, and testing, and provides an implementation roadmap to resolve them.

## Pipeline Architecture

```
CSV File → CSVGraphParserService → GraphSpec → NodeSpecConverter → Node
         → GraphBundleService → GraphBundle → GraphRegistryService (cache)
         → GraphBootstrapService → GraphAssemblyService → LangGraph
```

## Identified Gaps

### Gap 1: Output_Field Validator Rejects Multi-Output (SEVERITY: HIGH)

**Location:** `src/agentmap/models/validation/csv_row_model.py:77-90`

**Problem:** The `validate_output_field` validator only accepts single alphanumeric field names but the system supports pipe-separated multi-output fields (e.g., `summary|analysis|score`). The validator rejects valid multi-output configurations because `|` is not alphanumeric.

**Impact:** `agentmap validate` falsely reports errors for valid multi-output workflows. The parser (`parsers.py:207-215`) correctly splits pipe-separated output fields, but the Pydantic validator blocks them.

**Fix:** Update `validate_output_field` to support pipe-separated field names, mirroring `validate_input_fields` logic.

### Gap 2: CSV Double-Read for Hash Computation (SEVERITY: MEDIUM)

**Location:** `src/agentmap/services/graph/graph_registry_service.py:80-99`

**Problem:** `compute_hash()` reads the CSV file to compute SHA-256, then the parser reads it again for parsing. This is redundant I/O for large CSV files.

**Fix:** Return both the hash and the file content from `compute_hash()`, pass content to the parser to avoid re-reading.

### Gap 3: No Edge Target Validation (SEVERITY: HIGH)

**Location:** `src/agentmap/services/csv_graph_parser/validators.py`

**Problem:** Edge targets (Edge, Success_Next, Failure_Next) reference node names but are never validated against the actual set of nodes defined in the CSV. Invalid references are only discovered at runtime during graph assembly.

**Fix:** Add a `validate_graph_edges()` method to `CSVStructureValidator` that cross-references edge targets against defined nodes within each graph.

### Gap 4: No AgentType Validation (SEVERITY: MEDIUM)

**Location:** `src/agentmap/models/validation/csv_row_model.py`

**Problem:** AgentType field accepts any string without validation against known/registered agent types. Typos like `opanai` instead of `openai` are not caught until runtime.

**Fix:** Add an optional AgentType validator that warns (not errors) for unrecognized agent types, providing suggestions for likely typos.

### Gap 5: No Graph-Level Semantic Validation (SEVERITY: MEDIUM)

**Location:** `src/agentmap/services/csv_graph_parser/validators.py`

**Problem:** Validation occurs per-row but not per-graph. Issues like orphan nodes (no incoming/outgoing edges), duplicate node names within a graph, and missing entry points are not caught during validation.

**Fix:** Add graph-level semantic validation that checks structural integrity after all rows are parsed.

### Gap 6: Insufficient Ingestion Pipeline Test Coverage (SEVERITY: MEDIUM)

**Problem:** No dedicated end-to-end ingestion pipeline tests. Integration tests exist for specific features (column aliases, parallel parsing, context parsing) but there are no tests for:
- Multi-output field validation
- Edge target cross-validation
- Graph semantic validation
- The full ingestion pipeline from CSV to GraphBundle
- Error recovery and reporting

**Fix:** Add comprehensive test suite covering the ingestion pipeline gaps being resolved.

## Implementation Plan

### Phase 1: Validation Fixes (Core)

1. **Fix Output_Field validator** - Update to support pipe-separated fields
2. **Add edge target validation** - Cross-reference edge targets against node definitions
3. **Add AgentType soft validation** - Warn on unrecognized agent types
4. **Add graph-level semantic validation** - Orphan nodes, duplicates, entry point detection

### Phase 2: Performance Fix

5. **Fix CSV double-read** - Return content from hash computation

### Phase 3: Test Coverage

6. **Add ingestion pipeline tests** - Cover all new validation and the gaps fixed

## Files to Modify

| File | Change |
|------|--------|
| `src/agentmap/models/validation/csv_row_model.py` | Fix Output_Field validator for multi-output |
| `src/agentmap/services/csv_graph_parser/validators.py` | Add edge target, graph-level, AgentType validation |
| `src/agentmap/services/graph/graph_registry_service.py` | Return content from compute_hash() |
| `src/agentmap/services/graph/graph_bundle_service.py` | Accept pre-read content |
| `tests/fresh_suite/unit/services/csv_graph_parser/test_ingestion_pipeline_gaps.py` | New test file |

## Out of Scope

The following gaps were identified during analysis but are outside the scope of
this resolution plan. They are documented here for future planning.

### Ingestion Source Diversity
- **Non-CSV ingestion sources** (JSON, YAML, Python dict) - pipeline is tightly coupled to CSV
- **Remote URL ingestion** - cannot ingest from HTTP URLs or cloud storage directly
- **Multi-sheet / batched workflow support** - each execution requires a separate CSV file

### Pipeline Features
- **Incremental ingestion** - must re-ingest entire CSV for any change; no patch/merge operations
- **Workflow versioning** - no version control, tagging, or dependency tracking across workflows
- **Custom column support** - columns outside the predefined set are logged as warnings and ignored
- **Metadata preservation** - no way to attach workflow metadata (version, author, created_date) in CSV
- **Schema inference** - cannot auto-detect workflow structure from data

### Architectural Gaps Found During Exploration
- **ApplicationBootstrapService missing** - referenced in docs/comments but no concrete implementation; functionality split between GraphBootstrapService and DI container bootstrap
- **Blob storage agents incomplete** - class files exist but not fully registered in BuiltinDefinitionConstants
- **ProtocolBasedRequirementsAnalyzer not centralized** - functionality embedded in DeclarationRegistryService rather than a dedicated analyzer
- **Bundle update service partial** - updates agent mappings from declarations but doesn't re-resolve services
- **Service dependency topological sort** - `calculate_load_order()` returns sorted list but doesn't do actual topological sort based on dependencies
- **Telemetry adoption inconsistent** - optional telemetry service with silent degradation, but not uniformly checked across all agents
- **Host service YAML integration incomplete** - source exists but usage pattern unclear
- **Memory service lifecycle ambiguous** - service exists in constants but automatic configuration unclear

### Code-Level TODOs Found in Existing Code
- `graph_bundle_service.py:238` - "FIX this... it doesn't seem to be picking up all the protocols"
- `graph_bundle_service.py:247` - "Check if this is still needed"
- `graph_bundle_service.py:249` - "Extract function_mappings if needed"
- `graph_bootstrap_service.py:182` - "Should this be FeatureRegistryService?" (provider discovery logic placement)

### Vision / Multimodal Support
- PR #110 adds `ask_vision()` to LLMService - no new agent type needed; existing LLM agents gain vision capability through the service layer
