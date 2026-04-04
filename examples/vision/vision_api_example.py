#!/usr/bin/env python3
"""
Vision / Multimodal API Example — AgentMap

Demonstrates using LLMService.ask_vision() directly to extract
information from an image.  Two modes are shown:

  1. File path mode  — returns a markdown table
  2. Base64 / bytes  — returns CSV data

Both produce the same multimodal request under the hood; the
difference is how you hand the image to the service and what
output format you request in the prompt.

Requirements:
  - ANTHROPIC_API_KEY (or OPENAI_API_KEY) set in your environment
  - agentmap installed with LLM dependencies
"""

import base64
import os
import sys

from dotenv import load_dotenv

# Resolve paths relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
IMAGE_PATH = os.path.join(SCRIPT_DIR, "visual-table-test.png")

# Load API keys from project root .env
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# --------------------------------------------------------------------------- #
# Bootstrap AgentMap and get the LLM service
# --------------------------------------------------------------------------- #
from agentmap.runtime.init_ops import ensure_initialized, get_container

ensure_initialized()
container = get_container()
llm_service = container.llm_service()

PROMPT_MARKDOWN = (
    "Extract all the data from this table image. "
    "Return the result as a markdown table with the same columns and rows."
)

PROMPT_CSV = (
    "Extract all the data from this table image. "
    "Return the result as CSV with a header row. No other text, just the CSV."
)

# ═══════════════════════════════════════════════════════════════════════════════
# Example 1 — File path mode
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("Example 1: ask_vision() with a file path → Markdown table")
print("=" * 70)

result_markdown = llm_service.ask_vision(
    prompt=PROMPT_MARKDOWN,
    image=IMAGE_PATH,          # pass the path — service reads & encodes it
    provider="anthropic",      # or "openai", "google"
)

print(result_markdown)
print()

# ═══════════════════════════════════════════════════════════════════════════════
# Example 2 — Raw bytes mode → CSV output
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("Example 2: ask_vision() with raw bytes → CSV output")
print("=" * 70)

with open(IMAGE_PATH, "rb") as f:
    image_bytes = f.read()

result_csv = llm_service.ask_vision(
    prompt=PROMPT_CSV,
    image=image_bytes,         # pass bytes directly
    image_type="image/png",    # must specify MIME when using bytes
    provider="anthropic",
)

print(result_csv)
print()

# ═══════════════════════════════════════════════════════════════════════════════
# Bonus — Show what the raw base64 payload looks like (truncated)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("Bonus: what gets sent to the LLM (truncated)")
print("=" * 70)

b64 = base64.b64encode(image_bytes).decode("ascii")
print(f"  MIME type : image/png")
print(f"  Base64 len: {len(b64)} chars")
print(f"  Preview   : data:image/png;base64,{b64[:60]}...")
