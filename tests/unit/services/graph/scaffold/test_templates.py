"""
Unit tests for Templates service.

These tests validate the Templates service using proper dependency injection
with MockServiceFactory following established testing patterns.
"""

import sys
import os
import unittest

# Add tests directory to path to allow import  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

from agentmap.services.graph.scaffold.templates import Templates
from agentmap.services.indented_template_composer import IndentedTemplateComposer
from agentmap.models.scaffold_types import ServiceRequirements

try:
    from tests.utils.mock_service_factory import MockServiceFactory
except ImportError:
    # Fallback: create basic mocks manually if MockServiceFactory not available
    from unittest.mock import Mock
    
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


class TestTemplates(unittest.TestCase):
    """Test Templates functionality with proper dependency injection."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        # Create mock dependencies following established patterns
        self.mock_app_config = MockServiceFactory.create_mock_app_config_service()
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        
        # Create IndentedTemplateComposer with required dependencies
        self.composer = IndentedTemplateComposer(
            app_config_service=self.mock_app_config,
            logging_service=self.mock_logging
        )
        
        # Create Templates service under test
        self.templates = Templates(self.composer)

    def test_render_agent_contains_class(self):
        """Test that render_agent returns code containing the agent class."""
        # Create test service requirements with all required parameters
        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={}
        )
        
        # Call render_agent with minimal info structure
        info = {"attrs": {}}
        code = self.templates.render_agent("My", info, service_reqs)
        
        # Verify the code contains the expected class definition
        self.assertIn("class MyAgent", code)

    def test_render_function_contains_def(self):
        """Test that render_function returns code containing the function definition."""
        # Call render_function with minimal info structure
        info = {"params": {}}
        code = self.templates.render_function("do_stuff", info)
        
        # Verify the code contains the expected function definition
        self.assertIn("def do_stuff", code)

    def test_initialization(self):
        """Test Templates service initialization."""
        self.assertIsNotNone(self.templates)
        self.assertEqual(self.templates.composer, self.composer)


if __name__ == "__main__":
    unittest.main()