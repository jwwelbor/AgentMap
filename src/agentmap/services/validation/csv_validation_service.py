# src/agentmap/services/validation/csv_validation_service.py
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Dict

import pandas as pd
from pydantic import ValidationError as PydanticValidationError

from agentmap.models.validation.csv_row_model import CSVRowModel
from agentmap.models.validation.validation_models import (
    ValidationResult,
)
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.logging_service import LoggingService


class CSVValidationService:
    def __init__(
        self,
        logging_service: LoggingService,
        function_resolution_service: FunctionResolutionService,
        agent_registry_service: AgentRegistryService,
    ):
        """Initialize the CSV validator."""
        self.function_resolution_service = function_resolution_service
        self.agent_registry = agent_registry_service
        self.required_columns = {"GraphName", "Node"}
        self.optional_columns = {
            "AgentType",
            "Prompt",
            "Description",
            "Context",
            "Input_Fields",
            "Output_Field",
            "Edge",
            "Success_Next",
            "Failure_Next",
        }
        self.all_columns = self.required_columns | self.optional_columns

        # Column alias mapping for flexible column naming
        self.column_aliases = {
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
        }

        self.logger = logging_service.get_logger("agentmap.csv_validation")

    def validate_file(self, csv_path: Path) -> ValidationResult:
        """
        Main validation entry point for a CSV file.

        Args:
            csv_path: Path to the CSV file to validate

        Returns:
            ValidationResult with all validation issues found
        """
        result = ValidationResult(
            file_path=str(csv_path), file_type="csv", is_valid=True
        )

        # Calculate file hash for caching
        try:
            with open(csv_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
                result.file_hash = file_hash
        except Exception as e:
            result.add_error(f"Cannot read file: {e}")
            return result

        # Check if file exists and is readable
        if not csv_path.exists():
            result.add_error(f"CSV file does not exist: {csv_path}")
            return result

        if not csv_path.is_file():
            result.add_error(f"Path is not a file: {csv_path}")
            return result

        try:
            # Load CSV with pandas
            df = pd.read_csv(csv_path)

            # Normalize column names to canonical form
            df = self._normalize_columns(df)

            # Run all validation checks
            self._validate_structure(df, result)
            self._validate_rows(df, result)

            # Only run graph-level validation if no structural errors
            if not result.has_errors:
                graphs = self._build_graphs_for_validation(df, result)
                if graphs:
                    self._validate_graph_consistency(graphs, result)
                    self._validate_routing_logic(df, graphs, result)
                    self._validate_agent_types(df, result)

        except pd.errors.EmptyDataError:
            result.add_error("CSV file is empty")
        except pd.errors.ParserError as e:
            result.add_error(f"CSV parsing error: {e}")
        except Exception as e:
            result.add_error(f"Unexpected error during validation: {e}")

        return result

    def _validate_structure(self, df: pd.DataFrame, result: ValidationResult) -> None:
        """Validate the basic structure of the CSV file."""

        # Check if DataFrame is empty
        if df.empty:
            result.add_error("CSV file contains no data rows")
            return

        # Check for required columns
        missing_required = self.required_columns - set(df.columns)
        if missing_required:
            for col in missing_required:
                result.add_error(f"Required column missing: '{col}'")

        # Check for unexpected columns
        unexpected_columns = set(df.columns) - self.all_columns
        if unexpected_columns:
            for col in unexpected_columns:
                result.add_warning(
                    f"Unexpected column found: '{col}'",
                    suggestion="Check for typos or remove if not needed",
                )

        # Check for completely empty required columns
        for col in self.required_columns:
            if col in df.columns and df[col].isna().all():
                result.add_error(f"Required column '{col}' is completely empty")

        # Info about data
        result.add_info(f"CSV contains {len(df)} rows and {len(df.columns)} columns")

    def _validate_rows(self, df: pd.DataFrame, result: ValidationResult) -> None:
        """Validate individual rows against the Pydantic model."""

        for idx, row in df.iterrows():
            line_number = idx + 2  # +1 for 0-indexing, +1 for header row

            try:
                # Convert row to dict, handling NaN values
                row_dict = {}
                for col in df.columns:
                    value = row[col]
                    # Convert NaN to None
                    if pd.isna(value):
                        row_dict[col] = None
                    else:
                        row_dict[col] = (
                            str(value).strip() if str(value).strip() else None
                        )

                # Validate with Pydantic model
                CSVRowModel(**row_dict)

            except PydanticValidationError as e:
                for error in e.errors():
                    field = error.get("loc", [None])[0]
                    message = error.get("msg", "Validation error")
                    value = error.get("input")

                    result.add_error(
                        message=f"Row validation error: {message}",
                        line_number=line_number,
                        field_name=str(field) if field else None,
                        value=str(value) if value is not None else None,
                    )
            except Exception as e:
                result.add_error(
                    f"Unexpected error validating row: {e}", line_number=line_number
                )

    def _build_graphs_for_validation(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> Dict[str, Dict]:
        """Build graph structures for validation purposes."""
        graphs = defaultdict(dict)

        for idx, row in df.iterrows():
            line_number = idx + 2

            try:
                graph_name = (
                    str(row["GraphName"]).strip() if pd.notna(row["GraphName"]) else ""
                )
                node_name = str(row["Node"]).strip() if pd.notna(row["Node"]) else ""

                if not graph_name:
                    result.add_error(
                        "Empty GraphName",
                        line_number=line_number,
                        field_name="GraphName",
                    )
                    continue

                if not node_name:
                    result.add_error(
                        "Empty Node name", line_number=line_number, field_name="Node"
                    )
                    continue

                # Check for duplicate nodes within a graph
                if node_name in graphs[graph_name]:
                    result.add_error(
                        f"Duplicate node '{node_name}' in graph '{graph_name}'",
                        line_number=line_number,
                        field_name="Node",
                    )
                    continue

                # Store node information for graph validation
                graphs[graph_name][node_name] = {
                    "line_number": line_number,
                    "agent_type": (
                        str(row.get("AgentType", "")).strip()
                        if pd.notna(row.get("AgentType"))
                        else ""
                    ),
                    "edge": (
                        str(row.get("Edge", "")).strip()
                        if pd.notna(row.get("Edge"))
                        else ""
                    ),
                    "success_next": (
                        str(row.get("Success_Next", "")).strip()
                        if pd.notna(row.get("Success_Next"))
                        else ""
                    ),
                    "failure_next": (
                        str(row.get("Failure_Next", "")).strip()
                        if pd.notna(row.get("Failure_Next"))
                        else ""
                    ),
                    "prompt": (
                        str(row.get("Prompt", "")).strip()
                        if pd.notna(row.get("Prompt"))
                        else ""
                    ),
                }

            except Exception as e:
                result.add_error(
                    f"Error processing row for graph validation: {e}",
                    line_number=line_number,
                )

        # Info about graphs found
        if graphs:
            graph_info = []
            for graph_name, nodes in graphs.items():
                graph_info.append(f"'{graph_name}' ({len(nodes)} nodes)")
            result.add_info(f"Found {len(graphs)} graph(s): {', '.join(graph_info)}")

        return dict(graphs)

    def _validate_graph_consistency(
        self, graphs: Dict[str, Dict], result: ValidationResult
    ) -> None:
        """Validate graph-level consistency rules."""

        for graph_name, nodes in graphs.items():
            if not nodes:
                result.add_warning(f"Graph '{graph_name}' has no nodes")
                continue

            # Check for isolated nodes (no incoming or outgoing edges)
            nodes_with_outgoing = set()
            nodes_with_incoming = set()

            for node_name, node_info in nodes.items():
                # Track outgoing edges
                if (
                    node_info.get("edge")
                    or node_info.get("success_next")
                    or node_info.get("failure_next")
                ):
                    nodes_with_outgoing.add(node_name)

                # Track incoming edges
                for other_node, other_info in nodes.items():
                    if other_node == node_name:
                        continue

                    targets = [
                        other_info.get("edge"),
                        other_info.get("success_next"),
                        other_info.get("failure_next"),
                    ]

                    if node_name in targets:
                        nodes_with_incoming.add(node_name)

            # Find potential entry points (nodes with no incoming edges)
            entry_points = set(nodes.keys()) - nodes_with_incoming
            if not entry_points:
                result.add_warning(
                    f"Graph '{graph_name}' has no clear entry point (all nodes have incoming edges)",
                    suggestion="Consider which node should be the starting point",
                )
            elif len(entry_points) > 1:
                entry_list = ", ".join(f"'{ep}'" for ep in sorted(entry_points))
                result.add_info(
                    f"Graph '{graph_name}' has multiple potential entry points: {entry_list}"
                )

            # Find terminal nodes (nodes with no outgoing edges)
            terminal_nodes = set(nodes.keys()) - nodes_with_outgoing
            if not terminal_nodes:
                result.add_warning(
                    f"Graph '{graph_name}' has no terminal nodes (all nodes have outgoing edges)",
                    suggestion="Consider adding terminal nodes or check for cycles",
                )

    def _validate_routing_logic(
        self, df: pd.DataFrame, graphs: Dict[str, Dict], result: ValidationResult
    ) -> None:
        """Validate routing logic and edge references."""

        for graph_name, nodes in graphs.items():
            # Collect all valid node names for this graph
            valid_nodes = set(nodes.keys())

            for node_name, node_info in nodes.items():
                line_number = node_info["line_number"]

                # Check edge targets exist
                edge_targets = [
                    ("Edge", node_info.get("edge")),
                    ("Success_Next", node_info.get("success_next")),
                    ("Failure_Next", node_info.get("failure_next")),
                ]

                for field_name, target in edge_targets:
                    if target:
                        # Check for function references
                        func_ref = self.function_resolution_service.extract_func_ref(
                            target
                        )
                        if func_ref:
                            # For function references, we can't validate the target nodes here
                            # as they're determined at runtime
                            result.add_info(
                                f"Node '{node_name}' uses function routing: {func_ref}",
                                line_number=line_number,
                            )
                            continue

                        # Check if target node exists in the same graph
                        if target not in valid_nodes:
                            result.add_error(
                                f"Node '{node_name}' references non-existent target '{target}' in {field_name}",
                                line_number=line_number,
                                field_name=field_name,
                                value=target,
                                suggestion=f"Valid targets: {', '.join(sorted(valid_nodes))}",
                            )

                # Check for nodes with no outgoing edges (except if they're terminal nodes)
                has_any_edge = any(
                    [
                        node_info.get("edge"),
                        node_info.get("success_next"),
                        node_info.get("failure_next"),
                    ]
                )

                if not has_any_edge:
                    result.add_info(
                        f"Node '{node_name}' has no outgoing edges (terminal node)",
                        line_number=line_number,
                    )

    def _validate_agent_types(self, df: pd.DataFrame, result: ValidationResult) -> None:
        """Validate agent types against the available agent registry."""

        unique_agent_types = set()

        for idx, row in df.iterrows():
            line_number = idx + 2
            agent_type = (
                str(row.get("AgentType", "")).strip()
                if pd.notna(row.get("AgentType"))
                else ""
            )

            if agent_type:
                unique_agent_types.add(agent_type)

                # Check if agent type is available
                agent_class = self.agent_registry.get_agent_class(agent_type)
                if not agent_class:
                    result.add_warning(
                        f"Unknown agent type: '{agent_type}'",
                        line_number=line_number,
                        field_name="AgentType",
                        value=agent_type,
                        suggestion="Check spelling or ensure agent is properly registered/available",
                    )

        # Info about agent types found
        if unique_agent_types:
            result.add_info(
                f"Found {len(unique_agent_types)} unique agent types: {', '.join(sorted(unique_agent_types))}"
            )

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to canonical form using case-insensitive matching.

        Args:
            df: DataFrame with potentially non-standard column names

        Returns:
            DataFrame with normalized column names
        """
        rename_map = {}

        for col in df.columns:
            # Check if this column matches any alias (case-insensitive)
            col_lower = col.lower()
            normalized = False

            for primary_name, aliases in self.column_aliases.items():
                # Check if it's already the primary name (case-insensitive)
                if col_lower == primary_name.lower():
                    if col != primary_name:
                        rename_map[col] = primary_name
                    normalized = True
                    break

                # Check aliases (case-insensitive)
                for alias in aliases:
                    if col_lower == alias.lower():
                        rename_map[col] = primary_name
                        normalized = True
                        break

                if normalized:
                    break

        if rename_map:
            self.logger.info(f"Normalizing column names: {rename_map}")
            df = df.rename(columns=rename_map)

        return df
