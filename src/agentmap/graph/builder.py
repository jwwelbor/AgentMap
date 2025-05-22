"""
Graph builder for AgentMap.

Parses a CSV file to construct one or more workflow definitions.
Each workflow is identified by a unique GraphName.
"""

import csv
from collections import defaultdict
from pathlib import Path

from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError

from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.logging.service import LoggingService

class Node:
    def __init__(self, name, context=None, agent_type=None, inputs=None, output=None, prompt=None, description=None):
        self.name = name
        self.context = context
        self.agent_type = agent_type
        self.inputs = inputs or []
        self.output = output
        self.prompt = prompt
        self.description = description  # New field for node description
        self.edges = {}  # condition: next_node

    def add_edge(self, condition, target_node):
        self.edges[condition] = target_node
        
    def has_conditional_routing(self):
        """Check if this node has conditional routing (success/failure paths)."""
        return "success" in self.edges or "failure" in self.edges

    def __repr__(self):
        edge_info = ", ".join([f"{k}->{v}" for k, v in self.edges.items()])
        return f"<Node {self.name} [{self.agent_type}] → {edge_info}>"

@inject
class GraphBuilder:
    def __init__(self,
                csv_path,
                logging_service: LoggingService = Provide[ApplicationContainer.logging.logging_service]
        ):
        self.csv_path = Path(csv_path)
        self.logger = logging_service.get_class_logger(self)
        self.logger.info(f"[GraphBuilder] Initialized with CSV: {self.csv_path}")
        self.graphs = defaultdict(dict)  # GraphName: { node_name: Node }

    def get_graph(self, name):
        return self.graphs.get(name, {})
    
    def _create_node(self, graph, node_name, context, agent_type, input_fields, output_field, prompt, description=None):
        """Create a new node with the given properties."""
        agent_type = agent_type or "Default"
        self.logger.trace(f"  ➕ Creating Node: graph: {graph}, node_name: {node_name}")
        self.logger.trace(f"                    context: {context}")
        self.logger.trace(f"                    agent_type: {agent_type}")
        self.logger.trace(f"                    input_fields: {input_fields}")
        self.logger.trace(f"                    output_field: {output_field}")
        self.logger.trace(f"                    prompt: {prompt}")
        self.logger.trace(f"                    description: {description}")
        # Only create if not already exists
        if node_name not in graph:
            graph[node_name] = Node(
                node_name, 
                context, 
                agent_type, 
                input_fields, 
                output_field, 
                prompt,
                description
            )
            self.logger.debug(f"  ➕ Created Node: {node_name} with agent_type: {agent_type}, output_field: {output_field}")
        else:
            self.logger.debug(f"  ⏩ Node {node_name} already exists, skipping creation")
            
        return graph[node_name]
    
    def _create_nodes_from_csv(self):
        """First pass: Create all nodes from CSV definitions."""
        row_count = 0
        
        with self.csv_path.open() as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                row_count += 1
                graph_name = row.get("GraphName", "").strip()
                node_name = row.get("Node", "").strip()
                context = row.get("Context", "").strip()
                agent_type = row.get("AgentType", "").strip()
                input_fields = [x.strip() for x in row.get("Input_Fields", "").split("|") if x.strip()]
                output_field = row.get("Output_Field", "").strip()
                prompt = row.get("Prompt", "").strip()
                description = row.get("Description", "").strip()  # New field for node description
                
                self.logger.debug(f"[Row {row_count}] Processing: Graph='{graph_name}', Node='{node_name}', AgentType='{agent_type}'")
                
                if not graph_name:
                    self.logger.warning(f"[Line {row_count}] Missing GraphName. Skipping row.")
                    continue
                if not node_name:
                    self.logger.warning(f"[Line {row_count}] Missing Node. Skipping row.")
                    continue
                    
                # Get or create the graph
                graph = self.graphs[graph_name]
                
                # Create the node if it doesn't exist
                self._create_node(
                    graph, node_name, context, agent_type, 
                    input_fields, output_field, prompt, description
                )
        
        return row_count
    
    def _connect_nodes_with_edges(self):
        """Second pass: Connect nodes with edges."""
        with self.csv_path.open() as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                graph_name = row.get("GraphName", "").strip()
                node_name = row.get("Node", "").strip()
                edge_name = row.get("Edge", "").strip()
                success_next = row.get("Success_Next", "").strip()
                failure_next = row.get("Failure_Next", "").strip()
                
                if not graph_name or not node_name:
                    continue
                    
                graph = self.graphs[graph_name]
                
                # Check for conflicting edge definitions
                if edge_name and (success_next or failure_next):
                    self.logger.debug(f"  ⚠️ CONFLICT: Node '{node_name}' has both Edge and Success/Failure defined!")
                    raise InvalidEdgeDefinitionError(
                        f"Node '{node_name}' has both Edge and Success/Failure defined. "
                        f"Please use either Edge OR Success/Failure_Next, not both."
                    )
                
                # Connect with direct edge
                if edge_name:
                    self._connect_direct_edge(graph, node_name, edge_name, graph_name)
                
                # Connect with conditional edges
                elif success_next or failure_next:
                    if success_next:
                        self._connect_success_edge(graph, node_name, success_next, graph_name)
                    
                    if failure_next:
                        self._connect_failure_edge(graph, node_name, failure_next, graph_name)
    
    def _connect_direct_edge(self, graph, source_node, target_node, graph_name):
        """Connect nodes with a direct edge."""
        # Verify the edge target exists
        if target_node not in graph:
            self.logger.error(f"  ❌ Edge target '{target_node}' not defined in graph '{graph_name}'")
            raise ValueError(f"Edge target '{target_node}' is not defined as a node in graph '{graph_name}'")
        
        graph[source_node].add_edge("default", target_node)
        self.logger.debug(f"  🔗 {source_node} --default--> {target_node}")
    
    def _connect_success_edge(self, graph, source_node, target_node, graph_name):
        """Connect nodes with a success edge."""
        # Verify the success target exists
        if target_node not in graph:
            self.logger.error(f"  ❌ Success target '{target_node}' not defined in graph '{graph_name}'")
            raise ValueError(f"Success target '{target_node}' is not defined as a node in graph '{graph_name}'")
        
        graph[source_node].add_edge("success", target_node)
        self.logger.debug(f"  🔗 {source_node} --success--> {target_node}")
    
    def _connect_failure_edge(self, graph, source_node, target_node, graph_name):
        """Connect nodes with a failure edge."""
        # Verify the failure target exists
        if target_node not in graph:
            self.logger.error(f"  ❌ Failure target '{target_node}' not defined in graph '{graph_name}'")
            raise ValueError(f"Failure target '{target_node}' is not defined as a node in graph '{graph_name}'")
        
        graph[source_node].add_edge("failure", target_node)
        self.logger.debug(f"  🔗 {source_node} --failure--> {target_node}")
    
    def build(self):
        """Build all graphs from the CSV file."""
        if not self.csv_path.exists():
            self.logger.error(f"[GraphBuilder] CSV file not found: {self.csv_path}")
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        # Step 1: Create all nodes first
        row_count = self._create_nodes_from_csv()
        
        # Step 2: Connect nodes with edges
        self._connect_nodes_with_edges()
        
        self.logger.info(f"[GraphBuilder] Parsed {row_count} rows and built {len(self.graphs)} graph(s)")
        self.logger.debug(f"Graphs found: {list(self.graphs.keys())}")
        
        return self.graphs
    
    def print_graphs(self):
        for name, nodes in self.graphs.items():
            self.logger.debug(f"Graph: {name}")
            for node in nodes.values():
                self.logger.debug(f"  {node}")


# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) != 2:
#         self.logger.debug("Usage: python -m agentmap.graph.builder path/to/your.csv")
#     else:
#         gb = GraphBuilder(sys.argv[1])
#         gb.build()
#         gb.print_graphs()