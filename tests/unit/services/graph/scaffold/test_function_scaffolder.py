from pathlib import Path
from agentmap.services.graph.scaffold.function_scaffolder import FunctionScaffolder
from agentmap.services.graph.scaffold.templates import Templates

def test_function_scaffolder_writes_file(tmp_path: Path):
    out = tmp_path / "do_stuff.py"
    scaff = FunctionScaffolder(Templates())
    res = scaff.scaffold("do_stuff", {"params": {}}, out)
    assert res == out
    assert out.exists()
    assert "def do_stuff" in out.read_text(encoding="utf-8")
