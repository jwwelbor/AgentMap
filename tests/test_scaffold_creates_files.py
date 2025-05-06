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