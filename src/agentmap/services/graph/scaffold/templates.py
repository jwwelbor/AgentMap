from typing import Any, Dict

from agentmap.models.scaffold_types import ServiceRequirements
from agentmap.services.indented_template_composer import IndentedTemplateComposer


class Templates:
    def __init__(self, composer: IndentedTemplateComposer):
        """
        Initialize Templates with required IndentedTemplateComposer dependency.

        Args:
            composer: IndentedTemplateComposer service (required, no default)
        """
        self.composer = composer

    def render_agent(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> str:
        return self.composer.compose_template(agent_type, info, service_reqs)

    def render_function(self, func_name: str, info: Dict[str, Any]) -> str:
        return self.composer.compose_function_template(func_name, info)
