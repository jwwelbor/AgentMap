"""Host service configurator for AgentMap.

Handles configuration of host-defined services and execution trackers.
"""

from typing import Any, Optional


class HostServiceConfigurator:
    """Configurator for host services and execution trackers."""

    def __init__(
        self,
        logging_service: Any,
        host_protocol_configuration_service: Optional[Any] = None,
    ):
        """Initialize host service configurator.

        Args:
            logging_service: Logging service instance
            host_protocol_configuration_service: Optional host protocol configuration service
        """
        self.logger = logging_service.get_class_logger(self)
        self.host_protocol_configuration_service = host_protocol_configuration_service

    def configure_host_services(self, agent: Any) -> int:
        """Configure host-defined services for an agent.

        Args:
            agent: Agent instance to configure

        Returns:
            Number of host services configured
        """
        if not self.host_protocol_configuration_service:
            return 0

        try:
            # Delegate to host protocol configuration service
            configured = self.host_protocol_configuration_service.configure_agent(agent)
            return (
                configured if isinstance(configured, int) else (1 if configured else 0)
            )
        except Exception as e:
            self.logger.debug(f"Host service configuration skipped: {e}")
            return 0

    def configure_execution_tracker(
        self, agent: Any, tracker: Optional[Any] = None
    ) -> bool:
        """Configure execution tracker on an agent if supported.

        Args:
            agent: Agent instance to configure
            tracker: Optional execution tracker instance

        Returns:
            True if tracker was configured, False otherwise
        """
        if not tracker:
            return False

        if not hasattr(agent, "set_execution_tracker"):
            return False

        try:
            agent.set_execution_tracker(tracker)
            agent_name = getattr(agent, "name", "unknown")
            self.logger.debug(f"Execution tracker configured for agent: {agent_name}")
            return True
        except Exception as e:
            agent_name = getattr(agent, "name", "unknown")
            self.logger.warning(
                f"Failed to configure execution tracker for {agent_name}: {e}"
            )
            return False
