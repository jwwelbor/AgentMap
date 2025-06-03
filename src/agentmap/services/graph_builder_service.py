"""
GraphBuilderService for AgentMap.

Service containing business logic for parsing CSV files and building Graph domain models.
This extracts and wraps the core functionality from the original GraphBuilder class.
"""

import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, List

from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.services.logging_service import LoggingService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError


class GraphBuilderService:
    """
    Service for building Graph domain models from CSV files.
    
    Contains all CSV parsing and graph building business logic extracted from
    the original GraphBuilder. Returns clean Graph domain models instead of
    raw dictionaries.
    """
    
    def __init__(
        self,
        logging_service: LoggingService,
        app_config_service: AppConfigService
    ):
        """Initialize service with dependency injection."""
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        self.logger.info("[GraphBuilderService] Initialized")
    
    def build_from_csv(self, csv_path: Path, graph_name: Optional[str] = None) -> Graph:
        """
        Build single graph from CSV file.
        
        Args:
            csv_path: Path to CSV file containing graph definitions
            graph_name: Specific graph name to extract (returns first graph if None)
            
        Returns:
            Graph domain model for the specified or first graph found
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If specified graph_name not found in CSV
        """
        self.logger.info(f"[GraphBuilderService] Building single graph from: {csv_path}")
        
        # Build all graphs first
        all_graphs = self.build_all_from_csv(csv_path)
        
        if not all_graphs:
            raise ValueError(f"No graphs found in CSV file: {csv_path}")
        
        # Return specific graph if requested
        if graph_name:
            if graph_name not in all_graphs:
                available_graphs = list(all_graphs.keys())
                raise ValueError(
                    f"Graph '{graph_name}' not found in CSV. "
                    f"Available graphs: {available_graphs}"
                )
            return all_graphs[graph_name]
        
        # Return first graph if no specific name requested
        first_graph_name = next(iter(all_graphs))
        self.logger.info(f"[GraphBuilderService] Returning first graph: {first_graph_name}")
        return all_graphs[first_graph_name]
    
    def build_all_from_csv(self, csv_path: Path) -> Dict[str, Graph]:
        """
        Build all graphs found in CSV file.
        
        Args:
            csv_path: Path to CSV file containing graph definitions
            
        Returns:
            Dictionary mapping graph names to Graph domain models
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
        """
        csv_path = Path(csv_path)
        self.logger.info(f"[GraphBuilderService] Building all graphs from: {csv_path}")
        
        if not csv_path.exists():
            self.logger.error(f"[GraphBuilderService] CSV file not found: {csv_path}")
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Step 1: Parse CSV and create raw node data
        raw_graphs = self._create_nodes_from_csv(csv_path)
        
        # Step 2: Connect nodes with edges
        self._connect_nodes_with_edges(raw_graphs, csv_path)
        
        # Step 3: Convert to domain models
        domain_graphs = self._convert_to_domain_models(raw_graphs)
        
        self.logger.info(
            f"[GraphBuilderService] Successfully built {len(domain_graphs)} graph(s): "
            f"{list(domain_graphs.keys())}"
        )
        
        return domain_graphs
    
    def validate_csv_before_building(self, csv_path: Path) -> List[str]:
        """
        Pre-validate CSV structure and content.
        
        Args:
            csv_path: Path to CSV file to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        csv_path = Path(csv_path)
        
        if not csv_path.exists():
            errors.append(f"CSV file not found: {csv_path}")
            return errors
        
        try:
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                
                # Check required columns
                required_columns = {"GraphName", "Node"}
                missing_columns = required_columns - set(reader.fieldnames or [])
                if missing_columns:
                    errors.append(f"Missing required columns: {missing_columns}")
                    return errors
                
                # Validate row content
                row_count = 0
                for row in reader:
                    row_count += 1
                    graph_name = self._safe_get_csv_field(row, "GraphName", "").strip()
                    node_name = self._safe_get_csv_field(row, "Node", "").strip()
                    
                    if not graph_name:
                        errors.append(f"Line {row_count}: Missing GraphName")
                    if not node_name:
                        errors.append(f"Line {row_count}: Missing Node name")
                
                if row_count == 0:
                    errors.append("CSV file is empty or contains no data rows")
                    
        except Exception as e:
            errors.append(f"Error reading CSV file: {str(e)}")
        
        return errors
    
    def _create_nodes_from_csv(self, csv_path: Path) -> Dict[str, Dict[str, Node]]:
        """
        First pass: Create all nodes from CSV definitions.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Dictionary mapping graph names to node dictionaries
        """
        graphs = defaultdict(dict)  # GraphName: { node_name: Node }
        row_count = 0
        
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                row_count += 1
                graph_name = self._safe_get_csv_field(row, "GraphName").strip()
                node_name = self._safe_get_csv_field(row, "Node").strip()
                context = self._safe_get_csv_field(row, "Context").strip()
                agent_type = self._safe_get_csv_field(row, "AgentType").strip()
                input_fields = [x.strip() for x in self._safe_get_csv_field(row, "Input_Fields").split("|") if x.strip()]
                output_field = self._safe_get_csv_field(row, "Output_Field").strip()
                prompt = self._safe_get_csv_field(row, "Prompt").strip()
                description = self._safe_get_csv_field(row, "Description").strip()
                
                self.logger.debug(
                    f"[Row {row_count}] Processing: Graph='{graph_name}', "
                    f"Node='{node_name}', AgentType='{agent_type}'"
                )
                
                if not graph_name:
                    self.logger.warning(f"[Line {row_count}] Missing GraphName. Skipping row.")
                    continue
                if not node_name:
                    self.logger.warning(f"[Line {row_count}] Missing Node. Skipping row.")
                    continue
                
                # Get or create the graph
                graph = graphs[graph_name]
                
                # Create the node if it doesn't exist
                self._create_node(
                    graph, node_name, context, agent_type,
                    input_fields, output_field, prompt, description
                )
        
        self.logger.info(f"[GraphBuilderService] Processed {row_count} rows")
        return dict(graphs)  # Convert defaultdict to regular dict
    
    def _create_node(
        self, 
        graph: Dict[str, Node], 
        node_name: str, 
        context: str, 
        agent_type: str,
        input_fields: List[str], 
        output_field: str, 
        prompt: str, 
        description: str = None
    ) -> Node:
        """
        Create a new node with the given properties.
        
        Args:
            graph: Graph dictionary to add node to
            node_name: Name of the node
            context: Node context
            agent_type: Type of agent
            input_fields: List of input field names
            output_field: Output field name
            prompt: Node prompt
            description: Node description
            
        Returns:
            Created or existing Node instance
        """
        agent_type = agent_type or "Default"
        
        self.logger.trace(f"  ➕ Creating Node: node_name: {node_name}")
        self.logger.trace(f"                    context: {context}")
        self.logger.trace(f"                    agent_type: {agent_type}")
        self.logger.trace(f"                    input_fields: {input_fields}")
        self.logger.trace(f"                    output_field: {output_field}")
        self.logger.trace(f"                    prompt: {prompt}")
        self.logger.trace(f"                    description: {description}")
        
        # Only create if not already exists
        if node_name not in graph:
            # Convert context string to dict if needed (preserve existing logic)
            context_dict = {"context": context} if context else None
            
            graph[node_name] = Node(
                name=node_name,
                context=context_dict,
                agent_type=agent_type,
                inputs=input_fields,
                output=output_field,
                prompt=prompt,
                description=description
            )
            self.logger.debug(
                f"  ➕ Created Node: {node_name} with agent_type: {agent_type}, "
                f"output_field: {output_field}"
            )
        else:
            self.logger.debug(f"  ⏩ Node {node_name} already exists, skipping creation")
        
        return graph[node_name]
    
    def _connect_nodes_with_edges(self, graphs: Dict[str, Dict[str, Node]], csv_path: Path) -> None:
        """
        Second pass: Connect nodes with edges.
        
        Args:
            graphs: Dictionary of graphs with nodes
            csv_path: Path to CSV file
        """
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                graph_name = self._safe_get_csv_field(row, "GraphName").strip()
                node_name = self._safe_get_csv_field(row, "Node").strip()
                edge_name = self._safe_get_csv_field(row, "Edge").strip()
                success_next = self._safe_get_csv_field(row, "Success_Next").strip()
                failure_next = self._safe_get_csv_field(row, "Failure_Next").strip()
                
                if not graph_name or not node_name:
                    continue
                
                graph = graphs[graph_name]
                
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
    
    def _connect_direct_edge(self, graph: Dict[str, Node], source_node: str, target_node: str, graph_name: str) -> None:
        """Connect nodes with a direct edge."""
        # Verify the edge target exists
        if target_node not in graph:
            self.logger.error(f"  ❌ Edge target '{target_node}' not defined in graph '{graph_name}'")
            raise ValueError(f"Edge target '{target_node}' is not defined as a node in graph '{graph_name}'")
        
        graph[source_node].add_edge("default", target_node)
        self.logger.debug(f"  🔗 {source_node} --default--> {target_node}")
    
    def _connect_success_edge(self, graph: Dict[str, Node], source_node: str, target_node: str, graph_name: str) -> None:
        """Connect nodes with a success edge."""
        # Verify the success target exists
        if target_node not in graph:
            self.logger.error(f"  ❌ Success target '{target_node}' not defined in graph '{graph_name}'")
            raise ValueError(f"Success target '{target_node}' is not defined as a node in graph '{graph_name}'")
        
        graph[source_node].add_edge("success", target_node)
        self.logger.debug(f"  🔗 {source_node} --success--> {target_node}")
    
    def _connect_failure_edge(self, graph: Dict[str, Node], source_node: str, target_node: str, graph_name: str) -> None:
        """Connect nodes with a failure edge."""
        # Verify the failure target exists
        if target_node not in graph:
            self.logger.error(f"  ❌ Failure target '{target_node}' not defined in graph '{graph_name}'")
            raise ValueError(f"Failure target '{target_node}' is not defined as a node in graph '{graph_name}'")
        
        graph[source_node].add_edge("failure", target_node)
        self.logger.debug(f"  🔗 {source_node} --failure--> {target_node}")
    
    def _convert_to_domain_models(self, raw_graphs: Dict[str, Dict[str, Node]]) -> Dict[str, Graph]:
        """
        Convert raw node dictionaries to Graph domain models.
        
        Args:
            raw_graphs: Dictionary mapping graph names to node dictionaries
            
        Returns:
            Dictionary mapping graph names to Graph domain models
        """
        domain_graphs = {}
        
        for graph_name, nodes_dict in raw_graphs.items():
            # Create Graph domain model
            graph = Graph(name=graph_name)
            
            # Add all nodes to the graph
            for node_name, node in nodes_dict.items():
                graph.nodes[node_name] = node
            
            # Detect entry point (node with no incoming edges)
            self._detect_entry_point(graph)
            
            domain_graphs[graph_name] = graph
            
            self.logger.debug(
                f"Converted graph '{graph_name}' with {len(nodes_dict)} nodes. "
                f"Entry point: {graph.entry_point}"
            )
        
        return domain_graphs
    
    def _detect_entry_point(self, graph: Graph) -> None:
        """
        Detect and set the entry point for a graph.
        
        Entry point is a node that has no incoming edges from other nodes.
        
        Args:
            graph: Graph domain model to analyze
        """
        # Collect all target nodes (nodes that are referenced as edge targets)
        target_nodes = set()
        for node in graph.nodes.values():
            target_nodes.update(node.edges.values())
        
        #set entry point to first node
        graph.entry_point = next(iter(graph.nodes))
        # # Find nodes with no incoming edges
        # I don't know why this would be needed
        # entry_candidates = []
        # for node_name in graph.nodes:
        #     if node_name not in target_nodes:
        #         entry_candidates.append(node_name)
        
        # # Set entry point
        # if len(entry_candidates) == 1:
        #     graph.entry_point = entry_candidates[0]
        #     self.logger.debug(f"Detected entry point: {graph.entry_point}")
        # elif len(entry_candidates) > 1:
        #     # Multiple possible entry points - use first alphabetically for consistency
        #     graph.entry_point = sorted(entry_candidates)[0]
        #     self.logger.warning(
        #         f"Multiple entry point candidates: {entry_candidates}. "
        #         f"Using: {graph.entry_point}"
        #     )
        # else:
        #     # No clear entry point (possibly circular) - use first node
        #     if graph.nodes:
        #         graph.entry_point = next(iter(graph.nodes))
        #         self.logger.warning(
        #             f"No clear entry point found. Using first node: {graph.entry_point}"
        #         )

    def _safe_get_csv_field(self, row: Dict, field_name: str, default: str = "") -> str:
        """
        Safely extract field value from CSV row, handling None values.
        
        Args:
            row: CSV row dictionary
            field_name: Name of the field to extract
            default: Default value if field is missing or None
            
        Returns:
            String value, never None
        """
        value = row.get(field_name, default)
        return value if value is not None else default