"""
CustomAgentDeclarationManager for AgentMap.

Service that manages custom_agents.yaml file operations using template-based YAML generation.
Provides functionality to read, add/update, and write custom agent declarations with proper
YAML formatting and structure.

This service uses the template system to ensure consistent formatting and follows
clean architecture principles with proper dependency injection.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.indented_template_composer import IndentedTemplateComposer
from agentmap.services.logging_service import LoggingService


class CustomAgentDeclarationManager:
    """
    Service for managing custom agent declarations in YAML format.

    This service handles all operations related to custom_agents.yaml file:
    - Reading existing declarations
    - Adding new agent entries using templates
    - Updating existing agent entries
    - Writing properly formatted YAML with consistent structure

    Uses template-based YAML generation to ensure consistent formatting and
    proper structure across all declarations.
    """

    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        template_composer: IndentedTemplateComposer,
    ):
        """
        Initialize CustomAgentDeclarationManager with required dependencies.

        Args:
            app_config_service: Application configuration service
            logging_service: Logging service for error handling and debugging
            template_composer: Template composer for YAML generation
        """
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.template_composer = template_composer
        self._declarations = None
        self.file_path = self.get_custom_agents_yaml_path()

        # Template strings for YAML generation
        self.YAML_HEADER_TEMPLATE = """version: "{version}"
namespace: "{namespace}"

agents:"""

        self.AGENT_ENTRY_TEMPLATE = """  {agent_type}:
    class_path: "{class_path}"
    requires:
      services: {services_yaml}
      protocols: {protocols_yaml}"""

        self.logger.info("[CustomAgentDeclarationManager] Initialized successfully")

    def get_custom_agents_yaml_path(self) -> Path:
        """
        Get the path to the custom_agents.yaml file.

        Places the YAML file in the same directory as the Python agent files
        for easier management and co-location of related files.

        Returns:
            Path object pointing to custom_agents.yaml file
        """
        # Use the same directory as the Python agent files
        # This ensures the YAML declarations are co-located with the code
        custom_agents_dir = self.config.get_custom_agents_path()

        # Place custom_agents.yaml in the same directory as the Python files
        return custom_agents_dir / "custom_agents.yaml"

    def load_declarations(self) -> Dict[str, Any]:
        """
        Read existing custom_agents.yaml file or return empty structure.

        Returns:
            Dictionary containing the YAML structure with version, namespace, and agents
        """

        if self._declarations is not None:
            return self._declarations

        try:
            if self.file_path.exists():
                self.logger.debug(
                    f"[CustomAgentDeclarationManager] Loading declarations from {self.file_path}"
                )
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                    if content is None:
                        content = {}

                    # Ensure proper structure
                    if "agents" not in content:
                        content["agents"] = {}

                    self.logger.debug(
                        f"[CustomAgentDeclarationManager] Loaded {len(content.get('agents', {}))} agent declarations"
                    )
                    return content
            else:
                self.logger.debug(
                    f"[CustomAgentDeclarationManager] File {self.file_path} does not exist, returning empty structure"
                )
                return self._create_empty_structure()

        except Exception as e:
            self.logger.error(
                f"[CustomAgentDeclarationManager] Failed to load declarations from {self.file_path}: {e}"
            )
            raise

    def _create_empty_structure(self) -> Dict[str, Any]:
        """
        Create empty YAML structure with default values.

        Returns:
            Dictionary with default version, namespace, and empty agents section
        """
        return {"version": "1.0", "namespace": "custom", "agents": {}}

    def compose_yaml_declaration(
        self,
        agent_type: str,
        class_path: str,
        services: Optional[List[str]] = None,
        protocols: Optional[List[str]] = None,
    ) -> str:
        """
        Generate YAML string for agent declaration using template.

        Args:
            agent_type: Type identifier for the agent
            class_path: Full class path for the agent implementation
            services: List of required service names (optional)
            protocols: List of required protocol names (optional)

        Returns:
            YAML string for the agent declaration
        """
        services = services or []
        protocols = protocols or []

        # Format lists as YAML
        services_yaml = self._format_yaml_list(services)
        protocols_yaml = self._format_yaml_list(protocols)

        # Generate agent entry using template
        agent_yaml = self.AGENT_ENTRY_TEMPLATE.format(
            agent_type=agent_type,
            class_path=class_path,
            services_yaml=services_yaml,
            protocols_yaml=protocols_yaml,
        )

        self.logger.debug(
            f"[CustomAgentDeclarationManager] Composed YAML declaration for {agent_type}"
        )
        return agent_yaml

    def _format_yaml_list(self, items: List[str]) -> str:
        """
        Format a Python list as a YAML list string.

        Args:
            items: List of strings to format

        Returns:
            YAML-formatted list string
        """
        if not items:
            return "[]"
        elif len(items) == 1:
            return f'["{items[0]}"]'
        else:
            quoted_items = [f'"{item}"' for item in items]
            return f'[{", ".join(quoted_items)}]'

    def add_or_update_agent(
        self,
        agent_type: str,
        class_path: str,
        services: Optional[List[str]] = None,
        protocols: Optional[List[str]] = None,
    ) -> None:
        """
        Add new agent or update existing agent entry using template.

        Args:
            agent_type: Type identifier for the agent
            class_path: Full class path for the agent implementation
            services: List of required service names (optional)
            protocols: List of required protocol names (optional)
        """
        services = services or []
        protocols = protocols or []

        try:
            # Load existing declarations
            declarations = self.load_declarations()

            # Create agent entry
            agent_entry = {
                "class_path": class_path,
                "requires": {"services": services, "protocols": protocols},
            }

            # Add or update the agent
            declarations["agents"][agent_type] = agent_entry

            action = (
                "Updated" if agent_type in declarations.get("agents", {}) else "Added"
            )
            self.logger.info(
                f"[CustomAgentDeclarationManager] {action} agent declaration for {agent_type}"
            )

            # Save the declarations
            self.save_declarations(declarations)

        except Exception as e:
            self.logger.error(
                f"[CustomAgentDeclarationManager] Failed to add/update agent {agent_type}: {e}"
            )
            raise

    def save_declarations(self, declarations: Dict[str, Any]) -> None:
        """
        Write declarations to custom_agents.yaml file.

        Args:
            declarations: Dictionary containing the complete YAML structure
        """

        try:
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write YAML file with proper formatting
            with open(self.file_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    declarations,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                    allow_unicode=True,
                )

            self.logger.info(
                f"[CustomAgentDeclarationManager] Successfully saved declarations to {self.file_path}"
            )

        except Exception as e:
            self.logger.error(
                f"[CustomAgentDeclarationManager] Failed to save declarations to {self.file_path}: {e}"
            )
            raise

    def get_agent_declaration(self, agent_type: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific agent declaration by type.

        Args:
            agent_type: Type identifier for the agent

        Returns:
            Agent declaration dictionary or None if not found
        """
        declarations = self.load_declarations()
        return declarations.get("agents", {}).get(agent_type)

    def remove_agent_declaration(self, agent_type: str) -> bool:
        """
        Remove an agent declaration from the file.

        Args:
            agent_type: Type identifier for the agent to remove

        Returns:
            True if agent was removed, False if agent was not found
        """
        try:
            declarations = self.load_declarations()

            if agent_type in declarations.get("agents", {}):
                del declarations["agents"][agent_type]
                self.save_declarations(declarations)
                self.logger.info(
                    f"[CustomAgentDeclarationManager] Removed agent declaration for {agent_type}"
                )
                return True
            else:
                self.logger.warning(
                    f"[CustomAgentDeclarationManager] Agent {agent_type} not found for removal"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[CustomAgentDeclarationManager] Failed to remove agent {agent_type}: {e}"
            )
            raise

    def list_agent_types(self) -> List[str]:
        """
        Get list of all agent types in the declarations.

        Returns:
            List of agent type identifiers
        """
        declarations = self.load_declarations()
        return list(declarations.get("agents", {}).keys())

    def get_declaration_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current declarations file.

        Returns:
            Dictionary containing statistics about the declarations
        """
        declarations = self.load_declarations()

        return {
            "file_path": str(self.file_path),
            "file_exists": self.file_path.exists(),
            "version": declarations.get("version", "unknown"),
            "namespace": declarations.get("namespace", "unknown"),
            "total_agents": len(declarations.get("agents", {})),
            "agent_types": list(declarations.get("agents", {}).keys()),
        }
