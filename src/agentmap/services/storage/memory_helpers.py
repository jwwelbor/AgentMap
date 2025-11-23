"""
Helper functions for memory storage operations.

This module provides utility functions for path-based operations,
query filtering, and document management.
"""

from typing import Any, Dict


class MemoryStorageHelpers:
    """
    Helper class for memory storage operations.

    Provides utilities for:
    - Path-based data access and updates
    - Query filtering
    - Collection name normalization
    - Document ID generation
    """

    @staticmethod
    def normalize_collection_name(collection: str, case_sensitive: bool = True) -> str:
        """
        Normalize collection name based on case sensitivity setting.

        Args:
            collection: Collection name
            case_sensitive: Whether to maintain case sensitivity

        Returns:
            Normalized collection name
        """
        if case_sensitive:
            return collection
        else:
            return collection.lower()

    @staticmethod
    def generate_document_id(collection_data: Dict[str, Any]) -> str:
        """
        Generate a unique document ID for a collection.

        Args:
            collection_data: Collection data dictionary

        Returns:
            Generated document ID
        """
        # Simple incremental ID generation
        max_id = 0
        for doc_id in collection_data.keys():
            if doc_id.isdigit():
                max_id = max(max_id, int(doc_id))

        return str(max_id + 1)

    @staticmethod
    def apply_path(data: Any, path: str) -> Any:
        """
        Extract data from nested structure using dot notation.

        Args:
            data: Data structure to traverse
            path: Dot-notation path (e.g., "user.address.city")

        Returns:
            Value at the specified path or None if not found
        """
        if not path:
            return data

        components = path.split(".")
        current = data

        for component in components:
            if current is None:
                return None

            # Handle arrays with numeric indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            # Handle dictionaries
            elif isinstance(current, dict):
                current = current.get(component)
            else:
                return None

        return current

    @staticmethod
    def update_path(data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specified path.

        Args:
            data: Data structure to modify
            path: Dot-notation path
            value: New value to set

        Returns:
            Updated data structure
        """
        if not path:
            return value

        # Make a copy to avoid modifying original
        if isinstance(data, dict):
            result = data.copy()
        elif isinstance(data, list):
            result = data.copy()
        else:
            # If data is not a container, start with empty dict
            result = {}

        components = path.split(".")
        current = result

        # Navigate to the parent of the target
        for i, component in enumerate(components[:-1]):
            # Handle array indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                # Extend the list if needed
                while len(current) <= index:
                    current.append({})

                if current[index] is None:
                    if i < len(components) - 2 and components[i + 1].isdigit():
                        current[index] = []
                    else:
                        current[index] = {}

                current = current[index]

            # Handle dictionary keys
            else:
                if not isinstance(current, dict):
                    current = {}

                if component not in current:
                    if i < len(components) - 2 and components[i + 1].isdigit():
                        current[component] = []
                    else:
                        current[component] = {}

                current = current[component]

        # Set the value at the final path component
        last_component = components[-1]

        if last_component.isdigit() and isinstance(current, list):
            index = int(last_component)
            while len(current) <= index:
                current.append(None)
            current[index] = value
        elif isinstance(current, dict):
            current[last_component] = value

        return result

    @staticmethod
    def apply_query_filter(
        data: Dict[str, Any], query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply query filtering to collection data.

        Args:
            data: Collection data (document_id -> document)
            query: Query parameters (modified in place)

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
