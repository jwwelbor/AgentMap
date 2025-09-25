from pathlib import Path
from agentmap.services.graph.scaffold.agent_scaffolder import AgentScaffolder
from agentmap.services.graph.scaffold.templates import Templates
from agentmap.services.graph.scaffold.service_requirements_parser import ServiceRequirementsParser

def test_agent_scaffolder_writes_file(tmp_path: Path):
    out = tmp_path / "MyAgent.py"
    scaff = AgentScaffolder(Templates(), ServiceRequirementsParser())
    res = scaff.scaffold("My", {"attrs": {}}, out)
    assert res == out
    assert out.exists()
    assert "class MyAgent" in out.read_text(encoding="utf-8")
