"""
Simplified GraphRunnerService for AgentMap.

Pure orchestration service that coordinates graph execution by delegating to 
GraphBootstrapService and GraphExecutionService. Takes Bundle parameters only.
No CSV parsing, bundle creation, or complex dependency management.
"""

from agentmap.models.execution_result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.logging_service import LoggingService
from agentmap.services.graph.graph_bootstrap_service import GraphBootstrapService
from agentmap.services.graph.graph_execution_service import GraphExecutionService


class GraphRunnerService:
    """
    Simplified facade service for graph execution orchestration.
    
    This service only orchestrates - it takes a prepared Bundle and delegates
    to specialized services for bootstrap and execution. No bundle creation logic.
    """
    
    def __init__(
        self,
        graph_bootstrap_service: GraphBootstrapService,  # GraphBootstrapService protocol
        graph_execution_service: GraphExecutionService,  # GraphExecutionService protocol  
        logging_service: LoggingService
    ):
        """Initialize simplified orchestration service with minimal dependencies."""
        self.graph_bootstrap = graph_bootstrap_service
        self.graph_execution = graph_execution_service
        self.logger = logging_service.get_class_logger(self)
        
        self.logger.info("GraphRunnerService initialized for simplified orchestration")
    
    def run(self, bundle: GraphBundle) -> ExecutionResult:
        """
        Run graph execution using a prepared bundle.
        
        Pure orchestration: bootstrap agents from bundle, then execute.
        No bundle validation, creation, or modification.
        
        Args:
            bundle: Prepared GraphBundle with all metadata
            
        Returns:
            ExecutionResult from graph execution
            
        Raises:
            Exception: Any errors from bootstrap or execution (not swallowed)
        """
        self.logger.info(f"Running graph from bundle: {bundle.graph_name}")
        
        # Phase 1: Bootstrap agents from bundle
        self.logger.debug("Bootstrapping agents from bundle")
        agents = self.graph_bootstrap.bootstrap_agents(bundle)
        self.logger.debug(f"Bootstrap completed: {len(agents)} agents ready")
        
        # Phase 2: Execute graph with bootstrapped agents  
        self.logger.debug("Executing graph")
        result = self.graph_execution.execute(bundle, agents)
        self.logger.info(f"Graph execution completed: {result.success}")
        
        return result
