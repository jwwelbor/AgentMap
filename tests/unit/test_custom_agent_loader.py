"""Unit tests for CustomAgentLoader logging behavior."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

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


if __name__ == "__main__":
    unittest.main()
