"""
CSVGraphParserService for AgentMap.

Service for parsing CSV files into GraphSpec domain models following clean
architecture principles. This service handles pure CSV parsing logic
extracted from GraphBuilderService and leverages proven patterns from
CSVValidationService.
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd

from agentmap.models.graph_spec import GraphSpec, NodeSpec
from agentmap.models.node import Node
from agentmap.models.validation.validation_models import ValidationResult
from agentmap.services.csv_graph_parser.column_config import CSVColumnConfig
from agentmap.services.csv_graph_parser.converters import NodeSpecConverter
from agentmap.services.csv_graph_parser.parsers import CSVRowParser
from agentmap.services.csv_graph_parser.validators import CSVStructureValidator
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

        # Initialize components
        self.column_config = CSVColumnConfig()
        self.validator = CSVStructureValidator(self.column_config, self.logger)
        self.parser = CSVRowParser(self.column_config, self.logger)
        self.converter = NodeSpecConverter(self.logger)

        # Expose column configuration for backwards compatibility
        self.required_columns = self.column_config.required_columns
        self.optional_columns = self.column_config.optional_columns
        self.all_columns = self.column_config.all_columns
        self.column_aliases = self.column_config.column_aliases

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
            # Use pandas for robust CSV reading
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
            # Load CSV with pandas
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

    # Delegate methods to components

    def _validate_csv_structure(self, df: pd.DataFrame, csv_path: Path) -> None:
        """Delegate to validator component."""
        self.validator.validate_csv_structure(df, csv_path)

    def _parse_dataframe_to_spec(self, df: pd.DataFrame, csv_path: Path) -> GraphSpec:
        """Delegate to parser component."""
        return self.parser.parse_dataframe_to_spec(df, csv_path)

    def _parse_edge_targets(self, edge_value: str):
        """Delegate to parser component."""
        return self.parser.parse_edge_targets(edge_value)

    def _parse_row_to_node_spec(self, row, line_number: int):
        """Delegate to parser component."""
        return self.parser.parse_row_to_node_spec(row, line_number)

    def _safe_get_field(self, row, field_name: str, default: str = "") -> str:
        """Delegate to parser component."""
        return self.parser._safe_get_field(row, field_name, default)

    def _validate_dataframe_structure(self, df: pd.DataFrame, result: ValidationResult) -> None:
        """Delegate to validator component."""
        self.validator.validate_dataframe_structure(df, result)

    def _validate_dataframe_rows(self, df: pd.DataFrame, result: ValidationResult) -> None:
        """Delegate to validator component."""
        self.validator.validate_dataframe_rows(df, result)

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Delegate to parser component."""
        return self.parser.normalize_columns(df)

    def _convert_node_specs_to_nodes(self, node_specs: List[NodeSpec]) -> Dict[str, Node]:
        """Delegate to converter component."""
        return self.converter.convert_node_specs_to_nodes(node_specs)
