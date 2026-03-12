"""
Protocol conformance tests for StateAdapterService.

Validates that StateAdapterService conforms to StateAdapterServiceProtocol,
including the expected_params parameter added by E01 input field mapping.

AC Coverage: AC-07 (Protocol signature updated)
"""

import inspect
import unittest
from typing import List, Optional

from agentmap.services.protocols.service_protocols import StateAdapterServiceProtocol
from agentmap.services.state_adapter_service import StateAdapterService


class TestStateAdapterProtocolConformance(unittest.TestCase):
    """Tests that StateAdapterService conforms to StateAdapterServiceProtocol."""

    def test_isinstance_check(self) -> None:
        """StateAdapterService instance must satisfy the runtime_checkable protocol."""
        service = StateAdapterService()
        self.assertIsInstance(
            service,
            StateAdapterServiceProtocol,
            "StateAdapterService must be an instance of StateAdapterServiceProtocol",
        )

    def test_get_inputs_signature_has_expected_params(self) -> None:
        """get_inputs must have an expected_params parameter with correct type and default."""
        sig = inspect.signature(StateAdapterService.get_inputs)
        params = sig.parameters

        self.assertIn(
            "expected_params",
            params,
            "get_inputs must have an 'expected_params' parameter",
        )

        param = params["expected_params"]

        # Default value must be None
        self.assertIs(
            param.default,
            None,
            "expected_params default must be None",
        )

        # Annotation must be Optional[List[str]]
        annotation = param.annotation
        self.assertEqual(
            annotation,
            Optional[List[str]],
            f"expected_params annotation must be Optional[List[str]], got {annotation}",
        )

    def test_get_inputs_callable_without_expected_params(self) -> None:
        """get_inputs must be callable with only state and input_fields (backward compat)."""
        state = {"foo": 1, "bar": 2}
        fields = ["foo", "bar"]

        # Must not raise when called without expected_params
        result = StateAdapterService.get_inputs(state, fields)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["foo"], 1)
        self.assertEqual(result["bar"], 2)

    def test_get_inputs_callable_with_expected_params_none(self) -> None:
        """Passing expected_params=None must produce identical results to omitting it."""
        state = {"foo": 1, "bar": 2}
        fields = ["foo", "bar"]

        result_without = StateAdapterService.get_inputs(state, fields)
        result_with_none = StateAdapterService.get_inputs(
            state, fields, expected_params=None
        )

        self.assertEqual(
            result_without,
            result_with_none,
            "expected_params=None must produce identical results to omitting it",
        )

    def test_protocol_get_inputs_signature_matches_concrete(self) -> None:
        """Protocol and concrete class get_inputs signatures must have same parameters."""
        protocol_sig = inspect.signature(StateAdapterServiceProtocol.get_inputs)
        concrete_sig = inspect.signature(StateAdapterService.get_inputs)

        protocol_params = set(protocol_sig.parameters.keys()) - {"self"}
        concrete_params = set(concrete_sig.parameters.keys()) - {"self"}

        self.assertEqual(
            protocol_params,
            concrete_params,
            f"Protocol params {protocol_params} must match concrete params {concrete_params}",
        )


if __name__ == "__main__":
    unittest.main()
