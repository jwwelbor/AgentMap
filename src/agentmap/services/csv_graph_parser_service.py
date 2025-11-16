"""
CSVGraphParserService for AgentMap.

Service for parsing CSV files into GraphSpec domain models following clean
architecture principles. This service handles pure CSV parsing logic
extracted from GraphBuilderService and leverages proven patterns from
CSVValidationService.
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from agentmap.models.graph_spec import GraphSpec, NodeSpec
from agentmap.models.node import Node
from agentmap.models.validation.validation_models import ValidationResult
from agentmap.services.logging_service import LoggingService


class CSVGraphParserService:
    """
    Service for parsing CSV files into GraphSpec domain models.

    This service extracts pure CSV parsing logic from GraphBuilderService,
    leveraging proven patterns from CSVValidationService for robust CSV handling.
    Returns clean GraphSpec domain models as intermediate format.
    """

    def __init__(self, logging_service: LoggingService):
        """Initialize service with dependency injection."""
        self.logger = logging_service.get_class_logger(self)

        # Define expected CSV structure (from existing validation service)
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
            "Tool_Source",
            "Available_Tools",
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
            "Tool_Source": ["tool_source", "ToolSource", "ToolFile", "ToolModule"],
            "Available_Tools": [
                "available_tools",
                "AvailableTools",
                "Tools",
                "ToolList",
            ],
        }

        self.logger.info("[CSVGraphParserService] Initialized")

    def parse_csv_to_graph_spec(self, csv_path: Path) -> GraphSpec:
        """
        Parse CSV file to GraphSpec domain model.

        Args:
            csv_path: Path to CSV file containing graph definitions

        Returns:
            GraphSpec containing all parsed graph and node specifications

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV structure is invalid
        """
        csv_path = Path(csv_path)
        self.logger.info(f"[CSVGraphParserService] Parsing CSV: {csv_path}")

        if not csv_path.exists():
            self.logger.error(f"[CSVGraphParserService] CSV file not found: {csv_path}")
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        if not csv_path.is_file():
            self.logger.error(f"[CSVGraphParserService] Path is not a file: {csv_path}")
            raise ValueError(f"Path is not a file: {csv_path}")

        try:
            # Use pandas for robust CSV reading (pattern from CSVValidationService)
            df = pd.read_csv(csv_path)

            # Normalize column names to canonical form
            df = self._normalize_columns(df)

            # Validate basic structure
            self._validate_csv_structure(df, csv_path)

            # Parse rows to GraphSpec
            graph_spec = self._parse_dataframe_to_spec(df, csv_path)

            self.logger.info(
                f"[CSVGraphParserService] Successfully parsed {graph_spec.total_rows} rows "
                f"into {len(graph_spec.graphs)} graph(s): {list(graph_spec.graphs.keys())}"
            )

            return graph_spec

        except pd.errors.EmptyDataError:
            error_msg = f"CSV file is empty: {csv_path}"
            self.logger.error(f"[CSVGraphParserService] {error_msg}")
            raise ValueError(error_msg)
        except pd.errors.ParserError as e:
            error_msg = f"CSV parsing error in {csv_path}: {e}"
            self.logger.error(f"[CSVGraphParserService] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error parsing CSV {csv_path}: {e}"
            self.logger.error(f"[CSVGraphParserService] {error_msg}")
            raise ValueError(error_msg)

    def validate_csv_structure(self, csv_path: Path) -> ValidationResult:
        """
        Pre-validate CSV structure and return detailed validation result.

        Args:
            csv_path: Path to CSV file to validate

        Returns:
            ValidationResult with validation details
        """
        from agentmap.models.validation.validation_models import ValidationResult

        result = ValidationResult(
            file_path=str(csv_path), file_type="csv", is_valid=True
        )

        self.logger.debug(
            f"[CSVGraphParserService] Validating CSV structure: {csv_path}"
        )

        # Check file existence
        if not csv_path.exists():
            result.add_error(f"CSV file does not exist: {csv_path}")
            return result

        if not csv_path.is_file():
            result.add_error(f"Path is not a file: {csv_path}")
            return result

        try:
            # Load CSV with pandas (proven pattern)
            df = pd.read_csv(csv_path)

            # Normalize column names to canonical form
            df = self._normalize_columns(df)

            # Validate structure
            self._validate_dataframe_structure(df, result)

            # Validate row content
            self._validate_dataframe_rows(df, result)

        except pd.errors.EmptyDataError:
            result.add_error("CSV file is empty")
        except pd.errors.ParserError as e:
            result.add_error(f"CSV parsing error: {e}")
        except Exception as e:
            result.add_error(f"Unexpected error during validation: {e}")

        return result

    def _validate_csv_structure(self, df: pd.DataFrame, csv_path: Path) -> None:
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
        missing_required = self.required_columns - set(df.columns)
        if missing_required:
            raise ValueError(
                f"Missing required columns in {csv_path}: {missing_required}. "
                f"Required columns: {self.required_columns}"
            )

        # Check for completely empty required columns
        for col in self.required_columns:
            if col in df.columns and df[col].isna().all():
                raise ValueError(
                    f"Required column '{col}' is completely empty in {csv_path}"
                )

        # Log warnings for unexpected columns
        unexpected_columns = set(df.columns) - self.all_columns
        if unexpected_columns:
            self.logger.warning(
                f"[CSVGraphParserService] Unexpected columns in {csv_path}: {unexpected_columns}. "
                f"Expected columns: {self.all_columns}"
            )

        self.logger.debug(
            f"[CSVGraphParserService] CSV structure valid: {len(df)} rows, {len(df.columns)} columns"
        )

    def _parse_dataframe_to_spec(self, df: pd.DataFrame, csv_path: Path) -> GraphSpec:
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
                node_spec = self._parse_row_to_node_spec(row, line_number)
                if node_spec:  # Only add valid node specs
                    graph_spec.add_node_spec(node_spec)

            except Exception as e:
                self.logger.warning(
                    f"[CSVGraphParserService] Error parsing row {line_number}: {e}. Skipping row."
                )
                continue

        return graph_spec

    def _parse_edge_targets(self, edge_value: str) -> Optional[Union[str, List[str]]]:
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
            _parse_edge_targets("")                -> None
            _parse_edge_targets("NextNode")        -> "NextNode"
            _parse_edge_targets("A|B|C")           -> ["A", "B", "C"]
            _parse_edge_targets("Node | Other")    -> ["Node", "Other"]
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

    def _parse_row_to_node_spec(
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

        # Parse edge information - NOW supports parallel targets
        edge = self._parse_edge_targets(self._safe_get_field(row, "Edge"))
        success_next = self._parse_edge_targets(
            self._safe_get_field(row, "Success_Next")
        )
        failure_next = self._parse_edge_targets(
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

    def _validate_dataframe_structure(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """Validate DataFrame structure for ValidationResult."""
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

    def _validate_dataframe_rows(
        self, df: pd.DataFrame, result: ValidationResult
    ) -> None:
        """Validate DataFrame rows for ValidationResult."""
        from pydantic import ValidationError as PydanticValidationError

        from agentmap.models.validation.csv_row_model import CSVRowModel

        for idx, row in df.iterrows():
            line_number = int(idx) + 2  # +1 for 0-indexing, +1 for header row

            try:
                # Convert row to dict, handling NaN values (pattern from CSVValidationService)
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
            self.logger.trace(
                f"[CSVGraphParserService] Normalizing column names: {rename_map}"
            )
            df = df.rename(columns=rename_map)

        return df

    def _convert_node_specs_to_nodes(
        self, node_specs: List[NodeSpec]
    ) -> Dict[str, Node]:
        """Convert NodeSpec objects to Node objects.

        Based on the pattern from GraphDefinitionService._create_nodes_from_specs
        but simplified for metadata bundle creation.

        Args:
            node_specs: List of NodeSpec objects from GraphSpec

        Returns:
            Dictionary mapping node names to Node objects
        """
        nodes_dict = {}

        for node_spec in node_specs:
            self.logger.debug(f"Converting NodeSpec to Node: {node_spec.name}")

            # Only create if not already exists (handle duplicate definitions)
            if node_spec.name not in nodes_dict:
                # Convert context string to dict if needed
                context_dict = (
                    {"context": node_spec.context} if node_spec.context else {}
                )

                # Use default agent type if not specified
                agent_type = node_spec.agent_type or "default"

                node = Node(
                    name=node_spec.name,
                    context=context_dict,
                    agent_type=agent_type,
                    inputs=node_spec.input_fields or [],
                    output=node_spec.output_field,
                    prompt=node_spec.prompt,
                    description=node_spec.description,
                    tool_source=node_spec.tool_source,
                    available_tools=node_spec.available_tools,
                )

                # Add edge information
                if node_spec.edge:
                    node.add_edge("default", node_spec.edge)
                elif node_spec.success_next or node_spec.failure_next:
                    if node_spec.success_next:
                        node.add_edge("success", node_spec.success_next)
                    if node_spec.failure_next:
                        node.add_edge("failure", node_spec.failure_next)

                nodes_dict[node_spec.name] = node

                self.logger.debug(
                    f"Created Node: {node_spec.name} with agent_type: {agent_type}, "
                    f"output: {node_spec.output_field}"
                )
            else:
                self.logger.debug(f"Node {node_spec.name} already exists, skipping")

        return nodes_dict
