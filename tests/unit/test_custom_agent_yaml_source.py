"""Unit tests for CustomAgentYAMLSource."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agentmap.services.declaration_parser import DeclarationParser
from agentmap.services.declaration_sources.custom_agent_yaml_source import (
    CustomAgentYAMLSource,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestCustomAgentYAMLSource(unittest.TestCase):
    """Tests for custom agent YAML loading behavior."""

    def setUp(self) -> None:
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.parser = DeclarationParser(self.mock_logging)

    def _make_source(self, custom_agents_path: Path) -> CustomAgentYAMLSource:
        mock_config = MagicMock()
        mock_config.get_custom_agents_path.return_value = custom_agents_path
        return CustomAgentYAMLSource(mock_config, self.parser, self.mock_logging)

    def test_load_agents_normalizes_service_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source(Path(tmpdir))
            yaml_data = {
                "agents": {
                    "llm_vision": {
                        "class_path": "app.agents.llm_vision.LlmVisionAgent",
                        "requires": {
                            "services": ["LLMService"],
                            "protocols": ["LLMCapableAgent"],
                        },
                    }
                }
            }

            with patch(
                "agentmap.services.declaration_sources.custom_agent_yaml_source.load_yaml_file",
                return_value=yaml_data,
            ):
                agents = source.load_agents()

        declaration = agents["llm_vision"]
        self.assertEqual(
            [req.name for req in declaration.service_requirements], ["llm_service"]
        )

    def test_load_agents_fails_fast_on_unknown_service_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source(Path(tmpdir))
            yaml_data = {
                "agents": {
                    "llm_vision": {
                        "class_path": "app.agents.llm_vision.LlmVisionAgent",
                        "requires": {
                            "services": ["DefinitelyNotAService"],
                            "protocols": ["LLMCapableAgent"],
                        },
                    }
                }
            }

            with patch(
                "agentmap.services.declaration_sources.custom_agent_yaml_source.load_yaml_file",
                return_value=yaml_data,
            ):
                with self.assertRaises(ValueError) as context:
                    source.load_agents()

        message = str(context.exception)
        self.assertIn("custom_agents.yaml", message)
        self.assertIn("llm_vision", message)
        self.assertIn("DefinitelyNotAService", message)
        self.assertIn("llm_service", message)
        self.assertIn("storage_service_manager", message)


if __name__ == "__main__":
    unittest.main()
