#!/usr/bin/env python3
"""
End-to-end test for host service integration.

Verifies the full pipeline: CSV parsing -> agent creation -> host service
injection -> workflow execution using the declarative YAML approach.

Run from repo root:
    uv run python examples/host_integration/test_basic_integration.py
"""

import os
import sys
import traceback
from pathlib import Path


def main() -> int:
    """Run end-to-end host integration test."""
    print("AgentMap Host Integration - End-to-End Test")
    print("=" * 50)

    # Resolve config path relative to this file's directory
    example_dir = Path(__file__).parent.resolve()
    config_file = str(example_dir / "agentmap_config.yaml")

    print(f"Config: {config_file}")
    print()

    # Step 1: Initialize AgentMap with the example config
    print("[1/3] Initializing AgentMap runtime...")
    try:
        from agentmap.runtime_api import ensure_initialized

        ensure_initialized(config_file=config_file)
        print("      OK - Runtime initialized")
    except Exception as e:
        print(f"      FAIL - {e}")
        traceback.print_exc()
        return 1

    # Step 2: Run the workflow
    print("[2/3] Running HostIntegrationDemo workflow...")
    try:
        from agentmap.runtime_api import run_workflow

        result = run_workflow(
            "example_workflow::HostIntegrationDemo",
            inputs={},
            config_file=config_file,
            force_create=True,
        )
        print("      OK - Workflow completed")
    except Exception as e:
        print(f"      FAIL - {e}")
        traceback.print_exc()
        return 1

    # Step 3: Validate results
    print("[3/3] Validating results...")
    errors = []

    if not result.get("success"):
        errors.append(f"Workflow not successful: {result}")

    outputs = result.get("outputs", {})

    # Check database agent produced user data
    db_result = outputs.get("database_result")
    if not db_result:
        errors.append("Missing database_result in outputs")
    elif not db_result.get("users"):
        errors.append("database_result has no users")

    # Check multi-service agent processed request
    ms_result = outputs.get("multi_service_result")
    if not ms_result:
        errors.append("Missing multi_service_result in outputs")

    # Check notification agent sent notifications
    notif_result = outputs.get("notification_result")
    if not notif_result:
        errors.append("Missing notification_result in outputs")

    if errors:
        for err in errors:
            print(f"      FAIL - {err}")
        print()
        print("Full result:")
        import json

        print(json.dumps(result, indent=2, default=str))
        return 1

    print("      OK - All assertions passed")
    print()
    print("Result summary:")
    print(f"  Users found: {db_result.get('count', '?')}")
    print(f"  Multi-service status: {outputs.get('status', '?')}")
    print(f"  Notification channels: {notif_result.get('channels', '?')}")
    print()
    print("End-to-end host integration is working!")
    return 0


if __name__ == "__main__":
    # Run from repo root so relative paths in config resolve correctly
    repo_root = Path(__file__).parent.parent.parent.resolve()
    os.chdir(repo_root)
    sys.exit(main())
