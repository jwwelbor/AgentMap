"""
CSV ID Detection module.

Handles smart ID column detection for CSV files.
"""

from typing import Optional

import pandas as pd


class CSVIdDetection:
    """
    Handles ID column detection logic for CSV files.

    Implements smart detection with priority:
    1. Exact match: "id" (case insensitive)
    2. Ends with "_id": user_id, customer_id, etc.
    3. Starts with "id_": id_user, etc.
    4. If multiple candidates, prefer "id" > first column > alphabetical
    """

    @staticmethod
    def detect_id_column(df: pd.DataFrame) -> Optional[str]:
        """
        Detect the ID column using smart detection logic.

        Priority:
        1. Exact match: "id" (case insensitive)
        2. Ends with "_id": user_id, customer_id, etc.
        3. Starts with "id_": id_user, etc.
        4. If multiple candidates, prefer "id" > first column > alphabetical

        Args:
            df: DataFrame to analyze

        Returns:
            Column name to use as ID, or None if no suitable column found
        """
        if df.empty or len(df.columns) == 0:
            return None

        columns = df.columns.tolist()
        candidates = []

        # Check for exact "id" match (case insensitive)
        for col in columns:
            if col.lower() == "id":
                return col  # Immediate return for exact match

        # Check for columns ending with "_id"
        for col in columns:
            if col.lower().endswith("_id"):
                candidates.append((col, "ends_with_id"))

        # Check for columns starting with "id_"
        for col in columns:
            if col.lower().startswith("id_"):
                candidates.append((col, "starts_with_id"))

        # If we have candidates, prioritize them
        if candidates:
            # Prefer ends_with_id over starts_with_id
            ends_with_id = [col for col, type_ in candidates if type_ == "ends_with_id"]
            if ends_with_id:
                # If multiple, prefer first column, then alphabetical
                return min(ends_with_id, key=lambda x: (columns.index(x), x.lower()))

            starts_with_id = [
                col for col, type_ in candidates if type_ == "starts_with_id"
            ]
            if starts_with_id:
                return min(starts_with_id, key=lambda x: (columns.index(x), x.lower()))

        # No ID column found
        return None

    @staticmethod
    def convert_document_id_to_column_type(
        document_id: str, df: pd.DataFrame, id_column: str
    ):
        """
        Convert document_id to match the ID column's data type.

        Args:
            document_id: Document ID to convert
            df: DataFrame containing the ID column
            id_column: Name of the ID column

        Returns:
            Converted document ID value

        Raises:
            ValueError: If conversion fails
        """
        if pd.api.types.is_numeric_dtype(df[id_column]):
            # Convert to numeric if the column is numeric
            return pd.to_numeric(document_id)
        else:
            # Keep as string for text columns
            return str(document_id)
