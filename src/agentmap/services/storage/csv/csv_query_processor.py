"""
CSV Query Processor - Query filtering and processing logic.

This module provides query processing capabilities for CSV data,
including filtering, sorting, and pagination.
"""

from typing import Any, Dict

import pandas as pd


class CSVQueryProcessor:
    """
    Handles query filtering and processing for CSV data.

    Responsibilities:
    - Applying field-based filters
    - Handling sorting operations
    - Managing pagination (offset/limit)
    - Supporting complex query combinations
    """

    @staticmethod
    def apply_query_filter(df: pd.DataFrame, query: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply query filters to DataFrame.

        Supports:
        - Field-based exact match filters
        - List-based "in" filters
        - Sorting (sort field + order)
        - Pagination (offset + limit)

        Args:
            df: DataFrame to filter
            query: Query parameters

        Returns:
            Filtered DataFrame
        """
        # Make a copy to avoid modifying original
        filtered_df = df.copy()

        # Apply field-based filters
        for field, value in query.items():
            if field in ["limit", "offset", "sort", "order"]:
                continue  # Skip special parameters

            if field in filtered_df.columns:
                if isinstance(value, list):
                    # Handle list values as "in" filter
                    filtered_df = filtered_df[filtered_df[field].isin(value)]
                else:
                    # Exact match filter
                    filtered_df = filtered_df[filtered_df[field] == value]

        # Apply sorting
        sort_field = query.get("sort")
        if sort_field and sort_field in filtered_df.columns:
            ascending = query.get("order", "asc").lower() != "desc"
            filtered_df = filtered_df.sort_values(by=sort_field, ascending=ascending)

        # Apply pagination
        offset = query.get("offset", 0)
        limit = query.get("limit")

        if offset and isinstance(offset, int) and offset > 0:
            filtered_df = filtered_df.iloc[offset:]

        if limit and isinstance(limit, int) and limit > 0:
            filtered_df = filtered_df.head(limit)

        return filtered_df
