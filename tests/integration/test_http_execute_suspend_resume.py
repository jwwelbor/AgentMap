"""Integration tests for HTTP execute/resume routes using the FastAPI adapter.

These tests spin up the FastAPI application with a temporary configuration and
exercise a full suspend → resume lifecycle to ensure the HTTP layer mirrors the
CLI behaviour.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agentmap.deployment.http.api.server import FastAPIServer


class TestHTTPExecuteSuspendResume(unittest.TestCase):
    """Verify the HTTP execution routes handle suspend/resume end-to-end."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)

        self._prepare_directories()
        self.storage_config_path = self._write_storage_config()
        self.config_file = self._write_app_config()
        self._write_suspend_workflow()

        # Defer TestClient creation to each test to respect lifespan start/stop.
        self.server = FastAPIServer(config_file=str(self.config_file))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _prepare_directories(self) -> None:
        """Create all directories referenced by the temporary configuration."""
        self.cache_path = self.base_path / "cache"
        self.custom_agents_path = self.base_path / "custom_agents"
        self.functions_path = self.base_path / "functions"
        self.metadata_bundles_path = self.base_path / "metadata_bundles"
        self.workflows_path = self.base_path / "workflows"
        self.prompts_path = self.base_path / "prompts"
        self.storage_base_path = self.base_path / "storage"

        for path in [
            self.cache_path,
            self.custom_agents_path,
            self.functions_path,
            self.metadata_bundles_path,
            self.workflows_path,
            self.prompts_path,
            self.storage_base_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        # Pre-create expected cache subdirectories used by checkpoints/interactions
        (self.cache_path / "checkpoints").mkdir(exist_ok=True)
        (self.cache_path / "interactions").mkdir(exist_ok=True)

    def _write_storage_config(self) -> Path:
        storage_config = {
            "core": {"base_directory": str(self.storage_base_path)},
            "json": {
                "enabled": True,
                "auto_create_files": True,
                "encoding": "utf-8",
                "indent": 2,
            },
            "csv": {
                "enabled": True,
                "default_directory": "csv",
                "auto_create_files": True,
            },
            "vector": {"enabled": False},
            "kv": {"enabled": False},
        }

        storage_config_path = self.base_path / "storage_config.yaml"
        storage_config_path.write_text(
            json.dumps(storage_config, indent=2), encoding="utf-8"
        )
        return storage_config_path

    def _write_app_config(self) -> Path:
        app_config = {
            "storage_config_path": str(self.storage_config_path),
            "paths": {
                "cache": str(self.cache_path),
                "custom_agents": str(self.custom_agents_path),
                "functions": str(self.functions_path),
                "metadata_bundles": str(self.metadata_bundles_path),
                "csv_repository": str(self.workflows_path),
            },
            "llm": {
                "anthropic": {
                    "api_key": "test-key",
                    "model": "claude-3-opus-20240229",
                }
            },
            "authentication": {
                "enabled": False,
            },
            "memory": {"enabled": False},
            "prompts": {
                "directory": str(self.prompts_path),
                "enable_cache": False,
            },
            "execution": {
                "tracking": {
                    "enabled": False,
                    "track_outputs": True,
                    "track_inputs": True,
                },
                "success_policy": {
                    "type": "all_nodes",
                    "custom_function": "",
                    "critical_nodes": [],
                },
            },
            "tracing": {"enabled": False},
            "logging": {
                "version": 1,
                "disable_existing_loggers": True,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "ERROR",
                    }
                },
                "root": {
                    "level": "ERROR",
                    "handlers": ["console"],
                },
            },
            "routing": {},
        }

        config_path = self.base_path / "app_config.yaml"
        config_path.write_text(json.dumps(app_config, indent=2), encoding="utf-8")
        return config_path

    def _write_suspend_workflow(self) -> None:
        """Create a workflow that suspends and resumes without interactive input."""
        workflow_csv = """GraphName,Node,AgentType,Input_Fields,Output_Field,Success_Next,Failure_Next,Prompt,Context,Description
SuspendResume,SeedRequest,default,seed_value,request_id,WaitForSignal,,"Seeding request from {seed_value}",,"Seed request without user input"
SuspendResume,WaitForSignal,suspend,request_id,resume_payload,Finalize,,"Waiting for external signal for {request_id}","{""reason"": ""test_suspend"", ""external_ref"": ""integration_test""}","Suspend execution until resume"
SuspendResume,Finalize,default,,final_message,,,"Workflow resumed successfully",,"Finalize after resume"
"""

        workflow_path = self.workflows_path / "suspend_resume.csv"
        workflow_path.write_text(workflow_csv, encoding="utf-8")

    def test_full_suspend_resume_flow(self) -> None:
        """Run a workflow to suspension and resume it via HTTP endpoints."""
        graph_identifier = "suspend_resume::SuspendResume"
        execute_payload = {"inputs": {"seed_value": "payload-123"}}

        with TestClient(self.server.app) as client:
            execute_response = client.post(
                f"/execute/{graph_identifier}", json=execute_payload
            )

            self.assertEqual(execute_response.status_code, 200)
            body = execute_response.json()

            self.assertFalse(body["success"])
            self.assertEqual(body["status"], "suspended")
            self.assertIsNotNone(body["thread_id"])
            self.assertIn("execution_summary", body)
            self.assertEqual(
                body["execution_summary"].get("status"), "suspended"
            )

            thread_id = body["thread_id"]

            resume_response = client.post(f"/resume/{thread_id}", json={})

            self.assertEqual(resume_response.status_code, 200)
            resume_body = resume_response.json()

            self.assertTrue(resume_body["success"])
            self.assertEqual(resume_body["status"], "completed")
            self.assertIn("execution_summary", resume_body)
            self.assertEqual(
                resume_body["execution_summary"].get("status"), "completed"
            )
            self.assertIn("outputs", resume_body)

            outputs = resume_body["outputs"] or {}
            # DefaultAgent includes execution metadata in output
            final_message = outputs.get("final_message", "")
            self.assertIn("Workflow resumed successfully", final_message)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
