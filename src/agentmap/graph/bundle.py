"""
Graph bundle for AgentMap.

Provides a container for compiled graph, node registry, and version information.
Ensures consistency between compiled components.
"""
import hashlib
import pickle
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

class GraphBundle:
    """
    Bundle for a compiled graph, node registry, and version information.
    Ensures consistency between components.
    """
    
    def __init__(self, graph, node_registry, logger: logging.Logger, csv_content=None, version_hash=None):
        """
        Initialize the graph bundle.
        
        Args:
            graph: Compiled LangGraph StateGraph
            node_registry: Node registry dictionary
            csv_content: Original CSV content for versioning
            version_hash: Pre-computed version hash
        """
        self.graph = graph
        self.node_registry = node_registry
        self.logger = logger
        
        # Generate version hash if not provided
        if version_hash:
            self.version_hash = version_hash
        elif csv_content:
            self.version_hash = self._generate_hash(csv_content)
        else:
            self.version_hash = None
            
    @staticmethod
    def _generate_hash(content):
        """Generate a hash from content for versioning."""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.md5(content).hexdigest()
    
    def to_dict(self):
        """Convert bundle to dictionary for serialization."""
        return {
            "graph": self.graph,
            "node_registry": self.node_registry,
            "version_hash": self.version_hash
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create bundle from dictionary."""
        return cls(
            graph=data.get("graph"),
            node_registry=data.get("node_registry"),
            version_hash=data.get("version_hash")
        )
    
    def save(self, path):
        """
        Save bundle to a pickle file.
        
        Args:
            path: Path to save the bundle
        """
        with open(path, 'wb') as f:
            pickle.dump(self.to_dict(), f)
        self.logger.debug(f"Saved graph bundle to {path} with version hash: {self.version_hash}")
    
    @classmethod
    def load(self, cls, path):
        """
        Load bundle from a pickle file.
        
        Args:
            path: Path to the bundle file
            
        Returns:
            GraphBundle instance
        """
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
                
            # Handle different formats
            if isinstance(data, dict) and "graph" in data:
                # New format with bundled components
                return cls.from_dict(data)
            else:
                # Old format with just the graph
                return cls(graph=data, node_registry=None, version_hash=None)
                
        except Exception as e:
            self.logger.error(f"Error loading graph bundle: {e}")
            return None
    
    def verify_csv(self, csv_content):
        """
        Verify if the bundle matches the current CSV content.
        
        Args:
            csv_content: Current CSV content to verify against
            
        Returns:
            bool: True if versions match, False otherwise
        """
        if not self.version_hash:
            return False
            
        current_hash = self._generate_hash(csv_content)
        return current_hash == self.version_hash