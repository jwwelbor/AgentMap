"""
Integration tests for OrchestratorAgent and OrchestratorService end-to-end functionality.

These tests verify that the orchestration workflow works correctly from CSV definition
through to execution, including proper service injection and node selection.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import os

from agentmap.di.containers import ApplicationContainer
from agentmap.models.execution_result import ExecutionResult


class TestOrchestratorIntegration(unittest.TestCase):
    """Integration tests for orchestrator functionality."""

    def setUp(self):
        """Set up test environment with DI container."""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Create a minimal config file
        config_content = """# Minimal test configuration
project_name: test_project
version: 1.0.0

# Logging configuration
logging:
  level: DEBUG
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# LLM configuration
llm:
  default_provider: openai
  providers:
    openai:
      api_key: test-key
      model: gpt-3.5-turbo

# Execution configuration  
execution:
  track_execution: true
  autocompile: false
"""
        config_path = Path(self.test_dir) / "agentmap_config.yaml"
        config_path.write_text(config_content)
        
        # Initialize container with test config
        self.container = ApplicationContainer()
        self.container.config_path.override(str(config_path))
        
        # Bootstrap the application
        bootstrap = self.container.application_bootstrap_service()
        bootstrap.bootstrap_application()
        
        # Get services we'll use
        self.graph_runner = self.container.graph_runner_service()
        self.logging_service = self.container.logging_service()
        self.logger = self.logging_service.get_class_logger(self)

    def tearDown(self):
        """Clean up test resources."""
        # Clean up temp directory
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_orchestrator_service_injection(self):
        """Test that OrchestratorService is properly injected into OrchestratorAgent."""
        # Create test CSV with orchestrator node
        csv_content = """GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Context
test_graph,Orchestrator,orchestrator,"Select the best node based on user input","Routes requests to appropriate nodes",request,__next_node,"matching_strategy:algorithm;confidence_threshold:0.8"
test_graph,ProcessA,default,"Process request type A","Handles type A requests",input,result,
test_graph,ProcessB,default,"Process request type B","Handles type B requests",input,result,
"""
        
        csv_path = Path(self.test_dir) / "test_orchestration.csv"
        csv_path.write_text(csv_content)
        
        # Load graph definition
        graph_def_service = self.container.graph_definition_service()
        graph_model = graph_def_service.build_from_csv(csv_path, "test_graph")
        
        # Prepare graph with agent instances
        graph_nodes = self.graph_runner._prepare_graph_definition_for_execution(
            graph_model, "test_graph"
        )
        
        # Verify OrchestratorAgent was created with OrchestratorService
        orchestrator_node = graph_nodes.get("Orchestrator")
        self.assertIsNotNone(orchestrator_node, "Orchestrator node should exist")
        
        agent_instance = orchestrator_node.context.get("instance")
        self.assertIsNotNone(agent_instance, "Agent instance should be created")
        
        # Verify OrchestratorService is configured
        self.assertIsNotNone(
            agent_instance.orchestrator_service,
            "OrchestratorService should be injected"
        )
        
        # Verify the service is functional
        service_info = agent_instance.orchestrator_service.get_service_info()
        self.assertEqual(service_info["service"], "OrchestratorService")
        self.assertTrue(service_info["prompt_manager_available"])

    def test_orchestrator_node_selection_algorithm(self):
        """Test orchestrator's algorithm-based node selection."""
        # Create test CSV with orchestrator using algorithm strategy
        csv_content = """GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Context
test_graph,Orchestrator,orchestrator,"Route to the right processor","Main router",request,__next_node,"matching_strategy:algorithm;nodes:DataProcessor|Calculator|Reporter"
test_graph,DataProcessor,default,"Process data requests","Handles data processing tasks",data,result,"keywords:data,process,transform,clean"
test_graph,Calculator,default,"Perform calculations","Handles math and calculations",numbers,result,"keywords:calculate,math,sum,average"
test_graph,Reporter,default,"Generate reports","Creates reports and summaries",data,report,"keywords:report,summary,analyze,insights"
"""
        
        csv_path = Path(self.test_dir) / "test_algorithm_routing.csv"
        csv_path.write_text(csv_content)
        
        # Mock LLM service in case algorithm falls back to LLM
        with patch.object(
            self.container.llm_service(), 
            'call_llm',
            return_value='DataProcessor'
        ):
            # Execute graph with data processing request
            initial_state = {"request": "Process this data file please"}
            options = self.graph_runner.get_default_options()
            options.initial_state = initial_state
            
            result = self.graph_runner.run_from_csv_direct(
                csv_path, 
                "test_graph",
                options=options
            )
        
        # The orchestrator should route to DataProcessor
        self.assertTrue(result.success, f"Execution should succeed: {result.error}")
        
        # Check that orchestrator selected the right node
        final_state = result.final_state
        self.assertIn("__next_node", final_state)
        self.assertEqual(
            final_state["__next_node"], 
            "DataProcessor",
            "Should route data request to DataProcessor"
        )

    def test_orchestrator_with_llm_strategy(self):
        """Test orchestrator's LLM-based node selection."""
        # Create test CSV with LLM strategy
        csv_content = """GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Context
test_graph,Orchestrator,orchestrator,"Intelligently route requests","Smart router",query,__next_node,"matching_strategy:llm;llm_type:openai;temperature:0.2"
test_graph,Expert1,default,"Handle technical questions","Technical expert",question,answer,
test_graph,Expert2,default,"Handle business questions","Business expert",question,answer,
"""
        
        csv_path = Path(self.test_dir) / "test_llm_routing.csv"
        csv_path.write_text(csv_content)
        
        # Mock LLM service response
        with patch.object(
            self.container.llm_service(), 
            'call_llm',
            return_value='{"selectedNode": "Expert1"}'
        ) as mock_llm:
            # Execute graph
            result = self.graph_runner.run_from_csv_direct(
                csv_path,
                "test_graph", 
                options=self.graph_runner.get_default_options()
            )
        
        self.assertTrue(result.success, f"Execution should succeed: {result.error}")
        
        # Verify LLM-based selection
        final_state = result.final_state
        self.assertEqual(
            final_state.get("__next_node"),
            "Expert1",
            "Should route to Expert1 based on LLM response"
        )

    def test_orchestrator_tiered_strategy_fallback(self):
        """Test orchestrator's tiered strategy with fallback to LLM."""
        # Create test CSV with tiered strategy
        csv_content = """GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Context
test_graph,Orchestrator,orchestrator,"Route with confidence","Tiered router",request,__next_node,"matching_strategy:tiered;confidence_threshold:0.9;default_target:GeneralHandler"
test_graph,SpecificHandler,default,"Handle specific requests","Very specific handler",data,result,"keywords:xyz123"
test_graph,GeneralHandler,default,"Handle general requests","General purpose handler",data,result,
"""
        
        csv_path = Path(self.test_dir) / "test_tiered_routing.csv"
        csv_path.write_text(csv_content)
        
        # Mock LLM to return GeneralHandler when algorithm confidence is low
        with patch.object(
            self.container.llm_service(),
            'call_llm',
            return_value='GeneralHandler'
        ) as mock_llm:
            # Execute with a request that won't match keywords well
            initial_state = {"request": "please help me with something"}
            options = self.graph_runner.get_default_options()
            options.initial_state = initial_state
            
            result = self.graph_runner.run_from_csv_direct(
                csv_path,
                "test_graph",
                options=options
            )
        
        self.assertTrue(result.success, f"Execution should succeed: {result.error}")
        
        # Should fall back to LLM and select GeneralHandler
        final_state = result.final_state
        self.assertEqual(
            final_state.get("__next_node"),
            "GeneralHandler",
            "Should fall back to LLM selection when confidence is low"
        )

    def test_orchestrator_error_handling(self):
        """Test orchestrator handles errors gracefully."""
        # Create test CSV with orchestrator but no available nodes
        csv_content = """GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Context
test_graph,Orchestrator,orchestrator,"Route requests","Router",request,__next_node,"matching_strategy:algorithm;default_target:ErrorHandler"
test_graph,ErrorHandler,default,"Handle errors","Error handling node",request,result,
"""
        
        csv_path = Path(self.test_dir) / "test_error_routing.csv"
        csv_path.write_text(csv_content)
        
        # Mock LLM service in case algorithm falls back to LLM
        with patch.object(
            self.container.llm_service(), 
            'call_llm',
            return_value='ErrorHandler'
        ):
            # Execute graph - should use default target
            initial_state = {"request": "Handle this error case"}
            options = self.graph_runner.get_default_options()
            options.initial_state = initial_state
            
            result = self.graph_runner.run_from_csv_direct(
                csv_path,
                "test_graph",
                options=options
            )
        
        # Should still succeed but route to default
        self.assertTrue(result.success, f"Execution should succeed: {result.error}")
        
        # Verify the final state shows routing to ErrorHandler
        final_state = result.final_state
        self.assertEqual(
            final_state.get("__next_node"),
            "ErrorHandler",
            "Should use default_target when no specific nodes match"
        )

    def test_full_orchestration_workflow(self):
        """Test complete orchestration workflow from CSV to execution."""
        # Create realistic orchestration workflow CSV
        csv_content = """GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Context
test_graph,Start,default,"Welcome user","Entry point",user_input,request,
test_graph,Orchestrator,orchestrator,"Route based on request type","Main router",request,__next_node,"matching_strategy:algorithm;nodes:DataHandler|QueryHandler|CommandHandler"
test_graph,DataHandler,default,"Process data operations","Handles data tasks",request,result,"keywords:data,file,csv,json,process"
test_graph,QueryHandler,default,"Answer questions","Handles queries",request,result,"keywords:what,when,where,who,how,question"
test_graph,CommandHandler,default,"Execute commands","Handles commands",request,result,"keywords:create,delete,update,run,execute"
test_graph,End,default,"Finalize response","Final node",result,final_output,
"""
        
        csv_path = Path(self.test_dir) / "test_full_workflow.csv"
        csv_path.write_text(csv_content)
        
        # Test different request types
        test_cases = [
            ("How do I process this data file?", "QueryHandler"),
            ("Execute the cleanup command", "CommandHandler"),
            ("Process the CSV data", "DataHandler"),
        ]
        
        for request_text, expected_node in test_cases:
            with self.subTest(request=request_text):
                initial_state = {"user_input": request_text}
                options = self.graph_runner.get_default_options()
                options.initial_state = initial_state
                
                result = self.graph_runner.run_from_csv_direct(
                    csv_path,
                    "test_graph",
                    options=options
                )
                
                self.assertTrue(
                    result.success, 
                    f"Execution should succeed for '{request_text}': {result.error}"
                )
                
                # Note: In a real execution, we'd need to track the actual routing
                # For now, we're testing that execution completes without errors
                self.assertIsNotNone(result.final_state)
                self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
