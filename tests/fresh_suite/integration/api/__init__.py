"""
API integration tests package.

This package contains comprehensive integration tests for all AgentMap API endpoints,
including execution, workflow management, validation, graph operations, info endpoints,
and authentication.

Test Structure:
- base_api_integration_test.py: Base test class with common functionality
- test_execution_endpoints.py: Tests for /execution endpoints
- test_workflow_endpoints.py: Tests for /workflows endpoints  s
- test_graph_endpoints.py: Tests for /graph endpoints
- test_auth_endpoints.py: Tests for authentication and authorization

All tests use real DI container instances and follow established testing patterns.
"""

# Import test classes for easy access
from .base_api_integration_test import BaseAPIIntegrationTest, APITestCase
from .test_workflow_endpoints import TestWorkflowEndpoints
from .test_graph_endpoints import TestGraphEndpoints
from .test_auth_endpoints import TestAuthenticationEndpoints

__all__ = [
    'BaseAPIIntegrationTest',
    'APITestCase',
    'TestWorkflowEndpoints',
    'TestGraphEndpoints',
    'TestAuthenticationEndpoints',
]
