#!/usr/bin/env python3
"""
AgentMap Host Application Integration Example (Declarative)

This example demonstrates declarative host service registration via YAML.
No programmatic container.register_host_service() calls are needed.

Host services are declared in host_services.yaml alongside custom_agents.yaml.
AgentMap auto-imports, instantiates, and registers them at runtime.

Run:
    python examples/host_integration/integration_example.py
"""

import sys
from pathlib import Path

# Add AgentMap to path for this example
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def main() -> int:
    """Demonstrate declarative host service integration."""
    print("AgentMap Declarative Host Service Integration Example")
    print("=" * 55)
    print()
    print("This example uses two YAML files in the custom agents directory:")
    print("  - host_services.yaml  : declares host services + protocols")
    print("  - custom_agents.yaml  : declares agents + required services")
    print()
    print("No programmatic registration is needed. AgentMap automatically:")
    print("  1. Loads host_services.yaml via HostServiceYAMLSource")
    print("  2. Bootstraps services (import, instantiate, register)")
    print("  3. Injects matching services into agents via protocol detection")
    print()
    print("See the YAML files in this directory for the full declarations.")
    print()

    # Show the YAML files
    example_dir = Path(__file__).parent

    print("--- host_services.yaml ---")
    host_yaml = example_dir / "host_services.yaml"
    if host_yaml.exists():
        print(host_yaml.read_text())
    print()

    print("--- custom_agents.yaml ---")
    agents_yaml = example_dir / "custom_agents.yaml"
    if agents_yaml.exists():
        print(agents_yaml.read_text())
    print()

    print("To use this in your own project:")
    print("  1. Place host_services.yaml in your custom agents directory")
    print("  2. Place custom_agents.yaml in the same directory")
    print("  3. Run 'agentmap run <your-workflow.csv>'")
    print("  4. Agents matching declared protocols get services injected")

    return 0


if __name__ == "__main__":
    sys.exit(main())
