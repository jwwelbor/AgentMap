import pytest

from agentmap.graph.routing import choose_next


def test_choose_next_success():
    state = {"last_action_success": True}
    result = choose_next(state, ["A", "B"], ["X", "Y"])
    assert result == ["A", "B"]

def test_choose_next_failure():
    state = {"last_action_success": False}
    result = choose_next(state, ["A", "B"], ["X", "Y"])
    assert result == ["X", "Y"]

def test_choose_next_single_success():
    state = {"last_action_success": True}
    result = choose_next(state, ["Only"], ["None"])
    assert result == "Only"

def test_choose_next_single_failure():
    state = {"last_action_success": False}
    result = choose_next(state, ["None"], ["Only"])
    assert result == "Only"