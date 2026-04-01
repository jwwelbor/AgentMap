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

try:
    from agentmap.builtin_definition_constants import BuiltinDefinitionConstants

    _KNOWN_AGENT_TYPES: Optional[Set[str]] = set(BuiltinDefinitionConstants.AGENTS.keys())
except ImportError:
    _KNOWN_AGENT_TYPES = None

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

        Performs a single pass over the DataFrame to collect all graph structure
        data, then validates edge targets, duplicate nodes, orphan nodes, and
        unrecognized agent types.

        Args:
            df: DataFrame to validate
            result: ValidationResult to populate with findings
        """
        edge_columns = self.column_config.edge_columns

        # --- Single-pass data collection ---
        # Per-graph node sets (for edge target validation)
        graph_nodes: Dict[str, Set[str]] = defaultdict(set)
        # Per-graph node line tracking (for duplicate detection)
        graph_node_lines: Dict[str, Dict[str, List[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # Per-graph edge connectivity (for orphan detection)
        graph_targets: Dict[str, Set[str]] = defaultdict(set)
        graph_sources: Dict[str, Set[str]] = defaultdict(set)
        # Per-row edge data for target validation (line_number, graph, col, targets)
        edge_refs: List[tuple] = []
        # Agent type data for validation (line_number, agent_type_str)
        agent_type_refs: List[tuple] = []

        for idx, row in df.iterrows():
            line_number = int(idx) + 2
            graph_name = str(row.get("GraphName", "")).strip()
            node_name = str(row.get("Node", "")).strip()
            if not graph_name or not node_name:
                continue

            graph_nodes[graph_name].add(node_name)
            graph_node_lines[graph_name][node_name].append(line_number)

            # Collect edge data
            for col in edge_columns:
                targets = self._parse_pipe_field(row, col)
                if targets:
                    graph_sources[graph_name].add(node_name)
                    for target in targets:
                        graph_targets[graph_name].add(target)
                    edge_refs.append((line_number, graph_name, col, targets))

            # Collect agent type data
            agent_type = row.get("AgentType")
            if not pd.isna(agent_type) and str(agent_type).strip():
                agent_type_refs.append((line_number, str(agent_type).strip().lower()))

        # --- Validate collected data ---
        self._check_edge_targets(edge_refs, graph_nodes, result)
        self._check_duplicate_nodes(graph_node_lines, result)
        self._check_orphan_nodes(graph_nodes, graph_targets, graph_sources, result)
        self._check_agent_types(agent_type_refs, result)

    @staticmethod
    def _parse_pipe_field(row, col: str) -> List[str]:
        """Parse a pipe-separated field value into a list of stripped strings."""
        value = row.get(col)
        if pd.isna(value) or not str(value).strip():
            return []
        return [t.strip() for t in str(value).strip().split("|") if t.strip()]

    @staticmethod
    def _suggest_typo(value: str, candidates: Set[str]) -> Optional[str]:
        """Return a 'Did you mean' suggestion if a close match exists."""
        close = get_close_matches(value, list(candidates), n=1, cutoff=0.6)
        return f"Did you mean '{close[0]}'?" if close else None

    def _check_edge_targets(
        self,
        edge_refs: List[tuple],
        graph_nodes: Dict[str, Set[str]],
        result: ValidationResult,
    ) -> None:
        """Validate that edge targets reference existing nodes within the same graph."""
        for line_number, graph_name, col, targets in edge_refs:
            valid_nodes = graph_nodes.get(graph_name, set())
            for target in targets:
                if target not in valid_nodes:
                    result.add_error(
                        message=f"Edge target '{target}' in column '{col}' does not match any node in graph '{graph_name}'",
                        line_number=line_number,
                        field_name=col,
                        value=target,
                        suggestion=self._suggest_typo(target, valid_nodes),
                    )

    @staticmethod
    def _check_duplicate_nodes(
        graph_node_lines: Dict[str, Dict[str, List[int]]],
        result: ValidationResult,
    ) -> None:
        """Validate that node names are unique within each graph."""
        for graph_name, nodes in graph_node_lines.items():
            for node_name, lines in nodes.items():
                if len(lines) > 1:
                    result.add_error(
                        message=f"Duplicate node name '{node_name}' in graph '{graph_name}' (lines {', '.join(str(l) for l in lines)})",
                        line_number=lines[1],
                        field_name="Node",
                        value=node_name,
                        suggestion="Each node must have a unique name within its graph",
                    )

    @staticmethod
    def _check_orphan_nodes(
        graph_nodes: Dict[str, Set[str]],
        graph_targets: Dict[str, Set[str]],
        graph_sources: Dict[str, Set[str]],
        result: ValidationResult,
    ) -> None:
        """Warn about nodes with no incoming or outgoing edges (potential orphans)."""
        for graph_name, nodes in graph_nodes.items():
            if len(nodes) <= 1:
                continue
            targets = graph_targets.get(graph_name, set())
            sources = graph_sources.get(graph_name, set())
            for node in nodes:
                if node not in targets and node not in sources:
                    result.add_warning(
                        message=f"Node '{node}' in graph '{graph_name}' has no incoming or outgoing edges (isolated node)",
                        suggestion="Add edges to connect this node or remove it if unused",
                    )

    @staticmethod
    def _check_agent_types(
        agent_type_refs: List[tuple],
        result: ValidationResult,
    ) -> None:
        """Warn about unrecognized agent types with suggestions for likely typos."""
        if _KNOWN_AGENT_TYPES is None:
            return

        for line_number, agent_type_str in agent_type_refs:
            if agent_type_str not in _KNOWN_AGENT_TYPES:
                suggestion = CSVStructureValidator._suggest_typo(
                    agent_type_str, _KNOWN_AGENT_TYPES
                )
                if not suggestion:
                    suggestion = "This may be a custom agent type. Ensure it is properly registered."
                result.add_warning(
                    message=f"Unrecognized agent type '{agent_type_str}'",
                    line_number=line_number,
                    field_name="AgentType",
                    value=agent_type_str,
                    suggestion=suggestion,
                )
