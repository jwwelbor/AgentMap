"""
CSV Document Operations module.

Handles document-level read, write, and delete operations.
"""

from typing import Any, Dict, Optional

import pandas as pd

from agentmap.services.storage.csv.id_detection import CSVIdDetection


class CSVDocumentOperations:
    """
    Handles document-level operations for CSV storage.

    Provides helper methods for:
    - Document lookup by ID
    - Document updates and inserts
    - Batch operations
    - Document deletion
    """

    # Special column for batch/multi-row operations
    BATCH_COLUMN = "_document_id"

    @staticmethod
    def find_document_by_id(
        df: pd.DataFrame,
        document_id: str,
        id_field: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single document by ID in the DataFrame.

        First checks for batch operations using BATCH_COLUMN.
        Then uses smart ID detection for single-row operations.

        Args:
            df: DataFrame to search
            document_id: Document ID to find
            id_field: Optional custom ID field (overrides auto-detection)

        Returns:
            Document as dict if found, or list of dicts for batch operations, None otherwise
        """
        # Check for batch column (multi-row document_id)
        if CSVDocumentOperations.BATCH_COLUMN in df.columns:
            matching_rows = df[df[CSVDocumentOperations.BATCH_COLUMN] == document_id]
            if len(matching_rows) > 0:
                # Return all rows in the batch (excluding the batch column)
                result_df = matching_rows.drop(columns=[CSVDocumentOperations.BATCH_COLUMN])
                return result_df.to_dict(orient="records")

        # Try smart ID column detection for single row
        id_column = id_field if id_field else CSVIdDetection.detect_id_column(df)

        if id_column is not None:
            # Use detected ID column
            try:
                # Try to convert document_id to match column type
                search_value = CSVIdDetection.convert_document_id_to_column_type(
                    document_id, df, id_column
                )
                matching_rows = df[df[id_column] == search_value]
                if len(matching_rows) > 0:
                    return matching_rows.iloc[0].to_dict()
            except (ValueError, TypeError):
                # Conversion failed, try direct string comparison
                matching_rows = df[df[id_column].astype(str) == str(document_id)]
                if len(matching_rows) > 0:
                    return matching_rows.iloc[0].to_dict()

        # No ID column or ID not found - try row index fallback
        try:
            row_index = int(document_id)
            if 0 <= row_index < len(df):
                return df.iloc[row_index].to_dict()
        except (ValueError, TypeError):
            pass

        return None

    @staticmethod
    def update_or_insert_document(
        existing_df: pd.DataFrame,
        new_data_df: pd.DataFrame,
        document_id: str,
        id_field: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Update existing document or insert new one.

        Args:
            existing_df: Existing DataFrame
            new_data_df: New data to insert/update (single row)
            document_id: Document ID
            id_field: Optional custom ID field

        Returns:
            Updated DataFrame
        """
        id_column = id_field if id_field else CSVIdDetection.detect_id_column(existing_df)

        if id_column is None:
            # No ID column detected - create one
            id_column = "id"
            new_data_df[id_column] = document_id
            if id_column not in existing_df.columns:
                existing_df[id_column] = None

        # Ensure the document_id is in the new data
        new_data_df[id_column] = document_id

        # Try to update existing row
        if id_column in existing_df.columns:
            mask = existing_df[id_column].astype(str) == str(document_id)
            if mask.any():
                # Update existing row
                for col in new_data_df.columns:
                    if col in existing_df.columns:
                        existing_df.loc[mask, col] = new_data_df[col].iloc[0]
                return existing_df
            else:
                # Append new row
                return pd.concat([existing_df, new_data_df], ignore_index=True)
        else:
            # Append new row
            return pd.concat([existing_df, new_data_df], ignore_index=True)

    @staticmethod
    def update_or_insert_batch(
        existing_df: pd.DataFrame,
        new_data_df: pd.DataFrame,
        document_id: str
    ) -> pd.DataFrame:
        """
        Update or insert a batch of rows identified by document_id.

        Uses the BATCH_COLUMN to track batches.

        Args:
            existing_df: Existing DataFrame
            new_data_df: New batch data
            document_id: Batch identifier

        Returns:
            Updated DataFrame
        """
        # Add batch column to new data
        new_data_df[CSVDocumentOperations.BATCH_COLUMN] = document_id

        if CSVDocumentOperations.BATCH_COLUMN in existing_df.columns:
            # Remove existing rows with same document_id
            filtered_df = existing_df[
                existing_df[CSVDocumentOperations.BATCH_COLUMN] != document_id
            ]
            # Append new batch
            return pd.concat([filtered_df, new_data_df], ignore_index=True)
        else:
            # No batch column in existing data, just append
            return pd.concat([existing_df, new_data_df], ignore_index=True)

    @staticmethod
    def bulk_update_documents(
        existing_df: pd.DataFrame,
        new_data_df: pd.DataFrame,
        id_field: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Bulk update documents based on ID column.

        Args:
            existing_df: Existing DataFrame
            new_data_df: New data to merge
            id_field: Optional custom ID field

        Returns:
            Updated DataFrame
        """
        id_column = id_field if id_field else CSVIdDetection.detect_id_column(existing_df)

        if id_column and id_column in new_data_df.columns:
            # Merge DataFrames on ID column
            updated_df = existing_df.copy()
            for _, row in new_data_df.iterrows():
                row_id = row[id_column]
                mask = updated_df[id_column] == row_id
                if mask.any():
                    # Update existing row
                    for col in row.index:
                        if col in updated_df.columns:
                            updated_df.loc[mask, col] = row[col]
                else:
                    # Append new row
                    updated_df = pd.concat(
                        [updated_df, row.to_frame().T],
                        ignore_index=True,
                    )
            return updated_df
        else:
            # No ID column, just append
            return pd.concat([existing_df, new_data_df], ignore_index=True)

    @staticmethod
    def delete_document_by_id(
        df: pd.DataFrame,
        document_id: str,
        id_field: Optional[str] = None
    ) -> tuple[pd.DataFrame, int, Optional[str]]:
        """
        Delete document(s) by ID.

        First checks for batch operations using BATCH_COLUMN.
        Then uses smart ID detection for single-row operations.

        Args:
            df: DataFrame to delete from
            document_id: Document ID to delete
            id_field: Optional custom ID field

        Returns:
            Tuple of (filtered_df, deleted_count, id_column_used)
        """
        initial_count = len(df)
        id_column = None

        # First check if there's a batch column (multi-row document_id)
        if CSVDocumentOperations.BATCH_COLUMN in df.columns:
            # Delete all rows with matching document_id
            df_filtered = df[df[CSVDocumentOperations.BATCH_COLUMN] != document_id]
            id_column = CSVDocumentOperations.BATCH_COLUMN
        else:
            # Try smart ID column detection for single row
            id_column = id_field if id_field else CSVIdDetection.detect_id_column(df)

            if id_column is not None:
                # Delete using detected ID column
                try:
                    # Try to convert document_id to match column type
                    search_value = CSVIdDetection.convert_document_id_to_column_type(
                        document_id, df, id_column
                    )
                    df_filtered = df[df[id_column] != search_value]
                except (ValueError, TypeError):
                    # Conversion failed, try direct string comparison
                    df_filtered = df[df[id_column].astype(str) != str(document_id)]
            else:
                # No ID column found - return empty result
                return df, 0, None

        deleted_count = initial_count - len(df_filtered)
        return df_filtered, deleted_count, id_column

    @staticmethod
    def document_exists(
        df: pd.DataFrame,
        document_id: str,
        id_field: Optional[str] = None
    ) -> bool:
        """
        Check if document exists in DataFrame.

        Args:
            df: DataFrame to search
            document_id: Document ID to check
            id_field: Optional custom ID field

        Returns:
            True if document exists, False otherwise
        """
        # First check if there's a batch column (multi-row document_id)
        if CSVDocumentOperations.BATCH_COLUMN in df.columns:
            return document_id in df[CSVDocumentOperations.BATCH_COLUMN].values

        # Try smart ID column detection for single row
        id_column = id_field if id_field else CSVIdDetection.detect_id_column(df)

        if id_column is not None:
            # Check using detected ID column
            try:
                # Try to convert document_id to match column type
                search_value = CSVIdDetection.convert_document_id_to_column_type(
                    document_id, df, id_column
                )
                return search_value in df[id_column].values
            except (ValueError, TypeError):
                # Conversion failed, try direct string comparison
                return str(document_id) in df[id_column].astype(str).values
        else:
            # No ID column - try row index fallback
            try:
                row_index = int(document_id)
                return 0 <= row_index < len(df)
            except (ValueError, TypeError):
                return False
