"""
Common utility functions for AgentMap.
"""
from typing import Optional


def extract_func_ref(value: str) -> Optional[str]:
    """Extract function name from a func: reference."""
    if isinstance(value, str) and value.startswith("func:"):
        return value.split("func:")[1].strip()
    return None

def import_function(func_name: str):
    """Import a function module by name."""
    try:
        mod = __import__(f"agentmap.functions.{func_name}", fromlist=[func_name])
        return getattr(mod, func_name)
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Could not load function '{func_name}': {e}")