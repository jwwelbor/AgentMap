"""
Migration utilities for AgentMap architectural transition.

This module provides backward compatibility utilities and mock services
for the migration from old architecture to new service-oriented architecture.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import Mock

# Re-export key classes for backward compatibility
from agentmap.models.execution_tracker import ExecutionTracker
from agentmap.services.llm_service import LLMService
from agentmap.services.storage.manager import StorageServiceManager


class MockLogger:
    """Simple mock logger that tracks calls for testing."""
    
    def __init__(self, name: str = "test"):
        self.name = name
        self.calls = []
    
    def _log(self, level: str, message: str, *args, **kwargs):
        """Record log calls for verification."""
        self.calls.append((level, message, args, kwargs))
    
    def debug(self, message: str, *args, **kwargs):
        self._log("debug", message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        self._log("info", message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self._log("warning", message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self._log("error", message, *args, **kwargs)
    
    def trace(self, message: str, *args, **kwargs):
        self._log("trace", message, *args, **kwargs)


class MockLoggingService:
    """Mock logging service that provides consistent logger behavior."""
    
    def __init__(self):
        self._loggers = {}
    
    def get_logger(self, name: str) -> MockLogger:
        """Get or create a mock logger."""
        if name not in self._loggers:
            self._loggers[name] = MockLogger(name)
        return self._loggers[name]
    
    def get_class_logger(self, instance: object) -> MockLogger:
        """Get logger for a class instance."""
        class_name = instance.__class__.__name__
        return self.get_logger(class_name)
    
    def get_module_logger(self, module_name: str) -> MockLogger:
        """Get logger for a module."""
        return self.get_logger(module_name)


class MockAppConfigService:
    """Mock application configuration service."""
    
    def __init__(self, config_overrides: Optional[Dict[str, Any]] = None):
        self.config_overrides = config_overrides or {}
    
    def get_csv_path(self) -> Path:
        """Get default CSV path."""
        return Path(self.config_overrides.get("csv_path", "graphs/workflow.csv"))
    
    def get_compiled_graphs_path(self) -> Path:
        """Get compiled graphs directory."""
        return Path(self.config_overrides.get("compiled_graphs_path", "compiled"))
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.config_overrides.get("logging", {
            "level": "DEBUG",
            "format": "[%(levelname)s] %(name)s: %(message)s"
        })
    
    def get_execution_config(self) -> Dict[str, Any]:
        """Get execution configuration."""
        return self.config_overrides.get("execution", {
            "tracking": {"enabled": True},
            "success_policy": {"type": "all_nodes"}
        })
    
    def get_tracking_config(self) -> Dict[str, Any]:
        """Get tracking configuration."""
        return self.config_overrides.get("tracking", {
            "enabled": True,
            "track_outputs": False,
            "track_inputs": False
        })
    
    def get_prompts_config(self) -> Dict[str, Any]:
        """Get prompts configuration."""
        return self.config_overrides.get("prompts", {
            "directory": "prompts",
            "registry_file": "prompts/registry.yaml"
        })


class MockNodeRegistryService:
    """Mock node registry service."""
    
    def __init__(self):
        self.nodes = {}
    
    def register_node(self, node_name: str, node_data: Any) -> None:
        """Register a node."""
        self.nodes[node_name] = node_data
    
    def get_node(self, node_name: str) -> Optional[Any]:
        """Get a registered node."""
        return self.nodes.get(node_name)
    
    def list_nodes(self) -> List[str]:
        """List all registered nodes."""
        return list(self.nodes.keys())
    
    def clear_registry(self) -> None:
        """Clear all registered nodes."""
        self.nodes.clear()
    
    def prepare_for_assembly(self, graph_def: Dict[str, Any], graph_name: str) -> Dict[str, Any]:
        """Prepare node registry for graph assembly."""
        # Mock implementation - in real service this would do complex preparation
        return {"prepared": True, "graph_name": graph_name}
    
    def verify_pre_compilation_injection(self, node_registry: Dict[str, Any]) -> Dict[str, Any]:
        """Verify pre-compilation injection."""
        return {
            "all_injected": True,
            "has_orchestrators": False,
            "stats": {"total_nodes": 0, "injected_nodes": 0}
        }


class MockGraphBundle:
    """Mock graph bundle for testing."""
    
    def __init__(self, graph: Any = None, node_registry: Any = None, version_hash: str = "test123"):
        self.graph = graph or Mock()
        self.node_registry = node_registry
        self.version_hash = version_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bundle to dictionary."""
        return {
            "graph": self.graph,
            "node_registry": self.node_registry,
            "version_hash": self.version_hash
        }
    
    @classmethod
    def load(cls, path: Path, logger: Any = None) -> 'MockGraphBundle':
        """Load a mock graph bundle."""
        return cls()
    
    def save(self, path: Path, logger: Any = None) -> None:
        """Save the mock graph bundle."""
        pass


def mock_create_graph_builder_with_registry(csv_path: Path, node_registry_service: Any = None):
    """Mock function to create graph builder with registry."""
    # This is a mock implementation that returns appropriate test objects
    from agentmap.services.graph_builder_service import GraphBuilder
    
    # Create a mock builder that won't actually try to read the CSV
    builder = Mock(spec=GraphBuilder)
    builder.csv_path = csv_path
    builder.node_registry_service = node_registry_service or MockNodeRegistryService()
    
    # Mock the build method to return empty graph structure
    builder.build.return_value = {}
    
    return builder


# Legacy compatibility aliases for existing tests
class MockExecutionTracker(ExecutionTracker):
    """Mock execution tracker that extends the real one for testing."""
    
    def __init__(self):
        # Initialize with minimal required parameters
        super().__init__(
            graph_name="test_graph",
            tracking_config={"enabled": True, "track_outputs": False, "track_inputs": False},
            success_policy_config={"type": "all_nodes"}
        )
        
        # Override with mock behavior for testing
        self.executions = []
        self.current_execution = None
    
    def start_execution(self, graph_name: str, initial_state: Any = None) -> str:
        """Start tracking execution."""
        execution_id = f"mock_exec_{len(self.executions)}"
        self.executions.append({
            "id": execution_id,
            "graph_name": graph_name,
            "initial_state": initial_state,
            "nodes": []
        })
        self.current_execution = execution_id
        return execution_id
    
    def record_node_start(self, node_name: str, inputs: Dict[str, Any]) -> None:
        """Record node start."""
        if self.current_execution:
            execution = next(e for e in self.executions if e["id"] == self.current_execution)
            execution["nodes"].append({
                "name": node_name,
                "inputs": inputs,
                "status": "started"
            })
    
    def record_node_result(self, node_name: str, success: bool, result: Any = None, error: str = None) -> None:
        """Record node result."""
        if self.current_execution:
            execution = next(e for e in self.executions if e["id"] == self.current_execution)
            for node in execution["nodes"]:
                if node["name"] == node_name and node["status"] == "started":
                    node.update({
                        "status": "completed",
                        "success": success,
                        "result": result,
                        "error": error
                    })
                    break


# Export commonly used mock services
__all__ = [
    'MockLogger',
    'MockLoggingService', 
    'MockAppConfigService',
    'MockNodeRegistryService',
    'MockGraphBundle',
    'MockExecutionTracker',
    'ExecutionTracker',
    'LLMService',
    'StorageServiceManager',
    'mock_create_graph_builder_with_registry'
]
