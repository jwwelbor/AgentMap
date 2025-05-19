"""
CSV storage agents for AgentMap.

This module provides agents for reading from and writing to CSV files.
"""

from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.agents.builtins.storage.csv.reader import CSVReaderAgent
from agentmap.agents.builtins.storage.csv.writer import CSVWriterAgent

# Register agents with the registry when available
try:
    from agentmap.agents.registry import register_agent
    
    # Register the CSV agents
    register_agent("csv_reader", CSVReaderAgent)
    register_agent("csv_writer", CSVWriterAgent)
    
    _registry_available = True
except ImportError:
    _registry_available = False

__all__ = [
    'CSVAgent',
    'CSVReaderAgent',
    'CSVWriterAgent',
]