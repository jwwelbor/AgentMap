"""
Configuration Examples Verification Test

Tests all YAML configuration examples from the host-service-integration.md 
documentation against the current AppConfigService implementation.

This ensures the documentation examples are accurate and work correctly.
"""

import unittest
import tempfile
import os
from pathlib import Path
from typing import Dict, Any

from agentmap.services.config.config_service import ConfigService
from agentmap.services.config.app_config_service import AppConfigService


class TestConfigurationExamples(unittest.TestCase):
    """Test configuration examples from documentation against AppConfigService."""

    def setUp(self):
        """Set up test environment."""
        self.config_service = ConfigService()
        self.temp_config_dir = Path(__file__).parent.parent.parent.parent.parent / "temp_config_test"
        self.examples_dir = Path(__file__).parent.parent.parent.parent.parent / "examples" / "host_integration"

    def _test_configuration_file(self, config_path: Path, test_name: str) -> Dict[str, Any]:
        """Test a single configuration file against AppConfigService."""
        result = {
            "test_name": test_name,
            "config_file": str(config_path),
            "passed": False,
            "errors": [],
            "warnings": [],
            "details": {}
        }

        try:
            # Test 1: Basic configuration loading
            app_config_service = AppConfigService(self.config_service, config_path)
            result["details"]["config_loaded"] = True

            # Test 2: Host application configuration access
            host_config = app_config_service.get_host_application_config()
            self.assertIsInstance(host_config, dict, f"Host config should be dict for {test_name}")
            result["details"]["host_config_loaded"] = True
            result["details"]["host_config_keys"] = list(host_config.keys())

            # Test 3: Host application enabled check
            enabled = app_config_service.is_host_application_enabled()
            self.assertIsInstance(enabled, bool, f"Host enabled should be bool for {test_name}")
            result["details"]["host_application_enabled"] = enabled

            # Test 4: Services configuration (if any services exist)
            services = host_config.get("services", {})
            result["details"]["services_count"] = len(services)
            
            if services:
                # Test first service configuration
                first_service = list(services.keys())[0]
                service_config = app_config_service.get_host_service_config(first_service)
                self.assertIsInstance(service_config, dict, f"Service config should be dict for {test_name}")
                result["details"]["first_service_name"] = first_service
                result["details"]["service_config_loaded"] = True
                result["details"]["service_config_keys"] = list(service_config.keys())

            # Test 5: Protocol folders (if specified)
            protocol_folders = host_config.get("protocol_folders", [])
            result["details"]["protocol_folders_count"] = len(protocol_folders)
            result["details"]["protocol_folders"] = protocol_folders

            # Test 6: Configuration validation
            validation_result = app_config_service.validate_host_config()
            self.assertIsInstance(validation_result, dict, f"Validation result should be dict for {test_name}")
            result["details"]["validation_passed"] = validation_result.get("valid", False)
            result["details"]["validation_warnings"] = len(validation_result.get("warnings", []))
            result["details"]["validation_errors"] = len(validation_result.get("errors", []))

            # Test 7: Environment variable detection
            with open(config_path, 'r') as f:
                config_content = f.read()
                result["details"]["has_env_vars"] = "${" in config_content

            result["passed"] = True

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def test_example1_basic_host_config(self):
        """Test Example 1: Basic host configuration from Step 5."""
        config_path = self.temp_config_dir / "example1_basic_host_config.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Basic Host Configuration")
        
        if not result["passed"]:
            self.fail(f"Basic host configuration test failed: {result['errors']}")

        # Verify specific expected structure
        details = result["details"]
        self.assertTrue(details.get("host_application_enabled", False), 
                       "Host application should be enabled")
        self.assertGreater(details.get("services_count", 0), 0, 
                          "Should have at least one service configured")
        self.assertTrue(details.get("has_env_vars", False), 
                       "Should contain environment variables")

    def test_example2_comprehensive_host_config(self):
        """Test Example 2: Comprehensive host application configuration."""
        config_path = self.temp_config_dir / "example2_comprehensive_host_config.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Comprehensive Host Configuration")
        
        if not result["passed"]:
            self.fail(f"Comprehensive host configuration test failed: {result['errors']}")

        # Verify multiple protocol folders
        details = result["details"]
        self.assertGreaterEqual(details.get("protocol_folders_count", 0), 2, 
                               "Should have multiple protocol folders")

    def test_example3_detailed_service_config(self):
        """Test Example 3: Detailed service configuration structure."""
        config_path = self.temp_config_dir / "example3_detailed_service_config.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Detailed Service Configuration")
        
        if not result["passed"]:
            self.fail(f"Detailed service configuration test failed: {result['errors']}")

        # Verify service has detailed configuration
        details = result["details"]
        self.assertTrue(details.get("service_config_loaded", False), 
                       "Service configuration should be loaded")

    def test_example4_environment_variables(self):
        """Test Example 4: Environment variables configuration."""
        config_path = self.temp_config_dir / "example4_environment_variables.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Environment Variables")
        
        if not result["passed"]:
            self.fail(f"Environment variables configuration test failed: {result['errors']}")

        # Verify environment variables are present
        details = result["details"]
        self.assertTrue(details.get("has_env_vars", False), 
                       "Should contain environment variable references")

    def test_example5a_development(self):
        """Test Example 5a: Development configuration."""
        config_path = self.temp_config_dir / "example5a_development.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Development Configuration")
        
        if not result["passed"]:
            self.fail(f"Development configuration test failed: {result['errors']}")

    def test_example5b_production(self):
        """Test Example 5b: Production configuration."""
        config_path = self.temp_config_dir / "example5b_production.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Production Configuration")
        
        if not result["passed"]:
            self.fail(f"Production configuration test failed: {result['errors']}")

    def test_example6_debug_logging(self):
        """Test Example 6: Debug logging configuration."""
        config_path = self.temp_config_dir / "example6_debug_logging.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Debug Logging Configuration")
        
        if not result["passed"]:
            self.fail(f"Debug logging configuration test failed: {result['errors']}")

    def test_example7_absolute_paths(self):
        """Test Example 7: Absolute protocol folder paths."""
        config_path = self.temp_config_dir / "example7_absolute_paths.yaml"
        if not config_path.exists():
            self.skipTest(f"Configuration file not found: {config_path}")

        result = self._test_configuration_file(config_path, "Absolute Protocol Paths")
        
        if not result["passed"]:
            self.fail(f"Absolute paths configuration test failed: {result['errors']}")

    def test_working_example_configuration(self):
        """Test the actual working example configuration."""
        config_path = self.examples_dir / "agentmap_config.yaml"
        if not config_path.exists():
            self.skipTest(f"Working example configuration not found: {config_path}")

        result = self._test_configuration_file(config_path, "Working Example")
        
        if not result["passed"]:
            self.fail(f"Working example configuration test failed: {result['errors']}")

        # Verify working example has multiple services
        details = result["details"]
        self.assertGreater(details.get("services_count", 0), 1, 
                          "Working example should have multiple services")

    def test_all_examples_comprehensive_report(self):
        """Generate a comprehensive report of all configuration examples."""
        test_files = [
            ("example1_basic_host_config.yaml", "Basic Host Configuration"),
            ("example2_comprehensive_host_config.yaml", "Comprehensive Host Configuration"),
            ("example3_detailed_service_config.yaml", "Detailed Service Configuration"),
            ("example4_environment_variables.yaml", "Environment Variables"),
            ("example5a_development.yaml", "Development Configuration"),
            ("example5b_production.yaml", "Production Configuration"),
            ("example6_debug_logging.yaml", "Debug Logging Configuration"),
            ("example7_absolute_paths.yaml", "Absolute Protocol Paths")
        ]

        results = []
        
        # Test all documentation examples
        for filename, test_name in test_files:
            config_path = self.temp_config_dir / filename
            if config_path.exists():
                result = self._test_configuration_file(config_path, test_name)
                results.append(result)

        # Test working example
        working_config_path = self.examples_dir / "agentmap_config.yaml"
        if working_config_path.exists():
            result = self._test_configuration_file(working_config_path, "Working Example")
            results.append(result)

        # Generate report
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r["passed"])
        failed_tests = total_tests - passed_tests

        report = f"""
Configuration Examples Verification Report
==========================================

Executive Summary:
- Total Tests: {total_tests}
- Passed: {passed_tests} ✅
- Failed: {failed_tests} ❌
- Success Rate: {(passed_tests/total_tests*100):.1f}%

Detailed Results:
"""

        for result in results:
            status = "✅ PASSED" if result["passed"] else "❌ FAILED"
            report += f"\n{result['test_name']}: {status}"
            
            if result["details"]:
                details = result["details"]
                report += f"\n  - Host App Enabled: {details.get('host_application_enabled', 'N/A')}"
                report += f"\n  - Services Count: {details.get('services_count', 0)}"
                report += f"\n  - Protocol Folders: {details.get('protocol_folders_count', 0)}"
                report += f"\n  - Has Env Vars: {details.get('has_env_vars', False)}"
                
            if result["errors"]:
                report += f"\n  - Errors: {'; '.join(result['errors'])}"

        print(report)

        # Assert overall success
        if failed_tests > 0:
            self.fail(f"{failed_tests} configuration examples failed verification. See report above.")


if __name__ == '__main__':
    unittest.main()
