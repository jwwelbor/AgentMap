"""
CLI Test Suite for AgentMap.

This package contains comprehensive tests for all CLI commands and workflows:

Main Command Tests:
- test_main_workflow_commands.py: run, compile, scaffold, export commands
- test_validation_commands.py: validate-csv, validate-config, validate-all commands  
- test_diagnostic_commands.py: diagnose, config, validate-cache commands

Integration and Error Tests:
- test_cli_integration.py: Cross-command workflows and integration scenarios
- test_cli_error_handling.py: Error handling, edge cases, and recovery

Base Classes:
- base_cli_test.py: Common test utilities and patterns

Test Coverage:
✅ All CLI commands with success and failure scenarios
✅ Option parsing and argument validation
✅ File system operations and error handling
✅ Service integration and delegation
✅ User experience and output formatting
✅ Cross-command workflows and data flow
✅ Error recovery and graceful degradation
✅ Performance and resource management

Usage:
    # Run all CLI tests
    python -m pytest tests/fresh_suite/cli/ -v
    
    # Run specific command tests
    python -m pytest tests/fresh_suite/cli/test_main_workflow_commands.py -v
    
    # Run integration tests
    python -m pytest tests/fresh_suite/cli/test_cli_integration.py -v

Testing Patterns:
- Uses typer.testing.CliRunner for command execution
- MockServiceFactory for consistent service mocking
- Real temporary file system for file operations
- Comprehensive assertion helpers for CLI-specific verification
- Following established patterns from TESTING_PATTERNS.md
"""

# Test discovery and organization
__all__ = [
    'BaseCLITest',
    'CLICommandTestMixin', 
    'CLIFileOperationTestMixin',
    'CLIServiceIntegrationTestMixin'
]

# Import base classes for external use
# from .base_cli_test import (
#     BaseCLITest,
#     CLICommandTestMixin,
#     CLIFileOperationTestMixin, 
#     CLIServiceIntegrationTestMixin
# )

# Version info for test suite
CLI_TEST_SUITE_VERSION = "1.0.0"

def run_all_cli_tests():
    """
    Convenience function to run all CLI tests programmatically.
    
    Returns:
        int: Exit code (0 for success, non-zero for failures)
    """
    import subprocess
    import sys
    from pathlib import Path
    
    # Get the directory containing this package
    cli_test_dir = Path(__file__).parent
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            str(cli_test_dir),
            "-v",
            "--tb=short"
        ], cwd=cli_test_dir.parent.parent.parent)
        
        return result.returncode
    except Exception as e:
        print(f"Error running CLI tests: {e}")
        return 1

def get_test_coverage_summary():
    """
    Return a summary of CLI test coverage.
    
    Returns:
        dict: Test coverage information
    """
    return {
        "commands_tested": [
            "run", "compile", "scaffold", "export",
            "validate-csv", "validate-config", "validate-all", 
            "diagnose", "config", "validate-cache"
        ],
        "test_categories": [
            "Basic functionality",
            "Option parsing",
            "Error handling", 
            "File operations",
            "Service integration",
            "Cross-command workflows",
            "User experience",
            "Performance"
        ],
        "total_test_files": 6,
        "estimated_test_count": "100+",
        "coverage_areas": {
            "success_scenarios": "✅ Complete",
            "error_handling": "✅ Comprehensive", 
            "edge_cases": "✅ Extensive",
            "integration": "✅ Full workflows",
            "user_experience": "✅ Detailed"
        }
    }

if __name__ == "__main__":
    # Allow running the CLI test suite directly
    import sys
    exit_code = run_all_cli_tests()
    sys.exit(exit_code)
