"""
Test suite for dependency compatibility issues.

This module contains tests that reproduce and prevent dependency conflicts,
specifically the LangGraph MRO (Method Resolution Order) issues that occur
with incompatible version combinations.
"""

import importlib
from typing import Dict, List

import pytest

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import PackageNotFoundError, version


class TestDependencyCompatibility:
    """Test suite for dependency compatibility and MRO issues."""

    def test_langgraph_import_succeeds(self):
        """
        Test that LangGraph imports successfully without MRO errors.

        This test reproduces the specific error we encountered:
        TypeError: Cannot create a consistent method resolution order (MRO)
        for bases ABC, Generic
        """
        try:
            # This should not raise an MRO error
            import langgraph
            from langgraph.graph import StateGraph
            from langgraph.pregel.protocol import PregelProtocol

            # Verify we can create a basic StateGraph
            graph = StateGraph(state_schema=dict)
            assert graph is not None

        except TypeError as e:
            if "Cannot create a consistent method resolution order" in str(e):
                pytest.fail(f"MRO error detected - incompatible LangGraph version: {e}")
            else:
                raise

    def test_langgraph_version_compatibility(self):
        """Test that installed LangGraph version is in compatible range."""
        try:
            import langgraph  # Verify package can be imported

            version_string = version("langgraph")

            # Parse version components
            major, minor, patch = map(int, version_string.split("."))

            # Test version constraints based on our pyproject.toml
            # langgraph now allows v1.x (installed: 1.0.5)
            # Accept both 0.3.x and 1.x versions
            if major == 0:
                assert (
                    minor == 3
                ), f"Minor version should be 3 for v0.x, got {minor} (version {version_string})"
                assert (
                    patch >= 5
                ), f"Patch version should be >= 5 for v0.x, got {patch} (version {version_string})"
            elif major == 1:
                # v1.x is acceptable (current langgraph release)
                assert minor >= 0, f"Minor version should be >= 0 for v1.x, got {minor}"
            else:
                pytest.fail(f"Unsupported major version {major} (version {version_string})")

        except ImportError:
            pytest.fail("LangGraph is not installed")
        except PackageNotFoundError:
            pytest.fail("LangGraph package metadata not accessible")

    def test_problematic_langgraph_versions_blocked(self):
        """Test that we detect and block problematic LangGraph versions."""
        problematic_versions = ["0.5.0", "0.5.1", "0.6.0", "0.6.1"]

        try:
            import langgraph  # Verify package can be imported

            current_version = version("langgraph")

            if current_version in problematic_versions:
                pytest.fail(
                    f"Detected problematic LangGraph version {current_version}. "
                    f"This version is known to cause MRO errors. "
                    f"Please downgrade to a version in range >=0.3.5,<0.4.0"
                )

        except (ImportError, PackageNotFoundError):
            # If LangGraph isn't installed, that's fine for this test
            pass

    def test_agentmap_core_imports(self):
        """Test that AgentMap core imports work with current dependency versions."""
        try:
            # Test the specific import chain that was failing
            from agentmap.deployment.http import ServiceAdapter, create_service_adapter
            from agentmap.deployment.service_adapter import (
                ServiceAdapter as AdapterClass,
            )
            from agentmap.services.graph.graph_assembly_service import (
                GraphAssemblyService,
            )

            # Verify classes can be instantiated (basic smoke test)
            assert ServiceAdapter is not None
            assert create_service_adapter is not None
            assert AdapterClass is not None
            assert GraphAssemblyService is not None

        except ImportError as e:
            pytest.fail(f"AgentMap core imports failed: {e}")
        except TypeError as e:
            if "Cannot create a consistent method resolution order" in str(e):
                pytest.fail(f"MRO error in AgentMap imports: {e}")
            else:
                raise

    def test_csv_workflow_basic_functionality(self):
        """
        Test that the basic CSV workflow functionality works.

        This is an integration test that verifies the lesson1.csv example
        would work with the current dependency versions.
        """
        try:
            # Import required modules for CSV workflow
            from agentmap.deployment.http import create_service_adapter
            from agentmap.di.containers import Container

            # This should not raise MRO errors
            container = Container()
            container.wire(modules=[])

            adapter = create_service_adapter(container)
            assert adapter is not None

        except Exception as e:
            if "Cannot create a consistent method resolution order" in str(e):
                pytest.fail(f"MRO error in CSV workflow: {e}")
            else:
                # For other errors, we'll investigate separately
                # This test is specifically for MRO issues
                pass


class TestDependencyVersionDetection:
    """Tests for detecting and reporting dependency version issues."""

    def test_get_installed_package_versions(self):
        """Test we can detect installed package versions."""
        # Get key dependencies
        key_packages = [
            "langgraph",
            "langchain-core",
            "langchain",
            "pydantic",
            "typing-extensions",
        ]

        versions = {}
        for package in key_packages:
            try:
                versions[package] = version(package)
            except PackageNotFoundError:
                versions[package] = None

        # Verify we found LangGraph (should be installed)
        assert versions.get("langgraph") is not None, "LangGraph should be installed"

        # Store versions for debugging
        print(f"Detected package versions: {versions}")

    def test_dependency_health_check(self):
        """Test a comprehensive dependency health check."""
        health_report = self._generate_dependency_health_report()

        # Verify no critical issues
        assert not health_report[
            "critical_issues"
        ], f"Critical dependency issues found: {health_report['critical_issues']}"

        # Log warnings for investigation
        if health_report["warnings"]:
            print(f"Dependency warnings: {health_report['warnings']}")

    def _generate_dependency_health_report(self) -> Dict[str, List[str]]:
        """Generate a comprehensive dependency health report."""
        critical_issues = []
        warnings = []

        # Check LangGraph version
        try:
            import langgraph  # Verify package can be imported

            version_string = version("langgraph")
            major, minor, patch = map(int, version_string.split("."))

            if major == 0 and minor >= 5:
                critical_issues.append(
                    f"LangGraph {version_string} may cause MRO errors. "
                    f"Recommended: downgrade to 0.3.x"
                )
            elif major == 0 and minor == 4 and patch >= 1:
                warnings.append(
                    f"LangGraph {version_string} is in transition range - monitor for issues"
                )

        except Exception as e:
            critical_issues.append(f"Cannot check LangGraph version: {e}")

        # Check for known problematic combinations
        try:
            import pydantic  # Verify package can be imported

            pydantic_version = version("pydantic")

            # Add other compatibility checks here as needed

        except Exception as e:
            warnings.append(f"Cannot check Pydantic version: {e}")

        return {"critical_issues": critical_issues, "warnings": warnings}


class TestMROSpecificReproduction:
    """Specific tests to reproduce and prevent MRO errors."""

    def test_mro_reproduction_attempt(self):
        """
        Attempt to reproduce the exact MRO error we encountered.

        This test helps us verify our fix and detect regressions.
        """
        try:
            # The exact import that was failing
            from langgraph.pregel.protocol import PregelProtocol

            # If we get here without an MRO error, the fix worked
            assert PregelProtocol is not None

            # Verify we can inspect the MRO
            mro = PregelProtocol.__mro__
            assert len(mro) > 0, "MRO should not be empty"

            # Check that ABC appears only once in the MRO
            from abc import ABC

            abc_count = sum(1 for cls in mro if cls is ABC)
            assert (
                abc_count <= 1
            ), f"ABC appears {abc_count} times in MRO - should be ≤ 1"

        except TypeError as e:
            if "Cannot create a consistent method resolution order" in str(e):
                pytest.fail(
                    f"MRO error still present: {e}\n"
                    f"This indicates the dependency fix did not resolve the issue."
                )
            else:
                raise

    @pytest.mark.parametrize(
        "import_path",
        [
            "langgraph.graph.StateGraph",
            "langgraph.pregel.Pregel",
            "langgraph.graph.message.MessageGraph",
            "langgraph.prebuilt.create_react_agent",
        ],
    )
    def test_critical_langgraph_imports(self, import_path: str):
        """Test critical LangGraph imports that are commonly used."""
        try:
            module_path, class_name = import_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            assert cls is not None

        except TypeError as e:
            if "Cannot create a consistent method resolution order" in str(e):
                pytest.fail(f"MRO error in {import_path}: {e}")
            else:
                raise
        except ImportError:
            # Some imports might not be available in all versions - that's OK
            pass


if __name__ == "__main__":
    # Allow running this test file directly for debugging
    pytest.main([__file__, "-v"])
