"""Documentation generator for AgentMap graphs."""

from typing import Dict, List


class DocumentationGenerator:
    """Generator for graph documentation in various formats."""

    @staticmethod
    def generate_markdown(graph_name: str, graph_def: Dict) -> List[str]:
        lines = [
            f"# Graph: {graph_name}",
            "",
            "## Overview",
            f"This document describes the structure and flow of the `{graph_name}` graph.",
            "",
            "## Nodes",
            "",
        ]
        for node_name, node in graph_def.items():
            inputs_str = ", ".join(node.inputs) if node.inputs else "None"
            lines.extend(
                [
                    f"### {node_name}",
                    f"- **Agent Type**: {node.agent_type}",
                    f"- **Inputs**: {inputs_str}",
                    f"- **Output**: {node.output or 'None'}",
                    f"- **Description**: {node.description or 'No description'}",
                    "",
                ]
            )
            if node.prompt:
                lines.extend(["**Prompt:**", "```", node.prompt, "```", ""])
            if node.edges:
                lines.extend(["**Edges:**", ""])
                for edge_type, target in node.edges.items():
                    lines.append(f"- `{edge_type}` -> `{target}`")
                lines.append("")
        return lines

    @staticmethod
    def generate_html(graph_name: str, graph_def: Dict) -> List[str]:
        lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"    <title>Graph: {graph_name}</title>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 2em; }",
            "        .node { margin: 1em 0; padding: 1em; border: 1px solid #ccc; }",
            "        .prompt { background: #f5f5f5; padding: 1em; }",
            "    </style>",
            "</head>",
            "<body>",
            f"    <h1>Graph: {graph_name}</h1>",
            "    <h2>Nodes</h2>",
        ]
        for node_name, node in graph_def.items():
            inputs_str = ", ".join(node.inputs) if node.inputs else "None"
            lines.extend(
                [
                    '    <div class="node">',
                    f"        <h3>{node_name}</h3>",
                    f"        <p><strong>Agent Type:</strong> {node.agent_type}</p>",
                    f"        <p><strong>Inputs:</strong> {inputs_str}</p>",
                    f'        <p><strong>Output:</strong> {node.output or "None"}</p>',
                    f'        <p><strong>Description:</strong> {node.description or "No description"}</p>',
                ]
            )
            if node.prompt:
                lines.extend(
                    [
                        '        <div class="prompt">',
                        "            <strong>Prompt:</strong><br>",
                        f"            <pre>{node.prompt}</pre>",
                        "        </div>",
                    ]
                )
            lines.append("    </div>")
        lines.extend(["</body>", "</html>"])
        return lines
