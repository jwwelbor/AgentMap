"""
Base integration test class for service integration tests.

This module provides the foundation for integration tests that verify real service
coordination using actual DI container instances. It follows the established patterns
from test_core_container.py while focusing on service workflow testing.
"""
import unittest
import tempfile
import shutil
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.di import initialize_di
from tests.utils.service_interface_auditor import ServiceInterfaceAuditor


class BaseIntegrationTest(unittest.TestCase):
    """
    Base class for service integration tests using real DI container.
    
    This class provides:
    - Real DI container setup with test configuration
    - Temporary directory management for test files
    - Service instance initialization following established patterns
    - Cleanup and resource management
    
    Subclasses should override setup_services() to initialize the specific
    services they need for testing.
    """
    
    def setUp(self):
        """Set up test fixtures with real DI container."""
        # Create temporary directory for test files and configurations
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test configuration following established patterns
        self.test_config_path = self._create_test_config()
        
        # Initialize real DI container with test configuration
        self.container = initialize_di(str(self.test_config_path))
        
        # Initialize service interface auditor for validation
        self.service_auditor = ServiceInterfaceAuditor()
        
        # Set up specific services (to be overridden by subclasses)
        self.setup_services()
    
    def tearDown(self):
        """Clean up test fixtures and temporary resources."""
        # Clean up temporary directory and all test files
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def setup_services(self):
        """
        Initialize real service instances from DI container.
        
        Subclasses should override this method to set up the specific
        services they need for integration testing. For example:
        
        def setup_services(self):
            self.graph_runner_service = self.container.graph_runner_service()
            self.graph_definition_service = self.container.graph_definition_service()
        """
        # Base implementation initializes common services
        self.logging_service = self.container.logging_service()
        self.app_config_service = self.container.app_config_service()
    
    def _create_test_config(self) -> Path:
        """
        Create comprehensive test configuration file for integration tests.
        
        This configuration includes all necessary settings for service integration
        testing, following the established pattern from test_core_container.py.
        
        Returns:
            Path to the created test configuration file
        """
        config_path = Path(self.temp_dir) / "integration_test_config.yaml"
        storage_config_path = Path(self.temp_dir) / "storage_config.yaml"
        
        # Use Python's yaml module to safely create configuration
        # This avoids Windows path escaping issues entirely
        config_data = {
            "logging": {
                "level": "DEBUG",
                "format": "[%(levelname)s] %(name)s: %(message)s"
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_key_anthropic",
                    "model": "claude-3-sonnet-20240229",
                    "temperature": 0.7
                },
                "openai": {
                    "api_key": "test_key_openai",
                    "model": "gpt-3.5-turbo",
                    "temperature": 0.7
                }
            },
            "routing": {
                "complexity_analysis": {
                    "prompt_length_thresholds": {
                        "low": 100,
                        "medium": 300,
                        "high": 800
                    },
                    "methods": {
                        "prompt_length": True,
                        "keyword_analysis": True,
                        "context_analysis": True,
                        "memory_analysis": True,
                        "structure_analysis": True
                    },
                    "keyword_weights": {
                        "complexity_keywords": 0.4,
                        "task_specific_keywords": 0.3,
                        "prompt_structure": 0.3
                    },
                    "context_analysis": {
                        "memory_size_threshold": 10,
                        "input_field_count_threshold": 5
                    }
                },
                "task_types": {
                    "general": {
                        "default_complexity": "medium",
                        "providers": ["anthropic", "openai"],
                        "provider_preference": ["anthropic", "openai"]
                    }
                },
                "routing_matrix": {
                    "general": {
                        "low": "openai",
                        "medium": "anthropic",
                        "high": "anthropic",
                        "critical": "anthropic"
                    }
                }
            },
            "execution": {
                "max_retries": 3,
                "timeout": 30,
                "tracking": {
                    "enabled": True,
                    "track_inputs": False,
                    "track_outputs": False
                }
            },
            "paths": {
                "csv_data": str(Path(self.temp_dir) / "csv_data"),
                "compiled_graphs": str(Path(self.temp_dir) / "compiled"),
                "custom_agents": str(Path(self.temp_dir) / "custom_agents"),
                "functions": str(Path(self.temp_dir) / "functions")
            },
            "storage_config_path": str(storage_config_path)
        }
        
        # Create storage configuration data
        storage_config_data = {
            "csv": {
                "default_directory": str(Path(self.temp_dir) / "csv_data"),
                "collections": {}
            },
            "vector": {
                "default_provider": "chroma",
                "collections": {
                    "test_collection": {
                        "provider": "chroma",
                        "settings": {
                            "persist_directory": str(Path(self.temp_dir) / "vector_data")
                        }
                    }
                }
            },
            "kv": {
                "default_provider": "local",
                "collections": {
                    "test_kv": {
                        "provider": "local",
                        "settings": {
                            "file_path": str(Path(self.temp_dir) / "kv_data.json")
                        }
                    }
                }
            },
            "json": {
                "default_directory": str(Path(self.temp_dir) / "json_data"),
                "collections": {}
            },
            "file": {
                "default_directory": str(Path(self.temp_dir) / "file_data"),
                "collections": {}
            }
        }
        
        # Write configuration files using yaml.dump for safety
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
        with open(storage_config_path, 'w') as f:
            yaml.dump(storage_config_data, f, default_flow_style=False, indent=2)
        
        # Create necessary directories
        (Path(self.temp_dir) / "csv_data").mkdir(parents=True, exist_ok=True)
        (Path(self.temp_dir) / "compiled").mkdir(parents=True, exist_ok=True)
        (Path(self.temp_dir) / "custom_agents").mkdir(parents=True, exist_ok=True)
        (Path(self.temp_dir) / "functions").mkdir(parents=True, exist_ok=True)
        
        return config_path
    
    def create_test_csv_file(self, content: str, filename: str = "test_graph.csv") -> Path:
        """
        Create a test CSV file with the given content.
        
        Args:
            content: CSV content as string
            filename: Name of the CSV file to create
            
        Returns:
            Path to the created CSV file
        """
        csv_path = Path(self.temp_dir) / "csv_data" / filename
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(content, encoding='utf-8')
        return csv_path
    
    def create_simple_test_graph_csv(self) -> str:
        """
        Create a simple test graph CSV content for integration testing.
        
        Returns:
            CSV content string with a basic two-node graph
        """
        return '''Graph,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,start_node,default,Start processing,Start node for testing,input_data,processed_data,end_node
test_graph,end_node,default,Finish processing,End node for testing,processed_data,final_result,
'''
    
    def create_complex_test_graph_csv(self) -> str:
        """
        Create a more complex test graph CSV content for advanced integration testing.
        
        Returns:
            CSV content string with a multi-node graph including conditional routing
        """
        return '''Graph,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Edge,Success_Next,Failure_Next
complex_graph,input_node,default,Process input data,Input processing node,raw_input,validated_input,validation_node,,
complex_graph,validation_node,default,Validate the input,Validation node,validated_input,validation_result,,process_node,error_node
complex_graph,process_node,default,Process validated data,Main processing node,validation_result,processed_output,output_node,,
complex_graph,error_node,default,Handle errors,Error handling node,validation_result,error_message,,,
complex_graph,output_node,default,Format final output,Output formatting node,processed_output,final_output,,,
'''
    
    def assert_service_created(self, service: Any, expected_class_name: str) -> None:
        """
        Assert that a service was created correctly with expected interface.
        
        Args:
            service: Service instance to validate
            expected_class_name: Expected class name of the service
        """
        self.assertIsNotNone(service, f"{expected_class_name} should not be None")
        self.assertEqual(type(service).__name__, expected_class_name)
        
        # Use service auditor to validate interface
        service_info = self.service_auditor.audit_service_interface(type(service))
        self.assertEqual(service_info.class_name, expected_class_name)
        self.assertGreater(len(service_info.public_methods), 0, 
                          f"{expected_class_name} should have public methods")
    
    def assert_file_exists(self, file_path: Path, description: str = "File") -> None:
        """
        Assert that a file exists and provide helpful error message.
        
        Args:
            file_path: Path to file that should exist
            description: Description of the file for error messages
        """
        self.assertTrue(file_path.exists(), 
                       f"{description} should exist at: {file_path}")
        self.assertTrue(file_path.is_file(), 
                       f"{description} should be a file: {file_path}")
    
    def assert_directory_exists(self, dir_path: Path, description: str = "Directory") -> None:
        """
        Assert that a directory exists and provide helpful error message.
        
        Args:
            dir_path: Path to directory that should exist
            description: Description of the directory for error messages
        """
        self.assertTrue(dir_path.exists(), 
                       f"{description} should exist at: {dir_path}")
        self.assertTrue(dir_path.is_dir(), 
                       f"{description} should be a directory: {dir_path}")
    
    def assert_graphs_equivalent(self, graph1, graph2, message_prefix: str = "Graphs") -> None:
        """
        Assert that two Graph objects are equivalent by comparing essential attributes.
        
        This avoids object identity issues when Node objects don't implement __eq__.
        
        Args:
            graph1: First graph to compare
            graph2: Second graph to compare
            message_prefix: Prefix for assertion error messages
        """
        self.assertEqual(graph1.name, graph2.name, f"{message_prefix} names should match")
        self.assertEqual(graph1.entry_point, graph2.entry_point, f"{message_prefix} entry points should match")
        self.assertEqual(len(graph1.nodes), len(graph2.nodes), f"{message_prefix} node counts should match")
        
        # Compare each node's essential attributes
        for node_name in graph1.nodes:
            self.assertIn(node_name, graph2.nodes, f"Node '{node_name}' should exist in both graphs")
            
            node1 = graph1.nodes[node_name]
            node2 = graph2.nodes[node_name]
            
            # Compare node attributes
            self.assertEqual(node1.name, node2.name, f"Node {node_name} names should match")
            self.assertEqual(node1.agent_type, node2.agent_type, f"Node {node_name} agent types should match")
            self.assertEqual(node1.prompt, node2.prompt, f"Node {node_name} prompts should match")
            self.assertEqual(node1.inputs, node2.inputs, f"Node {node_name} inputs should match")
            self.assertEqual(node1.output, node2.output, f"Node {node_name} outputs should match")
            self.assertEqual(node1.edges, node2.edges, f"Node {node_name} edges should match")
    
    def assert_service_has_logging(self, service: Any, service_name: str) -> None:
        """
        Assert that a service has logging capabilities.
        
        Handles different logging patterns: public 'logger' or private '_logger'.
        
        Args:
            service: Service instance to check
            service_name: Name of the service for error messages
        """
        # Check for logging capability - services may use different patterns
        has_logger = (hasattr(service, 'logger') and service.logger is not None) or \
                    (hasattr(service, '_logger') and service._logger is not None)
        
        self.assertTrue(has_logger, 
                      f"{service_name} should have logging capability (either 'logger' or '_logger' attribute)")
        
        # Verify the logger instance is valid
        logger_instance = getattr(service, 'logger', None) or getattr(service, '_logger', None)
        self.assertIsNotNone(logger_instance, 
                           f"{service_name} logger instance should not be None")
        
        # Check that the logger has basic logging methods
        basic_logging_methods = ['debug', 'info', 'warning', 'error']
        for method_name in basic_logging_methods:
            self.assertTrue(hasattr(logger_instance, method_name),
                          f"{service_name} logger should have '{method_name}' method")


class IntegrationTestCase(BaseIntegrationTest):
    """
    Alias for BaseIntegrationTest for backward compatibility.
    
    This allows tests to use either BaseIntegrationTest or IntegrationTestCase
    based on naming preferences.
    """
    pass
