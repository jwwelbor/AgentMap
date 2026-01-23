"""
Simple API integration test to fix the args/kwargs dependency injection issue.

This approach bypasses the complex base integration test and uses proper
dependency overrides to avoid the FastAPI validation error.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

from agentmap.deployment.http.api.server import create_fastapi_app


class MockServices:
    """Simple mock services with proper signatures (no *args, **kwargs)."""

    def __init__(self):
        # Create a temporary directory for tests
        self.temp_dir = tempfile.mkdtemp()

    def graph_runner_service(self):
        """Return a mock graph runner service."""
        mock_runner = Mock()

        # Create a proper mock result
        mock_result = Mock()
        mock_result.success = True
        mock_result.error = None
        mock_result.final_state = {"result": "test_success"}
        mock_result.total_duration = 1.0
        mock_result.execution_summary = None

        mock_runner.run.return_value = mock_result
        return mock_runner

    def app_config_service(self):
        """Return a mock app config service."""
        mock_config = Mock()
        mock_config.get_csv_repository_path.return_value = Path(self.temp_dir)
        mock_config.get_csv_path.return_value = Path(self.temp_dir) / "default.csv"
        return mock_config

    def graph_bundle_service(self):
        """Return a mock graph bundle service."""
        mock_bundle_service = Mock()
        mock_bundle = Mock()
        mock_bundle_service.get_or_create_bundle.return_value = (
            mock_bundle,
            False,
        )
        return mock_bundle_service

    def logging_service(self):
        """Return a mock logging service."""
        mock_logging = Mock()
        mock_logger = Mock()
        mock_logging.get_logger.return_value = mock_logger
        return mock_logging

    def auth_service(self):
        """Return a mock auth service."""
        mock_auth = Mock()
        mock_auth.is_authentication_enabled.return_value = (
            False  # Disable auth for tests
        )
        return mock_auth


class TestAPIFix(unittest.TestCase):
    """Test API with proper dependency overrides to fix args/kwargs issue."""

    def setUp(self):
        """Set up test with proper dependency injection."""
        # Create mock services
        self.mock_services = MockServices()

        # Create FastAPI app
        app = create_fastapi_app()

        # Override the container in app state (this is how the new architecture works)
        app.state.container = self.mock_services

        self.client = TestClient(app)

    def tearDown(self):
        """Clean up test resources."""
        shutil.rmtree(self.mock_services.temp_dir, ignore_errors=True)

    def test_health_endpoint(self):
        """Test basic health endpoint works."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")

    def test_execution_run_endpoint_basic(self):
        """Test basic execution endpoint without the args/kwargs error."""
        request_data = {"state": {"input": "test_value"}}

        response = self.client.post("/execute/run", json=request_data)

        # The key test: we should NOT get a 422 validation error about missing args/kwargs
        self.assertNotEqual(
            response.status_code,
            422,
            f"Should not get 422 args/kwargs error. Response: {response.text}",
        )


if __name__ == "__main__":
    unittest.main()
