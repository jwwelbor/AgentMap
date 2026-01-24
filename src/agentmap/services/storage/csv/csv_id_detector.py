"""
CSV ID Detector - Smart ID column detection logic.

This module provides intelligent detection of ID columns in CSV files,
supporting various naming conventions and patterns.
"""

from typing import Optional

import pandas as pd


class CSVIdDetector:
    """
    Handles smart ID column detection for CSV files.

    Responsibilities:
    - Detecting ID columns using multiple strategies
    - Supporting various naming conventions (id, user_id, id_user, etc.)
    - Providing fallback mechanisms
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
        ends_with_id_candidates = []
        starts_with_id_candidates = []

        for col in columns:
            col_lower = col.lower()
            if col_lower == "id":
                return col  # Immediate return for exact match
            if col_lower.endswith("_id"):
                ends_with_id_candidates.append(col)
            if col_lower.startswith("id_"):
                starts_with_id_candidates.append(col)

        # If we have candidates, prioritize them
        if ends_with_id_candidates:
            # If multiple, prefer first column, then alphabetical
            return min(
                ends_with_id_candidates, key=lambda x: (columns.index(x), x.lower())
            )

        if starts_with_id_candidates:
            return min(
                starts_with_id_candidates, key=lambda x: (columns.index(x), x.lower())
            )

        # No ID column found
        return None
