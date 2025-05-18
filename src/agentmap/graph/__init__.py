"""
Graph module for AgentMap.
"""

# Direct exports for convenience - importing directly to avoid circular imports
from agentmap.graph.assembler import GraphAssembler
from agentmap.graph.builder import GraphBuilder
from agentmap.graph.csv_loader import build_graph_from_csv
from agentmap.graph.bundle import GraphBundle  # Add the new class

# Full module exports
__all__ = [
    # Direct exports
    'GraphAssembler',
    'GraphBuilder',
    'build_graph_from_csv',
    'GraphBundle',  # Add to exports
    
    # Module names (not importing them here to avoid circularity)
    'assembler',
    'csv_loader',
    'routing',
    'scaffold',
    'serialization',
    'bundle',  # Add module name
]

# Note: We're intentionally NOT importing other modules here
# to avoid circular imports. Use direct imports instead.