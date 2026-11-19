"""Tests for serverless JSON request shape validation."""

import pytest

from agentmap.services.serverless.request_parser import RequestParser


@pytest.mark.parametrize("body", ["[]", "null", "1", '"value"'])
def test_parse_json_body_rejects_non_object_payloads(body):
    with pytest.raises(ValueError, match="must be an object"):
        RequestParser.parse_json_body(body)


def test_parse_json_body_accepts_object_payload():
    assert RequestParser.parse_json_body('{"state": {"count": 1}}') == {
        "state": {"count": 1}
    }
