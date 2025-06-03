# agentmap/graph/__init__.py
"""
Graph construction and assembly for AgentMap.

This module provides clean architecture wrappers around the existing
graph assembly functionality, following service wrapper patterns.
"""

# Import the GraphAssembler from the existing implementation
# This follows the service wrapper pattern - we reuse the existing proven implementation
try:
    # Try to import from the existing working implementation
    from agentmap.graph.assembler import GraphAssembler
except ImportError:
    # Fallback: Import from src_old if needed
    import sys
    import os
    
    # Add src_old to path temporarily if needed
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    src_old_path = os.path.join(current_dir, "..", "src_old")
    if os.path.exists(src_old_path) and src_old_path not in sys.path:
        sys.path.insert(0, src_old_path)
    
    try:
        from agentmap.graph.assembler import GraphAssembler
    except ImportError:
        # Create a minimal GraphAssembler if all else fails
        class GraphAssembler:
            """Minimal GraphAssembler for clean architecture compatibility."""
            
            def __init__(self, builder, node_registry=None):
                self.builder = builder
                self.node_registry = node_registry or {}
                self.nodes = {}
                self.entry_point = None
            
            def add_node(self, name, agent_instance):
                """Add a node to the graph."""
                self.nodes[name] = agent_instance
                self.builder.add_node(name, agent_instance)
            
            def set_entry_point(self, entry_point):
                """Set the graph entry point."""
                self.entry_point = entry_point
                self.builder.set_entry_point(entry_point)
            
            def process_node_edges(self, node_name, edges):
                """Process edges for a node."""
                for condition, target in edges.items():
                    self.builder.add_edge(node_name, target)
            
            def compile(self):
                """Compile the graph."""
                return self.builder.compile()

__all__ = ['GraphAssembler']
