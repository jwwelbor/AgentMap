"""
DeclarationParser service for AgentMap.

Service for parsing agent and service declarations from multiple formats
and normalizing them into unified declaration models. Ensures consistent
parsing behavior regardless of source format.
"""

from typing import Any, Dict, List, Union

from agentmap.models.declaration_models import (
    AgentDeclaration,
    ProtocolRequirement,
    ServiceDeclaration,
    ServiceRequirement,
)
from agentmap.services.logging_service import LoggingService


class DeclarationParser:
    """
    Parser service for normalizing declaration data into unified models.

    Handles multiple input formats (strings, simple dicts, full dicts) and
    converts them to standardized AgentDeclaration and ServiceDeclaration models.
    Provides consistent parsing behavior regardless of source format.
    """

    def __init__(self, logging_service: LoggingService):
        """Initialize parser with dependency injection."""
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[DeclarationParser] Initialized")

    def parse_agent(
        self, agent_type: str, data: Union[Dict[str, Any], str], source: str
    ) -> AgentDeclaration:
        """
        Parse agent declaration from various input formats.

        Args:
            agent_type: Type identifier for the agent
            data: Declaration data (string, simple dict, or full dict)
            source: Source tracking information

        Returns:
            Normalized AgentDeclaration model

        Raises:
            ValueError: If data format is invalid or required fields are missing
        """
        self.logger.trace(f"Parsing agent declaration for type: {agent_type}")

        try:
            if isinstance(data, str):
                # Simple string format: "agentmap.agents.EchoAgent"
                return AgentDeclaration(
                    agent_type=agent_type,
                    class_path=data.strip(),
                    source=source,
                )

            if isinstance(data, dict):
                # Extract class path from various possible locations
                class_path = self._extract_class_path(data, "agent")

                # Parse service requirements
                service_requirements = self._parse_service_requirements(
                    data.get("requires", []), data.get("services", [])
                )

                # Parse protocol requirements
                # Support both "protocols_implemented" (new) and legacy formats
                protocols_implemented = data.get("protocols_implemented", [])
                protocol_requirements = self._parse_protocol_requirements(
                    data.get("protocols", []),
                    data.get(
                        "implements", protocols_implemented
                    ),  # Use protocols_implemented as implements
                    data.get("requires_protocols", []),
                )

                # Extract capabilities (legacy field, kept for backward compatibility)
                capabilities = set(data.get("capabilities", []))

                # Extract metadata and config
                metadata = data.get("metadata", {})
                config = data.get("config", {})

                return AgentDeclaration(
                    agent_type=agent_type,
                    class_path=class_path,
                    service_requirements=service_requirements,
                    protocol_requirements=protocol_requirements,
                    capabilities=capabilities,
                    metadata=metadata,
                    config=config,
                    source=source,
                )

            raise ValueError(
                f"Unsupported data type for agent declaration: {type(data)}"
            )

        except Exception as e:
            error_msg = f"Failed to parse agent declaration for '{agent_type}' from {source}: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e

    def parse_service(
        self, service_name: str, data: Union[Dict[str, Any], str], source: str
    ) -> ServiceDeclaration:
        """
        Parse service declaration from various input formats.

        Args:
            service_name: Name of the service
            data: Declaration data (string, simple dict, or full dict)
            source: Source tracking information

        Returns:
            Normalized ServiceDeclaration model

        Raises:
            ValueError: If data format is invalid or required fields are missing
        """
        self.logger.trace(f"Parsing service declaration for: {service_name}")

        try:
            if isinstance(data, str):
                # Simple string format: "agentmap.services.EchoService"
                return ServiceDeclaration(
                    service_name=service_name,
                    class_path=data.strip(),
                    source=source,
                )

            if isinstance(data, dict):
                # Extract class path from various possible locations
                class_path = self._extract_class_path(data, "service")

                # Parse dependencies
                required_deps, optional_deps = self._parse_dependencies(
                    data.get("dependencies", []),
                    data.get("required", []),
                    data.get("optional", []),
                )

                # Parse protocols
                implements_protocols, requires_protocols = self._parse_protocols(
                    data.get("implements", []),
                    data.get("requires", []),
                    data.get("protocols", []),
                )

                # Extract service configuration
                singleton = data.get("singleton", True)
                lazy_load = data.get("lazy_load", False)
                factory_method = data.get("factory_method")

                # Extract metadata and config
                metadata = data.get("metadata", {})
                config = data.get("config", {})

                return ServiceDeclaration(
                    service_name=service_name,
                    class_path=class_path,
                    required_dependencies=required_deps,
                    optional_dependencies=optional_deps,
                    implements_protocols=implements_protocols,
                    requires_protocols=requires_protocols,
                    singleton=singleton,
                    lazy_load=lazy_load,
                    factory_method=factory_method,
                    metadata=metadata,
                    config=config,
                    source=source,
                )

            raise ValueError(
                f"Unsupported data type for service declaration: {type(data)}"
            )

        except Exception as e:
            error_msg = f"Failed to parse service declaration for '{service_name}' from {source}: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e

    @staticmethod
    def _extract_class_path(data: Dict[str, Any], declaration_type: str) -> str:
        """
        Extract class path from various possible locations in declaration data.

        Args:
            data: Declaration dictionary
            declaration_type: Type of declaration for error messages

        Returns:
            Normalized class path string

        Raises:
            ValueError: If no valid class path is found
        """
        # Try different possible locations for class path
        possible_keys = ["class_path", "class", "implementation.class", "module"]

        for key in possible_keys:
            if key in data and data[key]:
                return str(data[key]).strip()

        # Handle nested implementation structure
        if "implementation" in data and isinstance(data["implementation"], dict):
            impl = data["implementation"]
            if "class" in impl and impl["class"]:
                return str(impl["class"]).strip()

        raise ValueError(f"No valid class path found in {declaration_type} declaration")

    @staticmethod
    def _parse_service_requirements(
        requires: List[Any], services: List[Any]
    ) -> List[ServiceRequirement]:
        """
        Parse service requirements from different input structures.

        Args:
            requires: Requirements from 'requires' key
            services: Requirements from 'services' key

        Returns:
            List of ServiceRequirement models
        """
        requirements = []
        all_reqs = requires + services

        for req in all_reqs:
            if isinstance(req, str):
                requirements.append(ServiceRequirement.from_string(req))
            elif isinstance(req, dict):
                requirements.append(ServiceRequirement.from_dict(req))
            else:
                # Skip invalid requirements
                continue

        return requirements

    @staticmethod
    def _parse_protocol_requirements(
        protocols: List[Any], implements: List[Any], requires_protocols: List[Any]
    ) -> List[ProtocolRequirement]:
        """
        Parse protocol requirements from different input structures.

        Args:
            protocols: General protocol list
            implements: Protocols this agent implements
            requires_protocols: Protocols this agent requires

        Returns:
            List of ProtocolRequirement models
        """
        requirements = []

        # Parse general protocols
        for protocol in protocols:
            if isinstance(protocol, str):
                req = ProtocolRequirement.from_string(protocol)
            elif isinstance(protocol, dict):
                req = ProtocolRequirement.from_dict(protocol)
            else:
                continue
            requirements.append(req)

        # Parse implements protocols
        for protocol in implements:
            if isinstance(protocol, str):
                req = ProtocolRequirement.from_string(protocol)
                req.implements = True
            elif isinstance(protocol, dict):
                req = ProtocolRequirement.from_dict(protocol)
                req.implements = True
            else:
                continue
            requirements.append(req)

        # Parse requires protocols
        for protocol in requires_protocols:
            if isinstance(protocol, str):
                req = ProtocolRequirement.from_string(protocol)
                req.requires = True
            elif isinstance(protocol, dict):
                req = ProtocolRequirement.from_dict(protocol)
                req.requires = True
            else:
                continue
            requirements.append(req)

        return requirements

    @staticmethod
    def _parse_dependencies(
        dependencies: List[Any], required: List[Any], optional: List[Any]
    ) -> tuple[List[str], List[str]]:
        """
        Parse service dependencies into required and optional lists.

        Args:
            dependencies: General dependencies list
            required: Explicitly required dependencies
            optional: Explicitly optional dependencies

        Returns:
            Tuple of (required_dependencies, optional_dependencies)
        """
        required_deps = []
        optional_deps = []

        # Parse general dependencies (assumed required)
        for dep in dependencies:
            if isinstance(dep, str):
                required_deps.append(dep.strip())

        # Parse explicitly required dependencies
        for dep in required:
            if isinstance(dep, str):
                required_deps.append(dep.strip())

        # Parse explicitly optional dependencies
        for dep in optional:
            if isinstance(dep, str):
                optional_deps.append(dep.strip())

        # Remove duplicates while preserving order
        required_deps = list(dict.fromkeys(required_deps))
        optional_deps = list(dict.fromkeys(optional_deps))

        return required_deps, optional_deps

    @staticmethod
    def _parse_protocols(
        implements: List[Any], requires: List[Any], protocols: List[Any]
    ) -> tuple[List[str], List[str]]:
        """
        Parse protocol declarations into implements and requires lists.

        Args:
            implements: Protocols this service implements
            requires: Protocols this service requires
            protocols: General protocols list

        Returns:
            Tuple of (implements_protocols, requires_protocols)
        """
        implements_list = []
        requires_list = []

        # Parse general protocols (assumed implements)
        for protocol in protocols:
            if isinstance(protocol, str):
                implements_list.append(protocol.strip())

        # Parse implements protocols
        for protocol in implements:
            if isinstance(protocol, str):
                implements_list.append(protocol.strip())

        # Parse requires protocols
        for protocol in requires:
            if isinstance(protocol, str):
                requires_list.append(protocol.strip())

        # Remove duplicates while preserving order
        implements_list = list(dict.fromkeys(implements_list))
        requires_list = list(dict.fromkeys(requires_list))

        return implements_list, requires_list
