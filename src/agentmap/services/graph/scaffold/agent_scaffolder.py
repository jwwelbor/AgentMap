from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.custom_agent_declaration_manager import (
    CustomAgentDeclarationManager,
)
from agentmap.services.graph.scaffold.service_requirements_parser import (
    ServiceRequirementsParser,
)
from agentmap.services.graph.scaffold.templates import Templates
from agentmap.services.logging_service import LoggingService


class AgentScaffolder:
    def __init__(
        self,
        templates: Templates,
        service_parser: ServiceRequirementsParser,
        declaration_manager: CustomAgentDeclarationManager,
        logger: LoggingService,
    ):
        self.templates = templates
        self.service_parser = service_parser
        self.declaration_manager = declaration_manager
        self.logger = logger.get_class_logger(self)

    def scaffold(
        self,
        agent_type: str,
        info: Dict[str, Any],
        output_path: Path,
        overwrite: bool = False,
    ) -> Optional[Path]:
        file_name = f"{agent_type.lower()}_agent.py"
        file_path = output_path / file_name

        if file_path.exists() and not overwrite:
            return None

        try:
            service_reqs = self.service_parser.parse_services(info.get("context"))

            if service_reqs.services:
                self.logger.debug(
                    f"[AgentScaffolder] Scaffolding {agent_type} with services: {', '.join(service_reqs.services)}"
                )

            code = self.templates.render_agent(agent_type, info, service_reqs)

            with file_path.open("w") as out:
                out.write(code)

            class_name = self._generate_agent_class_name(agent_type)
            class_path = f"{agent_type.lower()}_agent.{class_name}"

            self.declaration_manager.add_or_update_agent(
                agent_type=agent_type,
                class_path=class_path,
                services=service_reqs.services,
                protocols=service_reqs.protocols,
            )

            self.logger.debug(f"[AgentScaffolder] ✅ Scaffolded agent: {file_path}")
            return file_path

        except Exception as e:
            self.logger.error(
                f"[AgentScaffolder] Failed to scaffold agent {agent_type}: {e}"
            )
            raise

    def _generate_agent_class_name(self, agent_type: str) -> str:
        if not agent_type:
            return "Agent"
        pascal_case = self._to_pascal_case(agent_type)
        return pascal_case if pascal_case.endswith("Agent") else pascal_case + "Agent"

    def _to_pascal_case(self, text: str) -> str:
        if not text:
            return ""
        if "_" not in text and "-" not in text and text[0].isupper():
            return text
        parts = text.replace("-", "_").split("_")
        return "".join(part.capitalize() for part in parts if part)
