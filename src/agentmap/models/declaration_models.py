"""
Declaration domain models for AgentMap.

This module contains unified data models for agent and service declarations
that work with any source format (Python dicts, YAML, etc.). These models
serve as the single source of truth for all declaration data regardless of format.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ServiceRequirement:
    """Pure data container for service requirement declarations.

    Attributes:
        name: Name of the required service
        optional: Whether the service is optional
        fallback: Optional fallback service name
        version: Optional version requirement
    """

    name: str
    optional: bool = False
    fallback: Optional[str] = None
    version: Optional[str] = None

    @classmethod
    def from_string(cls, requirement_string: str) -> "ServiceRequirement":
        """Create ServiceRequirement from string format.

        Args:
            requirement_string: String representation of service requirement

        Returns:
            ServiceRequirement instance
        """
        # Parse basic format like "service_name" or "service_name:version"
        parts = requirement_string.strip().split(":")
        name = parts[0]
        version = parts[1] if len(parts) > 1 else None
        return cls(name=name, version=version)

    @classmethod
    def from_dict(cls, requirement_dict: Dict[str, Any]) -> "ServiceRequirement":
        """Create ServiceRequirement from dictionary format.

        Args:
            requirement_dict: Dictionary containing service requirement data

        Returns:
            ServiceRequirement instance
        """
        return cls(
            name=requirement_dict["name"],
            optional=requirement_dict.get("optional", False),
            fallback=requirement_dict.get("fallback"),
            version=requirement_dict.get("version"),
        )


@dataclass
class ProtocolRequirement:
    """Pure data container for protocol requirement declarations.

    Attributes:
        name: Name of the protocol
        version: Optional version requirement
        implements: Whether this agent implements the protocol
        requires: Whether this agent requires the protocol
    """

    name: str
    version: Optional[str] = None
    implements: bool = False
    requires: bool = False

    @classmethod
    def from_string(cls, requirement_string: str) -> "ProtocolRequirement":
        """Create ProtocolRequirement from string format.

        Args:
            requirement_string: String representation of protocol requirement

        Returns:
            ProtocolRequirement instance
        """
        # Parse basic format like "protocol_name" or "protocol_name:version"
        parts = requirement_string.strip().split(":")
        name = parts[0]
        version = parts[1] if len(parts) > 1 else None
        return cls(name=name, version=version)

    @classmethod
    def from_dict(cls, requirement_dict: Dict[str, Any]) -> "ProtocolRequirement":
        """Create ProtocolRequirement from dictionary format.

        Args:
            requirement_dict: Dictionary containing protocol requirement data

        Returns:
            ProtocolRequirement instance
        """
        return cls(
            name=requirement_dict["name"],
            version=requirement_dict.get("version"),
            implements=requirement_dict.get("implements", False),
            requires=requirement_dict.get("requires", False),
        )


@dataclass
class AgentDeclaration:
    """Pure data container for agent declarations.

    This model only holds data - all business logic belongs in AgentFactoryService.

    Attributes:
        agent_type: Type identifier for the agent
        class_path: Full class path for agent instantiation
        service_requirements: List of required services
        protocol_requirements: List of protocol requirements
        capabilities: Set of capabilities this agent provides
        metadata: Additional metadata for the agent
        config: Configuration data for the agent
        source: Source tracking information
    """

    agent_type: str
    class_path: str
    service_requirements: List[ServiceRequirement] = field(default_factory=list)
    protocol_requirements: List[ProtocolRequirement] = field(default_factory=list)
    capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    source: str = ""

    def get_required_services(self) -> List[str]:
        """Get list of required service names.

        Returns:
            List of service names that are not optional
        """
        return [req.name for req in self.service_requirements if not req.optional]

    def get_all_services(self) -> List[str]:
        """Get list of all service names.

        Returns:
            List of all service names (required and optional)
        """
        return [req.name for req in self.service_requirements]

    def get_required_protocols(self) -> List[str]:
        """Get list of required protocol names.

        Returns:
            List of protocol names that are required
        """
        return [req.name for req in self.protocol_requirements if req.requires]


@dataclass
class ServiceDeclaration:
    """Pure data container for service declarations.

    This model only holds data - all business logic belongs in DI container services.

    Attributes:
        service_name: Name of the service
        class_path: Full class path for service instantiation
        required_dependencies: List of required dependency names
        optional_dependencies: List of optional dependency names
        implements_protocols: List of protocols this service implements
        requires_protocols: List of protocols this service requires
        singleton: Whether service should be singleton
        lazy_load: Whether service should be lazily loaded
        factory_method: Optional factory method name
        metadata: Additional metadata for the service
        config: Configuration data for the service
        source: Source tracking information
    """

    service_name: str
    class_path: str
    required_dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    implements_protocols: List[str] = field(default_factory=list)
    requires_protocols: List[str] = field(default_factory=list)
    singleton: bool = True
    lazy_load: bool = False
    factory_method: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
