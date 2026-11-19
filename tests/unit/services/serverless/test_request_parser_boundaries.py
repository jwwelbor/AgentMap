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


@pytest.mark.parametrize(
    "field",
    ["queryStringParameters", "pathParameters"],
)
@pytest.mark.parametrize("value", [["unexpected"], "unexpected", 7])
def test_extract_parameters_ignores_non_mapping_values(field, value):
    extractor = (
        RequestParser.extract_query_params
        if field == "queryStringParameters"
        else RequestParser.extract_path_params
    )

    assert extractor({field: value}) == {}


@pytest.mark.parametrize("method", [None, 4, ["GET"]])
def test_get_http_method_uses_post_for_non_string_values(method):
    assert RequestParser.get_http_method({"httpMethod": method}) == "POST"
