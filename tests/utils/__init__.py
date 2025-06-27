"""
Test utilities package for AgentMap.

This package contains reusable testing utilities including:
- MockServiceFactory: Mock service creation and configuration
- Path mocking utilities: Safe mocking of pathlib.Path operations
- Service interface auditing: Validation of mock completeness
"""

# Re-export commonly used utilities for convenience
from .mock_service_factory import MockServiceFactory
from .path_mocking_utils import (
    PathOperationsMocker,
    PathExistsMocker, 
    PathStatMocker,
    mock_path_exists,
    mock_path_stat,
    mock_compilation_currency,
    mock_file_comparison,
    mock_time_progression,
    MockServiceConfigHelper
)

__all__ = [
    # Mock service factory
    'MockServiceFactory',
    
    # Path mocking utilities
    'PathOperationsMocker',
    'PathExistsMocker',
    'PathStatMocker',
    'mock_path_exists',
    'mock_path_stat', 
    'mock_compilation_currency',
    'mock_file_comparison',
    'mock_time_progression',
    'MockServiceConfigHelper',
]
