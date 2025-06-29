"""
ApplicationBootstrapService for AgentMap.

Service that orchestrates agent registration and feature discovery by coordinating
AgentRegistryService, FeaturesRegistryService, and DependencyCheckerService.
This replaces the functionality previously handled by agents/__init__.py import-time side effects.
"""

import importlib.util
import inspect
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmap.services.agent_registry_service import AgentRegistryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.host_service_registry import HostServiceRegistry
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
        logging_service: LoggingService,
        host_service_registry: Optional[HostServiceRegistry] = None,
    ):
        """Initialize service with dependency injection following GraphRunnerService pattern."""
        self.agent_registry = agent_registry_service
        self.features_registry = features_registry_service
        self.dependency_checker = dependency_checker_service
        self.app_config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.host_service_registry = host_service_registry

        self.logger.info(
            "[ApplicationBootstrapService] Initialized with all dependencies"
        )
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
        self.logger.info(
            "🚀 [ApplicationBootstrapService] Starting application bootstrap"
        )

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

            # Step 6: Discover and register host protocols
            self.discover_and_register_host_protocols()

            # Step 7: Log startup summary
            self._log_startup_summary()

            self.logger.info(
                "✅ [ApplicationBootstrapService] Application bootstrap completed successfully"
            )

        except Exception as e:
            self.logger.error(f"❌ [ApplicationBootstrapService] Bootstrap failed: {e}")
            # Don't re-raise - use graceful degradation following storage service patterns
            self.logger.warning(
                "[ApplicationBootstrapService] Continuing with partial bootstrap"
            )

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
            ("graph", "agentmap.agents.builtins.graph_agent.GraphAgent"),
            ("human", "agentmap.agents.builtins.human_agent.HumanAgent"),
        ]

        registered_count = 0
        for agent_type, class_path in core_agents:
            try:
                agent_class = self._import_agent_class(class_path)
                self.agent_registry.register_agent(agent_type, agent_class)
                registered_count += 1
                self.logger.debug(
                    f"[ApplicationBootstrapService] ✅ Registered core agent: {agent_type}"
                )
            except Exception as e:
                self.logger.error(
                    f"[ApplicationBootstrapService] ❌ Failed to register core agent {agent_type}: {e}"
                )
                # Core agents failing is serious, but don't crash the entire bootstrap

        self.logger.info(
            f"[ApplicationBootstrapService] Registered {registered_count}/{len(core_agents)} core agents"
        )

    def register_custom_agents(self) -> None:
        """
        Dynamically discover and register custom agents from the custom agents directory.

        Scans the directory specified by app_config_service.get_custom_agents_path()
        for Python files containing agent classes and registers them automatically.

        This replaces the previous hardcoded agent list approach with dynamic discovery.
        """
        self.logger.debug(
            "[ApplicationBootstrapService] Dynamically discovering custom agents"
        )

        try:
            # Get custom agents directory from configuration
            custom_agents_path = self.app_config.get_custom_agents_path()

            if not custom_agents_path.exists():
                self.logger.info(
                    f"[ApplicationBootstrapService] Custom agents directory not found: {custom_agents_path}"
                )
                self.logger.info(
                    "[ApplicationBootstrapService] Skipping custom agent registration"
                )
                return

            self.logger.debug(
                f"[ApplicationBootstrapService] Scanning custom agents directory: {custom_agents_path}"
            )

            # Discover agent classes in the directory
            discovered_agents = self._discover_agent_classes(custom_agents_path)

            if not discovered_agents:
                self.logger.info(
                    "[ApplicationBootstrapService] No custom agent classes found"
                )
                return

            # Register each discovered agent
            registered_count = 0
            for agent_type, agent_class in discovered_agents:
                try:
                    self.agent_registry.register_agent(agent_type, agent_class)
                    registered_count += 1
                    self.logger.debug(
                        f"[ApplicationBootstrapService] ✅ Registered custom agent: {agent_type}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"[ApplicationBootstrapService] ❌ Failed to register custom agent {agent_type}: {e}"
                    )

            self.logger.info(
                f"[ApplicationBootstrapService] Registered {registered_count}/{len(discovered_agents)} custom agents"
            )

        except Exception as e:
            self.logger.error(
                f"[ApplicationBootstrapService] Failed to register custom agents: {e}"
            )
            # Don't re-raise - use graceful degradation
            self.logger.warning(
                "[ApplicationBootstrapService] Continuing without custom agents"
            )

    def discover_and_register_llm_agents(self) -> None:
        """
        Discover LLM providers and register available agents with proper feature coordination.

        Uses DependencyCheckerService for validation and FeaturesRegistryService for coordination.
        """
        self.logger.debug(
            "[ApplicationBootstrapService] Discovering and registering LLM agents"
        )

        # Enable the LLM feature (policy decision)
        self.features_registry.enable_feature("llm")

        # Discover and validate available providers
        available_providers = self.dependency_checker.discover_and_validate_providers(
            "llm"
        )

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
            self.logger.info(
                f"[ApplicationBootstrapService] ✅ LLM agents registered for providers: {registered_llm_agents}"
            )
        else:
            self.logger.info(
                "[ApplicationBootstrapService] ⚠️ No LLM providers available - LLM agents not registered"
            )
            missing_deps = self.features_registry.get_missing_dependencies("llm")
            if missing_deps:
                self.logger.debug(
                    f"[ApplicationBootstrapService] Missing LLM dependencies: {missing_deps}"
                )

    def discover_and_register_storage_agents(self) -> None:
        """
        Discover storage providers and register available agents with proper feature coordination.

        Uses DependencyCheckerService for validation and FeaturesRegistryService for coordination.
        """
        self.logger.debug(
            "[ApplicationBootstrapService] Discovering and registering storage agents"
        )

        # Enable the storage feature (policy decision)
        self.features_registry.enable_feature("storage")

        # Discover and validate available storage types
        available_storage_types = (
            self.dependency_checker.discover_and_validate_providers("storage")
        )

        # Register agents for validated storage types
        registered_storage_agents = []
        for storage_type, is_validated in available_storage_types.items():
            if is_validated:
                agent_count = self._register_storage_type_agents(storage_type)
                if agent_count > 0:
                    registered_storage_agents.append(storage_type)

        # Log results
        if registered_storage_agents:
            self.logger.info(
                f"[ApplicationBootstrapService] ✅ Storage agents registered for types: {registered_storage_agents}"
            )
        else:
            self.logger.info(
                "[ApplicationBootstrapService] ⚠️ No storage types available - storage agents not registered"
            )
            missing_deps = self.features_registry.get_missing_dependencies("storage")
            if missing_deps:
                self.logger.debug(
                    f"[ApplicationBootstrapService] Missing storage dependencies: {missing_deps}"
                )

    def register_mixed_dependency_agents(self) -> None:
        """
        Register agents with mixed or optional dependencies.

        These agents may depend on combinations of features or have optional dependencies
        that shouldn't prevent registration if core functionality is available.
        """
        self.logger.debug(
            "[ApplicationBootstrapService] Registering mixed-dependency agents"
        )

        mixed_agents = [
            ("summary", "agentmap.agents.builtins.summary_agent.SummaryAgent"),
            (
                "orchestrator",
                "agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent",
            ),
        ]

        registered_count = 0
        for agent_type, class_path in mixed_agents:
            if self._register_agent_if_available(agent_type, class_path):
                registered_count += 1

        self.logger.debug(
            f"[ApplicationBootstrapService] Registered {registered_count}/{len(mixed_agents)} mixed-dependency agents"
        )

    def discover_and_register_host_protocols(self) -> None:
        """
        Dynamically discover and register host-defined protocols.

        Scans host-specified protocol folders for Python files containing protocol classes
        and registers them for use by the host application's dependency injection system.

        This extends the existing dynamic discovery patterns used for agents to support
        host application extensibility without affecting core AgentMap functionality.
        """
        self.logger.debug(
            "[ApplicationBootstrapService] Discovering and registering host protocols"
        )

        try:
            # Check if host application support is enabled
            if not self.app_config.is_host_application_enabled():
                self.logger.debug(
                    "[ApplicationBootstrapService] Host application support disabled, skipping protocol discovery"
                )
                return

            # Get protocol discovery folders from configuration
            protocol_folders = self.app_config.get_host_protocol_folders()

            if not protocol_folders:
                self.logger.debug(
                    "[ApplicationBootstrapService] No host protocol folders configured"
                )
                return

            self.logger.debug(
                f"[ApplicationBootstrapService] Scanning {len(protocol_folders)} protocol folders"
            )

            # Discover protocol classes across all configured folders
            discovered_protocols = self._discover_protocol_classes(protocol_folders)

            if not discovered_protocols:
                self.logger.info(
                    "[ApplicationBootstrapService] No host protocol classes found"
                )
                return

            # Register discovered protocols
            registered_count = self._register_discovered_protocols(discovered_protocols)

            self.logger.info(
                f"[ApplicationBootstrapService] ✅ Registered {registered_count}/{len(discovered_protocols)} host protocols"
            )

        except Exception as e:
            self.logger.error(
                f"[ApplicationBootstrapService] Failed to discover host protocols: {e}"
            )
            # Don't re-raise - use graceful degradation following storage service patterns
            self.logger.warning(
                "[ApplicationBootstrapService] Continuing without host protocols"
            )

    def _discover_protocol_classes(self, protocol_folders: List[Path]) -> List[tuple]:
        """
        Dynamically discover protocol classes in the specified folders.

        Reuses the existing agent discovery patterns but adapted for protocol classes.
        Scans Python files for classes that appear to be protocol classes based on:
        - Class name ends with 'Protocol' or contains 'Protocol'
        - Class is defined using typing.Protocol or similar patterns
        - Class has appropriate protocol characteristics

        Args:
            protocol_folders: List of Path objects to scan for protocols

        Returns:
            List of (protocol_name, protocol_class) tuples
        """
        discovered_protocols = []

        try:
            for protocol_folder in protocol_folders:
                if not protocol_folder.exists():
                    self.logger.debug(
                        f"[ApplicationBootstrapService] Protocol folder not found: {protocol_folder}"
                    )
                    continue

                if not protocol_folder.is_dir():
                    self.logger.warning(
                        f"[ApplicationBootstrapService] Protocol path is not a directory: {protocol_folder}"
                    )
                    continue

                self.logger.debug(
                    f"[ApplicationBootstrapService] Scanning protocol folder: {protocol_folder}"
                )

                # Get all Python files in the folder
                python_files = list(protocol_folder.glob("*.py"))

                if not python_files:
                    self.logger.debug(
                        f"[ApplicationBootstrapService] No Python files found in: {protocol_folder}"
                    )
                    continue

                self.logger.debug(
                    f"[ApplicationBootstrapService] Found {len(python_files)} Python files in {protocol_folder}"
                )

                for py_file in python_files:
                    # Skip __init__.py and other special files
                    if py_file.name.startswith("_"):
                        continue

                    try:
                        # Import the module dynamically
                        module_name = py_file.stem
                        spec = importlib.util.spec_from_file_location(
                            module_name, py_file
                        )

                        if spec is None or spec.loader is None:
                            self.logger.debug(
                                f"[ApplicationBootstrapService] Could not load spec for {py_file}"
                            )
                            continue

                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Find protocol classes in the module
                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            if self._is_protocol_class(obj, module):
                                # Generate protocol name from class name
                                protocol_name = (
                                    self._generate_protocol_name_from_class_name(name)
                                )
                                discovered_protocols.append((protocol_name, obj))
                                self.logger.debug(
                                    f"[ApplicationBootstrapService] Discovered protocol class: {name} -> {protocol_name}"
                                )

                    except Exception as e:
                        self.logger.warning(
                            f"[ApplicationBootstrapService] Failed to scan protocol file {py_file}: {e}"
                        )
                        continue

            self.logger.debug(
                f"[ApplicationBootstrapService] Discovered {len(discovered_protocols)} protocol classes total"
            )
            return discovered_protocols

        except Exception as e:
            self.logger.error(
                f"[ApplicationBootstrapService] Error during protocol discovery: {e}"
            )
            return []

    def _is_protocol_class(self, cls, module) -> bool:
        """
        Determine if a class is a protocol class based on conventions.

        Args:
            cls: The class object to check
            module: The module containing the class

        Returns:
            True if the class appears to be a protocol class
        """
        try:
            # Must be defined in this module (not imported)
            if cls.__module__ != module.__name__:
                return False

            # Should have 'Protocol' in the name or be a typing.Protocol subclass
            class_name = cls.__name__

            # Check for Protocol naming conventions
            if not (class_name.endswith("Protocol") or "Protocol" in class_name):
                return False

            # Check if it's a typing.Protocol subclass (best indicator)
            try:
                import typing

                if hasattr(typing, "Protocol"):
                    # Check if it's a Protocol subclass
                    mro = inspect.getmro(cls)
                    for base in mro:
                        if hasattr(base, "_is_protocol") and getattr(
                            base, "_is_protocol", False
                        ):
                            return True
                        # Also check for typing.Protocol itself
                        if (
                            getattr(base, "__module__", "") == "typing"
                            and base.__name__ == "Protocol"
                        ):
                            return True
            except Exception:
                pass

            # Fallback: check for protocol-like characteristics
            # Protocols typically have abstract methods or are designed as interfaces
            if inspect.isabstract(cls):
                return True

            # Check for common protocol patterns (methods without implementation)
            try:
                methods = inspect.getmembers(cls, predicate=inspect.isfunction)
                if methods:
                    # If it has methods that look like interface definitions
                    for method_name, method in methods:
                        if not method_name.startswith("_"):
                            # Found public methods, likely a protocol
                            return True
            except Exception:
                pass

            return False

        except Exception as e:
            self.logger.debug(
                f"[ApplicationBootstrapService] Error checking protocol class {cls}: {e}"
            )
            return False

    def _generate_protocol_name_from_class_name(self, class_name: str) -> str:
        """
        Generate protocol name identifier from class name.

        Converts PascalCase protocol class names to snake_case protocol names.

        Examples:
        - 'DatabaseServiceProtocol' -> 'database_service'
        - 'LLMCapableProtocol' -> 'llm_capable'
        - 'CustomHostProtocol' -> 'custom_host'

        Args:
            class_name: The class name (e.g., 'DatabaseServiceProtocol')

        Returns:
            Snake case protocol name identifier
        """
        # Remove 'Protocol' suffix
        if class_name.endswith("Protocol"):
            name_without_protocol = class_name[:-8]  # Remove 'Protocol'
        else:
            name_without_protocol = class_name

        # Convert PascalCase to snake_case
        # First, handle sequences of uppercase letters followed by lowercase
        # e.g., "HTTPSConnection" -> "HTTPS_Connection" -> "https_connection"
        # This regex adds underscore before uppercase letters that:
        # 1. Follow a lowercase letter OR
        # 2. Are followed by a lowercase letter and preceded by another uppercase letter
        s1 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name_without_protocol)
        s2 = re.sub("([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
        snake_case = s2.lower()

        return snake_case

    def _register_discovered_protocols(self, protocols: List[tuple]) -> int:
        """
        Register discovered protocol classes with the host service registry.

        This registers the protocol definitions so they can be tracked and
        the host application can later register implementations for them.

        Args:
            protocols: List of (protocol_name, protocol_class) tuples

        Returns:
            Number of protocols successfully registered
        """
        registered_count = 0

        if not self.host_service_registry:
            self.logger.warning(
                "[ApplicationBootstrapService] HostServiceRegistry not available, skipping protocol registration"
            )
            return 0

        try:
            for protocol_name, protocol_class in protocols:
                try:
                    # Register the protocol as a "discovered" protocol
                    # This creates a placeholder registration that can be filled with an implementation later
                    self.host_service_registry.register_service_provider(
                        service_name=f"protocol:{protocol_name}",  # Prefix to indicate it's a protocol placeholder
                        provider=None,  # No implementation yet
                        protocols=[protocol_class],
                        metadata={
                            "type": "discovered_protocol",
                            "protocol_name": protocol_name,
                            "protocol_class": protocol_class.__name__,
                            "module": protocol_class.__module__,
                            "discovered_at": "bootstrap",
                            "implementation_status": "pending",
                        },
                    )

                    self.logger.debug(
                        f"[ApplicationBootstrapService] Registered discovered protocol: {protocol_name} -> {protocol_class.__name__}"
                    )
                    registered_count += 1

                except Exception as e:
                    self.logger.error(
                        f"[ApplicationBootstrapService] Failed to register protocol {protocol_name}: {e}"
                    )
                    continue

            if registered_count > 0:
                self.logger.info(
                    f"[ApplicationBootstrapService] Successfully registered {registered_count} discovered host protocols"
                )

                # Log a summary of discovered protocols for the host application
                discovered_protocols = self._get_discovered_protocols_summary()
                if discovered_protocols:
                    self.logger.info(
                        "[ApplicationBootstrapService] Discovered protocols awaiting implementation:"
                    )
                    for proto_info in discovered_protocols:
                        self.logger.info(
                            f"  - {proto_info['name']}: {proto_info['class']} (from {proto_info['module']})"
                        )

            return registered_count

        except Exception as e:
            self.logger.error(
                f"[ApplicationBootstrapService] Error during protocol registration: {e}"
            )
            return 0

    def _get_discovered_protocols_summary(self) -> List[Dict[str, str]]:
        """
        Get a summary of discovered protocols that need implementation.

        Returns:
            List of protocol information dictionaries
        """
        if not self.host_service_registry:
            return []

        discovered_protocols = []

        try:
            # Get all registered services
            all_services = self.host_service_registry.list_registered_services()

            for service_name in all_services:
                if service_name.startswith("protocol:"):
                    metadata = self.host_service_registry.get_service_metadata(
                        service_name
                    )
                    if metadata and metadata.get("type") == "discovered_protocol":
                        discovered_protocols.append(
                            {
                                "name": metadata.get("protocol_name", "unknown"),
                                "class": metadata.get("protocol_class", "unknown"),
                                "module": metadata.get("module", "unknown"),
                                "status": metadata.get(
                                    "implementation_status", "unknown"
                                ),
                            }
                        )
        except Exception as e:
            self.logger.error(
                f"[ApplicationBootstrapService] Error getting discovered protocols summary: {e}"
            )

        return discovered_protocols

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
                self.logger.debug(
                    "[ApplicationBootstrapService] No Python files found in custom agents directory"
                )
                return discovered_agents

            self.logger.debug(
                f"[ApplicationBootstrapService] Found {len(python_files)} Python files to scan"
            )

            for py_file in python_files:
                # Skip __init__.py and other special files
                if py_file.name.startswith("_"):
                    continue

                try:
                    # Import the module dynamically
                    module_name = py_file.stem
                    spec = importlib.util.spec_from_file_location(module_name, py_file)

                    if spec is None or spec.loader is None:
                        self.logger.debug(
                            f"[ApplicationBootstrapService] Could not load spec for {py_file}"
                        )
                        continue

                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find agent classes in the module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if self._is_agent_class(obj, module):
                            # Generate agent type from class name
                            agent_type = self._generate_agent_type_from_class_name(name)
                            discovered_agents.append((agent_type, obj))
                            self.logger.debug(
                                f"[ApplicationBootstrapService] Discovered agent class: {name} -> {agent_type}"
                            )

                except Exception as e:
                    self.logger.warning(
                        f"[ApplicationBootstrapService] Failed to scan {py_file}: {e}"
                    )
                    continue

            self.logger.debug(
                f"[ApplicationBootstrapService] Discovered {len(discovered_agents)} agent classes"
            )
            return discovered_agents

        except Exception as e:
            self.logger.error(
                f"[ApplicationBootstrapService] Error during agent discovery: {e}"
            )
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
            if not cls.__name__.endswith("Agent"):
                return False

            # Should not be abstract (should be instantiable)
            if inspect.isabstract(cls):
                return False

            # Should have a reasonable constructor (basic duck typing check)
            if not hasattr(cls, "__init__"):
                return False

            return True

        except Exception as e:
            self.logger.debug(
                f"[ApplicationBootstrapService] Error checking class {cls}: {e}"
            )
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
        if class_name.endswith("Agent"):
            name_without_agent = class_name[:-5]  # Remove 'Agent'
        else:
            name_without_agent = class_name

        # Convert PascalCase to snake_case
        # Insert underscore before uppercase letters that follow lowercase letters
        snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", name_without_agent).lower()

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
                ("chatgpt", "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent"),
            ],
            "anthropic": [
                (
                    "anthropic",
                    "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent",
                ),
                (
                    "claude",
                    "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent",
                ),
            ],
            "google": [
                ("google", "agentmap.agents.builtins.llm.google_agent.GoogleAgent"),
                ("gemini", "agentmap.agents.builtins.llm.google_agent.GoogleAgent"),
            ],
        }

        if provider not in provider_agents:
            self.logger.warning(
                f"[ApplicationBootstrapService] Unknown LLM provider: {provider}"
            )
            return 0

        registered_count = 0
        for agent_type, class_path in provider_agents[provider]:
            if self._register_agent_if_available(agent_type, class_path):
                registered_count += 1

        self.logger.debug(
            f"[ApplicationBootstrapService] Registered {registered_count} agents for LLM provider: {provider}"
        )
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
                ("csv_writer", "agentmap.agents.builtins.storage.csv.CSVWriterAgent"),
            ],
            "json": [
                (
                    "json_reader",
                    "agentmap.agents.builtins.storage.json.JSONDocumentReaderAgent",
                ),
                (
                    "json_writer",
                    "agentmap.agents.builtins.storage.json.JSONDocumentWriterAgent",
                ),
            ],
            "file": [
                (
                    "file_reader",
                    "agentmap.agents.builtins.storage.file.FileReaderAgent",
                ),
                (
                    "file_writer",
                    "agentmap.agents.builtins.storage.file.FileWriterAgent",
                ),
            ],
            "vector": [
                (
                    "vector_reader",
                    "agentmap.agents.builtins.storage.vector.VectorReaderAgent",
                ),
                (
                    "vector_writer",
                    "agentmap.agents.builtins.storage.vector.VectorWriterAgent",
                ),
            ],
        }

        if storage_type not in storage_agents:
            self.logger.debug(
                f"[ApplicationBootstrapService] No predefined agents for storage type: {storage_type}"
            )
            return 0

        registered_count = 0
        for agent_type, class_path in storage_agents[storage_type]:
            if self._register_agent_if_available(agent_type, class_path):
                registered_count += 1

        self.logger.debug(
            f"[ApplicationBootstrapService] Registered {registered_count} agents for storage type: {storage_type}"
        )
        return registered_count

    def _register_base_llm_agent(self) -> None:
        """Register the base LLM agent if any LLM provider is available."""
        if self._register_agent_if_available(
            "llm", "agentmap.agents.builtins.llm.llm_agent.LLMAgent"
        ):
            self.logger.debug(
                "[ApplicationBootstrapService] ✅ Registered base LLM agent"
            )

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
            self.logger.debug(
                f"[ApplicationBootstrapService] ✅ Registered agent: {agent_type}"
            )
            return True
        except ImportError as e:
            self.logger.debug(
                f"[ApplicationBootstrapService] ⚠️ Agent {agent_type} not available: {e}"
            )
            return False
        except Exception as e:
            self.logger.error(
                f"[ApplicationBootstrapService] ❌ Failed to register agent {agent_type}: {e}"
            )
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
        module_path, class_name = class_path.rsplit(".", 1)

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
                "available_storage_providers": storage_providers,
                "host_application_enabled": self.app_config.is_host_application_enabled(),
            },
            "agent_breakdown": {
                "core_agents": self._count_agents_by_prefix(
                    agent_types,
                    [
                        "default",
                        "echo",
                        "branching",
                        "failure",
                        "success",
                        "input",
                        "graph",
                        "human",
                    ],
                ),
                "custom_agents": self._count_custom_agents(agent_types),
                "llm_agents": self._count_agents_by_prefix(
                    agent_types,
                    [
                        "llm",
                        "openai",
                        "anthropic",
                        "google",
                        "gpt",
                        "claude",
                        "gemini",
                        "chatgpt",
                    ],
                ),
                "storage_agents": self._count_agents_by_prefix(
                    agent_types, ["csv_", "json_", "file_", "vector_"]
                ),
                "mixed_agents": self._count_agents_by_prefix(
                    agent_types, ["summary", "orchestrator"]
                ),
            },
            "host_application": {
                "enabled": self.app_config.is_host_application_enabled(),
                "protocol_folders_configured": len(
                    self.app_config.get_host_protocol_folders()
                ),
                "protocol_discovery_available": True,
            },
            "missing_dependencies": {
                "llm": self.features_registry.get_missing_dependencies("llm"),
                "storage": self.features_registry.get_missing_dependencies("storage"),
            },
        }

        return summary

    def _count_agents_by_prefix(
        self, agent_types: List[str], prefixes: List[str]
    ) -> int:
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
            "default",
            "echo",
            "branching",
            "failure",
            "success",
            "input",
            "graph",
            "human",  # core
            "llm",
            "openai",
            "anthropic",
            "google",
            "gpt",
            "claude",
            "gemini",
            "chatgpt",  # llm
            "csv_",
            "json_",
            "file_",
            "vector_",  # storage
            "summary",
            "orchestrator",  # mixed
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
        self.logger.info(
            f"   Total agents registered: {summary['total_agents_registered']}"
        )
        self.logger.info(f"   Core agents: {summary['agent_breakdown']['core_agents']}")
        self.logger.info(
            f"   Custom agents: {summary['agent_breakdown']['custom_agents']}"
        )
        self.logger.info(f"   LLM agents: {summary['agent_breakdown']['llm_agents']}")
        self.logger.info(
            f"   Storage agents: {summary['agent_breakdown']['storage_agents']}"
        )
        self.logger.info(
            f"   Mixed agents: {summary['agent_breakdown']['mixed_agents']}"
        )

        if summary["features"]["available_llm_providers"]:
            self.logger.info(
                f"   Available LLM providers: {summary['features']['available_llm_providers']}"
            )

        if summary["features"]["available_storage_providers"]:
            self.logger.info(
                f"   Available storage providers: {summary['features']['available_storage_providers']}"
            )

        # Log host application status
        if summary["features"]["host_application_enabled"]:
            self.logger.info(
                f"   Host application enabled with {summary['host_application']['protocol_folders_configured']} protocol folders"
            )

        # Log any missing dependencies
        missing_llm = summary["missing_dependencies"].get("llm", {})
        missing_storage = summary["missing_dependencies"].get("storage", {})

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
            "all_dependencies_injected": all(
                [
                    self.agent_registry is not None,
                    self.features_registry is not None,
                    self.dependency_checker is not None,
                    self.app_config is not None,
                    self.logger is not None,
                ]
            ),
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

            self.logger.warning(
                f"[ApplicationBootstrapService] Missing dependencies: {missing_deps}"
            )
