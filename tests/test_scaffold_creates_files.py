import os
import shutil
from pathlib import Path

from agentmap.graph.scaffold import scaffold_agents


def test_scaffold_creates_files(tmp_path):
    # Create a temporary directory for test
    test_dir = tmp_path / "custom_agents"
    functions_dir = tmp_path / "functions"
    
    # Use the test CSV with custom agents
    csv_path = Path("examples/NewAgentScaffold.csv")
    
    # Call the scaffold function
    scaffolded = scaffold_agents(
        output_dir=str(test_dir),
        func_dir=str(functions_dir),
        csv_path=str(csv_path)
    )
    
    # Check if files were created
    agent_files = list(test_dir.glob("*.py"))
    func_files = list(functions_dir.glob("*.py"))
    
    # Verify files were created
    assert len(agent_files) > 0
    assert any("weather" in f.name.lower() for f in agent_files)
    
    # We should have scaffolded more than 0 files
    assert scaffolded > 0


def test_scaffold_agent_content(tmp_path):
    # Create a test CSV in memory
    csv_content = (
        "GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt\n"
        "TestGraph,WeatherNode,,Weather Node,weather,SuccessNode,FailureNode,location,weather_data,Get weather for {location}"
    )
    csv_path = tmp_path / "test_scaffold.csv"
    with open(csv_path, "w") as f:
        f.write(csv_content)
    
    # Create output directories
    agent_dir = tmp_path / "agents"
    func_dir = tmp_path / "functions"
    
    # Call scaffold
    result = scaffold_agents(
        output_dir=str(agent_dir),
        func_dir=str(func_dir),
        csv_path=str(csv_path)
    )
    
    # Verify files were created
    agent_file = agent_dir / "weather_agent.py"
    assert agent_file.exists()
    
    # Verify content
    content = agent_file.read_text()
    assert "class WeatherAgent" in content
    assert "def process" in content
    assert "location" in content  # Input field
    assert "weather_data" in content  # Output field
    assert "Get weather for {location}" in content  # Prompt