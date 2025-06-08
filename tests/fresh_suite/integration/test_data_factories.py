"""
Test data factories for integration tests.

This module provides utilities for creating test CSV files, configuration data,
and other test artifacts needed for service integration testing. It follows
the established patterns and provides realistic test data for various scenarios.
"""
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class TestGraphSpec:
    """Specification for generating test graph data."""
    graph_name: str
    nodes: List[Dict[str, Any]]
    description: str = ""
    

class CSVTestDataFactory:
    """Factory for creating test CSV files and graph data."""
    
    @staticmethod
    def create_simple_linear_graph() -> TestGraphSpec:
        """Create a simple linear graph for basic integration testing."""
        nodes = [
            {
                "GraphName": "simple_linear",
                "Node": "start",
                "AgentType": "Default",
                "Prompt": "Start the workflow",
                "Description": "Initial node that starts processing",
                "Input_Fields": "user_input",
                "Output_Field": "start_output",
                "Edge": "middle",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "simple_linear",
                "Node": "middle",
                "AgentType": "Default", 
                "Prompt": "Process the data",
                "Description": "Middle processing node",
                "Input_Fields": "start_output",
                "Output_Field": "middle_output",
                "Edge": "end",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "simple_linear",
                "Node": "end",
                "AgentType": "Default",
                "Prompt": "Finalize the result",
                "Description": "Final node that completes processing",
                "Input_Fields": "middle_output",
                "Output_Field": "final_result",
                "Edge": "",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            }
        ]
        
        return TestGraphSpec(
            graph_name="simple_linear",
            nodes=nodes,
            description="A simple three-node linear workflow for basic integration testing"
        )
    
    @staticmethod
    def create_conditional_branching_graph() -> TestGraphSpec:
        """Create a graph with conditional branching for advanced integration testing."""
        nodes = [
            {
                "GraphName": "conditional_branch",
                "Node": "input_validator",
                "AgentType": "Default",
                "Prompt": "Validate the input data",
                "Description": "Validates input and determines processing path",
                "Input_Fields": "raw_input",
                "Output_Field": "validation_result",
                "Edge": "",
                "Context": "",
                "Success_Next": "success_processor",
                "Failure_Next": "error_handler"
            },
            {
                "GraphName": "conditional_branch",
                "Node": "success_processor",
                "AgentType": "Default",
                "Prompt": "Process valid data",
                "Description": "Processes data when validation succeeds",
                "Input_Fields": "validation_result",
                "Output_Field": "processed_data",
                "Edge": "output_formatter",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "conditional_branch",
                "Node": "error_handler",
                "AgentType": "Default",
                "Prompt": "Handle validation errors",
                "Description": "Handles cases where validation fails",
                "Input_Fields": "validation_result",
                "Output_Field": "error_message",
                "Edge": "output_formatter",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "conditional_branch",
                "Node": "output_formatter",
                "AgentType": "Default",
                "Prompt": "Format the final output",
                "Description": "Formats final output regardless of processing path",
                "Input_Fields": "processed_data|error_message",
                "Output_Field": "final_output",
                "Edge": "",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            }
        ]
        
        return TestGraphSpec(
            graph_name="conditional_branch",
            nodes=nodes,
            description="A graph with conditional branching for testing success/failure routing"
        )
    
    @staticmethod
    def create_multi_graph_csv() -> List[TestGraphSpec]:
        """Create multiple graphs in a single CSV for testing multi-graph scenarios."""
        graph1 = CSVTestDataFactory.create_simple_linear_graph()
        graph1.graph_name = "first_graph"
        for node in graph1.nodes:
            node["GraphName"] = "first_graph"
        
        graph2_nodes = [
            {
                "GraphName": "second_graph",
                "Node": "alpha",
                "AgentType": "Default",
                "Prompt": "Alpha processing",
                "Description": "First node in second graph",
                "Input_Fields": "alpha_input",
                "Output_Field": "alpha_output",
                "Edge": "beta",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "second_graph",
                "Node": "beta",
                "AgentType": "Default",
                "Prompt": "Beta processing",
                "Description": "Second node in second graph",
                "Input_Fields": "alpha_output",
                "Output_Field": "beta_output",
                "Edge": "",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            }
        ]
        
        graph2 = TestGraphSpec(
            graph_name="second_graph",
            nodes=graph2_nodes,
            description="Second graph for multi-graph testing"
        )
        
        return [graph1, graph2]
    
    @staticmethod
    def create_invalid_csv_samples() -> Dict[str, str]:
        """Create various invalid CSV samples for error handling testing."""
        return {
            "missing_headers": "Node,AgentType,Prompt\ntest_node,Default,test prompt",  # Missing GraphName header
            "empty_file": "",
            "malformed_csv": "GraphName,Node,AgentType\ntest_graph,node1,Default,extra_unmatched_data",  # Too many columns in data row
            "missing_required_fields": "Node\nnode1",  # Missing GraphName column
            "duplicate_nodes": '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,node1,Default,First,First node,input,output,
test_graph,node1,Default,Duplicate,Duplicate node,input,output,''',
            "circular_references": '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,node1,Default,First,First node,input,output,node2
test_graph,node2,Default,Second,Second node,output,result,node1''',
            "invalid_edge_targets": '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,node1,Default,First,First node,input,output,nonexistent_node'''
        }
    
    @staticmethod
    def convert_graph_spec_to_csv(graph_specs: List[TestGraphSpec]) -> str:
        """
        Convert TestGraphSpec objects to CSV string format.
        
        Args:
            graph_specs: List of TestGraphSpec objects to convert
            
        Returns:
            CSV string representation
        """
        if not graph_specs:
            return ""
        
        # Get all unique field names from all nodes
        all_fields = set()
        for spec in graph_specs:
            for node in spec.nodes:
                all_fields.update(node.keys())
        
        # Create header row
        headers = sorted(all_fields)
        csv_lines = [",".join(headers)]
        
        # Add data rows
        for spec in graph_specs:
            for node in spec.nodes:
                row = []
                for header in headers:
                    value = str(node.get(header, ""))
                    # Escape commas in values
                    if "," in value:
                        value = f'"{value}"'
                    row.append(value)
                csv_lines.append(",".join(row))
        
        return "\n".join(csv_lines)


class ConfigTestDataFactory:
    """Factory for creating test configuration files and data."""
    
    @staticmethod
    def create_minimal_config() -> Dict[str, Any]:
        """Create minimal configuration for basic service testing."""
        return {
            "logging": {
                "level": "DEBUG",
                "format": "[%(levelname)s] %(name)s: %(message)s"
            },
            "execution": {
                "max_retries": 1,
                "timeout": 10,
                "tracking": {
                    "enabled": True,
                    "track_inputs": False,
                    "track_outputs": False
                }
            }
        }
    
    @staticmethod
    def create_full_integration_config(temp_dir: str) -> Dict[str, Any]:
        """
        Create comprehensive configuration for full integration testing.
        
        Args:
            temp_dir: Temporary directory path for test files
            
        Returns:
            Full configuration dictionary
        """
        return {
            "logging": {
                "level": "DEBUG",
                "format": "[%(levelname)s] %(name)s: %(message)s"
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_anthropic_key",
                    "model": "claude-3-sonnet-20240229",
                    "temperature": 0.7
                },
                "openai": {
                    "api_key": "test_openai_key",
                    "model": "gpt-3.5-turbo",
                    "temperature": 0.7
                }
            },
            "execution": {
                "max_retries": 3,
                "timeout": 30,
                "tracking": {
                    "enabled": True,
                    "track_inputs": True,
                    "track_outputs": False
                }
            },
            "paths": {
                "csv_data": f"{temp_dir}/csv_data",
                "compiled_graphs": f"{temp_dir}/compiled",
                "custom_agents": f"{temp_dir}/custom_agents",
                "functions": f"{temp_dir}/functions"
            },
            "storage_config_path": f"{temp_dir}/storage_config.yaml"
        }
    
    @staticmethod
    def create_storage_config(temp_dir: str) -> Dict[str, Any]:
        """
        Create storage configuration for integration testing.
        
        Args:
            temp_dir: Temporary directory path for storage files
            
        Returns:
            Storage configuration dictionary
        """
        return {
            "csv": {
                "default_directory": f"{temp_dir}/csv_storage",
                "collections": {}
            },
            "json": {
                "default_directory": f"{temp_dir}/json_storage",
                "collections": {}
            },
            "kv": {
                "default_provider": "local",
                "collections": {
                    "test_kv": {
                        "provider": "local",
                        "settings": {
                            "file_path": f"{temp_dir}/test_kv.json"
                        }
                    }
                }
            },
            "vector": {
                "default_provider": "chroma",
                "collections": {
                    "test_vectors": {
                        "provider": "chroma",
                        "settings": {
                            "persist_directory": f"{temp_dir}/vector_storage"
                        }
                    }
                }
            }
        }
    
    @staticmethod
    def write_config_file(config_data: Dict[str, Any], file_path: Path) -> None:
        """
        Write configuration data to YAML file.
        
        Args:
            config_data: Configuration dictionary to write
            file_path: Path where to write the configuration file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)


class ExecutionTestDataFactory:
    """Factory for creating test execution data and scenarios."""
    
    @staticmethod
    def create_simple_execution_state() -> Dict[str, Any]:
        """Create simple execution state for basic testing."""
        return {
            "user_input": "test input data",
            "session_id": "test_session_123",
            "timestamp": "2025-06-05T12:00:00Z"
        }
    
    @staticmethod
    def create_complex_execution_state() -> Dict[str, Any]:
        """Create complex execution state for advanced testing scenarios."""
        return {
            "user_input": "complex test data with multiple fields",
            "session_id": "complex_session_456",
            "timestamp": "2025-06-05T12:00:00Z",
            "user_context": {
                "user_id": "test_user_789",
                "preferences": {
                    "language": "en",
                    "format": "json"
                }
            },
            "processing_options": {
                "validation_level": "strict",
                "output_format": "detailed",
                "include_metadata": True
            },
            "environment": {
                "test_mode": True,
                "debug_enabled": True
            }
        }
    
    @staticmethod
    def create_error_scenarios() -> Dict[str, Dict[str, Any]]:
        """Create various error scenarios for error handling testing."""
        return {
            "invalid_input": {
                "user_input": None,
                "session_id": "error_test_1"
            },
            "missing_required_field": {
                "session_id": "error_test_2"
                # Missing user_input intentionally
            },
            "malformed_data": {
                "user_input": {"invalid": "structure"},
                "session_id": "error_test_3"
            },
            "oversized_input": {
                "user_input": "x" * 10000,  # Very large input
                "session_id": "error_test_4"
            }
        }


class IntegrationTestDataManager:
    """
    Manager class for coordinating test data creation and cleanup.
    
    This class provides a unified interface for creating, managing,
    and cleaning up test data used in integration tests.
    """
    
    def __init__(self, temp_dir: Path):
        """
        Initialize test data manager.
        
        Args:
            temp_dir: Temporary directory for test files
        """
        self.temp_dir = Path(temp_dir)
        self.csv_factory = CSVTestDataFactory()
        self.config_factory = ConfigTestDataFactory()
        self.execution_factory = ExecutionTestDataFactory()
    
    def create_test_csv_file(self, graph_spec: TestGraphSpec, filename: str = None) -> Path:
        """
        Create a test CSV file from graph specification.
        
        Args:
            graph_spec: Graph specification to convert to CSV
            filename: Optional filename, defaults to graph_name.csv
            
        Returns:
            Path to created CSV file
        """
        if filename is None:
            filename = f"{graph_spec.graph_name}.csv"
        
        csv_content = self.csv_factory.convert_graph_spec_to_csv([graph_spec])
        csv_path = self.temp_dir / "csv_data" / filename
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(csv_content, encoding='utf-8')
        
        return csv_path
    
    def create_multi_graph_csv_file(self, graph_specs: List[TestGraphSpec], filename: str = "multi_graph.csv") -> Path:
        """
        Create a CSV file containing multiple graphs.
        
        Args:
            graph_specs: List of graph specifications
            filename: Name of the CSV file to create
            
        Returns:
            Path to created CSV file
        """
        csv_content = self.csv_factory.convert_graph_spec_to_csv(graph_specs)
        csv_path = self.temp_dir / "csv_data" / filename
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(csv_content, encoding='utf-8')
        
        return csv_path
    
    def setup_complete_test_environment(self) -> Dict[str, Path]:
        """
        Set up complete test environment with all necessary files and directories.
        
        Returns:
            Dictionary mapping resource names to their paths
        """
        # Create directory structure
        directories = [
            self.temp_dir / "csv_data",
            self.temp_dir / "compiled",
            self.temp_dir / "storage",
            self.temp_dir / "logs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create configuration files
        config_data = self.config_factory.create_full_integration_config(str(self.temp_dir))
        config_path = self.temp_dir / "config.yaml"
        self.config_factory.write_config_file(config_data, config_path)
        
        storage_data = self.config_factory.create_storage_config(str(self.temp_dir))
        storage_path = self.temp_dir / "storage_config.yaml"
        self.config_factory.write_config_file(storage_data, storage_path)
        
        # Create sample CSV files
        simple_graph = self.csv_factory.create_simple_linear_graph()
        simple_csv_path = self.create_test_csv_file(simple_graph, "simple_test.csv")
        
        conditional_graph = self.csv_factory.create_conditional_branching_graph()
        conditional_csv_path = self.create_test_csv_file(conditional_graph, "conditional_test.csv")
        
        multi_graphs = self.csv_factory.create_multi_graph_csv()
        multi_csv_path = self.create_multi_graph_csv_file(multi_graphs, "multi_graph_test.csv")
        
        return {
            "config": config_path,
            "storage_config": storage_path,
            "simple_csv": simple_csv_path,
            "conditional_csv": conditional_csv_path,
            "multi_csv": multi_csv_path,
            "csv_dir": self.temp_dir / "csv_data",
            "compiled_dir": self.temp_dir / "compiled",
            "storage_dir": self.temp_dir / "storage"
        }
