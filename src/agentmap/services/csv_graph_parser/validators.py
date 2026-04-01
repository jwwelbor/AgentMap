"""
CSV validation logic for graph parsing.

Provides validation functionality for CSV structure and row content,
generating detailed validation results with errors and warnings.
"""

from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set

import pandas as pd

from agentmap.models.validation.validation_models import ValidationResult
from agentmap.services.csv_graph_parser.column_config import CSVColumnConfig

if TYPE_CHECKING:
    from agentmap.services.logging_service import LoggingService


class CSVStructureValidator:
    """
    Validator for CSV structure and content.

    Handles validation of CSV files for graph definitions,
    checking structure, required columns, and row content.
    """

    def __init__(self, column_config: CSVColumnConfig, logger: "LoggingService"):
        """
        Initialize validator with column configuration and logger.

        Args:
            column_config: Column configuration for validation rules
            logger: Logger instance for logging validation messages
        """
        self.column_config = column_config
        self.logger = logger

    def validate_csv_structure(self, df: pd.DataFrame, csv_path: Path) -> None:
        """
        Validate CSV structure and raise errors for critical issues.

        Args:
            df: Pandas DataFrame to validate
            csv_path: Path for error messages

        Raises:
            ValueError: If structure is invalid
        """
        # Check if DataFrame is empty
        if df.empty:
            raise ValueError(f"CSV file contains no data rows: {csv_path}")

        # Check for required columns
        missing_required = self.column_config.required_columns - set(df.columns)
        if missing_required:
            raise ValueError(
                f"Missing required columns in {csv_path}: {missing_required}. "
                f"Required columns: {self.column_config.required_columns}"
            )

        # Check for completely empty required columns
        for col in self.column_config.required_columns:
            if col in df.columns and df[col].isna().all():
                raise ValueError(
                    f"Required column '{col}' is completely empty in {csv_path}"
                )

        # Log warnings for unexpected columns
        unexpected_columns = set(df.columns) - self.column_config.all_columns
        if unexpected_columns:
            self.logger.warning(
                f"[CSVGraphParserService] Unexpected columns in {csv_path}: {unexpected_columns}. "
                f"Expected columns: {self.column_config.all_columns}"
            )

        self.logger.debug(
            f"[CSVGraphParserService] CSV structure valid: {len(df)} rows, {len(df.columns)} columns"
        )

    def validate_dataframe_structure(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """
        Validate DataFrame structure for ValidationResult.

        Args:
            df: DataFrame to validate
            result: ValidationResult to populate with findings
        """
        # Check if DataFrame is empty
        if df.empty:
            result.add_error("CSV file contains no data rows")
            return

        # Check for required columns
        missing_required = self.column_config.required_columns - set(df.columns)
        if missing_required:
            for col in missing_required:
                result.add_error(f"Required column missing: '{col}'")

        # Check for unexpected columns
        unexpected_columns = set(df.columns) - self.column_config.all_columns
        if unexpected_columns:
            for col in unexpected_columns:
                result.add_warning(
                    f"Unexpected column found: '{col}'",
                    suggestion="Check for typos or remove if not needed",
                )

        # Check for completely empty required columns
        for col in self.column_config.required_columns:
            if col in df.columns and df[col].isna().all():
                result.add_error(f"Required column '{col}' is completely empty")

        # Info about data
        result.add_info(f"CSV contains {len(df)} rows and {len(df.columns)} columns")

    def validate_dataframe_rows(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """
        Validate DataFrame rows for ValidationResult.

        Args:
            df: DataFrame to validate
            result: ValidationResult to populate with findings
        """
        from pydantic import ValidationError as PydanticValidationError

        from agentmap.models.validation.csv_row_model import CSVRowModel

        for idx, row in df.iterrows():
            line_number = int(idx) + 2  # +1 for 0-indexing, +1 for header row

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
                        field=str(field) if field else None,
                        value=str(value) if value is not None else None,
                    )
            except Exception as e:
                result.add_error(
                    f"Unexpected error validating row: {e}", line_number=line_number
                )

    def validate_graph_semantics(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """
        Validate graph-level semantics after all rows are parsed.

        Checks for:
        - Edge targets referencing non-existent nodes
        - Duplicate node names within a graph
        - Orphan nodes (no incoming or outgoing edges)
        - Unrecognized agent types (warnings only)

        Args:
            df: DataFrame to validate
            result: ValidationResult to populate with findings
        """
        self._validate_edge_targets(df, result)
        self._validate_duplicate_nodes(df, result)
        self._validate_orphan_nodes(df, result)
        self._validate_agent_types(df, result)

    def _validate_edge_targets(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """Validate that edge targets reference existing nodes within the same graph."""
        edge_columns = ["Edge", "Success_Next", "Failure_Next"]

        # Build per-graph node sets
        graph_nodes: Dict[str, Set[str]] = defaultdict(set)
        for _, row in df.iterrows():
            graph_name = str(row.get("GraphName", "")).strip()
            node_name = str(row.get("Node", "")).strip()
            if graph_name and node_name:
                graph_nodes[graph_name].add(node_name)

        # Validate edge targets
        for idx, row in df.iterrows():
            line_number = int(idx) + 2
            graph_name = str(row.get("GraphName", "")).strip()
            if not graph_name:
                continue

            valid_nodes = graph_nodes.get(graph_name, set())

            for col in edge_columns:
                value = row.get(col)
                if pd.isna(value) or not str(value).strip():
                    continue

                raw = str(value).strip()
                # Parse pipe-separated targets
                targets = [t.strip() for t in raw.split("|") if t.strip()]

                for target in targets:
                    if target not in valid_nodes:
                        suggestion = None
                        close = get_close_matches(target, list(valid_nodes), n=1, cutoff=0.6)
                        if close:
                            suggestion = f"Did you mean '{close[0]}'?"
                        result.add_error(
                            message=f"Edge target '{target}' in column '{col}' does not match any node in graph '{graph_name}'",
                            line_number=line_number,
                            field_name=col,
                            value=target,
                            suggestion=suggestion,
                        )

    def _validate_duplicate_nodes(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """Validate that node names are unique within each graph."""
        graph_nodes: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))

        for idx, row in df.iterrows():
            line_number = int(idx) + 2
            graph_name = str(row.get("GraphName", "")).strip()
            node_name = str(row.get("Node", "")).strip()
            if graph_name and node_name:
                graph_nodes[graph_name][node_name].append(line_number)

        for graph_name, nodes in graph_nodes.items():
            for node_name, lines in nodes.items():
                if len(lines) > 1:
                    result.add_error(
                        message=f"Duplicate node name '{node_name}' in graph '{graph_name}' (lines {', '.join(str(l) for l in lines)})",
                        line_number=lines[1],
                        field_name="Node",
                        value=node_name,
                        suggestion="Each node must have a unique name within its graph",
                    )

    def _validate_orphan_nodes(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """Warn about nodes with no incoming or outgoing edges (potential orphans)."""
        edge_columns = ["Edge", "Success_Next", "Failure_Next"]

        # Build per-graph analysis
        graph_nodes: Dict[str, Set[str]] = defaultdict(set)
        graph_targets: Dict[str, Set[str]] = defaultdict(set)  # nodes referenced as targets
        graph_sources: Dict[str, Set[str]] = defaultdict(set)  # nodes that have outgoing edges

        for _, row in df.iterrows():
            graph_name = str(row.get("GraphName", "")).strip()
            node_name = str(row.get("Node", "")).strip()
            if not graph_name or not node_name:
                continue

            graph_nodes[graph_name].add(node_name)

            for col in edge_columns:
                value = row.get(col)
                if pd.isna(value) or not str(value).strip():
                    continue
                raw = str(value).strip()
                targets = [t.strip() for t in raw.split("|") if t.strip()]
                if targets:
                    graph_sources[graph_name].add(node_name)
                    for target in targets:
                        graph_targets[graph_name].add(target)

        for graph_name, nodes in graph_nodes.items():
            targets = graph_targets.get(graph_name, set())
            sources = graph_sources.get(graph_name, set())

            for node in nodes:
                has_incoming = node in targets
                has_outgoing = node in sources

                if not has_incoming and not has_outgoing and len(nodes) > 1:
                    result.add_warning(
                        message=f"Node '{node}' in graph '{graph_name}' has no incoming or outgoing edges (isolated node)",
                        suggestion="Add edges to connect this node or remove it if unused",
                    )

    def _validate_agent_types(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """Warn about unrecognized agent types with suggestions for likely typos."""
        try:
            from agentmap.builtin_definition_constants import BuiltinDefinitionConstants
            known_types = set(BuiltinDefinitionConstants.AGENTS.keys())
        except ImportError:
            return  # Skip if constants not available

        for idx, row in df.iterrows():
            line_number = int(idx) + 2
            agent_type = row.get("AgentType")
            if pd.isna(agent_type) or not str(agent_type).strip():
                continue

            agent_type_str = str(agent_type).strip().lower()

            if agent_type_str not in known_types:
                suggestion = None
                close = get_close_matches(agent_type_str, list(known_types), n=1, cutoff=0.6)
                if close:
                    suggestion = f"Did you mean '{close[0]}'?"
                else:
                    suggestion = "This may be a custom agent type. Ensure it is properly registered."

                result.add_warning(
                    message=f"Unrecognized agent type '{agent_type_str}'",
                    line_number=line_number,
                    field_name="AgentType",
                    value=agent_type_str,
                    suggestion=suggestion,
                )
