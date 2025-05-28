# def test_server_initialization():
#     """Test that the FastAPI server initializes correctly."""
#     from agentmap.server import app

#     # Just verify the app exists and has the expected properties
#     assert app is not None
#     assert app.title == "AgentMap Graph API"
    
#     # Check that routes are defined
#     assert any(route.path == "/run" for route in app.routes), "Expected /run route not found"