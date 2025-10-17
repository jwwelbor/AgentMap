"""
Graph domain model for AgentMap.

This module contains the Graph model which is a pure data container
for representing workflow graph structure.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from .node import Node


@dataclass
class Graph:
    """Pure data container for graph structure.

    Attributes:
        name: The name of the graph
        entry_point: Optional entry point node name
        nodes: Dictionary mapping node names to Node objects
    """

    name: str
    entry_point: Optional[str] = None
    nodes: Dict[str, Node] = field(default_factory=dict)
