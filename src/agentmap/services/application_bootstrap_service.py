"""
ApplicationBootstrapService for AgentMap.

Service that orchestrates agent registration and feature discovery by coordinating
AgentRegistryService, FeaturesRegistryService, and DependencyCheckerService.
This replaces the functionality previously handled by agents/__init__.py import-time side effects.
"""

from typing import Dict, List, Any, Optional
import os
import importlib.util
import inspect
import re
from pathlib import Path

from agentmap.services.agent_registry_service import AgentRegistryService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class ApplicationBootstrapService:
    """
    Service for orchestrating complete application bootstrap including agent registration and feature discovery.
    
    Coordinates between multiple services to provide comprehensive application initialization
    that replaces the previous agents/__init__.py import-time side effects with clean service orchestration.
    """
    
    def __init__(
        self,
        agent_registry_service: AgentRegistryService,
        features_registry_service: FeaturesRegistryService,
        dependency_checker_service: DependencyCheckerService,
        app_config_service: AppConfigService,
        logging_service: LoggingService
    ):
        """Initialize service with dependency injection following GraphRunnerService pattern."""
        self.agent_registry = agent_registry_service
        self.features_registry = features_registry_service
        self.dependency_checker = dependency_checker_service
        self.app_config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        
        self.logger.info("[ApplicationBootstrapService] Initialized with all dependencies")
        self._log_service_status()
    
    def bootstrap_application(self) -> None:
        """
        Main orchestration method that coordinates complete application bootstrap.
        
        Process:
        1. Register core agents (always available)
        2. Discover and validate LLM dependencies
        3. Register available LLM agents with aliases
        4. Discover and validate storage dependencies
        5. Register available storage agents
        6. Log startup summary
        """
        self.logger.info("🚀 [ApplicationBootstrapService] Starting application bootstrap")
        
        try:
            # Step 1: Register core agents that are always available
            self.register_core_agents()
            
            # Step 2: Register custom agents from custom_agents directory
            self.register_custom_agents()
            
            # Step 3: Discover and register LLM agents
            self.discover_and_register_llm_agents()
            
            # Step 4: Discover and register storage agents
            self.discover_and_register_storage_agents()
            
            # Step 5: Register additional mixed-dependency agents
            self.register_mixed_dependency_agents()
            
            # Step 5: Log startup summary
            self._log_startup_summary()
            
            self.logger.info("✅ [ApplicationBootstrapService] Application bootstrap completed successfully")
            
        except Exception as e:
            self.logger.error(f"❌ [ApplicationBootstrapService] Bootstrap failed: {e}")
            # Don't re-raise - use graceful degradation following storage service patterns
            self.logger.warning("[ApplicationBootstrapService] Continuing with partial bootstrap")
    
    def register_core_agents(self) -> None:
        """
        Register core agents that are always available (no external dependencies).
        
        These agents form the foundation of AgentMap and should always be registered
        regardless of optional dependencies availability.
        """
        self.logger.debug("[ApplicationBootstrapService] Registering core agents")
        
        core_agents = [
            ("default", "agentmap.agents.builtins.default_agent.DefaultAgent"),
            ("echo", "agentmap.agents.builtins.echo_agent.EchoAgent"),
            ("branching", "agentmap.agents.builtins.branching_agent.BranchingAgent"),
            ("failure", "agentmap.agents.builtins.failure_agent.FailureAgent"),
            ("success", "agentmap.agents.builtins.success_agent.SuccessAgent"),
            ("input", "agentmap.agents.builtins.input_agent.InputAgent"),
            ("graph", "agentmap.agents.builtins.graph_agent.GraphAgent")
        ]
        
        registered_count = 0
        for agent_type, class_path in core_agents:
            try:
                agent_class = self._import_agent_class(class_path)
                self.agent_registry.register_agent(agent_type, agent_class)
                registered_count += 1
                self.logger.debug(f"[ApplicationBootstrapService] ✅ Registered core agent: {agent_type}")
            except Exception as e:
                self.logger.error(f"[ApplicationBootstrapService] ❌ Failed to register core agent {agent_type}: {e}")
                # Core agents failing is serious, but don't crash the entire bootstrap
        
        self.logger.info(f"[ApplicationBootstrapService] Registered {registered_count}/{len(core_agents)} core agents")
    
    def register_custom_agents(self) -> None:
        """
        Dynamically discover and register custom agents from the custom agents directory.
        
        Scans the directory specified by app_config_service.get_custom_agents_path()
        for Python files containing agent classes and registers them automatically.
        
        This replaces the previous hardcoded agent list approach with dynamic discovery.
        """
        self.logger.debug("[ApplicationBootstrapService] Dynamically discovering custom agents")
        
        try:
            # Get custom agents directory from configuration
            custom_agents_path = self.app_config.get_custom_agents_path()
            
            if not custom_agents_path.exists():
                self.logger.info(f"[ApplicationBootstrapService] Custom agents directory not found: {custom_agents_path}")
                self.logger.info("[ApplicationBootstrapService] Skipping custom agent registration")
                return
            
            self.logger.debug(f"[ApplicationBootstrapService] Scanning custom agents directory: {custom_agents_path}")
            
            # Discover agent classes in the directory
            discovered_agents = self._discover_agent_classes(custom_agents_path)
            
            if not discovered_agents:
                self.logger.info("[ApplicationBootstrapService] No custom agent classes found")
                return
            
            # Register each discovered agent
            registered_count = 0
            for agent_type, agent_class in discovered_agents:
                try:
                    self.agent_registry.register_agent(agent_type, agent_class)
                    registered_count += 1
                    self.logger.debug(f"[ApplicationBootstrapService] ✅ Registered custom agent: {agent_type}")
                except Exception as e:
                    self.logger.error(f"[ApplicationBootstrapService] ❌ Failed to register custom agent {agent_type}: {e}")
            
            self.logger.info(f"[ApplicationBootstrapService] Registered {registered_count}/{len(discovered_agents)} custom agents")
            
        except Exception as e:
            self.logger.error(f"[ApplicationBootstrapService] Failed to register custom agents: {e}")
            # Don't re-raise - use graceful degradation
            self.logger.warning("[ApplicationBootstrapService] Continuing without custom agents")
    
    def discover_and_register_llm_agents(self) -> None:
        """
        Discover LLM providers and register available agents with proper feature coordination.
        
        Uses DependencyCheckerService for validation and FeaturesRegistryService for coordination.
        """
        self.logger.debug("[ApplicationBootstrapService] Discovering and registering LLM agents")
        
        # Enable the LLM feature (policy decision)
        self.features_registry.enable_feature("llm")
        
        # Discover and validate available providers
        available_providers = self.dependency_checker.discover_and_validate_providers("llm")
        
        # Register agents for validated providers
        registered_llm_agents = []
        for provider, is_validated in available_providers.items():
            if is_validated:
                agent_count = self._register_llm_provider_agents(provider)
                if agent_count > 0:
                    registered_llm_agents.append(provider)
        
        # Register base LLM agent if any provider is available
        if registered_llm_agents:
            self._register_base_llm_agent()
        
        # Log results
        if registered_llm_agents:
            self.logger.info(f"[ApplicationBootstrapService] ✅ LLM agents registered for providers: {registered_llm_agents}")
        else:
            self.logger.info("[ApplicationBootstrapService] ⚠️ No LLM providers available - LLM agents not registered")
            missing_deps = self.features_registry.get_missing_dependencies("llm")
            if missing_deps:
                self.logger.debug(f"[ApplicationBootstrapService] Missing LLM dependencies: {missing_deps}")
    
    def discover_and_register_storage_agents(self) -> None:
        """
        Discover storage providers and register available agents with proper feature coordination.
        
        Uses DependencyCheckerService for validation and FeaturesRegistryService for coordination.
        """
        self.logger.debug("[ApplicationBootstrapService] Discovering and registering storage agents")
        
        # Enable the storage feature (policy decision)
        self.features_registry.enable_feature("storage")
        
        # Discover and validate available storage types
        available_storage_types = self.dependency_checker.discover_and_validate_providers("storage")
        
        # Register agents for validated storage types
        registered_storage_agents = []
        for storage_type, is_validated in available_storage_types.items():
            if is_validated:
                agent_count = self._register_storage_type_agents(storage_type)
                if agent_count > 0:
                    registered_storage_agents.append(storage_type)
        
        # Log results
        if registered_storage_agents:
            self.logger.info(f"[ApplicationBootstrapService] ✅ Storage agents registered for types: {registered_storage_agents}")
        else:
            self.logger.info("[ApplicationBootstrapService] ⚠️ No storage types available - storage agents not registered")
            missing_deps = self.features_registry.get_missing_dependencies("storage")
            if missing_deps:
                self.logger.debug(f"[ApplicationBootstrapService] Missing storage dependencies: {missing_deps}")
    
    def register_mixed_dependency_agents(self) -> None:
        """
        Register agents with mixed or optional dependencies.
        
        These agents may depend on combinations of features or have optional dependencies
        that shouldn't prevent registration if core functionality is available.
        """
        self.logger.debug("[ApplicationBootstrapService] Registering mixed-dependency agents")
        
        mixed_agents = [
            ("summary", "agentmap.agents.builtins.summary_agent.SummaryAgent"),
            ("orchestrator", "agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent")
        ]
        
        registered_count = 0
        for agent_type, class_path in mixed_agents:
            if self._register_agent_if_available(agent_type, class_path):
                registered_count += 1
        
        self.logger.debug(f"[ApplicationBootstrapService] Registered {registered_count}/{len(mixed_agents)} mixed-dependency agents")
    
    def _discover_agent_classes(self, custom_agents_path: Path) -> List[tuple]:
        """
        Dynamically discover agent classes in the custom agents directory.
        
        Scans Python files for classes that appear to be agent classes based on:
        - Class name ends with 'Agent'
        - Class is not abstract
        - Class can be instantiated (has proper constructor)
        
        Args:
            custom_agents_path: Path to the custom agents directory
            
        Returns:
            List of (agent_type, agent_class) tuples
        """
        discovered_agents = []
        
        try:
            # Get all Python files in the directory
            python_files = list(custom_agents_path.glob("*.py"))
            
            if not python_files:
                self.logger.debug("[ApplicationBootstrapService] No Python files found in custom agents directory")
                return discovered_agents
            
            self.logger.debug(f"[ApplicationBootstrapService] Found {len(python_files)} Python files to scan")
            
            for py_file in python_files:
                # Skip __init__.py and other special files
                if py_file.name.startswith("_"):
                    continue
                
                try:
                    # Import the module dynamically
                    module_name = py_file.stem
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    
                    if spec is None or spec.loader is None:
                        self.logger.debug(f"[ApplicationBootstrapService] Could not load spec for {py_file}")
                        continue
                    
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find agent classes in the module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if self._is_agent_class(obj, module):
                            # Generate agent type from class name
                            agent_type = self._generate_agent_type_from_class_name(name)
                            discovered_agents.append((agent_type, obj))
                            self.logger.debug(f"[ApplicationBootstrapService] Discovered agent class: {name} -> {agent_type}")
                
                except Exception as e:
                    self.logger.warning(f"[ApplicationBootstrapService] Failed to scan {py_file}: {e}")
                    continue
            
            self.logger.debug(f"[ApplicationBootstrapService] Discovered {len(discovered_agents)} agent classes")
            return discovered_agents
            
        except Exception as e:
            self.logger.error(f"[ApplicationBootstrapService] Error during agent discovery: {e}")
            return []
    
    def _is_agent_class(self, cls, module) -> bool:
        """
        Determine if a class is an agent class based on conventions.
        
        Args:
            cls: The class object to check
            module: The module containing the class
            
        Returns:
            True if the class appears to be an agent class
        """
        try:
            # Must be defined in this module (not imported)
            if cls.__module__ != module.__name__:
                return False
            
            # Must end with 'Agent' 
            if not cls.__name__.endswith('Agent'):
                return False
            
            # Should not be abstract (should be instantiable)
            if inspect.isabstract(cls):
                return False
            
            # Should have a reasonable constructor (basic duck typing check)
            if not hasattr(cls, '__init__'):
                return False
            
            return True
            
        except Exception as e:
            self.logger.debug(f"[ApplicationBootstrapService] Error checking class {cls}: {e}")
            return False
    
    def _generate_agent_type_from_class_name(self, class_name: str) -> str:
        """
        Generate agent type identifier from class name.
        
        Converts PascalCase class names to snake_case agent types.
        
        Examples:
        - 'CombatRouterAgent' -> 'combat_router'
        - 'HelpAgentAgent' -> 'help_agent' 
        - 'MyCustomAgent' -> 'my_custom'
        
        Args:
            class_name: The class name (e.g., 'CombatRouterAgent')
            
        Returns:
            Snake case agent type identifier
        """
        # Remove 'Agent' suffix
        if class_name.endswith('Agent'):
            name_without_agent = class_name[:-5]  # Remove 'Agent'
        else:
            name_without_agent = class_name
        
        # Convert PascalCase to snake_case
        # Insert underscore before uppercase letters that follow lowercase letters
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', name_without_agent).lower()
        
        return snake_case
    
    def _register_llm_provider_agents(self, provider: str) -> int:
        """
        Register agents for a specific LLM provider with aliases.
        
        Args:
            provider: Provider name (openai, anthropic, google)
            
        Returns:
            Number of agents registered for this provider
        """
        provider_agents = {
            "openai": [
                ("openai", "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent"),
                ("gpt", "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent"),
                ("chatgpt", "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent")
            ],
            "anthropic": [
                ("anthropic", "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent"),
                ("claude", "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent")
            ],
            "google": [
                ("google", "agentmap.agents.builtins.llm.google_agent.GoogleAgent"),
                ("gemini", "agentmap.agents.builtins.llm.google_agent.GoogleAgent")
            ]
        }
        
        if provider not in provider_agents:
            self.logger.warning(f"[ApplicationBootstrapService] Unknown LLM provider: {provider}")
            return 0
        
        registered_count = 0
        for agent_type, class_path in provider_agents[provider]:
            if self._register_agent_if_available(agent_type, class_path):
                registered_count += 1
        
        self.logger.debug(f"[ApplicationBootstrapService] Registered {registered_count} agents for LLM provider: {provider}")
        return registered_count
    
    def _register_storage_type_agents(self, storage_type: str) -> int:
        """
        Register agents for a specific storage type.
        
        Args:
            storage_type: Storage type name (csv, json, file, vector, etc.)
            
        Returns:
            Number of agents registered for this storage type
        """
        storage_agents = {
            "csv": [
                ("csv_reader", "agentmap.agents.builtins.storage.csv.CSVReaderAgent"),
                ("csv_writer", "agentmap.agents.builtins.storage.csv.CSVWriterAgent")
            ],
            "json": [
                ("json_reader", "agentmap.agents.builtins.storage.json.JSONDocumentReaderAgent"),
                ("json_writer", "agentmap.agents.builtins.storage.json.JSONDocumentWriterAgent")
            ],
            "file": [
                ("file_reader", "agentmap.agents.builtins.storage.file.FileReaderAgent"),
                ("file_writer", "agentmap.agents.builtins.storage.file.FileWriterAgent")
            ],
            "vector": [
                ("vector_reader", "agentmap.agents.builtins.storage.vector.VectorReaderAgent"),
                ("vector_writer", "agentmap.agents.builtins.storage.vector.VectorWriterAgent")
            ]
        }
        
        if storage_type not in storage_agents:
            self.logger.debug(f"[ApplicationBootstrapService] No predefined agents for storage type: {storage_type}")
            return 0
        
        registered_count = 0
        for agent_type, class_path in storage_agents[storage_type]:
            if self._register_agent_if_available(agent_type, class_path):
                registered_count += 1
        
        self.logger.debug(f"[ApplicationBootstrapService] Registered {registered_count} agents for storage type: {storage_type}")
        return registered_count
    
    def _register_base_llm_agent(self) -> None:
        """Register the base LLM agent if any LLM provider is available."""
        if self._register_agent_if_available("llm", "agentmap.agents.builtins.llm.llm_agent.LLMAgent"):
            self.logger.debug("[ApplicationBootstrapService] ✅ Registered base LLM agent")
    
    def _register_agent_if_available(self, agent_type: str, class_path: str) -> bool:
        """
        Helper method to register an agent if it can be imported successfully.
        
        Provides graceful degradation - if agent can't be imported, log and continue
        rather than failing the entire bootstrap process.
        
        Args:
            agent_type: Type identifier for the agent
            class_path: Full import path to the agent class
            
        Returns:
            True if agent was registered successfully, False otherwise
        """
        try:
            agent_class = self._import_agent_class(class_path)
            self.agent_registry.register_agent(agent_type, agent_class)
            self.logger.debug(f"[ApplicationBootstrapService] ✅ Registered agent: {agent_type}")
            return True
        except ImportError as e:
            self.logger.debug(f"[ApplicationBootstrapService] ⚠️ Agent {agent_type} not available: {e}")
            return False
        except Exception as e:
            self.logger.error(f"[ApplicationBootstrapService] ❌ Failed to register agent {agent_type}: {e}")
            return False
    
    def _import_agent_class(self, class_path: str):
        """
        Import an agent class from its full path.
        
        Args:
            class_path: Full import path (e.g., 'agentmap.agents.builtins.default_agent.DefaultAgent')
            
        Returns:
            The imported agent class
            
        Raises:
            ImportError: If the class cannot be imported
        """
        module_path, class_name = class_path.rsplit('.', 1)
        
        try:
            module = __import__(module_path, fromlist=[class_name])
            agent_class = getattr(module, class_name)
            return agent_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Cannot import {class_path}: {e}")
    
    def get_bootstrap_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of the bootstrap process.
        
        Returns:
            Dictionary with bootstrap status and agent registration information
        """
        # Get agent registry status
        all_agents = self.agent_registry.list_agents()
        agent_types = self.agent_registry.get_registered_agent_types()
        
        # Get feature status
        llm_enabled = self.features_registry.is_feature_enabled("llm")
        storage_enabled = self.features_registry.is_feature_enabled("storage")
        
        # Get provider status
        llm_providers = self.features_registry.get_available_providers("llm")
        storage_providers = self.features_registry.get_available_providers("storage")
        
        summary = {
            "service": "ApplicationBootstrapService",
            "bootstrap_completed": True,
            "total_agents_registered": len(all_agents),
            "agent_types": agent_types,
            "features": {
                "llm_enabled": llm_enabled,
                "storage_enabled": storage_enabled,
                "available_llm_providers": llm_providers,
                "available_storage_providers": storage_providers
            },
            "agent_breakdown": {
                "core_agents": self._count_agents_by_prefix(agent_types, ["default", "echo", "branching", "failure", "success", "input", "graph"]),
                "custom_agents": self._count_custom_agents(agent_types),
                "llm_agents": self._count_agents_by_prefix(agent_types, ["llm", "openai", "anthropic", "google", "gpt", "claude", "gemini", "chatgpt"]),
                "storage_agents": self._count_agents_by_prefix(agent_types, ["csv_", "json_", "file_", "vector_"]),
                "mixed_agents": self._count_agents_by_prefix(agent_types, ["summary", "orchestrator"])
            },
            "missing_dependencies": {
                "llm": self.features_registry.get_missing_dependencies("llm"),
                "storage": self.features_registry.get_missing_dependencies("storage")
            }
        }
        
        return summary
    
    def _count_agents_by_prefix(self, agent_types: List[str], prefixes: List[str]) -> int:
        """Count agents that match any of the given prefixes."""
        count = 0
        for agent_type in agent_types:
            if any(agent_type.startswith(prefix) for prefix in prefixes):
                count += 1
        return count
    
    def _count_custom_agents(self, agent_types: List[str]) -> int:
        """Count custom agents (those not in core, llm, storage, or mixed categories)."""
        # Define all known built-in agent prefixes
        builtin_prefixes = [
            "default", "echo", "branching", "failure", "success", "input", "graph",  # core
            "llm", "openai", "anthropic", "google", "gpt", "claude", "gemini", "chatgpt",  # llm
            "csv_", "json_", "file_", "vector_",  # storage
            "summary", "orchestrator"  # mixed
        ]
        
        count = 0
        for agent_type in agent_types:
            # If agent doesn't match any builtin prefix, it's custom
            if not any(agent_type.startswith(prefix) for prefix in builtin_prefixes):
                count += 1
        return count
    
    def _log_startup_summary(self) -> None:
        """Log a comprehensive summary of the bootstrap process."""
        summary = self.get_bootstrap_summary()
        
        self.logger.info(f"📊 [ApplicationBootstrapService] Bootstrap Summary:")
        self.logger.info(f"   Total agents registered: {summary['total_agents_registered']}")
        self.logger.info(f"   Core agents: {summary['agent_breakdown']['core_agents']}")
        self.logger.info(f"   Custom agents: {summary['agent_breakdown']['custom_agents']}")
        self.logger.info(f"   LLM agents: {summary['agent_breakdown']['llm_agents']}")
        self.logger.info(f"   Storage agents: {summary['agent_breakdown']['storage_agents']}")
        self.logger.info(f"   Mixed agents: {summary['agent_breakdown']['mixed_agents']}")
        
        if summary['features']['available_llm_providers']:
            self.logger.info(f"   Available LLM providers: {summary['features']['available_llm_providers']}")
        
        if summary['features']['available_storage_providers']:
            self.logger.info(f"   Available storage providers: {summary['features']['available_storage_providers']}")
        
        # Log any missing dependencies
        missing_llm = summary['missing_dependencies'].get('llm', {})
        missing_storage = summary['missing_dependencies'].get('storage', {})
        
        if missing_llm:
            self.logger.debug(f"   Missing LLM dependencies: {missing_llm}")
        
        if missing_storage:
            self.logger.debug(f"   Missing storage dependencies: {missing_storage}")
    
    def _log_service_status(self) -> None:
        """Log the status of all injected services for debugging following GraphRunnerService pattern."""
        status = {
            "agent_registry_service": self.agent_registry is not None,
            "features_registry_service": self.features_registry is not None,
            "dependency_checker_service": self.dependency_checker is not None,
            "app_config_service": self.app_config is not None,
            "logging_service": self.logger is not None,
            "all_dependencies_injected": all([
                self.agent_registry is not None,
                self.features_registry is not None,
                self.dependency_checker is not None,
                self.app_config is not None,
                self.logger is not None
            ])
        }
        
        self.logger.debug(f"[ApplicationBootstrapService] Service status: {status}")
        
        if not status["all_dependencies_injected"]:
            missing_deps = []
            if not self.agent_registry:
                missing_deps.append("agent_registry_service")
            if not self.features_registry:
                missing_deps.append("features_registry_service")
            if not self.dependency_checker:
                missing_deps.append("dependency_checker_service")
            if not self.app_config:
                missing_deps.append("app_config_service")
            if not self.logger:
                missing_deps.append("logging_service")
            
            self.logger.warning(f"[ApplicationBootstrapService] Missing dependencies: {missing_deps}")
