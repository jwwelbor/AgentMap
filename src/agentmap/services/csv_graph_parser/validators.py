"""
CSV validation logic for graph parsing.

Provides validation functionality for CSV structure and row content,
generating detailed validation results with errors and warnings.
"""

from pathlib import Path
from typing import TYPE_CHECKING

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
