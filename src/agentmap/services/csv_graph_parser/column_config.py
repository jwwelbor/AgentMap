"""
Column configuration for CSV graph parsing.

Defines the expected CSV structure, required/optional columns, and column aliases
for flexible column naming in CSV workflow definitions.
"""

from typing import Dict, List, Set


class CSVColumnConfig:
    """
    Configuration for CSV column definitions and aliases.

    Centralizes all column-related configuration for CSV parsing,
    including required columns, optional columns, and alias mappings.
    """

    def __init__(self):
        """Initialize column configuration."""
        # Define expected CSV structure
        self.required_columns: Set[str] = {"GraphName", "Node"}
        self.optional_columns: Set[str] = {
            "AgentType",
            "Prompt",
            "Description",
            "Context",
            "Input_Fields",
            "Output_Field",
            "Edge",
            "Success_Next",
            "Failure_Next",
            "Tool_Source",
            "Available_Tools",
        }
        self.all_columns: Set[str] = self.required_columns | self.optional_columns

        # Column alias mapping for flexible column naming
        self.column_aliases: Dict[str, List[str]] = {
            # Primary name -> acceptable aliases
            "GraphName": [
                "graph_name",
                "Graph",
                "WorkflowName",
                "workflow_name",
                "workflow",
            ],
            "Node": ["node_name", "NodeName", "Step", "StepName", "name"],
            "AgentType": ["agent_type", "Agent", "Type"],
            "Prompt": ["prompt", "Instructions", "Template", "prompt_template"],
            "Description": ["description", "desc", "Details"],
            "Input_Fields": ["input_fields", "Inputs", "InputFields"],
            "Output_Field": ["output_field", "Output", "OutputField"],
            "Edge": ["edge", "next_node", "NextNode", "Target", "next"],
            "Success_Next": [
                "success_next",
                "next_on_success",
                "SuccessTarget",
                "on_success",
            ],
            "Failure_Next": [
                "failure_next",
                "next_on_failure",
                "FailureTarget",
                "on_failure",
            ],
            "Context": ["context", "Config", "Configuration"],
            "Tool_Source": ["tool_source", "ToolSource", "ToolFile", "ToolModule"],
            "Available_Tools": [
                "available_tools",
                "AvailableTools",
                "Tools",
                "ToolList",
            ],
        }

    def get_canonical_name(self, column_name: str) -> str:
        """
        Get the canonical (primary) name for a column.

        Args:
            column_name: The column name to look up

        Returns:
            The canonical name if found, otherwise the original name
        """
        col_lower = column_name.lower()

        for primary_name, aliases in self.column_aliases.items():
            # Check if it's already the primary name (case-insensitive)
            if col_lower == primary_name.lower():
                return primary_name

            # Check aliases (case-insensitive)
            for alias in aliases:
                if col_lower == alias.lower():
                    return primary_name

        # Not found in aliases, return original
        return column_name
