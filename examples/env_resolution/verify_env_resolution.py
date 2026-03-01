#!/usr/bin/env python3
"""
Verify that env: prefix resolution works in AgentMap config loading.

Run:  python examples/env_resolution/verify_env_resolution.py
"""

import os
import sys
import tempfile

import yaml

# Set test env vars BEFORE importing ConfigService
os.environ["TEST_OPENAI_KEY"] = "sk-test-openai-12345"
os.environ["TEST_ANTHROPIC_KEY"] = "sk-ant-test-anthropic-67890"
# Deliberately leave TEST_GOOGLE_KEY unset to test default fallback

from agentmap.services.config.config_service import ConfigService  # noqa: E402

# Reset singleton so we get a fresh instance
ConfigService._instance = None
service = ConfigService()

# Write a config that uses env: syntax
config = {
    "llm": {
        "openai": {
            "api_key": "env:TEST_OPENAI_KEY",
            "model": "gpt-4.1-mini",
        },
        "anthropic": {
            "api_key": "env:TEST_ANTHROPIC_KEY",
        },
        "google": {
            "api_key": "env:TEST_GOOGLE_KEY:default-google-key",
            "model": "env:TEST_MISSING_MODEL:gemini-2.5-flash",
        },
    },
}

with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
    yaml.dump(config, f)
    tmp_path = f.name

try:
    result = service.load_config(tmp_path)

    checks = [
        ("env:VAR (present)", result["llm"]["openai"]["api_key"], "sk-test-openai-12345"),
        ("env:VAR (present)", result["llm"]["anthropic"]["api_key"], "sk-ant-test-anthropic-67890"),
        ("env:VAR:default (missing var)", result["llm"]["google"]["api_key"], "default-google-key"),
        ("env:VAR:default (missing var)", result["llm"]["google"]["model"], "gemini-2.5-flash"),
        ("plain string (no env:)", result["llm"]["openai"]["model"], "gpt-4.1-mini"),
    ]

    all_passed = True
    for label, actual, expected in checks:
        status = "PASS" if actual == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {label}: {actual!r} == {expected!r}")

    print()
    if all_passed:
        print("All checks passed.")
    else:
        print("Some checks FAILED.")
        sys.exit(1)
finally:
    os.unlink(tmp_path)
    ConfigService._instance = None
