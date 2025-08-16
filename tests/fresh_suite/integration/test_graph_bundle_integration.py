"""
GraphBundle Service Integration Tests.

This module tests the GraphBundleService using real services instead of mocks
to catch signature mismatches and integration issues. These tests verify that
the service correctly integrates with ProtocolBasedRequirementsAnalyzer,
DIContainerAnalyzer, and other dependencies in the actual runtime environment.
"""

import unittest
import json
from pathlib import Path
from typing import Dict, Any

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.models.graph_bundle import GraphBundle


class TestGraphBundleIntegration(BaseIntegrationTest):
    """
    Integration tests for GraphBundleService with real service dependencies.
    
    These tests verify end-to-end functionality using actual service instances
    from the DI container, ensuring proper service coordination and catching
    integration issues that unit tests with mocks might miss.
    """
    
    def setup_services(self):
        """Initialize real service instances for integration testing."""
        super().setup_services()
        
        # Core services needed for GraphBundleService
        self.csv_parser_service = self.container.csv_graph_parser_service()
        self.protocol_analyzer = self.container.protocol_requirements_analyzer()
        self.agent_factory_service = self.container.agent_factory_service()
        
        # Create DIContainerAnalyzer manually to avoid agentmap.cli.utils import issue
        from agentmap.services.di_container_analyzer import DIContainerAnalyzer
        self.di_container_analyzer = DIContainerAnalyzer(self.container, self.logging_service)
        
        # Create GraphBundleService manually with all dependencies
        from agentmap.services.graph.graph_bundle_service import GraphBundleService
        self.graph_bundle_service = GraphBundleService(
            logging_service=self.logging_service,
            csv_parser=self.csv_parser_service,
            protocol_requirements_analyzer=self.protocol_analyzer,
            di_container_analyzer=self.di_container_analyzer,
            agent_factory_service=self.agent_factory_service
        )
        
        # Verify service initialization
        self.assert_service_created(self.graph_bundle_service, "GraphBundleService")
        self.assert_service_created(self.csv_parser_service, "CSVGraphParserService")
        self.assert_service_created(self.protocol_analyzer, "ProtocolBasedRequirementsAnalyzer")
        self.assert_service_created(self.agent_factory_service, "AgentFactoryService")
        
        # Verify enhanced dependencies are available
        self.assertTrue(
            self.graph_bundle_service._has_enhanced_dependencies,
            "GraphBundleService should have enhanced dependencies for metadata bundle creation"
        )
    
    def test_graph_bundle_with_real_analyzer(self):
        """
        Test metadata bundle creation using real ProtocolBasedRequirementsAnalyzer.
        
        This test verifies that the GraphBundleService correctly integrates with
        the real ProtocolBasedRequirementsAnalyzer using the fixed signature
        (nodes parameter instead of CSV path).
        """
        # Create test CSV content with realistic graph structure
        csv_content = self._create_realistic_test_csv()
        csv_path = self.create_test_csv_file(csv_content, "integration_test_graph.csv")
        
        # Verify CSV file was created
        self.assert_file_exists(csv_path, "Integration test CSV file")
        
        # Test metadata bundle creation with real services
        try:
            bundle = self.graph_bundle_service.create_metadata_bundle(
                csv_path=csv_path,
                graph_name="integration_test_graph"
            )
            
            # Verify bundle was created successfully
            self.assertIsNotNone(bundle, "Bundle should be created successfully")
            self.assertIsInstance(bundle, GraphBundle, "Result should be a GraphBundle")
            self.assertTrue(bundle.is_metadata_only, "Bundle should be metadata-only")
            
            # Verify bundle contains expected metadata
            self.assertEqual(bundle.graph_name, "integration_test_graph")
            self.assertIsInstance(bundle.nodes, dict, "Bundle should contain nodes dictionary")
            self.assertGreater(len(bundle.nodes), 0, "Bundle should have at least one node")
            
            # Verify required agents and services were analyzed
            self.assertIsInstance(bundle.required_agents, set, "Required agents should be a set")
            self.assertIsInstance(bundle.required_services, set, "Required services should be a set")
            self.assertGreater(len(bundle.required_services), 0, "Should have required services")
            
            # Verify CSV hash was generated
            self.assertIsNotNone(bundle.csv_hash, "Bundle should have CSV hash")
            self.assertIsInstance(bundle.csv_hash, str, "CSV hash should be string")
            
            # Verify the bundle can validate against the original CSV
            validation_result = self.graph_bundle_service.validate_bundle(bundle, csv_content)
            self.assertTrue(validation_result, "Bundle should validate against original CSV")
            
            print(
                f"Successfully created metadata bundle with {len(bundle.nodes)} nodes, "
                f"{len(bundle.required_agents)} agent types, "
                f"{len(bundle.required_services)} services"
            )
            
        except Exception as e:
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            self.fail(f"Metadata bundle creation failed with error: {e}")
    
    def test_metadata_bundle_csv_roundtrip(self):
        """
        Test complete roundtrip: CSV → Bundle → Save → Load → Validate.
        
        This test verifies the full lifecycle of metadata bundle operations,
        ensuring all components work together correctly.
        """
        # Create test CSV with multiple node types
        csv_content = self._create_multi_agent_test_csv()
        csv_path = self.create_test_csv_file(csv_content, "roundtrip_test_graph.csv")
        
        # Step 1: Create metadata bundle from CSV
        original_bundle = self.graph_bundle_service.create_metadata_bundle(
            csv_path=csv_path,
            graph_name="roundtrip_test"
        )
        
        self.assertIsNotNone(original_bundle, "Original bundle should be created")
        
        # Step 2: Save bundle to file
        bundle_path = Path(self.temp_dir) / "roundtrip_test_bundle.json"
        self.graph_bundle_service.save_bundle(original_bundle, bundle_path)
        
        # Verify bundle file was created with correct extension
        expected_json_path = bundle_path.with_suffix('.json')
        self.assert_file_exists(expected_json_path, "Saved bundle JSON file")
        
        # Step 3: Load bundle from file
        loaded_bundle = self.graph_bundle_service.load_bundle(expected_json_path)
        
        self.assertIsNotNone(loaded_bundle, "Loaded bundle should not be None")
        self.assertIsInstance(loaded_bundle, GraphBundle, "Loaded object should be GraphBundle")
        self.assertTrue(loaded_bundle.is_metadata_only, "Loaded bundle should be metadata-only")
        
        # Step 4: Verify bundle integrity after roundtrip
        self.assertEqual(
            original_bundle.graph_name, loaded_bundle.graph_name,
            "Graph name should be preserved"
        )
        self.assertEqual(
            len(original_bundle.nodes), len(loaded_bundle.nodes),
            "Node count should be preserved"
        )
        self.assertEqual(
            original_bundle.required_agents, loaded_bundle.required_agents,
            "Required agents should be preserved"
        )
        self.assertEqual(
            original_bundle.required_services, loaded_bundle.required_services,
            "Required services should be preserved"
        )
        self.assertEqual(
            original_bundle.csv_hash, loaded_bundle.csv_hash,
            "CSV hash should be preserved"
        )
        
        # Step 5: Validate both bundles against original CSV
        original_validation = self.graph_bundle_service.validate_bundle(original_bundle, csv_content)
        loaded_validation = self.graph_bundle_service.validate_bundle(loaded_bundle, csv_content)
        
        self.assertTrue(original_validation, "Original bundle should validate against CSV")
        self.assertTrue(loaded_validation, "Loaded bundle should validate against CSV")
        
        # Step 6: Verify JSON structure is as expected
        with expected_json_path.open('r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        self.assertEqual(json_data["format"], "metadata", "JSON should have metadata format")
        self.assertEqual(json_data["graph_name"], "roundtrip_test", "JSON should preserve graph name")
        self.assertIn("nodes", json_data, "JSON should contain nodes")
        self.assertIn("required_agents", json_data, "JSON should contain required agents")
        self.assertIn("required_services", json_data, "JSON should contain required services")
        self.assertIn("csv_hash", json_data, "JSON should contain CSV hash")
        
        print(
            f"Successfully completed roundtrip test with {len(loaded_bundle.nodes)} nodes"
        )
    
    def test_metadata_bundle_from_content_string(self):
        """
        Test metadata bundle creation from CSV content string.
        
        This tests the create_metadata_bundle_from_content method to ensure
        it properly handles string content without requiring file I/O.
        """
        # Create CSV content string directly
        csv_content = self._create_realistic_test_csv()
        
        # Create bundle from content string
        bundle = self.graph_bundle_service.create_metadata_bundle_from_content(
            csv_content=csv_content,
            graph_name="content_string_test"
        )
        
        # Verify bundle creation
        self.assertIsNotNone(bundle, "Bundle should be created from content string")
        self.assertTrue(bundle.is_metadata_only, "Bundle should be metadata-only")
        self.assertEqual(bundle.graph_name, "content_string_test")
        
        # Verify content analysis worked
        self.assertGreater(len(bundle.nodes), 0, "Should have parsed nodes from content")
        self.assertGreater(len(bundle.required_services), 0, "Should have analyzed required services")
        
        # Verify hash generation
        self.assertIsNotNone(bundle.csv_hash, "Should have generated CSV hash")
        
        # Verify validation against original content
        validation_result = self.graph_bundle_service.validate_bundle(bundle, csv_content)
        self.assertTrue(validation_result, "Bundle should validate against original content string")
    
    def test_service_dependency_analysis_integration(self):
        """
        Test that service dependency analysis correctly identifies all required services.
        
        This test verifies that the integration between ProtocolBasedRequirementsAnalyzer
        and DIContainerAnalyzer correctly identifies the full dependency tree.
        """
        # Create CSV with agents that need different services
        csv_content = self._create_multi_service_test_csv()
        csv_path = self.create_test_csv_file(csv_content, "dependency_analysis_test.csv")
        
        # Create bundle and analyze dependencies
        bundle = self.graph_bundle_service.create_metadata_bundle(
            csv_path=csv_path,
            graph_name="dependency_test"
        )
        
        # Verify basic services are included
        expected_base_services = {
            "state_adapter_service",
            "execution_tracking_service"
        }
        
        for service in expected_base_services:
            self.assertIn(
                service, bundle.required_services,
                f"Bundle should include base service: {service}"
            )
        
        # Verify the dependency analysis found transitive dependencies
        # (The exact services depend on what the test agents require)
        self.assertGreater(
            len(bundle.required_services), len(expected_base_services),
            "Should have more than just base services due to agent dependencies"
        )
        
        # Log discovered dependencies for debugging
        print(f"Discovered required services: {sorted(bundle.required_services)}")
        print(f"Discovered required agents: {sorted(bundle.required_agents)}")
    
    def _create_realistic_test_csv(self) -> str:
        """Create realistic CSV content for integration testing."""
        return '''Graph,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Edge
integration_test,start_node,Default,Start the integration test,Initial processing node,test_input,processed_data,analysis_node
integration_test,analysis_node,Default,Analyze the processed data,Data analysis node,processed_data,analysis_result,end_node
integration_test,end_node,Default,Complete the test,Final processing node,analysis_result,final_output,
'''
    
    def _create_multi_agent_test_csv(self) -> str:
        """Create CSV content with multiple different agent types."""
        return '''Graph,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Edge
roundtrip_test,input_node,Default,Process input data,Input processing,raw_input,clean_input,llm_node
roundtrip_test,llm_node,LLM,Analyze the input with AI,LLM analysis node,clean_input,ai_analysis,storage_node
roundtrip_test,storage_node,Default,Store the results,Storage node,ai_analysis,stored_result,output_node
roundtrip_test,output_node,Default,Format final output,Output formatting,stored_result,final_result,
'''
    
    def _create_multi_service_test_csv(self) -> str:
        """Create CSV content that requires multiple different services."""
        return '''Graph,Node,Agent_Type,Prompt,Description,Input_Fields,Output_Field,Edge
dependency_test,data_node,Default,Load initial data,Data loading node,raw_data,loaded_data,process_node
dependency_test,process_node,Default,Process the data,Processing node,loaded_data,processed_data,ai_node
dependency_test,ai_node,LLM,Use AI for analysis,AI analysis node,processed_data,ai_result,final_node
dependency_test,final_node,Default,Generate final output,Final output node,ai_result,final_output,
'''


if __name__ == '__main__':
    unittest.main()
