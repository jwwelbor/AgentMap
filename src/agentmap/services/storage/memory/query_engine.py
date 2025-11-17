"""
Query Engine for AgentMap Memory Storage.

This module provides query filtering, sorting, and pagination functionality
for in-memory document collections.
"""

from typing import Any, Dict


class QueryEngine:
    """
    Query filtering and document management for memory storage.

    Supports field-based filtering, sorting, and pagination of document collections.
    """

    @staticmethod
    def apply_query_filter(
        data: Dict[str, Any], query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply query filtering to collection data.

        Args:
            data: Collection data (document_id -> document)
            query: Query parameters

        Returns:
            Filtered data matching query criteria
        """
        if not query:
            return data

        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        sort_field = query.pop("sort", None)
        sort_order = query.pop("order", "asc").lower()

        # Apply field filtering
        filtered_data = {}
        for doc_id, doc_data in data.items():
            if not isinstance(doc_data, dict):
                continue

            matches = True
            for field, value in query.items():
                if doc_data.get(field) != value:
                    matches = False
                    break

            if matches:
                filtered_data[doc_id] = doc_data

        # Convert to list for sorting and pagination
        items = list(filtered_data.items())

        # Apply sorting
        if sort_field:
            reverse = sort_order == "desc"
            items.sort(
                key=lambda x: x[1].get(sort_field) if isinstance(x[1], dict) else None,
                reverse=reverse,
            )

        # Apply pagination
        if offset and isinstance(offset, int) and offset > 0:
            items = items[offset:]

        if limit and isinstance(limit, int) and limit > 0:
            items = items[:limit]

        # Convert back to dict
        return dict(items)

    @staticmethod
    def count_matching_documents(
        data: Dict[str, Any], query: Dict[str, Any]
    ) -> int:
        """
        Count documents matching a query.

        Args:
            data: Collection data (document_id -> document)
            query: Query parameters

        Returns:
            Count of matching documents
        """
        if not query:
            return len(data)

        # Make a copy to avoid modifying the original query
        query_copy = query.copy()
        filtered_data = QueryEngine.apply_query_filter(data, query_copy)
        return len(filtered_data)
