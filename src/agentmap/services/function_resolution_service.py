from pathlib import Path
from typing import Callable, Optional

from agentmap.exceptions.service_exceptions import FunctionResolutionException


class FunctionResolutionService:
    def __init__(self, functions_path: Path):
        self.functions_path = functions_path

    def extract_reference(self, value: str) -> Optional[str]:
        """Extracts a function name from a string like 'func:my_router'.

        Args:
            value: String that may contain a function reference (e.g., 'func:my_router')

        Returns:
            Function name if found, None otherwise
        """
        if isinstance(value, str) and value.startswith("func:"):
            return value.split("func:")[1].strip()
        return None

    def extract_func_ref(self, value: str) -> Optional[str]:
        """Alias for extract_reference - extracts a function name from a string like 'func:my_router'.

        This method provides the same functionality as extract_reference() for backward compatibility
        and consistent interface across services.

        Args:
            value: String that may contain a function reference (e.g., 'func:my_router')

        Returns:
            Function name if found, None otherwise
        """
        return self.extract_reference(value)

    def load_function(self, func_name: str) -> Callable:
        """Dynamically imports the function from functions dir."""
        try:
            mod = __import__(f"agentmap.functions.{func_name}", fromlist=[func_name])
            return getattr(mod, func_name)
        except (ImportError, AttributeError) as e:
            raise FunctionResolutionException(
                f"Could not load function '{func_name}': {e}"
            )
