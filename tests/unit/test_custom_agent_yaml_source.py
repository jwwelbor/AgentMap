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

    def test_load_agents_preserves_service_tokens(self) -> None:
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

        # Tokens are preserved verbatim; alias normalization happens at the
        # injection boundary, not during loading.
        declaration = agents["llm_vision"]
        self.assertEqual(
            [req.name for req in declaration.service_requirements], ["LLMService"]
        )

    def test_load_agents_accepts_host_service_tokens(self) -> None:
        """Host-registered service tokens load without raising.

        These are not built-in services, so they pass through loading; whether
        they actually exist is validated later at injection time.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source(Path(tmpdir))
            yaml_data = {
                "agents": {
                    "db_agent": {
                        "class_path": "app.agents.db.DbAgent",
                        "requires": {
                            "services": ["database_service"],
                            "protocols": ["DatabaseCapableAgent"],
                        },
                    }
                }
            }

            with patch(
                "agentmap.services.declaration_sources.custom_agent_yaml_source.load_yaml_file",
                return_value=yaml_data,
            ):
                agents = source.load_agents()

        declaration = agents["db_agent"]
        self.assertEqual(
            [req.name for req in declaration.service_requirements],
            ["database_service"],
        )


if __name__ == "__main__":
    unittest.main()
