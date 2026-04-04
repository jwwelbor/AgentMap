#!/usr/bin/env python3
"""
Vision / Multimodal CSV Graph Example — AgentMap

Demonstrates running an image-extraction workflow defined in a CSV graph.
The graph uses a custom VisionAgent that calls LLMService.ask_vision()
under the hood.

Graph definition (vision_workflow.csv):
  LoadImage → AnalyzeImage (VisionAgent) → FormatResult → End

Requirements:
  - ANTHROPIC_API_KEY set in your environment
  - agentmap installed with LLM dependencies
"""

import os
import sys

# Run from the example directory so relative config paths resolve
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

from agentmap.runtime_api import run_workflow

IMAGE_PATH = os.path.join(SCRIPT_DIR, "visual-table-test.png")

print("=" * 70)
print("Vision Graph Example: CSV-driven image extraction")
print("=" * 70)
print(f"Image: {IMAGE_PATH}")
print()

result = run_workflow(
    "vision_workflow::ImageExtract",
    {"image_path": IMAGE_PATH},
    config_file=os.path.join(SCRIPT_DIR, "agentmap_config.yaml"),
)

outputs = result.get("outputs", {})
extraction = outputs.get("extraction") or outputs.get("data") or result

print("--- Extracted table ---")
print(extraction)
