"""
Service for formatting graph execution results for development readability.

This service provides formatting capabilities for graph execution output,
making it easier to understand execution flow during development and testing.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional


class ExecutionFormatterService:
    """Service for formatting graph execution results for readability."""

    def format_execution_result(
        self, result: Dict[str, Any], verbose: bool = False
    ) -> str:
        """
        Format graph execution output for better readability.

        Args:
            result: The raw graph execution result
            verbose: If True, show detailed node execution info

        Returns:
            Formatted string output
        """
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("GRAPH EXECUTION SUMMARY")
        lines.append("=" * 80)

        # Extract execution summary if present
        exec_summary = result.get("__execution_summary")
        if exec_summary:
            # Basic info
            lines.append(f"\nGraph Name: {exec_summary.graph_name}")
            lines.append(f"Status: {exec_summary.status.upper()}")
            lines.append(
                f"Success: {'✅ Yes' if exec_summary.graph_success else '❌ No'}"
            )

            # Duration calculation
            if hasattr(exec_summary, "start_time") and hasattr(
                exec_summary, "end_time"
            ):
                duration = (
                    exec_summary.end_time - exec_summary.start_time
                ).total_seconds()
                lines.append(f"Total Duration: {duration:.2f} seconds")
                lines.append(
                    f"Start Time: {exec_summary.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                lines.append(
                    f"End Time: {exec_summary.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            # Node execution section
            if hasattr(exec_summary, "node_executions"):
                lines.append(f"\nNodes Executed: {len(exec_summary.node_executions)}")

                # Always show node execution order in basic mode
                lines.append("\n" + "=" * 80)
                lines.append("NODE EXECUTION ORDER")
                lines.append("=" * 80)

                if verbose:
                    # Detailed mode - full information
                    for i, node in enumerate(exec_summary.node_executions, 1):
                        lines.append(f"\n{i}. {node.node_name}")
                        lines.append(
                            f"   ├─ Status: {'✅ Success' if node.success else '❌ Failed'}"
                        )
                        lines.append(f"   ├─ Duration: {node.duration:.3f}s")

                        # Format time window
                        start_time = node.start_time.strftime("%H:%M:%S")
                        end_time = node.end_time.strftime("%H:%M:%S")
                        lines.append(f"   ├─ Time: {start_time} → {end_time}")

                        # Format output based on type
                        output_str = self._format_node_output(node.output)
                        lines.append(f"   └─ Output: {output_str}")

                        if node.error:
                            lines.append(f"   └─ ERROR: {node.error}")
                else:
                    # Basic mode - just node names and brief info
                    for i, node in enumerate(exec_summary.node_executions, 1):
                        status_icon = "✅" if node.success else "❌"
                        duration_str = f"{node.duration:.1f}s"

                        # Special formatting for different node types
                        if node.node_name == "UserInput" and isinstance(
                            node.output, str
                        ):
                            lines.append(
                                f'{i:2}. {node.node_name:<25} {duration_str:>8} {status_icon}  → "{node.output}"'
                            )
                        elif node.node_name == "Orchestrator" and isinstance(
                            node.output, str
                        ):
                            lines.append(
                                f"{i:2}. {node.node_name:<25} {duration_str:>8} {status_icon}  → {node.output}"
                            )
                        else:
                            lines.append(
                                f"{i:2}. {node.node_name:<25} {duration_str:>8} {status_icon}"
                            )

        # Key results section
        lines.append("\n" + "=" * 80)
        lines.append("FINAL STATE")
        lines.append("=" * 80)

        # Extract key results
        if "orchestrator_result" in result:
            lines.append(f"Orchestrator Decision: {result['orchestrator_result']}")

        if "exploration_result" in result:
            exp_result = result["exploration_result"]
            if isinstance(exp_result, dict) and "node" in exp_result:
                lines.append(f"Exploration Result: {exp_result['node']}")

        if "combat_result" in result:
            combat_result = result["combat_result"]
            if isinstance(combat_result, dict) and "node" in combat_result:
                lines.append(f"Combat Result: {combat_result['node']}")

        if "__policy_success" in result:
            lines.append(
                f"\nPolicy Success: {'✅ Yes' if result['__policy_success'] else '❌ No'}"
            )

        # User inputs/outputs
        if "input" in result:
            lines.append(f"\nLast Input: {result['input']}")

        if "__next_node" in result:
            lines.append(f"Next Node: {result['__next_node']}")

        # If not verbose, show a hint
        if not verbose and exec_summary and hasattr(exec_summary, "node_executions"):
            lines.append(
                f"\nℹ️  Use --pretty --verbose to see detailed node execution info"
            )

        return "\n".join(lines)

    def _format_node_output(self, output: Any) -> str:
        """Format node output for display."""
        if isinstance(output, dict):
            # Special handling for agent outputs
            if "processed" in output and "node" in output:
                agent_type = output.get("agent_type", "unknown")
                next_node = output.get("node", "unknown")
                return f"[{agent_type}] → {next_node}"
            else:
                # Truncate long dict outputs
                output_str = json.dumps(output, default=str)
                if len(output_str) > 100:
                    output_str = output_str[:97] + "..."
                return output_str
        else:
            # String outputs
            output_str = str(output)
            if len(output_str) > 100:
                output_str = output_str[:97] + "..."
            return output_str

    def format_simple_summary(self, result: Dict[str, Any]) -> str:
        """
        Simple one-line summary format for quick debugging.

        Args:
            result: The raw graph execution result

        Returns:
            Simple formatted string
        """
        exec_summary = result.get("__execution_summary", {})

        if hasattr(exec_summary, "graph_name"):
            status = "✅" if getattr(exec_summary, "graph_success", False) else "❌"
            duration = 0
            if hasattr(exec_summary, "start_time") and hasattr(
                exec_summary, "end_time"
            ):
                duration = (
                    exec_summary.end_time - exec_summary.start_time
                ).total_seconds()

            node_count = len(getattr(exec_summary, "node_executions", []))

            return f"{status} {exec_summary.graph_name} | {duration:.2f}s | {node_count} nodes | {exec_summary.status}"

        return "✅ Graph execution completed (no summary available)"
