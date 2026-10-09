"""The core collector requires its published outcome and retains first errors."""

import ast
import inspect
from decimal import Decimal

import pytest

from agentmap.models.llm_attempt import LLMAttemptOutcome
from agentmap.models.llm_execution import LLMUsage
from agentmap.services.llm.attempt_lifecycle import collect_evidence


def test_evidence_collector_requires_explicit_published_outcome__b102():
    parameter = inspect.signature(collect_evidence).parameters["outcome"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_core_evidence_collector_stays_within_ten_decisions__b102():
    tree = ast.parse(inspect.getsource(collect_evidence))
    branches = (ast.If, ast.IfExp, ast.For, ast.While, ast.ExceptHandler)
    decisions = 1 + sum(isinstance(node, branches) for node in ast.walk(tree))
    decisions += sum(
        len(node.values) - 1 for node in ast.walk(tree) if isinstance(node, ast.BoolOp)
    )
    assert decisions <= 10


@pytest.mark.parametrize(
    "failures",
    [(), ("usage",), ("cost",), ("identity",), ("usage", "cost", "identity")],
)
def test_independent_fields_and_first_failure_precedence_are_preserved__b102(failures):
    from types import SimpleNamespace

    events = []
    errors = {field: RuntimeError(field) for field in failures}
    usage = LLMUsage(input_tokens=10, output_tokens=20)
    initial = LLMAttemptOutcome(classification="provider_error", usage=usage)
    values = {
        "usage": usage,
        "cost": SimpleNamespace(currency="USD", total_cost=Decimal("0.30")),
        "identity": "provider-request",
    }

    def read(field, value):
        events.append(field)
        if field in errors:
            raise errors[field]
        return values[field]

    outcome, failure = collect_evidence(
        object(),
        lambda response: read("usage", response),
        lambda measured_usage: read("cost", measured_usage),
        lambda response: read("identity", response),
        outcome=initial,
    )
    assert events == ["usage", "cost", "identity"]
    assert outcome.usage == usage
    assert outcome.cost_usd == (None if "cost" in failures else Decimal("0.30"))
    assert outcome.provider_request_id == (
        None if "identity" in failures else "provider-request"
    )
    assert failure is (errors[failures[0]] if failures else None)
    assert initial.cost_usd is initial.provider_request_id is None
