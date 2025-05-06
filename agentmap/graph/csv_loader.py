import pandas as pd
from langgraph.graph import StateGraph

from agentmap.agents import AgentLoader
from agentmap.graph.assembler import GraphAssembler  # Import directly from module

def build_graph_from_csv(csv_path: str, context: dict = None) -> StateGraph:
    """
    Build a LangGraph from CSV definitions.
    
    Args:
        csv_path: Path to the CSV file
        context: Optional context dictionary for agent initialization
        
    Returns:
        Compiled LangGraph StateGraph
    """
    agent_loader = AgentLoader(context or {})
    # Create a StateGraph with a dict-based state
    builder = StateGraph(dict)
    # Create a GraphAssembler
    assembler = GraphAssembler(builder, enable_logging=True)
    
    df = pd.read_csv(csv_path)
    
    # First pass: Add all nodes
    for _, row in df.iterrows():
        node_name = row['Node']
        agent_type = row.get('AgentType', 'DefaultAgent')
        prompt = row.get('Prompt', '')
        
        # Get the agent instance
        agent = agent_loader.get_agent(agent_type, name=node_name, prompt=prompt)
        
        # Add the node to the graph
        assembler.add_node(node_name, agent)
    
    # Set entry point to the first node
    node_names = df['Node'].tolist()
    if node_names:
        assembler.set_entry_point(node_names[0])
    
    # Second pass: Add all edges
    for _, row in df.iterrows():
        node_name = row['Node']
        success_next = row.get('Success_Next')
        failure_next = row.get('Failure_Next')
        edge = row.get('Edge')
        
        # Create edges dictionary
        edges = {}
        
        # Add success/failure edges if defined
        if pd.notna(success_next):
            edges["success"] = success_next.strip()
        if pd.notna(failure_next):
            edges["failure"] = failure_next.strip()
        
        # Add direct edge if defined
        if pd.notna(edge):
            edges["default"] = edge.strip()
        
        # Process all edges for this node
        if edges:
            assembler.process_node_edges(node_name, edges)
    
    # Compile and return the graph
    return assembler.compile()