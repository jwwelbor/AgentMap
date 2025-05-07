# agentmap/agents/builtins/storage/csv_reader_agent.py

from typing import Any, Dict, List, Union

from agentmap.agents.builtins.storage.base_csv_agent import BaseCSVAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)


class CSVReaderAgent(BaseCSVAgent):
    """Agent for reading data from CSV files."""
    
    def process(self, inputs: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        # Get file path
        csv_path = self.get_collection(inputs)
        logger = get_logger(__name__)
        logger.info(f"Reading from {csv_path}")
        
        # Check if file exists
        if not self._check_file_exists(csv_path):
            self._handle_error("File Not Found", f"CSV file not found: {csv_path}")
        
        # Read CSV
        df = self._read_csv(csv_path)
        
        # Apply filters
        df = self._apply_filters(df, inputs)
        
        # Handle single record case
        if inputs.get("id") is not None and len(df) == 1 and not inputs.get("return_list", False):
            return df.iloc[0].to_dict()
        
        # Format output
        return self._format_data_for_output(df, inputs.get("format", "records"))