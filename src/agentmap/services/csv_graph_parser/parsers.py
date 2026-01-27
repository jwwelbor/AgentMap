"""
CSV row and dataframe parsing logic.

Provides parsing functionality to convert CSV data into GraphSpec and NodeSpec
domain models, handling edge targets, input fields, and other structured data.
"""

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

import pandas as pd

from agentmap.models.graph_spec import GraphSpec, NodeSpec
from agentmap.services.csv_graph_parser.column_config import CSVColumnConfig

if TYPE_CHECKING:
    from agentmap.services.logging_service import LoggingService


class CSVRowParser:
    """
    Parser for CSV rows and DataFrames.

    Handles parsing of CSV data into domain models, including
    column normalization, edge target parsing, and field extraction.
    """

    def __init__(self, column_config: CSVColumnConfig, logger: "LoggingService"):
        """
        Initialize parser with column configuration and logger.

        Args:
            column_config: Column configuration for parsing rules
            logger: Logger instance for logging parsing messages
        """
        self.column_config = column_config
        self.logger = logger

    def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
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

            for primary_name, aliases in self.column_config.column_aliases.items():
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
            self.logger.trace(
                f"[CSVGraphParserService] Normalizing column names: {rename_map}"
            )
            df = df.rename(columns=rename_map)

        return df

    def parse_dataframe_to_spec(self, df: pd.DataFrame, csv_path: Path) -> GraphSpec:
        """
        Parse pandas DataFrame to GraphSpec domain model.

        Args:
            df: Pandas DataFrame with validated structure
            csv_path: Path for metadata

        Returns:
            GraphSpec with all parsed data
        """
        graph_spec = GraphSpec(file_path=str(csv_path), total_rows=len(df))

        for idx, row in df.iterrows():
            line_number = int(idx) + 2  # +1 for 0-indexing, +1 for header row

            try:
                node_spec = self.parse_row_to_node_spec(row, line_number)
                if node_spec:  # Only add valid node specs
                    graph_spec.add_node_spec(node_spec)

            except Exception as e:
                self.logger.warning(
                    f"[CSVGraphParserService] Error parsing row {line_number}: {e}. Skipping row."
                )
                continue

        return graph_spec

    def parse_edge_targets(self, edge_value: str) -> Optional[Union[str, List[str]]]:
        """
        Parse edge target(s) from CSV field value.

        Detects pipe-separated targets for parallel execution and returns
        appropriate type (str for single, list for multiple).

        Args:
            edge_value: Raw edge value from CSV field

        Returns:
            - None if empty/whitespace
            - str if single target
            - list[str] if multiple pipe-separated targets

        Examples:
            parse_edge_targets("")                -> None
            parse_edge_targets("NextNode")        -> "NextNode"
            parse_edge_targets("A|B|C")           -> ["A", "B", "C"]
            parse_edge_targets("Node | Other")    -> ["Node", "Other"]
        """
        if not edge_value or not edge_value.strip():
            return None

        # Check for pipe delimiter indicating parallel targets
        if "|" in edge_value:
            # Split on pipe and clean each target
            targets = [
                target.strip()
                for target in edge_value.split("|")
                if target.strip()  # Filter out empty strings
            ]

            # Validate targets
            if not targets:
                self.logger.warning(
                    f"Edge value '{edge_value}' contains pipes but no valid targets"
                )
                return None

            # Return list for multiple targets (parallel execution)
            if len(targets) > 1:
                self.logger.debug(f"Parsed parallel edge targets: {targets}")
                return targets

            # Single target after splitting (edge case: "NodeA|")
            return targets[0]

        # No pipe delimiter - single target (existing behavior)
        return edge_value.strip()

    def parse_row_to_node_spec(
        self, row: pd.Series, line_number: int
    ) -> Optional[NodeSpec]:
        """
        Parse a single CSV row to NodeSpec.

        Args:
            row: Pandas Series representing CSV row
            line_number: Line number for debugging

        Returns:
            NodeSpec if row is valid, None if should be skipped
        """
        # Extract and clean required fields
        graph_name = self._safe_get_field(row, "GraphName").strip()
        node_name = self._safe_get_field(row, "Node").strip()

        # Skip rows with missing required fields
        if not graph_name:
            self.logger.warning(
                f"[Line {line_number}] Missing GraphName. Skipping row."
            )
            return None

        if not node_name:
            self.logger.warning(
                f"[Line {line_number}] Missing Node name. Skipping row."
            )
            return None

        # Parse optional fields
        agent_type = self._safe_get_field(row, "AgentType").strip() or None
        prompt = self._safe_get_field(row, "Prompt").strip() or None
        description = self._safe_get_field(row, "Description").strip() or None
        context = self._safe_get_field(row, "Context").strip() or None
        output_field = self._safe_get_field(row, "Output_Field").strip() or None

        # Parse input fields (pipe-separated format)
        input_fields_str = self._safe_get_field(row, "Input_Fields").strip()
        input_fields = (
            [field.strip() for field in input_fields_str.split("|") if field.strip()]
            if input_fields_str
            else []
        )

        # Parse output fields (pipe-separated format, same as input_fields)
        output_field_str = self._safe_get_field(row, "Output_Field").strip()
        output_fields = (
            [field.strip() for field in output_field_str.split("|") if field.strip()]
            if output_field_str
            else []
        )
        # For backward compatibility:
        # - If no valid fields after splitting, output_field is None
        # - If exactly one field, output_field is that single field (string)
        # - If multiple fields, output_field preserves the original string format
        if not output_fields:
            output_field = None
        elif len(output_fields) == 1:
            output_field = output_fields[0]
        # else: output_field stays as original (set earlier)

        # Parse edge information - supports parallel targets
        edge = self.parse_edge_targets(self._safe_get_field(row, "Edge"))
        success_next = self.parse_edge_targets(
            self._safe_get_field(row, "Success_Next")
        )
        failure_next = self.parse_edge_targets(
            self._safe_get_field(row, "Failure_Next")
        )

        # Parse tool information
        tool_source = self._safe_get_field(row, "Tool_Source").strip() or None
        available_tools_str = self._safe_get_field(row, "Available_Tools").strip()
        available_tools = (
            [tool.strip() for tool in available_tools_str.split("|") if tool.strip()]
            if available_tools_str
            else None
        )

        node_spec = NodeSpec(
            name=node_name,
            graph_name=graph_name,
            agent_type=agent_type,
            prompt=prompt,
            description=description,
            context=context,
            input_fields=input_fields,
            output_field=output_field,
            output_fields=output_fields,
            edge=edge,
            success_next=success_next,
            failure_next=failure_next,
            tool_source=tool_source,
            available_tools=available_tools,
            line_number=line_number,
        )

        self.logger.debug(
            f"[Line {line_number}] Parsed NodeSpec: Graph='{graph_name}', "
            f"Node='{node_name}', AgentType='{agent_type}'"
        )

        return node_spec

    def _safe_get_field(
        self, row: pd.Series, field_name: str, default: str = ""
    ) -> str:
        """
        Safely extract field value from pandas Series, handling NaN values.

        Args:
            row: Pandas Series representing CSV row
            field_name: Name of the field to extract
            default: Default value if field is missing or NaN

        Returns:
            String value, never None
        """
        value = row.get(field_name, default)

        # Handle pandas NaN values
        if pd.isna(value):
            return default

        # Convert to string and handle None
        str_value = str(value) if value is not None else default
        return str_value if str_value != "nan" else default
