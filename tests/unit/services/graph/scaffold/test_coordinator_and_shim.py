from pathlib import Path
from agentmap.services.graph.scaffold.coordinator import GraphScaffoldService
from agentmap.services.graph.graph_scaffold_service import GraphScaffoldService as ShimImport

def test_shim_and_direct_import_are_same_class():
    assert GraphScaffoldService is ShimImport

def test_coordinator_scaffolds_both(tmp_path: Path):
    svc = GraphScaffoldService()
    agent_out = tmp_path / "Agent.py"
    fn_out = tmp_path / "edge_fn.py"
    svc.scaffold_agent_class("Demo", {"attrs": {}}, agent_out)
    svc.scaffold_edge_function("edge_fn", {"params": {}}, fn_out)
    assert agent_out.exists()
    assert fn_out.exists()
