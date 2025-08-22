"""
ApplicationBootstrapService for AgentMap.

Centralized application bootstrapping with intelligent initialization.
Handles agent registration, feature discovery, and provides 
different bootstrap methods for various CLI commands.
"""

from typing import Optional, Set, Dict

from agentmap.services.config.agent_config_service import AgentConfigService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.logging_service import LoggingService
from agentmap.services.host_service_registry import HostServiceRegistry
from agentmap.services.agent_registry_service import AgentRegistryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from agentmap.services.protocols import DeclarationRegistryServiceProtocol
from agentmap.models.graph_bundle import GraphBundle

class ApplicationBootstrapService:
    """Centralized application bootstrapping with intelligent initialization."""
    
    def __init__(self,
                 agent_registry_service: AgentRegistryService,  # AgentRegistryService
                 features_registry_service: FeaturesRegistryService,  # FeaturesRegistryService
                 dependency_checker_service: DependencyCheckerService,  # DependencyCheckerService
                 app_config_service: AppConfigService,  # AppConfigService
                 logging_service: LoggingService,  # LoggingService
                 declaration_registry_service: DeclarationRegistryServiceProtocol,  # DeclarationRegistryService
                 host_service_registry: Optional[HostServiceRegistry] = None):  # HostServiceRegistry
        """
        Initialize ApplicationBootstrapService with required dependencies.
        
        Args:
            agent_registry_service: AgentRegistryService for agent registration
            features_registry_service: FeaturesRegistryService for feature management
            dependency_checker_service: DependencyCheckerService for dependency validation
            app_config_service: AppConfigService for application configuration
            logging_service: LoggingService for logging
            declaration_registry_service: DeclarationRegistryService for declaration-based bootstrapping
            host_service_registry: HostServiceRegistry for host service management
        """
        self.agent_registry = agent_registry_service
        self.features_registry = features_registry_service
        self.dependency_checker = dependency_checker_service
        self.app_config = app_config_service
        self.declaration_registry = declaration_registry_service
        self.host_service_registry = host_service_registry
        
        # Initialize logger using the service pattern
        self.logger = logging_service.get_class_logger(self)
        self.logging_service = logging_service
    
    def bootstrap_application(self, bundle: Optional[GraphBundle] = None) -> dict:
        """
        Main orchestration method that coordinates full application bootstrap.
        
        Process:
        1. Register core agents
        2. Register available LLM agents based on provider availability
        3. Register available storage agents based on storage availability
        4. Enable features based on availability
        5. Log bootstrap summary
        
        Returns:
            Dictionary with bootstrap status and loaded components
            
        Raises:
            RuntimeError: If critical agents cannot be registered
        """
        self.logger.info("🚀 [ApplicationBootstrapService] Starting full application bootstrap")
        
        # Step 1: Register core agents (always available)
        self._register_core_agents(bundle)
        
        # Step 2: Discover and register LLM agents based on provider availability
        self._discover_and_register_llm_agents(bundle)
        
        # Step 3: Discover and register storage agents based on storage availability
        self._discover_and_register_storage_agents(bundle)
        
        # Step 4: Register any custom agents from host services
        self._register_host_custom_agents(bundle)
        
        # Step 5: Enable features based on what was successfully registered
        self._enable_discovered_features(bundle)
        
        # Step 6: Log bootstrap summary
        summary = self._log_startup_summary(bundle)
        
        self.logger.info("✅ [ApplicationBootstrapService] Application bootstrap completed")
        
        return summary
    
    def bootstrap_for_scaffold(self) -> dict:
        """
        Bootstrap for scaffolding operations - minimal agent registration only.
        
        Returns:
            Dictionary with minimal bootstrap status
        """
        self.logger.info("🔧 [ApplicationBootstrapService] Bootstrapping for scaffold operations")
        
        # Only register core agents for scaffolding
        self._register_core_agents()
        
        # Get enabled features from the underlying model
        enabled_features = []
        if hasattr(self.features_registry, 'features_registry'):
            enabled_features = list(self.features_registry.features_registry.features_enabled)
        elif hasattr(self.features_registry, 'features_enabled'):
            enabled_features = list(self.features_registry.features_enabled)
        
        summary = {
            "service": "ApplicationBootstrapService",
            "bootstrap_type": "scaffold", 
            "bootstrap_completed": True,
            "agents_registered": len(self.agent_registry.get_registered_agent_types()),
            "features_enabled": enabled_features
        }
        
        self.logger.info("✅ [ApplicationBootstrapService] Scaffold bootstrap completed")
        return summary
    
    def bootstrap_for_validation(self) -> dict:
        """
        Bootstrap for validation operations - core agents and dependency checking.
        
        Returns:
            Dictionary with validation bootstrap status
        """
        self.logger.info("🔍 [ApplicationBootstrapService] Bootstrapping for validation operations")
        
        # Register core agents for validation
        self._register_core_agents()
        
        # Enable basic features for validation
        self.features_registry.enable_feature("validation")
        
        # Discover available providers for validation reporting
        llm_providers = self.dependency_checker.discover_and_validate_providers("llm")
        storage_providers = self.dependency_checker.discover_and_validate_providers("storage")
        
        summary = {
            "service": "ApplicationBootstrapService", 
            "bootstrap_type": "validation",
            "bootstrap_completed": True,
            "agents_registered": len(self.agent_registry.get_all_agent_types()),
            "features_enabled": list(self.features_registry.get_enabled_features()),
            "available_providers": {
                "llm": list(llm_providers.keys()) if llm_providers else [],
                "storage": list(storage_providers.keys()) if storage_providers else []
            }
        }
        
        self.logger.info("✅ [ApplicationBootstrapService] Validation bootstrap completed")
        return summary
    
    def bootstrap_for_analysis(self, graph_id: Optional[str] = None) -> dict:
        """
        Bootstrap for analysis operations - full agent discovery and feature enablement.
        
        Args:
            graph_id: Optional specific graph ID to analyze
            
        Returns:
            Dictionary with analysis bootstrap status
        """
        self.logger.info(f"📊 [ApplicationBootstrapService] Bootstrapping for analysis: {graph_id or 'all'}")
        
        # Full bootstrap for analysis (similar to main bootstrap)
        self._register_core_agents()
        self._discover_and_register_llm_agents()
        self._discover_and_register_storage_agents()
        self._enable_discovered_features()
        
        summary = {
            "service": "ApplicationBootstrapService",
            "bootstrap_type": "analysis",
            "graph_id": graph_id,
            "bootstrap_completed": True,
            "agents_registered": len(self.agent_registry.get_all_agent_types()),
            "features_enabled": list(self.features_registry.get_enabled_features())
        }
        
        self.logger.info("✅ [ApplicationBootstrapService] Analysis bootstrap completed")
        return summary
    
    # def bootstrap_for_csv(self, csv_path, config_file: Optional[str] = None) -> tuple:
    #     """
    #     Bootstrap for CSV execution - full agent registration and bundle creation.
        
    #     Args:
    #         csv_path: Path to CSV file
    #         config_file: Optional config file path
            
    #     Returns:
    #         Tuple of (container, bundle) for execution
    #     """
    #     from pathlib import Path
    #     csv_path = Path(csv_path)
    #     self.logger.info(f"🚀 [ApplicationBootstrapService] Bootstrapping for CSV execution: {csv_path}")
        
    #     # registry_service = 

    #     csv_hash = registry_service.compute_hash(csv_path)
    #     bundle_path = registry_service.find_bundle(csv_hash)

    #     if bundle_path:
    #         # Load existing bundle (no CSV parsing!)
    #         return self.bundle_service.load_bundle(bundle_path)
    #     else:
    #         # Slow path - parse CSV, compile, register
    #         bundle = self.compile_from_csv(csv_path)
    #         self.registry_service.register(csv_hash, graph_name, bundle_path, ...)
    #         return bundle



    #     # Full bootstrap for execution
    #     self.bootstrap_application()
        
    #     # Create container with all services
    #     from agentmap.di import initialize_application
    #     container = initialize_application(config_file)
        
    #     # Get bundle service and create bundle from CSV
    #     graph_bundle_service: GraphBundleService = container.graph_bundle_service()
        
    #     # Create bundle
    #     bundle = graph_bundle_service.create_bundle_from_csv(
    #         csv_path=str(csv_path)
    #     )
        
    #     self.logger.info("✅ [ApplicationBootstrapService] CSV bootstrap completed with bundle")
    #     return container, bundle
    
    def bootstrap_for_scaffold_v2(self, config_file: Optional[str] = None):
        """
        Bootstrap for scaffolding - minimal services.
        Returns the DI container for scaffolding operations.
        """
        self.logger.info("🔧 [ApplicationBootstrapService] Bootstrapping for scaffold operations")
        
        # Minimal bootstrap
        self._register_core_agents()
        
        # Create container with minimal services
        from agentmap.di import initialize_di
        container = initialize_di(config_file)
        
        self.logger.info("✅ [ApplicationBootstrapService] Scaffold bootstrap completed")
        return container
    
    def bootstrap_for_validation_v2(self, config_file: Optional[str] = None):
        """
        Bootstrap for validation - core agents and validation services.
        Returns the DI container for validation operations.
        """
        self.logger.info("🔍 [ApplicationBootstrapService] Bootstrapping for validation")
        
        # Register core agents
        self._register_core_agents()
        self.features_registry.enable_feature("validation")
        
        # Create container with validation services
        from agentmap.di import initialize_di
        container = initialize_di(config_file)
        
        self.logger.info("✅ [ApplicationBootstrapService] Validation bootstrap completed")
        return container
    
    def _register_core_agents(self, bundle: Optional[GraphBundle] = None) -> None:
        """
        Register core built-in agents that are always available.
        
        Core agents include: default, echo, branching, failure, success, input, graph, human.
        """
        self.logger.debug("[ApplicationBootstrapService] Registering core agents")
        
        core_agents = AgentConfigService.get_core_agents()

        if bundle:
            required_core_agents = self._get_common_elements(core_agents.keys(), bundle.required_agents)
        else:
            required_core_agents = core_agents.keys()
            
        
        registered_count = 0
        for agent_type in required_core_agents:
            class_path = core_agents[agent_type]
            if self._register_agent(agent_type, class_path):                
                registered_count += 1
                
        self.logger.info(f"[ApplicationBootstrapService] ✅ Registered {registered_count} core agents")
    
    def _discover_and_register_llm_agents(self, bundle: Optional[GraphBundle] = None) -> None:
        """
        Discover available LLM providers and register corresponding agents.
        """
        self.logger.debug("[ApplicationBootstrapService] Discovering and registering LLM agents")
        
        # Enable LLM feature
        self.features_registry.enable_feature("llm")
        
        # Discover available providers
        available_providers = self.dependency_checker.discover_and_validate_providers("llm")
        
        if not available_providers:
            self.logger.info("[ApplicationBootstrapService] No LLM providers available - skipping LLM agents")
            return
            
        # Get LLM agent class paths and provider mappings from AgentConfigService
        llm_agents = AgentConfigService.get_llm_agents()
        agent_to_provider_mappings = AgentConfigService.get_llm_agent_to_provider()

        if bundle:
            required_llm_agents = self._get_common_elements(llm_agents.keys(), bundle.required_agents)
        else:
            required_llm_agents = llm_agents.keys()

        
        registered_count = 0
        for agent_type in required_llm_agents:
            class_path = llm_agents[agent_type]
            required_provider = agent_to_provider_mappings.get(agent_type)
            
            # Register if provider available or if it's the base LLM agent
            if required_provider is None or available_providers.get(required_provider):
                if self._register_agent(agent_type, class_path):
                    registered_count += 1
                    
        self.logger.info(f"[ApplicationBootstrapService] ✅ Registered {registered_count} LLM agents")
        

    def _discover_and_register_storage_agents(self, bundle: Optional[GraphBundle] = None) -> None:
        """
        Discover available storage types and register corresponding agents.
        """
        self.logger.debug("[ApplicationBootstrapService] Discovering and registering storage agents")
        
        # Enable storage feature
        self.features_registry.enable_feature("storage")
        
        # Discover available storage types
        available_storage = self.dependency_checker.discover_and_validate_providers("storage")
        
        if not available_storage:
            self.logger.info("[ApplicationBootstrapService] No storage providers available - skipping storage agents")
            return
            
        # Get storage agent class paths and type mappings from AgentConfigService
        storage_agents = AgentConfigService.get_storage_agents()
        agent_to_storage_type_mappings = AgentConfigService.get_agent_to_storage_type()

        if bundle:
            required_storage_agents = self._get_common_elements(storage_agents.keys(), bundle.required_agents)
        else:
            required_storage_agents = storage_agents.keys()

        registered_count = 0
        for agent_type in required_storage_agents:
            class_path = storage_agents[agent_type]
            required_storage_type = agent_to_storage_type_mappings.get(agent_type)
            
            # Register if storage type is available
            if required_storage_type and available_storage.get(required_storage_type):
                if self._register_agent(agent_type, class_path):
                    registered_count += 1
                    
        self.logger.info(f"[ApplicationBootstrapService] ✅ Registered {registered_count} storage agents")
    
    def _register_host_custom_agents(self, bundle: Optional[GraphBundle] = None) -> None:
        """
        Register any custom agents provided by host services.
        """
        self.logger.debug("[ApplicationBootstrapService] Checking for host custom agents")
        
        # This could be extended to discover custom agents from host services
        # For now, this is a placeholder for future host integration
        
        self.logger.debug("[ApplicationBootstrapService] Host custom agent registration completed")
    
    def _enable_discovered_features(self, bundle: Optional[GraphBundle] = None) -> None:
        """
        Enable features based on what was successfully discovered and registered.
        """
        self.logger.debug("[ApplicationBootstrapService] Enabling discovered features")
        
        # Core features are always enabled
        self.features_registry.enable_feature("core")
        
        # Check what providers are available and enable corresponding features
        if (bundle and "llm" in bundle.required_services) or bundle is None:
            llm_providers = self.dependency_checker.discover_and_validate_providers("llm")
            if llm_providers:
                self.features_registry.enable_feature("llm")
                self.logger.debug(f"[ApplicationBootstrapService] LLM feature enabled with providers: {list(llm_providers.keys())}")

        if (bundle and "storage" in bundle.required_services) or bundle is None:
            storage_providers = self.dependency_checker.discover_and_validate_providers("storage")
            if storage_providers:
                self.features_registry.enable_feature("storage")
                self.logger.debug(f"[ApplicationBootstrapService] Storage feature enabled with types: {list(storage_providers.keys())}")
                    
    
    def _register_agent(self, agent_type: str, class_path: str) -> bool:
        """
        Register an agent with the registry.
        
        Args:
            agent_type: Type identifier for the agent
            class_path: Full import path to the agent class
            
        Returns:
            True if agent was registered successfully, False on error
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
            class_path: Full import path to the agent class
            
        Returns:
            The imported agent class
            
        Raises:
            ImportError: If the class cannot be imported
        """
        module_path, class_name = class_path.rsplit(".", 1)
        
        try:
            module = __import__(module_path, fromlist=[class_name])
            agent_class = getattr(module, class_name)
            return agent_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Cannot import {class_path}: {e}")
    
    def _log_startup_summary(self, bundle: Optional[GraphBundle] = None) -> dict:
        """
        Log a summary of the application bootstrap process.
        
        Returns:
            Dictionary with bootstrap summary
        """
        summary = self.get_bootstrap_summary()
        
        self.logger.info("📊 [ApplicationBootstrapService] Bootstrap Summary:")
        self.logger.info(f"   Total agents registered: {summary['total_agents']}")
        self.logger.info(f"   Features enabled: {len(summary['features_enabled'])}")
        self.logger.info(f"   Agent breakdown: {summary['agent_breakdown']}")
        
        if bundle:
            self.logger.info(f"   Bundle name: {bundle.graph_name}")
            self.logger.debug(f"   Bundle ID: {bundle.graph_id}")
            self.logger.debug(f"   Nodes: {len(bundle.nodes)}")
            self.logger.debug(f"   Required agents: {len(bundle.required_agents)}")
            self.logger.debug(f"   Required services: {len(bundle.required_services)}")

        if summary['features_enabled']:
            self.logger.debug(f"   Enabled features: {summary['features_enabled']}")
            
        return summary
    
    def get_bootstrap_summary(self) -> dict:
        """
        Get comprehensive summary of the bootstrap process.
        
        Returns:
            Dictionary with detailed bootstrap status
        """
        all_agent_types = self.agent_registry.get_registered_agent_types()
        
        # Get enabled features from the underlying model
        enabled_features = []
        if hasattr(self.features_registry, 'features_registry'):
            # Access the model's features_enabled set
            enabled_features = list(self.features_registry.features_registry.features_enabled)
        elif hasattr(self.features_registry, 'features_enabled'):
            # Direct access if available
            enabled_features = list(self.features_registry.features_enabled)
        
        # Categorize registered agents using AgentConfigService
        core_agents = AgentConfigService.get_core_agent_types()
        llm_agents = AgentConfigService.get_llm_agent_types()
        storage_agents = AgentConfigService.get_storage_agent_types()
        mixed_agents = AgentConfigService.get_mixed_dependency_agent_types()
        
        # All builtin agents
        all_builtin_agents = core_agents | llm_agents | storage_agents | mixed_agents
        
        agent_breakdown = {
            "core": len([a for a in all_agent_types if a in core_agents]),
            "llm": len([a for a in all_agent_types if a in llm_agents]),
            "storage": len([a for a in all_agent_types if a in storage_agents]),
            "mixed": len([a for a in all_agent_types if a in mixed_agents]),
            "custom": len([a for a in all_agent_types if a not in all_builtin_agents])
        }
        
        return {
            "service": "ApplicationBootstrapService",
            "bootstrap_completed": True,
            "total_agents": len(all_agent_types),
            "agent_types": sorted(list(all_agent_types)),
            "features_enabled": enabled_features,
            "agent_breakdown": agent_breakdown,
            "providers_discovered": {
                "llm": list(self.dependency_checker.discover_and_validate_providers("llm").keys()),
                "storage": list(self.dependency_checker.discover_and_validate_providers("storage").keys())
            }
        }

    # New declaration-based bootstrap methods
    
    def bootstrap_from_declarations(
        self, agent_types: Set[str], services: Set[str], protocols: Set[str]
    ) -> Dict:
        """
        Bootstrap application using only declarations without loading implementations.
        
        This method provides fast bootstrap by working with declaration metadata only,
        eliminating circular dependencies and implementation loading overhead.
        
        Args:
            agent_types: Set of agent types to register (declarations only)
            services: Set of service names to register (declarations only)
            protocols: Set of protocol names to register (declarations only)
            
        Returns:
            Dictionary with bootstrap metadata and placeholder information
        """
        self.logger.info("⚡ [ApplicationBootstrapService] Starting declaration-based bootstrap")
        
        # Initialize bootstrap metadata
        bootstrap_metadata = {
            "bootstrap_type": "declarations",
            "agent_declarations_registered": 0,
            "service_declarations_registered": 0,
            "features_enabled": [],
            "missing_declarations": [],
            "bootstrap_completed": False,
        }
        
        # Register agent declarations (placeholders for lazy loading)
        for agent_type in agent_types:
            if self._register_agent_declaration(agent_type):
                bootstrap_metadata["agent_declarations_registered"] += 1
            else:
                bootstrap_metadata["missing_declarations"].append(f"agent:{agent_type}")
        
        # Register service declarations (placeholders for lazy loading)
        for service_name in services:
            if self._register_service_declaration(service_name):
                bootstrap_metadata["service_declarations_registered"] += 1
            else:
                bootstrap_metadata["missing_declarations"].append(f"service:{service_name}")
        
        # Enable features based on declarations
        enabled_features = self._enable_features_from_declarations(agent_types, services)
        bootstrap_metadata["features_enabled"] = enabled_features
        
        bootstrap_metadata["bootstrap_completed"] = True
        
        self.logger.info(
            f"✅ [ApplicationBootstrapService] Declaration bootstrap completed: "
            f"{bootstrap_metadata['agent_declarations_registered']} agents, "
            f"{bootstrap_metadata['service_declarations_registered']} services, "
            f"{len(enabled_features)} features"
        )
        
        return bootstrap_metadata
    
    def _register_agent_declaration(self, agent_type: str) -> bool:
        """
        Register agent declaration for lazy loading without loading implementation.
        
        Args:
            agent_type: Type of agent to register declaration for
            
        Returns:
            True if declaration was found and registered, False otherwise
        """
        declaration = self.declaration_registry.get_agent_declaration(agent_type)
        if declaration:
            # Store declaration metadata for later lazy loading
            # This could be enhanced to store declaration in a registry
            self.logger.debug(f"Registered declaration for agent: {agent_type}")
            return True
        else:
            self.logger.warning(f"No declaration found for agent type: {agent_type}")
            return False
    
    def _register_service_declaration(self, service_name: str) -> bool:
        """
        Register service declaration for lazy loading without loading implementation.
        
        Args:
            service_name: Name of service to register declaration for
            
        Returns:
            True if declaration was found and registered, False otherwise
        """
        declaration = self.declaration_registry.get_service_declaration(service_name)
        if declaration:
            # Store declaration metadata for later lazy loading
            # This could be enhanced to store declaration in a registry
            self.logger.debug(f"Registered declaration for service: {service_name}")
            return True
        else:
            self.logger.warning(f"No declaration found for service: {service_name}")
            return False
    
    def _enable_features_from_declarations(
        self, agent_types: Set[str], services: Set[str]
    ) -> list[str]:
        """
        Enable features based on declared agent capabilities and services.
        
        Args:
            agent_types: Set of declared agent types
            services: Set of declared services
            
        Returns:
            List of feature names that were enabled
        """
        enabled_features = []
        
        # Always enable core features
        self.features_registry.enable_feature("core")
        enabled_features.append("core")
        
        # Enable LLM features if LLM-related agents or services are declared
        llm_indicators = {
            "llm", "openai", "anthropic", "google", "llm_service", 
            "llm_routing_service", "openai_service"
        }
        if agent_types & llm_indicators or services & llm_indicators:
            self.features_registry.enable_feature("llm")
            enabled_features.append("llm")
            self.logger.debug("Enabled LLM features based on declarations")
        
        # Enable storage features if storage-related agents or services are declared
        storage_indicators = {
            "csv_reader", "csv_writer", "json_reader", "json_writer",
            "storage_service", "blob_storage_service", "json_storage_service"
        }
        if agent_types & storage_indicators or services & storage_indicators:
            self.features_registry.enable_feature("storage")
            enabled_features.append("storage")
            self.logger.debug("Enabled storage features based on declarations")
        
        # Enable validation features if validation-related components are declared
        validation_indicators = {"validation_service", "csv_validation_service"}
        if services & validation_indicators:
            self.features_registry.enable_feature("validation")
            enabled_features.append("validation")
            self.logger.debug("Enabled validation features based on declarations")
        
        return enabled_features

    @staticmethod
    def _get_matching_elements(dict_a: dict, dict_b: dict) -> dict:
        """Return elements that exist in both dictionaries with same key-value pairs."""
        return {k: v for k, v in dict_a.items() if k in dict_b and dict_b[k] == v}
    
    @staticmethod
    def _get_common_elements(set_a: Set, set_b: Set) -> set:
        """Return elements that exist in both sets."""
        return set(set_a) & set(set_b)