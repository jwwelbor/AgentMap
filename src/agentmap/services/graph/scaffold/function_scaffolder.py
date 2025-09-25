from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.graph.scaffold.templates import Templates
from agentmap.services.logging_service import LoggingService


class FunctionScaffolder:
    def __init__(self, templates: Templates, logger: LoggingService):
        self.templates = templates
        self.logger = logger.get_class_logger(self)

    def scaffold(
        self, func_name: str, info: Dict[str, Any], output_path: Path, overwrite: bool = False
    ) -> Optional[Path]:
        file_name = f"{func_name}.py"
        file_path = output_path / file_name

        if file_path.exists() and not overwrite:
            return None

        code = self.templates.render_function(func_name, info)

        with file_path.open("w") as out:
            out.write(code)

        self.logger.debug(f"[FunctionScaffolder] ✅ Scaffolded function: {file_path}")
        return file_path
