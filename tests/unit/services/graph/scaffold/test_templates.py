from agentmap.services.graph.scaffold.templates import Templates

def test_render_agent_contains_class():
    t = Templates()
    code = t.render_agent("My", {"attrs": {}})
    assert "class MyAgent" in code

def test_render_function_contains_def():
    t = Templates()
    code = t.render_function("do_stuff", {"params": {}})
    assert "def do_stuff" in code
