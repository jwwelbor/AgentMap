---
sidebar_position: 2
title: Comprehensive Testing Guide
description: Detailed testing examples, service integration patterns, and workflow testing for AgentMap development
keywords: [integration testing, service testing, workflow testing, detailed examples, AgentMap testing]
---

# Comprehensive Testing Guide

Detailed testing patterns and examples for AgentMap development. Use this guide for implementing complex testing scenarios and understanding advanced patterns.

:::tip For Development Conversations
Reference specific sections when discussing testing implementations:
- 🏗️ **Service Integration** - Multi-service coordination testing
- 🔄 **Workflow Testing** - End-to-end CSV-to-execution testing  
- ⚡ **Performance Patterns** - Load and scalability testing
- 🎭 **Mock Coordination** - Complex dependency management
:::

## 🏗️ Advanced Service Integration Testing

### Multi-Service Coordination Example

```python
import unittest
from unittest.mock import Mock, create_autospec
from agentmap.services.complex_service import ComplexService
from tests.utils.mock_service_factory import MockServiceFactory

class TestComplexServiceIntegration(unittest.TestCase):
    """Complete integration testing with multiple dependencies."""
    
    def setUp(self):
        """Set up realistic service dependencies."""
        self.config_overrides = {
            "processing": {"enabled": True, "timeout": 60, "batch_size": 100},
            "storage": {"cache_enabled": True, "max_cache_size": 1000}
        }
        
        # Create coordinated mock services
        self.mock_config = MockServiceFactory.create_mock_app_config_service(
            self.config_overrides
        )
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        self.mock_storage = MockServiceFactory.create_mock_storage_service()
        self.mock_llm = MockServiceFactory.create_mock_llm_service()
        
        # Create service with all dependencies
        self.service = ComplexService(
            app_config_service=self.mock_config,
            logging_service=self.mock_logging,
            storage_service=self.mock_storage,
            llm_service=self.mock_llm
        )
        self.logger = self.service.logger
    
    def test_coordinated_workflow_execution(self):
        """Test service coordinating multiple dependencies."""
        # Configure storage behavior
        self.mock_storage.get_cached_data.return_value = None  # Cache miss
        self.mock_storage.store_data.return_value = True
        
        # Configure LLM processing
        self.mock_llm.process_batch.return_value = {
            "processed_items": 5,
            "success": True,
            "results": ["result1", "result2", "result3", "result4", "result5"]
        }
        
        # Execute coordinated workflow
        input_data = ["item1", "item2", "item3", "item4", "item5"]
        result = self.service.process_workflow(input_data)
        
        # Verify coordination between services
        self.mock_storage.get_cached_data.assert_called_once()
        self.mock_llm.process_batch.assert_called_once_with(
            input_data, batch_size=100
        )
        self.mock_storage.store_data.assert_called_once()
        
        # Verify result structure
        self.assertTrue(result.success)
        self.assertEqual(len(result.processed_items), 5)
        
        # Verify logging coordination
        logger_calls = self.logger.calls
        expected_log_sequence = [
            ("info", "[ComplexService] Starting workflow with 5 items"),
            ("debug", "[ComplexService] Cache miss, processing fresh"),
            ("info", "[ComplexService] LLM processing completed: 5 items"),
            ("debug", "[ComplexService] Results cached successfully")
        ]
        
        for expected_call in expected_log_sequence:
            self.assertTrue(any(call == expected_call for call in logger_calls))
```

### Error Propagation Testing

```python
def test_error_handling_across_services(self):
    """Test error handling and recovery patterns."""
    # Configure LLM to fail
    self.mock_llm.process_batch.side_effect = Exception("LLM service unavailable")
    
    # Configure storage fallback
    self.mock_storage.get_fallback_data.return_value = {
        "fallback_results": ["fallback1", "fallback2"],
        "source": "cache"
    }
    
    # Execute with error handling
    input_data = ["item1", "item2"]
    result = self.service.process_workflow_with_fallback(input_data)
    
    # Verify error handling
    self.assertFalse(result.success)
    self.assertEqual(result.source, "cache")
    self.assertEqual(len(result.fallback_results), 2)
    
    # Verify fallback was used
    self.mock_storage.get_fallback_data.assert_called_once()
    
    # Verify error logging
    logger_calls = self.logger.calls
    error_calls = [call for call in logger_calls if call[0] == "error"]
    self.assertTrue(any("LLM service unavailable" in call[1] for call in error_calls))
```

### Configuration Flexibility Testing

```python
def test_dynamic_configuration_changes(self):
    """Test service adapts to configuration changes during execution."""
    # Test with high timeout configuration
    self.mock_config.get_processing_config.return_value = {
        "timeout": 120,
        "retry_count": 3
    }
    
    result1 = self.service.execute_with_config()
    self.assertEqual(result1.timeout_used, 120)
    
    # Change configuration for next call
    self.mock_config.get_processing_config.return_value = {
        "timeout": 30,
        "retry_count": 1
    }
    
    result2 = self.service.execute_with_config()
    self.assertEqual(result2.timeout_used, 30)
    
    # Verify both configurations were accessed
    self.assertEqual(self.mock_config.get_processing_config.call_count, 2)
```

## 🔄 End-to-End Workflow Testing

### Complete CSV-to-Execution Testing

```python
def test_complete_agentmap_workflow(self):
    """Test full AgentMap workflow from CSV to execution."""
    # Create comprehensive test workflow
    workflow_csv = '''graph_name,node_name,agent_type,context,NextNode,input_fields,output_field,prompt
user_interaction,start,input,Collect user request,analyze,user_request,raw_request,What would you like to analyze?
user_interaction,analyze,llm,Analyze user request,process,raw_request,analysis,"Analyze this request: {raw_request}"
user_interaction,process,llm,Process based on analysis,format,analysis,processed_data,"Process: {analysis}"
user_interaction,format,llm,Format final response,end,processed_data,final_result,"Format: {processed_data}"
user_interaction,end,output,Return formatted result,,final_result,,{final_result}'''
    
    csv_file = self.create_test_csv_file("workflow.csv", workflow_csv)
    
    # Configure all workflow services
    self.configure_complete_workflow_services()
    
    # Execute complete workflow
    initial_state = {"user_request": "analyze market trends"}
    result = self.service.execute_complete_workflow("user_interaction", initial_state)
    
    # Verify workflow execution
    self.assertTrue(result.success)
    self.assertIn("final_result", result.final_state)
    
    # Verify all stages executed
    execution_log = result.execution_log
    expected_stages = ["start", "analyze", "process", "format", "end"]
    for stage in expected_stages:
        self.assertTrue(any(stage in log_entry for log_entry in execution_log))
    
    # Verify data flow through workflow
    self.assertIn("market trends", result.final_state["final_result"])

def configure_complete_workflow_services(self):
    """Configure all services for complete workflow testing."""
    # Configure LLM responses for each stage
    llm_responses = {
        "analyze": {"analysis": "Market trend analysis requested"},
        "process": {"processed_data": "Detailed market analysis with trends"},
        "format": {"final_result": "Formatted market trends report"}
    }
    
    def llm_side_effect(prompt, **kwargs):
        if "Analyze this request" in prompt:
            return llm_responses["analyze"]
        elif "Process:" in prompt:
            return llm_responses["process"] 
        elif "Format:" in prompt:
            return llm_responses["format"]
        else:
            return {"result": "default_response"}
    
    self.mock_llm.process.side_effect = llm_side_effect
    
    # Configure storage for workflow state
    self.mock_storage.save_workflow_state.return_value = True
    self.mock_storage.load_workflow_state.return_value = None
```

### Agent Coordination with Protocol Safety

```python
def test_agent_coordination_with_protocols(self):
    """Test agent coordination with proper protocol handling for Python 3.11."""
    from unittest.mock import create_autospec
    
    # Create agent specs that DON'T implement NodeRegistryUser
    class StandardAgent:
        def run(self, state):
            return {"result": "standard_output"}
    
    class ProcessingAgent:
        def run(self, state):
            return {"processed": state.get("input", "")}
    
    # Use constrained mocks (Python 3.11 safe)
    mock_agent1 = create_autospec(StandardAgent, instance=True)
    mock_agent1.run.return_value = {"result": "agent1_output"}
    
    mock_agent2 = create_autospec(ProcessingAgent, instance=True) 
    mock_agent2.run.return_value = {"processed": "agent2_processed"}
    
    # Create real orchestrator when actually needed
    class TestOrchestratorAgent:
        def __init__(self):
            self.node_registry: Dict[str, Dict[str, Any]] = {}
        
        def run(self, state):
            return {"orchestrated": True, "agents_called": 2}
    
    orchestrator = TestOrchestratorAgent()
    
    # Test agent coordination
    agents = {
        "agent1": mock_agent1,
        "agent2": mock_agent2,
        "orchestrator": orchestrator
    }
    
    result = self.service.coordinate_agents(agents, {"input": "test_data"})
    
    # Verify coordination
    self.assertTrue(result.success)
    mock_agent1.run.assert_called_once()
    mock_agent2.run.assert_called_once()
    
    # Verify orchestrator was identified correctly
    self.assertEqual(result.orchestrators_found, 1)
```

## 🛠️ Advanced Path and File System Testing

### Complex File Operations with PathOperationsMocker

```python
from tests.utils.path_mocking_utils import PathOperationsMocker

def test_complex_file_workflow(self):
    """Test service that performs multiple file operations."""
    with PathOperationsMocker() as path_mocker:
        # Configure multiple file states
        path_mocker.configure_path(
            "input.csv", 
            exists=True, 
            content="name,value\ntest,123\n"
        )
        path_mocker.configure_path("output.json", exists=False)
        path_mocker.configure_directory(
            "temp_dir", 
            exists=True, 
            files=["temp1.txt", "temp2.txt"]
        )
        
        # Execute workflow
        result = self.service.process_files(
            input_file="input.csv",
            output_file="output.json",
            temp_directory="temp_dir"
        )
        
        # Verify file operations
        self.assertTrue(result.success)
        self.assertEqual(result.records_processed, 1)
        
        # Verify specific path operations were called
        path_mocker.assert_path_checked("input.csv")
        path_mocker.assert_file_written("output.json")
        path_mocker.assert_directory_listed("temp_dir")
```

### CSV Processing with Edge Cases

```python
def test_csv_processing_with_various_formats(self):
    """Test CSV processing handles different data formats and edge cases."""
    # Test data with various edge cases
    csv_content = '''graph_name,node_name,agent_type,context,NextNode,input_fields,output_field,prompt
"Test Graph","Start Node",input,"Get user input","Process Node","user_input,additional_data",processed_input,"Enter your request:"
Test Graph,Process Node,llm,Process the request,End Node,processed_input,result,"Process: {processed_input}"
"Test Graph","End Node",output,Return result,,result,,"Final result: {result}"'''
    
    csv_file = self.create_test_csv_file("complex_graph.csv", csv_content)
    
    # Mock file operations
    with self.patch_path_operations(csv_file, csv_content):
        result = self.service.load_and_validate_graph(csv_file)
    
    # Verify parsing handled edge cases
    self.assertTrue(result.success)
    self.assertEqual(len(result.nodes), 3)
    
    # Verify quoted values parsed correctly
    start_node = result.get_node("Start Node")
    self.assertEqual(start_node.context, "Get user input")
    self.assertEqual(start_node.prompt, "Enter your request:")
    
    # Verify complex field parsing
    self.assertEqual(start_node.input_fields, ["user_input", "additional_data"])
```

## 📊 Performance and Load Testing

### Performance Requirements Validation

```python
import time
from unittest.mock import patch

def test_processing_performance_requirements(self):
    """Verify service meets performance requirements."""
    # Configure fast mock responses
    self.mock_llm.process.return_value = {"result": "fast_response"}
    self.mock_storage.cache_lookup.return_value = None  # Cache miss
    
    # Test processing time for single request
    start_time = time.time()
    result = self.service.process_single_request("test_input")
    single_request_time = time.time() - start_time
    
    # Verify performance requirement
    self.assertLess(single_request_time, 0.1, "Single request too slow")
    self.assertTrue(result.success)
    
    # Test batch processing performance
    batch_inputs = [f"input_{i}" for i in range(10)]
    
    start_time = time.time()
    batch_result = self.service.process_batch_requests(batch_inputs)
    batch_time = time.time() - start_time
    
    # Verify batch efficiency
    self.assertLess(batch_time, single_request_time * 5, "Batch processing not efficient")
    self.assertEqual(len(batch_result.processed), 10)
```

### Caching Performance Testing

```python
def test_caching_performance_improvement(self):
    """Verify caching provides performance benefits."""
    cache_data = {"cached_result": "fast_cached_response"}
    
    # First call - cache miss (slower)
    self.mock_storage.cache_lookup.return_value = None
    self.mock_llm.process.return_value = {"result": "computed_response"}
    self.mock_storage.cache_store.return_value = True
    
    start_time = time.time()
    result1 = self.service.process_with_cache("test_key")
    first_call_time = time.time() - start_time
    
    # Verify first call hit LLM
    self.mock_llm.process.assert_called_once()
    self.mock_storage.cache_store.assert_called_once()
    
    # Second call - cache hit (faster)
    self.mock_storage.cache_lookup.return_value = cache_data
    
    start_time = time.time()
    result2 = self.service.process_with_cache("test_key")
    second_call_time = time.time() - start_time
    
    # Verify caching benefit
    self.assertLess(second_call_time, first_call_time * 0.5, "Cache not improving performance")
    self.assertEqual(result2.result, "fast_cached_response")
    
    # Verify LLM not called again
    self.mock_llm.process.assert_called_once()  # Still only once
```

### Concurrent Request Testing

```python
def test_concurrent_request_handling(self):
    """Test service handles concurrent requests correctly."""
    import threading
    import queue
    
    results_queue = queue.Queue()
    
    def process_request(request_id):
        """Process request in separate thread."""
        try:
            result = self.service.process_request(f"request_{request_id}")
            results_queue.put(("success", request_id, result))
        except Exception as e:
            results_queue.put(("error", request_id, str(e)))
    
    # Configure mock for concurrent access
    self.mock_llm.process.return_value = {"result": "concurrent_response"}
    
    # Launch concurrent requests
    threads = []
    for i in range(10):
        thread = threading.Thread(target=process_request, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for completion
    for thread in threads:
        thread.join(timeout=5)
    
    # Collect results
    results = []
    while not results_queue.empty():
        results.append(results_queue.get_nowait())
    
    # Verify all requests succeeded
    success_results = [r for r in results if r[0] == "success"]
    self.assertEqual(len(success_results), 10)
    
    # Verify service calls were made
    self.assertEqual(self.mock_llm.process.call_count, 10)
```

## 🎛️ CLI Testing Patterns

### End-to-End CLI Workflow Testing

```python
from tests.fresh_suite.cli.base_cli_test import BaseCLITest

class TestComplexCLIWorkflows(BaseCLITest):
    """Test complex CLI scenarios and user workflows."""
    
    def test_end_to_end_graph_creation_and_execution(self):
        """Test complete graph creation and execution workflow."""
        # Create test CSV
        csv_content = self.create_sample_graph_csv()
        csv_file = self.create_test_csv_file("e2e_graph.csv", csv_content)
        
        # Configure services for full workflow
        mock_container = self.create_mock_container()
        self.configure_e2e_services(mock_container)
        
        with self.patch_container_creation(mock_container):
            # Step 1: Compile graph
            compile_result = self.run_cli_command([
                "compile", "--graph", "e2e_test", "--csv", str(csv_file)
            ])
            self.assert_cli_success(compile_result, ["✅", "Compilation successful"])
            
            # Step 2: Validate compiled graph
            validate_result = self.run_cli_command([
                "validate", "--graph", "e2e_test"
            ])
            self.assert_cli_success(validate_result, ["✅", "Validation passed"])
            
            # Step 3: Execute graph
            execute_result = self.run_cli_command([
                "run", "--graph", "e2e_test", "--input", '{"start_data": "test"}'
            ])
            self.assert_cli_success(execute_result, ["✅", "Execution completed"])
        
        # Verify service coordination
        self.verify_e2e_service_calls(mock_container)
    
    def test_cli_error_handling_and_user_experience(self):
        """Test CLI handles errors gracefully with helpful messages."""
        mock_container = self.create_mock_container()
        
        # Configure service to fail
        self.mock_graph_compiler_service.compile_graph.side_effect = \
            Exception("Compilation failed: invalid node configuration")
        
        with self.patch_container_creation(mock_container):
            result = self.run_cli_command([
                "compile", "--graph", "failing_graph", "--csv", "invalid.csv"
            ])
        
        # Verify error handling
        self.assert_cli_failure(result)
        self.assertIn("Compilation failed", result.stdout)
        self.assertNotIn("Traceback", result.stdout)  # No stack trace leaked
        
        # Verify helpful error message
        self.assertIn("invalid node configuration", result.stdout)
```

## 📊 Test Data Management

### Realistic Test Data Factory

```python
class TestDataFactory:
    """Factory for generating realistic test data for various scenarios."""
    
    @staticmethod
    def create_complex_graph_csv():
        """Generate realistic graph CSV with edge cases."""
        return '''graph_name,node_name,agent_type,context,NextNode,input_fields,output_field,prompt
"Customer Service","Welcome",input,"Greet customer and collect issue","Route Request","customer_name,issue_type",customer_data,"Hello! I'm here to help. What's your name and what can I assist you with?"
"Customer Service","Route Request",llm,"Analyze customer issue and route appropriately","Technical Support,Billing Support,General Support",customer_data,routing_decision,"Based on this customer data: {customer_data}, route to the appropriate support team."
"Customer Service","Technical Support",llm,"Handle technical support requests","Resolution",routing_decision,technical_solution,"Provide technical support for: {routing_decision}"
"Customer Service","Billing Support",llm,"Handle billing inquiries","Resolution",routing_decision,billing_solution,"Address billing concern: {routing_decision}"  
"Customer Service","General Support",llm,"Handle general questions","Resolution",routing_decision,general_solution,"Provide general support for: {routing_decision}"
"Customer Service","Resolution",output,"Provide final response to customer","",technical_solution|billing_solution|general_solution,,"Thank you for contacting us. Here's the resolution: {solution}"'''
    
    @staticmethod
    def create_large_scale_graph(num_nodes=100):
        """Generate large graph for performance testing."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'graph_name', 'node_name', 'agent_type', 'context', 
            'NextNode', 'input_fields', 'output_field', 'prompt'
        ])
        
        # Generate nodes
        for i in range(num_nodes):
            next_node = f"node_{i+1}" if i < num_nodes - 1 else ""
            writer.writerow([
                "large_graph",
                f"node_{i}",
                "llm" if i % 3 != 0 else "input" if i == 0 else "output",
                f"Process step {i}",
                next_node,
                f"input_{i}",
                f"output_{i}",
                f"Process this data at step {i}: {{input_{i}}}"
            ])
        
        return output.getvalue()
    
    @staticmethod
    def create_workflow_with_conditions():
        """Generate workflow that includes conditional routing."""
        return '''graph_name,node_name,agent_type,context,NextNode,input_fields,output_field,prompt
"Review Process","Start",input,"Begin document review","Quality Check",document,initial_review,"Please provide the document for review"
"Review Process","Quality Check",llm,"Check document quality","Revision Required,Approval",initial_review,quality_assessment,"Assess the quality of: {initial_review}"
"Review Process","Revision Required",llm,"Request revisions","Quality Check",quality_assessment,revision_request,"Request these revisions: {quality_assessment}"
"Review Process","Approval",output,"Approve document","",quality_assessment,,"Document approved: {quality_assessment}"'''
```

### Test Environment Management

```python
class TestEnvironmentManager:
    """Manage isolated test environments for complex scenarios."""
    
    def __init__(self):
        self.temp_files = []
        self.original_env = {}
    
    def create_isolated_environment(self):
        """Create isolated test environment with proper cleanup."""
        import os
        import tempfile
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix="agentmap_test_")
        
        # Save original environment
        env_vars = ["AGENTMAP_CONFIG", "AGENTMAP_DATA_DIR", "AGENTMAP_LOG_LEVEL"]
        for var in env_vars:
            self.original_env[var] = os.environ.get(var)
        
        # Set test environment
        os.environ["AGENTMAP_CONFIG"] = os.path.join(self.temp_dir, "test_config.yaml")
        os.environ["AGENTMAP_DATA_DIR"] = os.path.join(self.temp_dir, "data")
        os.environ["AGENTMAP_LOG_LEVEL"] = "DEBUG"
        
        return self.temp_dir
    
    def cleanup_environment(self):
        """Clean up test environment and restore original state."""
        import os
        import shutil
        
        # Restore environment
        for var, value in self.original_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        
        # Remove temporary files
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def __enter__(self):
        return self.create_isolated_environment()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_environment()
```

## 🔧 Integration with Real Components

### Hybrid Testing (Real + Mock)

```python
def test_integration_with_real_config(self):
    """Integration test combining real config service with mocked externals."""
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.config.config_service import ConfigService
    
    # Use real config service with test configuration
    config_service = ConfigService()
    config_service.load_config("tests/data/test_config.yaml")
    
    real_app_config = AppConfigService(config_service=config_service)
    
    # Mock only external dependencies
    mock_logging_service = MockServiceFactory.create_mock_logging_service()
    
    # Test with real + mock combination
    service = MyService(
        app_config_service=real_app_config,  # Real
        logging_service=mock_logging_service  # Mock
    )
    
    result = service.process_with_real_config()
    self.assertTrue(result.success)
    
    # Verify real config was used
    self.assertIsNotNone(service.actual_config_value)
    
    # Verify mock interactions
    logger_calls = mock_logging_service.logger.calls
    self.assertTrue(any("real config" in call[1].lower() for call in logger_calls))
```

## 🎯 Best Practices Summary

### Testing Philosophy
- 🎯 **Test behavior, not implementation** - Focus on what services do
- 🔄 **Use realistic data flows** - Mirror production scenarios
- 🛡️ **Security by default** - Never test insecure patterns
- ⚡ **Performance awareness** - Include timing assertions
- 🧩 **Isolation and repeatability** - Independent test execution

### Implementation Patterns
- ✅ **MockServiceFactory for consistency** - Standard service mocking
- ✅ **create_autospec() for agents** - Python 3.11 compatibility
- ✅ **Path utilities first** - Avoid manual Path mocking
- ✅ **Realistic test data** - Use production-like scenarios
- ✅ **Error scenario coverage** - Test failure paths

## 📚 Related Documentation

- **[Quick Reference](/docs/testing/quick-reference)** - Essential patterns and standards
- **[Troubleshooting](/docs/testing/troubleshooting)** - Debugging test issues
- **[Advanced Patterns](/docs/testing/advanced-patterns)** - Performance and specialized testing

---

**For Development Conversations:** Reference specific sections to get targeted assistance with testing implementations and complex scenarios.
