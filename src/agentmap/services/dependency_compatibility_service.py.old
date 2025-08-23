"""
Dependency Compatibility Service

This service provides utilities for detecting, diagnosing, and handling
dependency compatibility issues, particularly MRO conflicts and version
incompatibilities in the LangGraph ecosystem.
"""

import importlib
import logging
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pkg_resources


class CompatibilityLevel(Enum):
    """Compatibility levels for dependency assessment."""

    COMPATIBLE = "compatible"
    WARNING = "warning"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass
class DependencyIssue:
    """Represents a dependency compatibility issue."""

    package: str
    current_version: str
    issue_type: str
    severity: CompatibilityLevel
    description: str
    recommendation: str


@dataclass
class CompatibilityReport:
    """Comprehensive compatibility assessment report."""

    overall_status: CompatibilityLevel
    issues: List[DependencyIssue]
    warnings: List[str]
    recommendations: List[str]
    package_versions: Dict[str, str]


class DependencyCompatibilityService:
    """
    Service for detecting and handling dependency compatibility issues.

    This service follows SOLID principles:
    - Single Responsibility: Only handles dependency compatibility
    - Open/Closed: Extensible for new dependency checks
    - Liskov Substitution: Can be replaced with enhanced implementations
    - Interface Segregation: Focused interface for compatibility checking
    - Dependency Inversion: Depends on abstractions, not concretions
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the compatibility service."""
        self.logger = logger or logging.getLogger(__name__)
        self._known_issues = self._initialize_known_issues()

    def check_compatibility(self) -> CompatibilityReport:
        """
        Perform a comprehensive dependency compatibility check.

        Returns:
            CompatibilityReport: Detailed assessment of current dependency state
        """
        self.logger.info("Starting dependency compatibility check")

        package_versions = self._get_package_versions()
        issues = []
        warnings = []
        recommendations = []

        # Check LangGraph compatibility
        langgraph_issues = self._check_langgraph_compatibility(package_versions)
        issues.extend(langgraph_issues)

        # Check for known problematic combinations
        combination_issues = self._check_known_combinations(package_versions)
        issues.extend(combination_issues)

        # Check for MRO-specific issues
        mro_issues = self._check_mro_issues()
        issues.extend(mro_issues)

        # Determine overall status
        overall_status = self._determine_overall_status(issues)

        # Generate recommendations
        if overall_status != CompatibilityLevel.COMPATIBLE:
            recommendations.extend(self._generate_recommendations(issues))

        report = CompatibilityReport(
            overall_status=overall_status,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
            package_versions=package_versions,
        )

        self.logger.info(
            f"Compatibility check complete. Status: {overall_status.value}"
        )
        return report

    def validate_startup_compatibility(self) -> bool:
        """
        Quick startup validation for critical compatibility issues.

        Returns:
            bool: True if startup is safe, False if critical issues detected
        """
        try:
            # Test critical imports that caused the original issue
            self._test_critical_imports()

            # Quick version check for known problematic versions
            if self._has_known_problematic_versions():
                return False

            return True

        except Exception as e:
            self.logger.error(f"Startup compatibility validation failed: {e}")
            return False

    def fix_mro_issues(self) -> bool:
        """
        Attempt to fix MRO issues using monkey patching as emergency measure.

        Returns:
            bool: True if fix was applied successfully
        """
        try:
            # Check if MRO issue exists
            if not self._detect_mro_issue():
                self.logger.info("No MRO issues detected")
                return True

            self.logger.warning("MRO issue detected, attempting emergency fix")

            # Apply monkey patch for known MRO issues
            success = self._apply_mro_patch()

            if success:
                self.logger.info("MRO emergency fix applied successfully")
            else:
                self.logger.error("Failed to apply MRO emergency fix")

            return success

        except Exception as e:
            self.logger.error(f"Error during MRO fix attempt: {e}")
            return False

    def _get_package_versions(self) -> Dict[str, str]:
        """Get versions of key packages."""
        key_packages = [
            "langgraph",
            "langchain-core",
            "langchain",
            "langchain-community",
            "pydantic",
            "typing-extensions",
            "abc",
        ]

        versions = {}
        for package in key_packages:
            try:
                if package == "abc":
                    # abc is a built-in module
                    versions[package] = (
                        f"Python {sys.version_info.major}.{sys.version_info.minor}"
                    )
                else:
                    dist = pkg_resources.get_distribution(package)
                    versions[package] = dist.version
            except pkg_resources.DistributionNotFound:
                versions[package] = "Not installed"
            except Exception:
                versions[package] = "Unknown"

        return versions

    def _check_langgraph_compatibility(
        self, versions: Dict[str, str]
    ) -> List[DependencyIssue]:
        """Check LangGraph version compatibility."""
        issues = []

        langgraph_version = versions.get("langgraph", "Not installed")
        if langgraph_version == "Not installed":
            issues.append(
                DependencyIssue(
                    package="langgraph",
                    current_version="Not installed",
                    issue_type="missing_dependency",
                    severity=CompatibilityLevel.INCOMPATIBLE,
                    description="LangGraph is required but not installed",
                    recommendation='Install LangGraph: pip install "langgraph>=0.3.5,<0.4.0"',
                )
            )
            return issues

        try:
            major, minor, patch = map(int, langgraph_version.split("."))

            # Check for known problematic versions
            if major == 0 and minor >= 5:
                issues.append(
                    DependencyIssue(
                        package="langgraph",
                        current_version=langgraph_version,
                        issue_type="mro_incompatible_version",
                        severity=CompatibilityLevel.INCOMPATIBLE,
                        description=f"LangGraph {langgraph_version} contains MRO-breaking changes",
                        recommendation='Downgrade to stable version: pip install "langgraph>=0.3.5,<0.4.0"',
                    )
                )
            elif major == 0 and minor == 4 and patch >= 1:
                issues.append(
                    DependencyIssue(
                        package="langgraph",
                        current_version=langgraph_version,
                        issue_type="potentially_incompatible_version",
                        severity=CompatibilityLevel.WARNING,
                        description=f"LangGraph {langgraph_version} may have compatibility issues",
                        recommendation="Monitor for issues or downgrade to 0.3.x for stability",
                    )
                )

        except ValueError:
            issues.append(
                DependencyIssue(
                    package="langgraph",
                    current_version=langgraph_version,
                    issue_type="invalid_version_format",
                    severity=CompatibilityLevel.WARNING,
                    description=f"Cannot parse LangGraph version: {langgraph_version}",
                    recommendation="Verify LangGraph installation",
                )
            )

        return issues

    def _check_known_combinations(
        self, versions: Dict[str, str]
    ) -> List[DependencyIssue]:
        """Check for known problematic package combinations."""
        issues = []

        # Add checks for known problematic combinations
        # This can be extended as we discover more incompatibilities

        return issues

    def _check_mro_issues(self) -> List[DependencyIssue]:
        """Check for actual MRO issues by testing imports."""
        issues = []

        try:
            self._test_critical_imports()
        except TypeError as e:
            if "Cannot create a consistent method resolution order" in str(e):
                issues.append(
                    DependencyIssue(
                        package="langgraph",
                        current_version="Unknown",
                        issue_type="mro_error",
                        severity=CompatibilityLevel.INCOMPATIBLE,
                        description=f"MRO error detected: {str(e)}",
                        recommendation="Downgrade LangGraph to compatible version",
                    )
                )
        except Exception as e:
            issues.append(
                DependencyIssue(
                    package="unknown",
                    current_version="Unknown",
                    issue_type="import_error",
                    severity=CompatibilityLevel.WARNING,
                    description=f"Import test failed: {str(e)}",
                    recommendation="Check dependency installation",
                )
            )

        return issues

    def _test_critical_imports(self) -> None:
        """Test critical imports that are known to cause MRO issues."""
        # The specific import that was failing in the original issue
        from langgraph.graph import StateGraph
        from langgraph.pregel.protocol import PregelProtocol

        # Test that we can create basic instances
        graph = StateGraph(state_schema=dict)

        # Verify MRO is valid
        mro = PregelProtocol.__mro__
        if len(mro) == 0:
            raise ValueError("Invalid MRO detected")

    def _has_known_problematic_versions(self) -> bool:
        """Quick check for known problematic versions."""
        try:
            import langgraph

            version = langgraph.__version__

            # Known problematic versions
            problematic_versions = ["0.5.0", "0.5.1", "0.6.0", "0.6.1", "0.6.2"]
            return version in problematic_versions

        except Exception:
            return False

    def _detect_mro_issue(self) -> bool:
        """Detect if MRO issue exists."""
        try:
            self._test_critical_imports()
            return False
        except TypeError as e:
            return "Cannot create a consistent method resolution order" in str(e)
        except Exception:
            return False

    def _apply_mro_patch(self) -> bool:
        """
        Apply emergency monkey patch for MRO issues.

        Note: This is a last-resort measure. Proper fix is version downgrade.
        """
        try:
            # This would contain specific patches for known MRO issues
            # For now, we just log that a patch would be applied
            self.logger.warning("MRO patch would be applied here (not implemented)")
            return False

        except Exception as e:
            self.logger.error(f"Failed to apply MRO patch: {e}")
            return False

    def _determine_overall_status(
        self, issues: List[DependencyIssue]
    ) -> CompatibilityLevel:
        """Determine overall compatibility status from issues."""
        if not issues:
            return CompatibilityLevel.COMPATIBLE

        severities = [issue.severity for issue in issues]

        if CompatibilityLevel.INCOMPATIBLE in severities:
            return CompatibilityLevel.INCOMPATIBLE
        elif CompatibilityLevel.WARNING in severities:
            return CompatibilityLevel.WARNING
        else:
            return CompatibilityLevel.UNKNOWN

    def _generate_recommendations(self, issues: List[DependencyIssue]) -> List[str]:
        """Generate actionable recommendations based on issues."""
        recommendations = []

        # Get unique recommendations
        unique_recommendations = set(issue.recommendation for issue in issues)
        recommendations.extend(unique_recommendations)

        # Add general recommendations
        recommendations.append(
            "Update pyproject.toml to use upper bounds: 'langgraph = \">=0.3.5,<0.4.0\"'"
        )
        recommendations.append("Use Poetry lock files to freeze working combinations")

        return recommendations

    def _initialize_known_issues(self) -> Dict[str, Any]:
        """Initialize database of known dependency issues."""
        return {
            "langgraph_mro_versions": ["0.5.0", "0.5.1", "0.6.0", "0.6.1", "0.6.2"],
            "safe_langgraph_versions": ["0.3.5", "0.3.28", "0.3.30"],
            "problematic_combinations": [
                # Add known problematic combinations as they're discovered
            ],
        }


def create_dependency_compatibility_service(
    logger: Optional[logging.Logger] = None,
) -> DependencyCompatibilityService:
    """
    Factory function to create a DependencyCompatibilityService instance.

    Args:
        logger: Optional logger instance

    Returns:
        DependencyCompatibilityService: Configured service instance
    """
    return DependencyCompatibilityService(logger)


# Convenience functions for quick checks
def quick_compatibility_check() -> bool:
    """Quick compatibility check for startup validation."""
    service = create_dependency_compatibility_service()
    return service.validate_startup_compatibility()


def get_compatibility_report() -> CompatibilityReport:
    """Get full compatibility report."""
    service = create_dependency_compatibility_service()
    return service.check_compatibility()


if __name__ == "__main__":
    # Allow running this module directly for debugging
    logging.basicConfig(level=logging.INFO)

    service = create_dependency_compatibility_service()
    report = service.check_compatibility()

    print(f"Overall Status: {report.overall_status.value}")
    print(f"Issues Found: {len(report.issues)}")

    for issue in report.issues:
        print(f"- {issue.package} {issue.current_version}: {issue.description}")
        print(f"  Recommendation: {issue.recommendation}")
