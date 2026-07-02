#!/usr/bin/env python3
"""
Run GraphAgent subgraph mapping examples.
"""

import os
import sys
from pathlib import Path
from pprint import pprint

EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parents[1]

sys.path.insert(0, str(REPO_ROOT / "src"))
os.chdir(EXAMPLE_DIR)

from agentmap import run_workflow


def clean_outputs(outputs):
    """Remove execution metadata so the mapping behavior is easier to inspect."""
    if isinstance(outputs, dict):
        cleaned = {}
        for key, value in outputs.items():
            if key in {"__execution_summary", "__policy_success", "subgraph_bundles"}:
                continue
            cleaned[key] = clean_outputs(value)
        return cleaned
    if isinstance(outputs, list):
        return [clean_outputs(item) for item in outputs]
    return outputs


def run_case(title, graph_name, inputs):
    print("=" * 72)
    print(title)
    print("=" * 72)
    print(f"Graph:  {graph_name}")
    print(f"Inputs: {inputs}")

    result = run_workflow(graph_name, inputs)
    print("Success:", result["success"])
    pprint(clean_outputs(result["outputs"]))
    print()


def main():
    run_case(
        "Example 1: Store the entire child final state under one parent field",
        "DirectSubgraphState",
        {"raw_data": "hello from parent"},
    )

    run_case(
        "Example 2: Pass selected parent fields straight into the child graph",
        "ChildInputPassThrough",
        {"text": "passed straight into child text", "request_id": "req-42"},
    )

    run_case(
        "Example 3: Remap parent raw_data -> child text before subgraph execution",
        "RemappedChildInput",
        {"raw_data": "hello through child remap", "request_id": "req-42"},
    )

    run_case(
        "Example 4: Remap child child_final -> parent selected_parent on return",
        "OutputRemapExample",
        {"raw_data": "mapped back to parent"},
    )


if __name__ == "__main__":
    main()
