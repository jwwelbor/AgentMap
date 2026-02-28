#!/usr/bin/env python3
"""
AgentMap Host Application Integration Example

Demonstrates the declarative host service integration pipeline end-to-end:
  1. host_services.yaml declares services + protocols
  2. custom_agents.yaml declares agents + required services
  3. AgentMap auto-imports, instantiates, registers, and injects at runtime

Run from repo root:
    uv run python examples/host_integration/integration_example.py
"""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    """Demonstrate declarative host service integration by running a workflow."""
    print("AgentMap Declarative Host Service Integration Example")
    print("=" * 55)
    print()

    # Resolve config path relative to this file
    example_dir = Path(__file__).parent.resolve()
    config_file = str(example_dir / "agentmap_config.yaml")

    # Step 1: Initialize
    print("Initializing AgentMap with host service config...")
    from agentmap.runtime_api import ensure_initialized, run_workflow

    ensure_initialized(config_file=config_file)
    print("Runtime ready.")
    print()

    # Step 2: Run the workflow
    print("Running HostIntegrationDemo workflow...")
    print("-" * 40)
    result = run_workflow(
        "example_workflow::HostIntegrationDemo",
        inputs={},
        config_file=config_file,
        force_create=True,
    )
    print("-" * 40)
    print()

    # Step 3: Show results
    if result.get("success"):
        print("Workflow completed successfully!")
        print()

        outputs = result.get("outputs", {})

        db_result = outputs.get("database_result", {})
        if db_result:
            print(f"Database: Found {db_result.get('count', 0)} users")
            for user in db_result.get("users", []):
                print(f"  - {user.get('name')} ({user.get('email')})")

        ms_result = outputs.get("multi_service_result", {})
        if ms_result:
            print(f"\nMulti-service: {ms_result.get('summary', 'N/A')}")

        notif_result = outputs.get("notification_result", {})
        if notif_result:
            channels = notif_result.get("channels", [])
            print(f"\nNotifications sent via: {', '.join(channels)}")
    else:
        print("Workflow failed!")
        print(json.dumps(result, indent=2, default=str))
        return 1

    print()
    print("To use this in your own project:")
    print("  1. Place host_services.yaml in your custom agents directory")
    print("  2. Place custom_agents.yaml in the same directory")
    print("  3. Set paths.custom_agents in your agentmap_config.yaml")
    print("  4. Run 'agentmap run <your-workflow.csv>'")

    return 0


if __name__ == "__main__":
    # Run from repo root so relative paths in config resolve correctly
    repo_root = Path(__file__).parent.parent.parent.resolve()
    os.chdir(repo_root)
    sys.exit(main())
