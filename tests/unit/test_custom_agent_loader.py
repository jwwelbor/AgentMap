"""Unit tests for CustomAgentLoader logging behavior."""

import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from agentmap.services.custom_agent_loader import CustomAgentLoader


class TestCustomAgentLoader(unittest.TestCase):
    """Tests for dotted-path custom agent loading diagnostics."""

    def test_dotted_import_path_does_not_emit_error_for_missing_file(self) -> None:
        mock_logging = MagicMock()
        mock_logger = MagicMock()
        mock_logging.get_class_logger.return_value = mock_logger

        loader = CustomAgentLoader(Path("/tmp/nonexistent-custom-agents"), mock_logging)

        result = loader.load_agent_class(
            "app.agents.ingestion.llm_vision_agent.LlmVisionAgent"
        )

        self.assertIsNone(result)
        mock_logger.error.assert_not_called()

    def test_non_class_attribute_is_not_loaded_as_agent(self) -> None:
        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        loader = CustomAgentLoader(Path("/tmp/custom-agents"), mock_logging)
        module = ModuleType("bad_agent")
        module.BadAgent = object()

        with patch.object(loader, "_load_module", return_value=module):
            self.assertIsNone(loader.load_agent_class("bad_agent.BadAgent"))


if __name__ == "__main__":
    unittest.main()
