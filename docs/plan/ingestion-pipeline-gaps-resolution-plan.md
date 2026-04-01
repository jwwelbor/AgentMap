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

- Non-CSV ingestion sources (JSON, YAML) - future enhancement
- Workflow versioning/repository features - separate initiative
- Remote URL ingestion - separate initiative
- Vision agent type support - upcoming release, will be added to known agent types when available
