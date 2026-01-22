"""
Simple CLI Test Runner

Run CLI tests by category or all at once using the simplified test approach.
"""

import sys
import unittest
from pathlib import Path


def run_tests(test_pattern=None):
    """Run CLI tests with optional pattern filtering."""
    # Get the directory containing this script
    test_dir = Path(__file__).parent

    # Discover and run tests
    loader = unittest.TestLoader()

    if test_pattern:
        # Load specific test file
        if test_pattern == "validation":
            suite = loader.loadTestsFromName(
                "test_validation_commands", start_dir=test_dir
            )
        elif test_pattern == "workflow":
            suite = loader.loadTestsFromName(
                "test_main_workflow_commands", start_dir=test_dir
            )
        elif test_pattern == "diagnostic":
            suite = loader.loadTestsFromName(
                "test_diagnostic_commands", start_dir=test_dir
            )
        elif test_pattern == "integration":
            suite = loader.loadTestsFromName("test_cli_integration", start_dir=test_dir)
        else:
            print(f"Unknown test pattern: {test_pattern}")
            print("Available patterns: validation, workflow, diagnostic, integration")
            return False
    else:
        # Load all tests
        suite = loader.discover(test_dir, pattern="test_*.py")

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return success/failure
    return result.wasSuccessful()


def main():
    """Main entry point for test runner."""
    print("🧪 AgentMap CLI Test Runner - Simplified Edition")
    print("=" * 50)

    # Check for command line argument
    test_pattern = None
    if len(sys.argv) > 1:
        test_pattern = sys.argv[1]

    if test_pattern:
        print(f"Running CLI tests for: {test_pattern}")
    else:
        print("Running all CLI tests")

    print()

    # Run tests
    success = run_tests(test_pattern)

    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
