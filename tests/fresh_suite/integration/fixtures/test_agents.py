"""
Test agents for integration testing of input field mapping.

These agents declare expected_params to exercise positional binding mode
in end-to-end integration tests.
"""

from typing import Any, Dict, List, Optional

from agentmap.agents.base_agent import BaseAgent


class PositionalBindingTestAgent(BaseAgent):
    """Test agent that declares expected_params for positional binding testing.

    When this agent is used in a workflow and Input_Fields are plain names
    (no colon syntax), positional binding mode activates automatically.
    The CSV field values are mapped to the expected_params names by index.
    """

    expected_params: Optional[List[str]] = ["addend_a", "addend_b"]

    def process(self, inputs: Dict[str, Any]) -> Any:
        """Sum the positionally-bound parameters."""
        a = inputs.get("addend_a", 0)
        b = inputs.get("addend_b", 0)
        try:
            return int(a) + int(b)
        except (TypeError, ValueError):
            return f"addend_a={a}, addend_b={b}"
