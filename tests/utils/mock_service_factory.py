"""
Standardized MockServiceFactory for Pure Mock Objects.

This factory creates pure unittest.Mock objects to replace custom mock classes
from migration_utils.py. It ensures consistent mock behavior across all tests
and eliminates the need for custom mock class implementations.

Pattern established by ExecutionTrackingService test refactoring:
- Use pure unittest.Mock objects instead of custom classes
- Configure mock methods to return expected values
- Provide realistic interface behavior for testing
"""

from unittest.mock import Mock
from typing import Dict, Any, Optional, List
from pathlib import Path


class MockServiceFactory:
    """
    Factory for creating standardized Mock objects for common services.
    
    This replaces custom mock classes (MockLoggingService, MockAppConfigService, etc.)
    with pure unittest.Mock objects that have the same interface behavior.
    
    Usage Examples:
        # Create mock services using MockServiceFactory
        mock_logging = MockServiceFactory.create_mock_logging_service()
        logger = mock_logging.get_class_logger(some_instance)  # Standard pattern
        logger2 = mock_logging.get_class_logger("service.name")  # LLMService pattern
        
        # Create a mock app config service
        mock_config = MockServiceFactory.create_mock_app_config_service()
        tracking_config = mock_config.get_tracking_config()
        
        # Create a mock node registry service
        mock_registry = MockServiceFactory.create_mock_node_registry_service()
        mock_registry.register_node("test_node", node_data)
    """
    
    @staticmethod
    def create_mock_logging_service(logger_name: str = "test") -> Mock:
        """
        Create a pure Mock object that replaces MockLoggingService.
        
        This Mock provides the same interface as MockLoggingService but uses
        pure unittest.Mock objects instead of custom logger classes.
        
        Args:
            logger_name: Base name for loggers (default: "test")
            
        Returns:
            Mock object with get_logger, get_class_logger, and get_module_logger methods
            
        Example:
            mock_logging = MockServiceFactory.create_mock_logging_service()
            service = SomeService(logging_service=mock_logging)
            logger = service.logger  # Will be a Mock object
        """
        mock_service = Mock()
        
        def create_mock_logger(name: str) -> Mock:
            """Create a mock logger with call tracking."""
            mock_logger = Mock()
            mock_logger.name = name
            mock_logger.calls = []  # Track calls for verification
            
            # Configure logging methods to track calls
            def track_log_call(level, message, *args, **kwargs):
                mock_logger.calls.append((level, message, args, kwargs))
            
            mock_logger.debug.side_effect = lambda msg, *args, **kwargs: track_log_call("debug", msg, *args, **kwargs)
            mock_logger.info.side_effect = lambda msg, *args, **kwargs: track_log_call("info", msg, *args, **kwargs)
            mock_logger.warning.side_effect = lambda msg, *args, **kwargs: track_log_call("warning", msg, *args, **kwargs)
            mock_logger.error.side_effect = lambda msg, *args, **kwargs: track_log_call("error", msg, *args, **kwargs)
            mock_logger.trace.side_effect = lambda msg, *args, **kwargs: track_log_call("trace", msg, *args, **kwargs)
            
            return mock_logger
        
        def get_logger(name: str) -> Mock:
            """Get logger by name."""
            return create_mock_logger(name)
        
        def get_class_logger(instance_or_name) -> Mock:
            """Get logger for class instance or by name - handle both patterns."""
            if isinstance(instance_or_name, str):
                # LLMService pattern: get_class_logger("agentmap.llm")
                logger_name = instance_or_name
            elif hasattr(instance_or_name, '__class__'):
                # Standard pattern: get_class_logger(self)
                logger_name = instance_or_name.__class__.__name__
            else:
                # Fallback
                logger_name = str(type(instance_or_name).__name__)
            return create_mock_logger(logger_name)
        
        def get_module_logger(name: str) -> Mock:
            """Get logger for module."""
            return create_mock_logger(name)
        
        # Configure service methods
        mock_service.get_logger.side_effect = get_logger
        mock_service.get_class_logger.side_effect = get_class_logger
        mock_service.get_module_logger.side_effect = get_module_logger
        
        return mock_service
    
    @staticmethod
    def create_mock_app_config_service(config_overrides: Optional[Dict[str, Any]] = None) -> Mock:
        """
        Create a pure Mock object that replaces MockAppConfigService.
        
        This Mock provides the same interface as MockAppConfigService with
        all expected configuration methods and default return values.
        
        Args:
            config_overrides: Optional dict to override default config values
            
        Returns:
            Mock object with all app config service methods
            
        Example:
            config = {"tracking": {"enabled": False}}
            mock_config = MockServiceFactory.create_mock_app_config_service(config)
            tracking_config = mock_config.get_tracking_config()  # Returns False for enabled
        """
        mock_service = Mock()
        
        # Default configurations
        defaults = {
            "csv_path": "graphs/workflow.csv",
            "compiled_graphs_path": "compiled",
            "autocompile": True,
            "logging": {
                "level": "DEBUG",
                "format": "[%(levelname)s] %(name)s: %(message)s"
            },
            "execution": {
                "tracking": {"enabled": True},
                "success_policy": {"type": "all_nodes"}
            },
            "tracking": {
                "enabled": True,
                "track_outputs": False,
                "track_inputs": False
            },
            "prompts": {
                "directory": "prompts",
                "registry_file": "prompts/registry.yaml",
                "enable_cache": True
            }
        }
        
        # Apply overrides
        if config_overrides:
            for key, value in config_overrides.items():
                if isinstance(value, dict) and key in defaults:
                    defaults[key].update(value)
                else:
                    defaults[key] = value
        
        # Configure all expected methods
        mock_service.get_csv_path.return_value = Path(defaults["csv_path"])
        mock_service.get_compiled_graphs_path.return_value = Path(defaults["compiled_graphs_path"])
        mock_service.get_logging_config.return_value = defaults["logging"]
        mock_service.get_execution_config.return_value = defaults["execution"]
        mock_service.get_tracking_config.return_value = defaults["tracking"]
        mock_service.get_prompts_config.return_value = defaults["prompts"]
        
        # Add get_value method for generic config access with nested path support
        def get_value(key: str, default: Any = None) -> Any:
            """Get value with support for nested paths like 'storage.csv'."""
            if '.' in key:
                # Handle nested keys like 'storage.csv'
                keys = key.split('.')
                current = defaults
                for k in keys:
                    if isinstance(current, dict) and k in current:
                        current = current[k]
                    else:
                        return default
                return current
            return defaults.get(key, default)
        
        mock_service.get_value.side_effect = get_value
        
        # CRITICAL FIX: Add get_section method that PromptManagerService requires
        def get_section(section_name: str) -> Dict[str, Any]:
            """Get configuration section by name."""
            return defaults.get(section_name, {})
        
        mock_service.get_section.side_effect = get_section
        
        return mock_service
    
    @staticmethod
    def create_mock_node_registry_service() -> Mock:
        """
        Create a pure Mock object that replaces MockNodeRegistryService.
        
        This Mock provides the same interface as MockNodeRegistryService with
        a dictionary-based storage for registered nodes.
        
        Returns:
            Mock object with node registry methods and state tracking
            
        Example:
            mock_registry = MockServiceFactory.create_mock_node_registry_service()
            mock_registry.register_node("test_node", {"type": "processor"})
            node = mock_registry.get_node("test_node")  # Returns the registered data
        """
        mock_service = Mock()
        
        # Internal storage for nodes (this allows realistic behavior)
        nodes_storage = {}
        
        def register_node(node_name: str, node_data: Any) -> None:
            nodes_storage[node_name] = node_data
        
        def get_node(node_name: str) -> Optional[Any]:
            return nodes_storage.get(node_name)
        
        def list_nodes() -> List[str]:
            return list(nodes_storage.keys())
        
        def clear_registry() -> None:
            nodes_storage.clear()
        
        def prepare_for_assembly(graph_def: Dict[str, Any], graph_name: str) -> Dict[str, Any]:
            return {"prepared": True, "graph_name": graph_name}
        
        def verify_pre_compilation_injection(node_registry: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "all_injected": True,
                "has_orchestrators": False,
                "stats": {"total_nodes": len(nodes_storage), "injected_nodes": len(nodes_storage)}
            }
        
        # Configure methods with realistic behavior
        mock_service.register_node.side_effect = register_node
        mock_service.get_node.side_effect = get_node
        mock_service.list_nodes.side_effect = list_nodes
        mock_service.clear_registry.side_effect = clear_registry
        mock_service.prepare_for_assembly.side_effect = prepare_for_assembly
        mock_service.verify_pre_compilation_injection.side_effect = verify_pre_compilation_injection
        
        return mock_service
    
    @staticmethod
    def create_mock_execution_tracker(
        graph_name: str = "test_graph",
        tracking_config: Optional[Dict[str, Any]] = None
    ) -> Mock:
        """
        Create a pure Mock object that replaces MockExecutionTracker.
        
        This Mock provides the same interface as ExecutionTracker with
        realistic state tracking for executions and nodes.
        
        Args:
            graph_name: Name of the graph being tracked
            tracking_config: Configuration for tracking behavior
            
        Returns:
            Mock object with execution tracking methods and state
            
        Example:
            mock_tracker = MockServiceFactory.create_mock_execution_tracker()
            exec_id = mock_tracker.start_execution("my_graph")
            mock_tracker.record_node_start("node1", {"input": "value"})
        """
        mock_tracker = Mock()
        
        # Default tracking config
        default_config = {
            "enabled": True,
            "track_outputs": False,
            "track_inputs": False
        }
        if tracking_config:
            default_config.update(tracking_config)
        
        # Internal state
        executions_storage = []
        current_execution = None
        
        def start_execution(name: str, initial_state: Any = None) -> str:
            nonlocal current_execution
            execution_id = f"mock_exec_{len(executions_storage)}"
            execution = {
                "id": execution_id,
                "graph_name": name,
                "initial_state": initial_state,
                "nodes": []
            }
            executions_storage.append(execution)
            current_execution = execution_id
            return execution_id
        
        def record_node_start(node_name: str, inputs: Dict[str, Any] = None) -> None:
            if current_execution:
                execution = next(e for e in executions_storage if e["id"] == current_execution)
                execution["nodes"].append({
                    "name": node_name,
                    "inputs": inputs,
                    "status": "started"
                })
        
        def record_node_result(node_name: str, success: bool, result: Any = None, error: str = None) -> None:
            if current_execution:
                execution = next(e for e in executions_storage if e["id"] == current_execution)
                for node in execution["nodes"]:
                    if node["name"] == node_name and node["status"] == "started":
                        node.update({
                            "status": "completed",
                            "success": success,
                            "result": result,
                            "error": error
                        })
                        break
        
        def get_executions() -> List[Dict[str, Any]]:
            return executions_storage.copy()
        
        # Configure methods
        mock_tracker.start_execution.side_effect = start_execution
        mock_tracker.record_node_start.side_effect = record_node_start
        mock_tracker.record_node_result.side_effect = record_node_result
        mock_tracker.get_executions.side_effect = get_executions
        
        # Static properties
        mock_tracker.graph_name = graph_name
        mock_tracker.tracking_config = default_config
        
        return mock_tracker
    
    @staticmethod
    def create_mock_graph_bundle(
        graph: Any = None,
        node_registry: Any = None,
        version_hash: str = "test123"
    ) -> Mock:
        """
        Create a pure Mock object that replaces MockGraphBundle.
        
        This Mock provides the same interface as MockGraphBundle with
        configurable graph data and registry.
        
        Args:
            graph: Graph object (defaults to Mock)
            node_registry: Node registry object (defaults to None)
            version_hash: Version hash string
            
        Returns:
            Mock object with graph bundle methods
            
        Example:
            mock_bundle = MockServiceFactory.create_mock_graph_bundle()
            bundle_dict = mock_bundle.to_dict()
            mock_bundle.save(Path("test.pkl"))
        """
        mock_bundle = Mock()
        
        # Set properties
        mock_bundle.graph = graph or Mock()
        mock_bundle.node_registry = node_registry
        mock_bundle.version_hash = version_hash
        
        # Configure methods
        def to_dict() -> Dict[str, Any]:
            return {
                "graph": mock_bundle.graph,
                "node_registry": mock_bundle.node_registry,
                "version_hash": mock_bundle.version_hash
            }
        
        def load(path: Path, logger: Any = None):
            return mock_bundle
    
    @staticmethod
    def create_mock_graph_definition_service() -> Mock:
        """
        Create a pure Mock object for GraphDefinitionService.
        
        This Mock provides realistic interface behavior for graph definition loading
        and building operations that GraphRunnerService requires.
        
        Returns:
            Mock object with build_from_csv and build_all_from_csv methods
            
        Example:
            mock_graph_def = MockServiceFactory.create_mock_graph_definition_service()
            graph_model = mock_graph_def.build_from_csv(Path("test.csv"), "test_graph")
        """
        mock_service = Mock()
        
        # Create mock graph domain model with nodes
        def create_mock_graph_model(graph_name: str) -> Mock:
            mock_graph = Mock()
            mock_graph.nodes = {
                "node1": Mock(name="node1", agent_type="default", inputs=["input1"], 
                             output="output1", prompt="Test prompt", description="Test node",
                             context={}, edges=["node2"]),
                "node2": Mock(name="node2", agent_type="default", inputs=["input2"], 
                             output="output2", prompt="Test prompt 2", description="Test node 2",
                             context={}, edges=[])
            }
            return mock_graph
        
        def build_from_csv(csv_path: Path, graph_name: str) -> Mock:
            return create_mock_graph_model(graph_name)
        
        def build_all_from_csv(csv_path: Path) -> Dict[str, Mock]:
            return {
                "test_graph": create_mock_graph_model("test_graph"),
                "another_graph": create_mock_graph_model("another_graph")
            }
        
        # Configure methods
        mock_service.build_from_csv.side_effect = build_from_csv
        mock_service.build_all_from_csv.side_effect = build_all_from_csv
        
        return mock_service
    
    @staticmethod
    def create_mock_graph_execution_service() -> Mock:
        """
        Create a pure Mock object for GraphExecutionService.
        
        This Mock provides realistic ExecutionResult objects for both compiled
        and definition-based graph execution methods.
        
        Returns:
            Mock object with execute_compiled_graph and execute_from_definition methods
            
        Example:
            mock_execution = MockServiceFactory.create_mock_graph_execution_service()
            result = mock_execution.execute_compiled_graph(Path("test.pkl"), {})
        """
        mock_service = Mock()
        
        def create_mock_execution_result(graph_name: str, source: str, success: bool = True) -> Mock:
            """Create a mock ExecutionResult with realistic structure."""
            from unittest.mock import Mock
            
            # Note: Using total_duration and compiled_from fields as used by the actual ExecutionResult model
            # rather than execution_time and source_info from the old implementation
            mock_result = Mock()
            mock_result.graph_name = graph_name
            mock_result.success = success
            mock_result.final_state = {"result": "test_output", "status": "completed"}
            mock_result.execution_summary = Mock()
            mock_result.total_duration = 1.5
            mock_result.compiled_from = source
            mock_result.error = None if success else "Mock execution error"
            
            return mock_result
        
        def execute_compiled_graph(bundle_path: Path, state: Dict[str, Any]) -> Mock:
            graph_name = bundle_path.stem
            return create_mock_execution_result(graph_name, "precompiled")
        
        def execute_from_definition(graph_def: Dict[str, Any], state: Dict[str, Any]) -> Mock:
            graph_name = "test_graph"  # Default for mock
            return create_mock_execution_result(graph_name, "memory")
        
        def setup_execution_tracking(graph_name: str) -> Mock:
            mock_tracker = Mock()
            mock_tracker.graph_name = graph_name
            return mock_tracker
        
        # Configure methods
        mock_service.execute_compiled_graph.side_effect = execute_compiled_graph
        mock_service.execute_from_definition.side_effect = execute_from_definition
        mock_service.setup_execution_tracking.side_effect = setup_execution_tracking
        
        return mock_service
    
    @staticmethod
    def create_mock_compilation_service() -> Mock:
        """
        Create a pure Mock object for CompilationService.
        
        This Mock provides realistic compilation result behavior for graph
        autocompilation and compilation management operations.
        
        Returns:
            Mock object with auto_compile_if_needed method
            
        Example:
            mock_compilation = MockServiceFactory.create_mock_compilation_service()
            result = mock_compilation.auto_compile_if_needed("test_graph", Path("test.csv"), options)
        """
        mock_service = Mock()
        
        def create_mock_compilation_result(success: bool = True) -> Mock:
            """Create a mock compilation result."""
            mock_result = Mock()
            mock_result.success = success
            mock_result.error = None if success else "Mock compilation error"
            mock_result.bundle_path = Path("compiled/test_graph.pkl") if success else None
            return mock_result
        
        def auto_compile_if_needed(graph_name: str, csv_path: Path, options: Any) -> Mock:
            # Default to successful compilation
            return create_mock_compilation_result(success=True)
        
        # Configure methods
        mock_service.auto_compile_if_needed.side_effect = auto_compile_if_needed
        
        return mock_service
    
    @staticmethod
    def create_mock_graph_bundle_service() -> Mock:
        """
        Create a pure Mock object for GraphBundleService.
        
        This Mock provides realistic bundle loading and management behavior
        for compiled graph bundle operations.
        
        Returns:
            Mock object with load_bundle method
            
        Example:
            mock_bundle_service = MockServiceFactory.create_mock_graph_bundle_service()
            bundle = mock_bundle_service.load_bundle(Path("test.pkl"))
        """
        mock_service = Mock()
        
        def load_bundle(bundle_path: Path) -> Mock:
            """Load a mock graph bundle."""
            mock_bundle = Mock()
            mock_bundle.graph = Mock()  # Mock executable graph
            mock_bundle.node_registry = {"node1": Mock(), "node2": Mock()}
            mock_bundle.version_hash = "mock_hash_123"
            return mock_bundle
        
        def save_bundle(bundle: Any, bundle_path: Path) -> None:
            """Mock save operation."""
            pass
        
        # Configure methods
        mock_service.load_bundle.side_effect = load_bundle
        mock_service.save_bundle.side_effect = save_bundle
        
        return mock_service
    
    @staticmethod
    def create_mock_llm_service() -> Mock:
        """
        Create a pure Mock object for LLMService.
        
        This Mock provides basic LLM service interface for agent injection
        and LLM operations that GraphRunnerService requires.
        
        Returns:
            Mock object with LLM service methods
            
        Example:
            mock_llm = MockServiceFactory.create_mock_llm_service()
            response = mock_llm.generate("test prompt")
        """
        mock_service = Mock()
        
        # Configure basic LLM methods
        mock_service.generate.return_value = "Mock LLM response"
        mock_service.get_model_name.return_value = "mock-model"
        mock_service.is_available.return_value = True
        
        return mock_service
    
    @staticmethod
    def create_mock_storage_service_manager() -> Mock:
        """
        Create a pure Mock object for StorageServiceManager.
        
        This Mock provides storage service injection capabilities
        for agents that require storage operations.
        
        Returns:
            Mock object with storage service manager methods
            
        Example:
            mock_storage = MockServiceFactory.create_mock_storage_service_manager()
            csv_service = mock_storage.get_csv_service()
        """
        mock_service = Mock()
        
        # Mock individual storage services
        mock_csv_service = Mock()
        mock_json_service = Mock()
        mock_file_service = Mock()
        mock_vector_service = Mock()
        
        # Configure storage service getters
        mock_service.get_csv_service.return_value = mock_csv_service
        mock_service.get_json_service.return_value = mock_json_service
        mock_service.get_file_service.return_value = mock_file_service
        mock_service.get_vector_service.return_value = mock_vector_service
        
        return mock_service
    
    @staticmethod
    def create_mock_execution_policy_service() -> Mock:
        """
        Create a pure Mock object for ExecutionPolicyService.
        
        This Mock provides policy evaluation functionality for determining
        graph execution success based on configured policies.
        
        Returns:
            Mock object with evaluate_success_policy method
            
        Example:
            mock_policy = MockServiceFactory.create_mock_execution_policy_service()
            success = mock_policy.evaluate_success_policy(execution_summary)
        """
        mock_service = Mock()
        
        def evaluate_success_policy(execution_summary: Any) -> bool:
            """Mock policy evaluation - default to True for successful tests."""
            return True
        
        # Configure methods
        mock_service.evaluate_success_policy.side_effect = evaluate_success_policy
        
        return mock_service
    
    @staticmethod
    def create_mock_state_adapter_service() -> Mock:
        """
        Create a pure Mock object for StateAdapterService.
        
        This Mock provides state management operations for getting and setting
        values in the execution state dictionary.
        
        Returns:
            Mock object with get_value and set_value methods
            
        Example:
            mock_state = MockServiceFactory.create_mock_state_adapter_service()
            value = mock_state.get_value(state, "key")
            new_state = mock_state.set_value(state, "key", "value")
        """
        mock_service = Mock()
        
        def get_value(state: Dict[str, Any], key: str, default: Any = None) -> Any:
            """Mock get value from state."""
            return state.get(key, default)
        
        def set_value(state: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
            """Mock set value in state - returns updated state."""
            updated_state = state.copy()
            updated_state[key] = value
            return updated_state
        
        # Configure methods
        mock_service.get_value.side_effect = get_value
        mock_service.set_value.side_effect = set_value
        
        return mock_service
    
    @staticmethod
    def create_mock_dependency_checker_service() -> Mock:
        """
        Create a pure Mock object for DependencyCheckerService.
        
        This Mock provides dependency validation for LLM and storage services
        that agents may require for proper functionality.
        
        Returns:
            Mock object with check_llm_dependencies and check_storage_dependencies methods
            
        Example:
            mock_deps = MockServiceFactory.create_mock_dependency_checker_service()
            has_llm, missing = mock_deps.check_llm_dependencies()
        """
        mock_service = Mock()
        
        def check_llm_dependencies(provider: Optional[str] = None) -> tuple:
            """Mock LLM dependency check - default to available."""
            return (True, [])  # (has_dependencies, missing_dependencies)
        
        def check_storage_dependencies(provider: Optional[str] = None) -> tuple:
            """Mock storage dependency check - default to available."""
            return (True, [])  # (has_dependencies, missing_dependencies)
        
        def get_installation_guide(service_type: str, category: str) -> str:
            """Mock installation guide."""
            return f"pip install agentmap[{category}]"
        
        # Configure methods
        mock_service.check_llm_dependencies.side_effect = check_llm_dependencies
        mock_service.check_storage_dependencies.side_effect = check_storage_dependencies
        mock_service.get_installation_guide.side_effect = get_installation_guide
        
        return mock_service
    
    @staticmethod
    def create_mock_graph_assembly_service() -> Mock:
        """
        Create a pure Mock object for GraphAssemblyService.
        
        This Mock provides graph assembly functionality for converting
        graph definitions into executable compiled graphs.
        
        Returns:
            Mock object with assemble_graph method
            
        Example:
            mock_assembly = MockServiceFactory.create_mock_graph_assembly_service()
            compiled_graph = mock_assembly.assemble_graph(graph_def, node_registry)
        """
        mock_service = Mock()
        
        def assemble_graph(graph_def: Dict[str, Any], node_registry: Any = None, enable_logging: bool = True) -> Mock:
            """Mock graph assembly - returns executable graph mock."""
            mock_compiled_graph = Mock()
            
            # Mock invoke method for graph execution
            def invoke(state: Dict[str, Any]) -> Dict[str, Any]:
                # Mock execution - return state with some results
                result_state = state.copy()
                result_state["execution_result"] = "mock_output"
                result_state["nodes_executed"] = list(graph_def.keys()) if graph_def else []
                return result_state
            
            mock_compiled_graph.invoke.side_effect = invoke
            return mock_compiled_graph
        
        # Configure methods
        mock_service.assemble_graph.side_effect = assemble_graph
        
        return mock_service
    
    @staticmethod
    def create_mock_csv_graph_parser_service() -> Mock:
        """
        Create a pure Mock object for CSVGraphParserService.
        
        This Mock provides realistic GraphSpec and ValidationResult objects
        for CSV parsing operations that GraphDefinitionService requires.
        
        Returns:
            Mock object with parse_csv_to_graph_spec and validate_csv_structure methods
            
        Example:
            mock_parser = MockServiceFactory.create_mock_csv_graph_parser_service()
            graph_spec = mock_parser.parse_csv_to_graph_spec(Path("test.csv"))
        """
        mock_service = Mock()
        
        def create_mock_node_spec(node_name: str, graph_name: str, line_number: int = 1) -> Mock:
            """Create a mock NodeSpec with realistic structure."""
            mock_node_spec = Mock()
            mock_node_spec.name = node_name
            mock_node_spec.graph_name = graph_name
            mock_node_spec.agent_type = "default"
            mock_node_spec.prompt = f"Test prompt for {node_name}"
            mock_node_spec.description = f"Test node {node_name}"
            mock_node_spec.context = None
            mock_node_spec.input_fields = ["input1"]
            mock_node_spec.output_field = "output1"
            mock_node_spec.edge = None
            mock_node_spec.success_next = None
            mock_node_spec.failure_next = None
            mock_node_spec.line_number = line_number
            return mock_node_spec
        
        def create_mock_graph_spec(csv_path: Path) -> Mock:
            """Create a mock GraphSpec with realistic structure."""
            mock_spec = Mock()
            
            # Create mock NodeSpec objects
            mock_node1 = create_mock_node_spec("node1", "test_graph", 2)
            mock_node2 = create_mock_node_spec("node2", "test_graph", 3)
            
            # Configure graphs dictionary
            mock_spec.graphs = {
                "test_graph": [mock_node1, mock_node2]
            }
            mock_spec.total_rows = 2
            mock_spec.file_path = str(csv_path)
            
            # Configure methods
            mock_spec.get_graph_names.return_value = ["test_graph"]
            mock_spec.get_nodes_for_graph.return_value = mock_spec.graphs["test_graph"]
            mock_spec.has_graph.return_value = True
            
            def add_node_spec(node_spec):
                # Mock implementation of add_node_spec
                if node_spec.graph_name not in mock_spec.graphs:
                    mock_spec.graphs[node_spec.graph_name] = []
                mock_spec.graphs[node_spec.graph_name].append(node_spec)
            
            mock_spec.add_node_spec.side_effect = add_node_spec
            
            return mock_spec
        
        def create_mock_validation_result(csv_path: Path, is_valid: bool = True) -> Mock:
            """Create a mock ValidationResult with realistic structure."""
            mock_result = Mock()
            mock_result.file_path = str(csv_path)
            mock_result.file_type = "csv"
            mock_result.is_valid = is_valid
            mock_result.errors = [] if is_valid else [Mock(message="Test validation error")]
            mock_result.warnings = []
            mock_result.info = [Mock(message="CSV contains 2 rows and 5 columns")]
            mock_result.file_hash = None
            mock_result.validation_time = Mock()
            
            # Configure properties
            mock_result.has_errors = len(mock_result.errors) > 0
            mock_result.has_warnings = len(mock_result.warnings) > 0
            mock_result.has_info = len(mock_result.info) > 0
            mock_result.error_count = len(mock_result.errors)
            mock_result.warning_count = len(mock_result.warnings)
            mock_result.info_count = len(mock_result.info)
            mock_result.total_issues = len(mock_result.errors) + len(mock_result.warnings) + len(mock_result.info)
            
            # Configure methods
            def add_error(message, **kwargs):
                error = Mock()
                error.message = message
                error.level = Mock()
                error.level.value = "error"
                mock_result.errors.append(error)
                mock_result.is_valid = False
            
            def add_warning(message, **kwargs):
                warning = Mock()
                warning.message = message
                warning.level = Mock()
                warning.level.value = "warning"
                mock_result.warnings.append(warning)
            
            def add_info(message, **kwargs):
                info = Mock()
                info.message = message
                info.level = Mock()
                info.level.value = "info"
                mock_result.info.append(info)
            
            mock_result.add_error.side_effect = add_error
            mock_result.add_warning.side_effect = add_warning
            mock_result.add_info.side_effect = add_info
            
            def raise_if_invalid():
                if not mock_result.is_valid:
                    raise ValueError(f"Validation failed for {csv_path}")
            
            mock_result.raise_if_invalid.side_effect = raise_if_invalid
            
            return mock_result
        
        # Configure service methods
        mock_service.parse_csv_to_graph_spec.side_effect = create_mock_graph_spec
        mock_service.validate_csv_structure.side_effect = create_mock_validation_result
        
        return mock_service
    
    @staticmethod
    def create_mock_agent_registry_service() -> Mock:
        """
        Create a pure Mock object for AgentRegistryService.
        
        This Mock provides agent registration checking capabilities
        for determining if an agent type is already registered.
        
        Returns:
            Mock object with has_agent, get_agent_class, and list_agents methods
            
        Example:
            mock_registry = MockServiceFactory.create_mock_agent_registry_service()
            has_agent = mock_registry.has_agent("input")  # True for builtin agents
        """
        mock_service = Mock()
        
        # Default builtin agent types (can be overridden in tests)
        builtin_agents = {
            "input", "orchestrator", "default", "echo", "branching", 
            "failure", "success", "graph", "llm", "openai", "anthropic", 
            "google", "summary", "csv_reader", "csv_writer", "json_reader", 
            "json_writer", "file_reader", "file_writer", "vector_reader", "vector_writer"
        }
        
        def has_agent(agent_type: str) -> bool:
            """Check if agent type is registered (builtin or custom)."""
            return agent_type.lower() in builtin_agents
        
        def get_agent_class(agent_type: str, default=None):
            """Mock get agent class."""
            if has_agent(agent_type):
                return Mock()  # Return a mock class
            return default
        
        def list_agents() -> Dict[str, Any]:
            """List all registered agents."""
            return {agent: Mock() for agent in builtin_agents}
        
        def get_registered_agent_types() -> List[str]:
            """Get list of registered agent type names."""
            return list(builtin_agents)
        
        # Configure methods
        mock_service.has_agent.side_effect = has_agent
        mock_service.get_agent_class.side_effect = get_agent_class
        mock_service.list_agents.side_effect = list_agents
        mock_service.get_registered_agent_types.side_effect = get_registered_agent_types
        
        return mock_service
    
    @staticmethod
    def create_mock_execution_tracking_service() -> Mock:
        """
        Create a pure Mock object for ExecutionTrackingService.
        
        This Mock provides execution tracking capabilities including
        tracker creation and execution recording operations.
        
        Returns:
            Mock object with create_tracker and tracking methods
            
        Example:
            mock_tracking = MockServiceFactory.create_mock_execution_tracking_service()
            tracker = mock_tracking.create_tracker()
        """
        mock_service = Mock()
        
        def create_tracker() -> Mock:
            """Create a mock execution tracker."""
            mock_tracker = Mock()
            mock_tracker.track_inputs = True
            mock_tracker.track_outputs = False
            mock_tracker.minimal_mode = False
            mock_tracker.overall_success = True
            mock_tracker.start_time = Mock()
            mock_tracker.end_time = None
            mock_tracker.node_executions = []
            mock_tracker.node_execution_counts = {}
            
            return mock_tracker
        
        def record_node_start(tracker: Mock, node_name: str, inputs: Dict[str, Any] = None) -> None:
            """Mock record node start."""
            pass
        
        def record_node_result(tracker: Mock, node_name: str, success: bool, result: Any = None, error: str = None) -> None:
            """Mock record node result."""
            pass
        
        def complete_execution(tracker: Mock) -> None:
            """Mock complete execution."""
            pass
        
        def to_summary(tracker: Mock, graph_name: str) -> Mock:
            """Mock create execution summary."""
            mock_summary = Mock()
            mock_summary.graph_name = graph_name
            mock_summary.graph_success = True
            mock_summary.status = "completed"
            return mock_summary
        
        # Configure methods
        mock_service.create_tracker.side_effect = create_tracker
        mock_service.record_node_start.side_effect = record_node_start
        mock_service.record_node_result.side_effect = record_node_result
        mock_service.complete_execution.side_effect = complete_execution
        mock_service.to_summary.side_effect = to_summary
        
        return mock_service
    
    @staticmethod
    def create_mock_graph_factory_service() -> Mock:
        """
        Create a pure Mock object for GraphFactoryService.
        
        This Mock provides graph creation operations including name resolution,
        entry point detection, and graph object creation from various sources.
        
        Returns:
            Mock object with create_graph_from_nodes, detect_entry_point, 
            and resolve_graph_name_from_definition methods
            
        Example:
            mock_factory = MockServiceFactory.create_mock_graph_factory_service()
            graph = mock_factory.create_graph_from_nodes("test_graph", nodes_dict)
        """
        mock_service = Mock()
        
        def create_graph_from_nodes(graph_name: str, nodes_dict: Dict[str, Any], auto_detect_entry_point: bool = True) -> Mock:
            """Create a mock Graph domain model from nodes dictionary."""
            mock_graph = Mock()
            mock_graph.name = graph_name
            mock_graph.nodes = nodes_dict.copy()
            mock_graph.entry_point = list(nodes_dict.keys())[0] if nodes_dict and auto_detect_entry_point else None
            return mock_graph
        
        def create_graph_from_definition(graph_def: Dict[str, Any], graph_name: Optional[str] = None) -> Mock:
            """Create a mock Graph domain model from definition dictionary."""
            if graph_name is None:
                graph_name = "test_graph"  # Default for mock
            
            mock_graph = Mock()
            mock_graph.name = graph_name
            mock_graph.nodes = graph_def.copy()
            mock_graph.entry_point = list(graph_def.keys())[0] if graph_def else None
            return mock_graph
        
        def resolve_graph_name_from_definition(graph_def: Dict[str, Any]) -> str:
            """Mock graph name resolution from definition."""
            # Check for explicit metadata
            if hasattr(graph_def, "get") and graph_def.get("__graph_name"):
                return graph_def["__graph_name"]
            
            # Check first node's graph_name attribute
            if graph_def:
                for node_name, node in graph_def.items():
                    if hasattr(node, "graph_name") and node.graph_name:
                        return node.graph_name
            
            # Generate name based on node count
            if graph_def:
                return f"graph_{len(graph_def)}_nodes"
            
            # Fallback
            return "unknown_graph"
        
        def resolve_graph_name_from_path(path: Path) -> str:
            """Mock graph name resolution from file path."""
            return path.stem
        
        def detect_entry_point(graph: Mock) -> Optional[str]:
            """Mock entry point detection - returns first node."""
            if not graph.nodes:
                return None
            
            node_names = list(graph.nodes.keys())
            
            # Check for explicitly marked entry point
            for node_name, node in graph.nodes.items():
                if hasattr(node, "_is_entry_point") and node._is_entry_point:
                    return node_name
            
            # Return first node (simple logic as requested)
            return node_names[0] if node_names else None
        
        def validate_graph_structure(graph: Mock) -> List[str]:
            """Mock graph validation - returns empty list (valid)."""
            errors = []
            
            if not graph.nodes:
                errors.append("Graph has no nodes")
                return errors
            
            if not graph.entry_point:
                errors.append("Graph has no entry point")
            elif graph.entry_point not in graph.nodes:
                errors.append(f"Entry point '{graph.entry_point}' not found in nodes")
            
            return errors
        
        def get_graph_summary(graph: Mock) -> Dict[str, Any]:
            """Mock graph summary."""
            return {
                "name": graph.name,
                "node_count": len(graph.nodes) if graph.nodes else 0,
                "node_names": list(graph.nodes.keys()) if graph.nodes else [],
                "entry_point": graph.entry_point,
                "total_edges": 0,  # Simplified for mock
                "validation_errors": validate_graph_structure(graph)
            }
        
        # Configure methods
        mock_service.create_graph_from_nodes.side_effect = create_graph_from_nodes
        mock_service.create_graph_from_definition.side_effect = create_graph_from_definition
        mock_service.resolve_graph_name_from_definition.side_effect = resolve_graph_name_from_definition
        mock_service.resolve_graph_name_from_path.side_effect = resolve_graph_name_from_path
        mock_service.detect_entry_point.side_effect = detect_entry_point
        mock_service.validate_graph_structure.side_effect = validate_graph_structure
        mock_service.get_graph_summary.side_effect = get_graph_summary
        
        return mock_service


# Convenience functions for quick mock creation
def create_logging_service_mock(logger_name: str = "test") -> Mock:
    """Quick function to create a logging service mock."""
    return MockServiceFactory.create_mock_logging_service(logger_name)


def create_app_config_service_mock(**config_overrides) -> Mock:
    """Quick function to create an app config service mock."""
    return MockServiceFactory.create_mock_app_config_service(config_overrides)


def create_node_registry_service_mock() -> Mock:
    """Quick function to create a node registry service mock."""
    return MockServiceFactory.create_mock_node_registry_service()


def create_graph_definition_service_mock() -> Mock:
    """Quick function to create a graph definition service mock."""
    return MockServiceFactory.create_mock_graph_definition_service()


def create_graph_execution_service_mock() -> Mock:
    """Quick function to create a graph execution service mock."""
    return MockServiceFactory.create_mock_graph_execution_service()


def create_compilation_service_mock() -> Mock:
    """Quick function to create a compilation service mock."""
    return MockServiceFactory.create_mock_compilation_service()


def create_graph_bundle_service_mock() -> Mock:
    """Quick function to create a graph bundle service mock."""
    return MockServiceFactory.create_mock_graph_bundle_service()


def create_llm_service_mock() -> Mock:
    """Quick function to create an LLM service mock."""
    return MockServiceFactory.create_mock_llm_service()


def create_storage_service_manager_mock() -> Mock:
    """Quick function to create a storage service manager mock."""
    return MockServiceFactory.create_mock_storage_service_manager()


def create_execution_policy_service_mock() -> Mock:
    """Quick function to create an execution policy service mock."""
    return MockServiceFactory.create_mock_execution_policy_service()


def create_state_adapter_service_mock() -> Mock:
    """Quick function to create a state adapter service mock."""
    return MockServiceFactory.create_mock_state_adapter_service()


def create_dependency_checker_service_mock() -> Mock:
    """Quick function to create a dependency checker service mock."""
    return MockServiceFactory.create_mock_dependency_checker_service()


def create_graph_assembly_service_mock() -> Mock:
    """Quick function to create a graph assembly service mock."""
    return MockServiceFactory.create_mock_graph_assembly_service()


def create_csv_graph_parser_service_mock() -> Mock:
    """Quick function to create a CSV graph parser service mock."""
    return MockServiceFactory.create_mock_csv_graph_parser_service()


def create_execution_tracking_service_mock() -> Mock:
    """Quick function to create an execution tracking service mock."""
    return MockServiceFactory.create_mock_execution_tracking_service()


def create_agent_registry_service_mock() -> Mock:
    """Quick function to create an agent registry service mock."""
    return MockServiceFactory.create_mock_agent_registry_service()


def create_graph_factory_service_mock() -> Mock:
    """Quick function to create a graph factory service mock."""
    return MockServiceFactory.create_mock_graph_factory_service()


# Usage examples and documentation
"""
Usage Patterns and Examples:

1. Basic Service Mocking:
    # Replace MockLoggingService with pure Mock
    mock_logging = MockServiceFactory.create_mock_logging_service()
    service = MyService(logging_service=mock_logging)
    
    # Verify logging calls
    logger = mock_logging.get_class_logger.return_value
    assert ("info", "Service initialized", (), {}) in logger.calls

2. Configuration Overrides:
    # Customize config behavior
    config_overrides = {"tracking": {"enabled": False}}
    mock_config = MockServiceFactory.create_mock_app_config_service(config_overrides)
    
    # Use in service
    service = MyService(app_config_service=mock_config)
    assert not service.is_tracking_enabled()

3. Node Registry Testing:
    # Test node registration
    mock_registry = MockServiceFactory.create_mock_node_registry_service()
    mock_registry.register_node("test_node", {"type": "processor"})
    
    # Verify registration
    node = mock_registry.get_node("test_node")
    assert node["type"] == "processor"

4. Integration with Existing Tests:
    # Replace migration_utils imports
    # Old: from agentmap.migration_utils import MockLoggingService
    # New: from tests.utils.mock_service_factory import MockServiceFactory
    
    # Old: self.mock_logging = MockLoggingService()
    # New: self.mock_logging = MockServiceFactory.create_mock_logging_service()

5. GraphRunnerService Testing:
    # Create all required mocks for GraphRunnerService
    mock_graph_execution = MockServiceFactory.create_mock_graph_execution_service()
    mock_graph_definition = MockServiceFactory.create_mock_graph_definition_service()
    mock_compilation = MockServiceFactory.create_mock_compilation_service()
    
    # Test execution delegation
    result = mock_graph_execution.execute_compiled_graph(Path("test.pkl"), {})
    assert result.graph_name == "test"
    assert result.success == True
    
6. Complex Service Coordination:
    # Test service interaction patterns
    mock_deps = MockServiceFactory.create_mock_dependency_checker_service()
    has_llm, missing = mock_deps.check_llm_dependencies()
    assert has_llm == True
    assert missing == []

Benefits of Pure Mock Objects:
- Standard Python testing patterns
- No custom class maintenance
- Better IDE support and autocompletion
- Easier debugging and inspection
- Consistent behavior across all tests
- Eliminates @patch decorator awkwardness
"""
