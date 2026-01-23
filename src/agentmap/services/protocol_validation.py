"""
Protocol validation utilities for HostServiceRegistry.

This module provides standalone functions for validating protocol types,
used by the registry and other components that need protocol validation.
"""

import inspect
import logging
from typing import Optional, Type


def is_valid_protocol(protocol: Type, logger: Optional[logging.Logger] = None) -> bool:
    """
    Validate that an object is a proper protocol type.

    Args:
        protocol: Object to validate as a protocol
        logger: Optional logger for debug output

    Returns:
        True if the object is a valid protocol type
    """
    try:
        # Must be a type/class
        if not inspect.isclass(protocol):
            return False

        # Check if it looks like a Protocol (has _is_protocol marker)
        if hasattr(protocol, "_is_protocol") and getattr(
            protocol, "_is_protocol", False
        ):
            return True

        # Check if it inherits from typing.Protocol
        import typing

        if hasattr(typing, "Protocol"):
            mro = inspect.getmro(protocol)
            for base in mro:
                if (
                    getattr(base, "__module__", "") == "typing"
                    and base.__name__ == "Protocol"
                ):
                    return True

        # Check if it's decorated with @runtime_checkable (has protocol-like attributes)
        if hasattr(protocol, "__class_getitem__") and hasattr(
            protocol, "__subclasshook__"
        ):
            # This is likely a runtime checkable protocol
            return True

        # If none of the above checks pass, it's not a valid protocol
        return False

    except Exception as e:
        if logger:
            logger.debug(f"Error validating protocol {protocol}: {e}")
        return False
