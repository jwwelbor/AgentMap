"""
Test utilities package for AgentMap.

This package contains reusable testing utilities including:
- MockServiceFactory: Mock service creation and configuration
- EnhancedServiceInterfaceAuditor: Service interface analysis and test generation
- Path mocking utilities: Safe mocking of pathlib.Path operations
"""

# Re-export commonly used utilities for convenience
from .mock_service_factory import MockServiceFactory
from .enhanced_service_auditor import EnhancedServiceInterfaceAuditor
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
    
    # Service interface auditing
    'EnhancedServiceInterfaceAuditor',
    
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
