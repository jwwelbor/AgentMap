"""
CSV Query Filtering module.

Handles query filtering and data transformation operations.
"""

from typing import Any, Dict

import pandas as pd


class CSVQueryFiltering:
    """
    Handles query filtering operations for CSV data.

    Supports:
    - Field-based filtering (exact match and list-based "in" filters)
    - Sorting (ascending/descending)
    - Pagination (offset and limit)
    """

    @staticmethod
    def apply_query_filter(df: pd.DataFrame, query: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply query filters to DataFrame.

        Supports:
        - Field filters: exact match or "in" for list values
        - Sorting: sort field with order (asc/desc)
        - Pagination: offset and limit

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
