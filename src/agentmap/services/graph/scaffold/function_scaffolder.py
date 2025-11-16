from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.graph.scaffold.templates import Templates
from agentmap.services.logging_service import LoggingService


class FunctionScaffolder:
    def __init__(self, templates: Templates, logger: LoggingService):
        self.templates = templates
        self.logger = logger.get_class_logger(self)

    def _detect_parallel_routing(self, info: Dict[str, Any]) -> Dict[str, bool]:
        """Detect whether routing targets are parallel (list-based).

        Args:
            info: Function information dictionary containing edge targets

        Returns:
            Dictionary with 'success_parallel' and 'failure_parallel' flags
        """
        success_next = info.get("success_next")
        failure_next = info.get("failure_next")

        return {
            "success_parallel": isinstance(success_next, list)
            and len(success_next) > 1,
            "failure_parallel": isinstance(failure_next, list)
            and len(failure_next) > 1,
            "has_parallel": (
                (isinstance(success_next, list) and len(success_next) > 1)
                or (isinstance(failure_next, list) and len(failure_next) > 1)
            ),
        }

    def scaffold(
        self,
        func_name: str,
        info: Dict[str, Any],
        output_path: Path,
        overwrite: bool = False,
    ) -> Optional[Path]:
        """Scaffold routing function with parallel execution support.

        Detects whether routing targets are parallel (list-based) and
        generates appropriate code that returns lists for parallel execution.
        """
        file_name = f"{func_name}.py"
        file_path = output_path / file_name

        if file_path.exists() and not overwrite:
            return None

        # Detect parallel routing patterns
        parallel_info = self._detect_parallel_routing(info)

        # Add parallel detection to info for template rendering
        info_with_parallel = {**info, **parallel_info}

        code = self.templates.render_function(func_name, info_with_parallel)

        with file_path.open("w") as out:
            out.write(code)

        # Enhanced logging for parallel functions
        if parallel_info["has_parallel"]:
            self.logger.debug(
                f"[FunctionScaffolder] ✅ Scaffolded PARALLEL routing function: {file_path}"
            )
        else:
            self.logger.debug(
                f"[FunctionScaffolder] ✅ Scaffolded function: {file_path}"
            )

        return file_path
