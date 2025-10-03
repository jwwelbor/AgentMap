import sys
from pathlib import Path
from unittest.mock import Mock

from agentmap.services.graph.scaffold.agent_scaffolder import AgentScaffolder
from agentmap.services.graph.scaffold.templates import Templates
from agentmap.services.graph.scaffold.service_requirements_parser import ServiceRequirementsParser
from agentmap.services.indented_template_composer import IndentedTemplateComposer

# Add tests directory to path to allow import
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

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
            
        @staticmethod
        def create_mock_custom_agent_declaration_manager():
            mock = Mock()
            mock.add_or_update_agent = Mock()
            return mock

def test_agent_scaffolder_writes_file(tmp_path: Path):
    """Test that AgentScaffolder writes a file with proper dependency injection."""
    out_dir = tmp_path  # AgentScaffolder expects a directory, not a file path
    
    # Create all required dependencies using MockServiceFactory following established patterns
    mock_app_config = MockServiceFactory.create_mock_app_config_service()
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_declaration_manager = MockServiceFactory.create_mock_custom_agent_declaration_manager()
    
    # Create IndentedTemplateComposer with required dependencies
    composer = IndentedTemplateComposer(mock_app_config, mock_logging)
    
    # Create Templates with the composer
    templates = Templates(composer)
    
    # Create ServiceRequirementsParser (no dependencies)
    service_parser = ServiceRequirementsParser()
    
    # Create AgentScaffolder with all required dependencies
    scaff = AgentScaffolder(templates, service_parser, mock_declaration_manager, mock_logging)
    
    # Test scaffolding operation with proper info structure
    info = {
        "node_name": "MyNode",
        "description": "Test agent description",
        "input_fields": ["input1", "input2"],
        "output_field": "output1",
        "prompt": "Test prompt",
        "context": "Test context"
    }
    res = scaff.scaffold("My", info, out_dir)
    
    # AgentScaffolder creates the filename internally: {agent_type.lower()}_agent.py
    expected_file = out_dir / "my_agent.py"
    
    assert res == expected_file
    assert expected_file.exists()
    assert "class MyAgent" in expected_file.read_text(encoding="utf-8")
