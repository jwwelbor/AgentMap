"""Tests for shared JSON object parsing in CLI state helpers."""

import pytest

from agentmap.deployment.cli.run_command import parse_json_state as parse_run_state
from agentmap.deployment.cli.utils.cli_utils import parse_json_object


def test_shared_parser_returns_json_objects():
    assert parse_json_object('{"count": 2}') == {"count": 2}


@pytest.mark.parametrize("value", ["[]", "null", '"text"', "3"])
def test_shared_parser_rejects_non_object_roots(value):
    with pytest.raises(ValueError, match="JSON value must be an object"):
        parse_json_object(value)


def test_run_state_wrapper_preserves_its_error_context():
    with pytest.raises(ValueError, match="JSON state must be an object"):
        parse_run_state("[]")

    with pytest.raises(ValueError, match="Invalid JSON in state"):
        parse_run_state("{")
