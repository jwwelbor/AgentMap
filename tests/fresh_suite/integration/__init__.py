"""
Integration tests for AgentMap services.

This package contains integration tests that verify real service coordination
using actual DI container instances. These tests complement the unit tests
(which use MockServiceFactory) by testing cross-service workflows and
end-to-end service interactions.

Test Categories:
- Core Service Coordination: Basic service-to-service delegation
- CSV Processing Pipeline: File I/O → Parsing → Domain Models
- Graph Execution Workflow: Graph → Agents → Execution → Results
- Compilation Workflow: Graph → Bundle → File I/O
- Error Handling: Cross-service error propagation and graceful degradation
"""
