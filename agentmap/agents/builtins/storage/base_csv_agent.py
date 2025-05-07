# Shared CSV base class
from typing import Any, Dict

import pandas as pd

from agentmap.agents.builtins.storage.base_storage_agent import \
    BaseStorageAgent
from agentmap.logging import get_logger


class BaseCSVAgent(BaseStorageAgent):
    """
    Base class for CSV storage agents with shared functionality.
    """
    
    def _ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for a file path exists.
        """
        import os
        directory = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(directory, exist_ok=True)
    
    def _check_file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists and log appropriately.
        """
        import os
        exists = os.path.exists(file_path)
        logger = get_logger(f"{self.__class__.__name__}")
        
        if not exists:
            logger.debug(f"File does not exist: {file_path}")
        return exists
    
    def _read_csv(self, file_path: str) -> pd.DataFrame:
        """
        Read a CSV file with standardized error handling.
        """
        import pandas as pd
        logger = get_logger(f"{self.__class__.__name__}")
        
        try:
            df = pd.read_csv(file_path)
            logger.debug(f"Read {len(df)} rows from {file_path}")
            return df
        except Exception as e:
            self._handle_error("CSV Read Error", f"Failed to read {file_path}", e)
    
    def _write_csv(self, df: pd.DataFrame, file_path: str, mode: str = 'w', header: bool = True) -> None:
        """
        Write a DataFrame to CSV with standardized error handling.
        """
        logger = get_logger(f"{self.__class__.__name__}")
        
        try:
            # Ensure directory exists
            self._ensure_directory_exists(file_path)
            
            # Write to CSV
            if mode == 'w':
                df.to_csv(file_path, index=False)
            elif mode == 'a':
                df.to_csv(file_path, mode='a', header=header, index=False)
            
            logger.debug(f"Wrote {len(df)} rows to {file_path} (mode: {mode})")
        except Exception as e:
            self._handle_error("CSV Write Error", f"Failed to write to {file_path}", e)
    
    def _apply_filters(self, df: pd.DataFrame, inputs: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply common filtering operations from inputs.
        """
        logger = get_logger(f"{self.__class__.__name__}")
        
        # Apply query filter
        query = inputs.get("query")
        if query:
            if isinstance(query, str):
                df = df.query(query)
                logger.debug(f"Applied query filter: {query}, {len(df)} rows remaining")
            elif isinstance(query, dict):
                for col, value in query.items():
                    if col in df.columns:
                        df = df[df[col] == value]
                logger.debug(f"Applied dict filter, {len(df)} rows remaining")
        
        # Apply ID filter
        id_value = inputs.get("id")
        if id_value is not None:
            id_field = inputs.get("id_field", "id")
            if id_field in df.columns:
                df = df[df[id_field] == id_value]
                logger.debug(f"Applied ID filter: {id_field}={id_value}, {len(df)} rows remaining")
        
        # Apply limit
        limit = inputs.get("limit")
        if limit and isinstance(limit, int) and limit > 0:
            df = df.head(limit)
            logger.debug(f"Applied limit: {limit}")
        
        return df