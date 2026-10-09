"""Governed-rate refusals retain safe, distinct diagnostics."""

from unittest.mock import Mock

import pytest

from agentmap.exceptions import AttemptLifecycleRefusal, LLMConfigurationError
from agentmap.services.llm.governed_accounting import governed_rates


@pytest.mark.parametrize(
    "failure,category",
    [
        (LLMConfigurationError("secret catalog value"), "configuration"),
        (ValueError("secret catalog value"), "unexpected"),
    ],
)
def test_governed_rates_refuses_with_safe_diagnostic(failure, category):
    calculator = Mock()
    calculator.get_rates.side_effect = failure
    calculator._logger = Mock()

    with pytest.raises(AttemptLifecycleRefusal) as raised:
        governed_rates(calculator, "synthetic", "synthetic-model")

    assert isinstance(raised.value.original, LLMConfigurationError)
    assert "secret catalog value" not in str(raised.value)
    diagnostic = repr(calculator._logger.warning.call_args)
    assert "secret catalog value" not in diagnostic
    assert f"category={category}" in diagnostic
    assert "stage=rate_lookup" in diagnostic
