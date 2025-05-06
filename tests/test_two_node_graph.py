from langgraph.graph import StateGraph

from agentmap.agents.builtins.default_agent import DefaultAgent


def test_two_node_graph():
    # Create a simple two-node graph
    g = StateGraph(dict)
    
    # Create two basic agents
    a = DefaultAgent(name="A", prompt="Hi", context={})
    b = DefaultAgent(name="B", prompt="Bye", context={})
    
    # Add nodes to the graph
    g.add_node("A", a.run)
    g.add_node("B", b.run)
    
    # Create a linear flow A -> B
    g.add_edge("A", "B")
    
    # Set entry and end points
    g.set_entry_point("A")
    g.set_finish_point("B")
    
    # Compile the graph
    graph = g.compile()
    
    # Run the graph with empty input
    out = graph.invoke({})
    
    # Verify output is a dictionary
    assert isinstance(out, dict)
    # Verify last node executed successfully
    assert out.get("last_action_success") is True