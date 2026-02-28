"""Integration tests for HTTP execute/resume routes using the FastAPI adapter.

These tests use the BaseAPIIntegrationTest pattern with a properly configured
container to exercise suspend → resume lifecycle reliably without file I/O race conditions.
"""

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agentmap.deployment.http.api.server import create_fastapi_app

sys.path.insert(0, str(Path(__file__).parent.parent))

from fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestHTTPExecuteSuspendResume(BaseIntegrationTest):
    """Verify the HTTP execution routes handle suspend/resume end-to-end."""

    def setUp(self) -> None:
        """Set up test with runtime facade initialization and disabled authentication."""
        # DO NOT call super().setUp() - it initializes a container with wrong config
        # Instead, manually set up only what we need

        # Reset runtime manager to ensure clean state
        from agentmap.runtime.runtime_manager import RuntimeManager

        RuntimeManager.reset()

        # Create temp directory for test artifacts
        import tempfile

        self.temp_dir = tempfile.mkdtemp()

        # Create suspend/resume workflow CSV in test directory
        self._write_suspend_workflow()

        # Create test configuration with authentication disabled
        test_config_path = self._create_test_config()

        # Initialize runtime facade with test configuration
        # This MUST happen before creating FastAPI app so lifespan hook works correctly
        from agentmap.runtime_api import ensure_initialized

        ensure_initialized(config_file=str(test_config_path))

        # Now create the FastAPI app - it will use the configured runtime facade
        self.app = create_fastapi_app()

        # Manually set the container in app state for TestClient (bypasses lifespan)
        from agentmap.runtime_api import get_container

        self.app.state.container = get_container()

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_config(self) -> Path:
        """Create test configuration file with authentication disabled."""
        import yaml

        config_path = Path(self.temp_dir) / "test_config.yaml"
        storage_config_path = Path(self.temp_dir) / "storage_config.yaml"

        # Create config with authentication DISABLED
        config_data = {
            "authentication": {
                "enabled": False,
            },
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG",
                    }
                },
                "root": {"level": "DEBUG", "handlers": ["console"]},
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-sonnet-4-6",
                }
            },
            "paths": {
                "csv_repository": str(Path(self.temp_dir) / "storage" / "csv"),
                "csv_data": str(Path(self.temp_dir) / "storage" / "csv"),
            },
            "storage_config_path": str(storage_config_path),
        }

        storage_config_data = {
            "base_directory": str(Path(self.temp_dir) / "storage"),
            "csv": {"default_directory": "csv", "collections": {}},
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

        with open(storage_config_path, "w") as f:
            yaml.dump(storage_config_data, f, default_flow_style=False, indent=2)

        return config_path

    def _write_suspend_workflow(self) -> None:
        """Create a workflow that suspends and resumes without interactive input."""
        workflow_csv = """GraphName,Node,AgentType,Input_Fields,Output_Field,Success_Next,Failure_Next,Prompt,Context,Description
SuspendResume,SeedRequest,default,seed_value,request_id,WaitForSignal,,"Seeding request from {seed_value}",,"Seed request without user input"
SuspendResume,WaitForSignal,suspend,request_id,resume_payload,Finalize,,"Waiting for external signal for {request_id}","{""reason"": ""test_suspend"", ""external_ref"": ""integration_test""}","Suspend execution until resume"
SuspendResume,Finalize,default,,final_message,,,"Workflow resumed successfully",,"Finalize after resume"
"""

        # Use the csv directory from BaseIntegrationTest setup
        workflow_path = Path(self.temp_dir) / "storage" / "csv" / "suspend_resume.csv"
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(workflow_csv, encoding="utf-8")

    def test_full_suspend_resume_flow(self) -> None:
        """Run a workflow to suspension and resume it via HTTP endpoints."""
        graph_identifier = "suspend_resume::SuspendResume"
        execute_payload = {"inputs": {"seed_value": "payload-123"}}

        # Execute workflow - should suspend at WaitForSignal node
        execute_response = self.client.post(
            f"/execute/{graph_identifier}", json=execute_payload
        )

        self.assertEqual(
            execute_response.status_code,
            200,
            f"Execute failed: {execute_response.text}",
        )
        body = execute_response.json()

        # Verify workflow suspended (status="suspended" but execution_summary status="interrupted" in LangGraph 1.x)
        self.assertFalse(body["success"], "Workflow should suspend, not complete")
        self.assertEqual(body["status"], "suspended")
        self.assertIsNotNone(body["thread_id"])
        self.assertIn("execution_summary", body)
        # LangGraph 1.x uses "interrupted" in the execution summary
        self.assertIn(
            body["execution_summary"].get("status"), ["suspended", "interrupted"]
        )

        thread_id = body["thread_id"]

        # Resume workflow with empty payload (suspend agent doesn't need input)
        resume_response = self.client.post(f"/resume/{thread_id}", json={})

        self.assertEqual(
            resume_response.status_code, 200, f"Resume failed: {resume_response.text}"
        )
        resume_body = resume_response.json()

        # Verify workflow completed after resume
        self.assertTrue(resume_body["success"], "Workflow should complete after resume")
        self.assertEqual(resume_body["status"], "completed")
        self.assertIn("execution_summary", resume_body)
        self.assertEqual(resume_body["execution_summary"].get("status"), "completed")
        self.assertIn("outputs", resume_body)

        outputs = resume_body["outputs"] or {}
        # DefaultAgent includes execution metadata in output
        final_message = outputs.get("final_message", "")
        self.assertIn("Workflow resumed successfully", final_message)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
