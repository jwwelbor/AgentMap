import os
import sys
from pathlib import Path
from unittest.mock import Mock

from agentmap.services.graph.scaffold.function_scaffolder import FunctionScaffolder
from agentmap.services.graph.scaffold.templates import Templates
from agentmap.services.indented_template_composer import IndentedTemplateComposer

# Add tests directory to path to allow import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

try:
    from tests.utils.mock_service_factory import MockServiceFactory
except ImportError:
    # Fallback: create basic mocks manually
    class MockServiceFactory:
        @staticmethod
        def create_mock_app_config_service():
            mock = Mock()
            mock.get_prompts_config.return_value = {"directory": "prompts"}
            return mock

        @staticmethod
        def create_mock_logging_service():
            mock = Mock()
            mock_logger = Mock()
            mock_logger.debug = Mock()
            mock_logger.info = Mock()
            mock_logger.warning = Mock()
            mock_logger.error = Mock()
            mock.get_class_logger.return_value = mock_logger
            return mock


def test_function_scaffolder_writes_file(tmp_path: Path):
    """Test that FunctionScaffolder writes a function file successfully."""
    # Create mock services using MockServiceFactory pattern
    mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
    mock_logging_service = MockServiceFactory.create_mock_logging_service()

    # Configure prompts config for IndentedTemplateComposer
    mock_app_config_service.get_prompts_config.return_value = {"directory": "prompts"}

    # Create IndentedTemplateComposer with mocked dependencies
    composer = IndentedTemplateComposer(
        app_config_service=mock_app_config_service, logging_service=mock_logging_service
    )

    # Mock the template rendering to return basic function code
    composer._load_template_internal = Mock(
        return_value='def {func_name}(state: Dict[str, Any]) -> str:\n    """Edge function."""\n    return "success"'
    )

    # Create Templates with the mock composer
    templates = Templates(composer)

    # Create FunctionScaffolder with mocked dependencies
    scaff = FunctionScaffolder(templates, mock_logging_service)

    # Expected output file path
    out = tmp_path / "do_stuff.py"

    # Call scaffold method
    res = scaff.scaffold("do_stuff", {"params": {}}, tmp_path)

    # Verify result
    assert res == out
    assert out.exists()

    # Verify file content contains expected function definition
    content = out.read_text(encoding="utf-8")
    assert "def do_stuff" in content
