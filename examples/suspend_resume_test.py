"""
Quick suspend → resume workflow demo.

Usage:
    poetry run python scripts/suspend_resume_demo.py \
        --graph suspend_agent_examples::APIIntegration \
        --config agentmap_local_config.yaml

If the workflow only suspends (no human interaction), omit --resume-action/--resume-data.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from agentmap.runtime_api import ensure_initialized, resume_workflow, run_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a suspend/resume workflow demo.")
    parser.add_argument(
        "--graph",
        required=True,
        help="Graph identifier to run (e.g. suspend_agent_examples::APIIntegration).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional config file to load before execution.",
    )
    parser.add_argument(
        "--inputs",
        default="{}",
        help="JSON string of initial inputs for the workflow.",
    )
    parser.add_argument(
        "--resume-action",
        default=None,
        help="Optional resume action (approve/reject/respond/etc.) for human-interaction agents.",
    )
    parser.add_argument(
        "--resume-data",
        default=None,
        help="Optional JSON payload with extra data to accompany the resume action.",
    )
    return parser.parse_args()


def load_json(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - CLI convenience
        raise SystemExit(f"Invalid JSON: {exc}") from exc


def main() -> None:
    args = parse_args()

    ensure_initialized(config_file=args.config)
    initial_state = load_json(args.inputs)

    print(f"▶️  Running graph: {args.graph}")
    result = run_workflow(
        graph_name=args.graph,
        inputs=initial_state,
        config_file=args.config,
    )

    if not result.get("interrupted"):
        print("✅ Workflow completed without suspension.")
        print(json.dumps(result, indent=2, default=str))
        return

    thread_id = result.get("thread_id")
    if not thread_id:
        raise SystemExit("Suspended execution did not return a thread_id.")

    print("⏸️  Workflow suspended")
    print(json.dumps(result, indent=2, default=str))

    resume_token = {
        "thread_id": thread_id,
        "response_action": args.resume_action,
    }
    resume_payload = load_json(args.resume_data)
    if resume_payload:
        resume_token["response_data"] = resume_payload

    print("🔄  Resuming workflow…")
    resumed = resume_workflow(
        resume_token=json.dumps(resume_token),
        config_file=args.config,
    )

    print("📤 Resume result")
    print(json.dumps(resumed, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())