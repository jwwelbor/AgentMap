"""
Host Protocol Configuration Service for clean dependency injection.

This service handles the configuration of host-defined protocols on agents,
removing the need for services to access the container directly.
"""

import re
from typing import Any

from agentmap.services.host_service_registry import HostServiceRegistry
from agentmap.services.logging_service import LoggingService


class HostProtocolConfigurationService:
    """
    Service responsible for configuring host-defined protocols on agents.

    This service encapsulates the logic for discovering which protocols an agent
    implements and automatically injecting the corresponding services. It follows
    proper dependency injection principles by receiving all dependencies through
    its constructor rather than accessing the container directly.
    """

    def __init__(
        self,
        host_service_registry: HostServiceRegistry,
        logging_service: LoggingService,
    ):
        """
        Initialize the host protocol configuration service.

        Args:
            host_service_registry: Registry containing host service registrations
            logging_service: Service for logging operations
        """
        self.registry = host_service_registry
        self.logger = logging_service.get_logger("agentmap.host_protocol_config")

    def configure_host_protocols(self, agent: Any) -> int:
        """
        Configure host-defined protocols on an agent.

        Discovers which protocols the agent implements and automatically injects
        the corresponding services by calling the appropriate configuration methods.

        Args:
            agent: Agent instance to configure

        Returns:
            Number of host services successfully configured
        """
        configured_count = 0
        agent_name = getattr(agent, "name", "unknown")

        try:
            # Get all registered services from the registry
            registered_services = self.registry.list_registered_services()

            for service_name in registered_services:
                # Skip protocol placeholders
                if service_name.startswith("protocol:"):
                    continue

                # Get protocols for this service
                protocols = self.registry.get_service_protocols(service_name)

                for protocol in protocols:
                    # Check if agent implements this protocol
                    if isinstance(agent, protocol):
                        configured = self._configure_service_for_protocol(
                            agent, service_name, protocol
                        )
                        if configured:
                            configured_count += 1

            if configured_count > 0:
                self.logger.debug(
                    f"Configured {configured_count} host services for agent '{agent_name}'"
                )
            else:
                self.logger.debug(
                    f"No host services configured for agent '{agent_name}' (no matching protocols)"
                )

        except Exception as e:
            self.logger.error(
                f"Failed to configure host protocols for agent '{agent_name}': {e}"
            )

        return configured_count

    def _configure_service_for_protocol(
        self, agent: Any, service_name: str, protocol: type
    ) -> bool:
        """
        Configure a specific service on an agent for a given protocol.

        Args:
            agent: Agent instance to configure
            service_name: Name of the service to configure
            protocol: Protocol type the agent implements

        Returns:
            True if service was successfully configured, False otherwise
        """
        agent_name = getattr(agent, "name", "unknown")

        try:
            # Get the service instance from registry
            service_instance = self._get_service_instance(service_name)
            if not service_instance:
                self.logger.warning(
                    f"Could not get instance for service '{service_name}'"
                )
                return False

            # Determine the configuration method name
            configure_method_name = self._get_configure_method_name(protocol)

            # Check if agent has the configuration method
            if hasattr(agent, configure_method_name):
                # Call the configuration method
                getattr(agent, configure_method_name)(service_instance)
                self.logger.debug(
                    f"Configured host service '{service_name}' for agent '{agent_name}' "
                    f"via method '{configure_method_name}'"
                )
                return True
            else:
                self.logger.debug(
                    f"Agent '{agent_name}' implements {protocol.__name__} "
                    f"but lacks {configure_method_name} method"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Failed to configure service '{service_name}' for agent '{agent_name}': {e}"
            )
            return False

    def _get_service_instance(self, service_name: str) -> Any:
        """
        Get a service instance from the registry.

        Args:
            service_name: Name of the service

        Returns:
            Service instance or None if not available
        """
        try:
            service_provider = self.registry.get_service_provider(service_name)
            if service_provider:
                # If provider is callable (factory/class), instantiate it
                if callable(service_provider):
                    return service_provider()
                else:
                    return service_provider
        except Exception as e:
            self.logger.error(
                f"Failed to get instance for service '{service_name}': {e}"
            )

        return None

    def _get_configure_method_name(self, protocol: type) -> str:
        """
        Convert protocol name to configuration method name.

        Examples:
            EmailServiceProtocol -> configure_email_service
            DatabaseProtocol -> configure_database_service
            MyCustomProtocol -> configure_my_custom_service
            SMSServiceProtocol -> configure_sms_service

        Args:
            protocol: Protocol type

        Returns:
            Configuration method name
        """
        protocol_name = protocol.__name__

        # Remove common suffixes
        if protocol_name.endswith("ServiceProtocol"):
            base_name = protocol_name[:-15]  # Remove 'ServiceProtocol'
        elif protocol_name.endswith("Protocol"):
            base_name = protocol_name[:-8]  # Remove 'Protocol'
        else:
            base_name = protocol_name

        # Convert to snake_case - handle acronyms and regular camelCase
        # First, handle sequences of capitals (like SMS -> sms)
        snake_case = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", base_name)
        # Then insert underscores before any capital letter that follows a lowercase letter
        snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", snake_case).lower()

        # Create method name
        return f"configure_{snake_case}_service"

    def get_configuration_status(self, agent: Any) -> dict:
        """
        Get detailed status of what host services could be configured for an agent.

        Useful for debugging and understanding why services may not be configured.

        Args:
            agent: Agent instance to analyze

        Returns:
            Dictionary with configuration status information
        """
        agent_name = getattr(agent, "name", "unknown")
        status = {
            "agent_name": agent_name,
            "agent_type": type(agent).__name__,
            "implemented_protocols": [],
            "available_services": [],
            "configuration_potential": [],
        }

        try:
            # Check all registered services
            for service_name in self.registry.list_registered_services():
                if service_name.startswith("protocol:"):
                    continue

                protocols = self.registry.get_service_protocols(service_name)
                for protocol in protocols:
                    protocol_info = {
                        "protocol": protocol.__name__,
                        "service": service_name,
                        "agent_implements": isinstance(agent, protocol),
                        "configure_method": self._get_configure_method_name(protocol),
                        "method_exists": False,
                    }

                    if isinstance(agent, protocol):
                        status["implemented_protocols"].append(protocol.__name__)
                        protocol_info["method_exists"] = hasattr(
                            agent, protocol_info["configure_method"]
                        )

                    status["configuration_potential"].append(protocol_info)

            # Get list of available services
            status["available_services"] = [
                s
                for s in self.registry.list_registered_services()
                if not s.startswith("protocol:")
            ]

            # Summary
            status["summary"] = {
                "total_protocols_implemented": len(status["implemented_protocols"]),
                "total_services_available": len(status["available_services"]),
                "configuration_ready": sum(
                    1
                    for p in status["configuration_potential"]
                    if p["agent_implements"] and p["method_exists"]
                ),
            }

        except Exception as e:
            status["error"] = str(e)

        return status
