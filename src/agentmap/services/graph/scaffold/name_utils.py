"""
Name generation utilities for scaffolding.

This module provides functions for generating proper class names
and converting between naming conventions.
"""


def to_pascal_case(text: str) -> str:
    """
    Convert text to PascalCase, handling underscores and preserving existing case.

    Args:
        text: Input text (may contain underscores, hyphens, or mixed case)

    Returns:
        PascalCase version of the text

    Examples:
        >>> to_pascal_case("test")
        'Test'
        >>> to_pascal_case("some_class")
        'SomeClass'
        >>> to_pascal_case("my-component")
        'MyComponent'
        >>> to_pascal_case("AlreadyPascal")
        'AlreadyPascal'
    """
    if not text:
        return ""

    # If text has no underscores/hyphens and starts with uppercase, preserve it
    if "_" not in text and "-" not in text and text[0].isupper():
        return text

    # Split on underscores/hyphens and capitalize each part
    parts = text.replace("-", "_").split("_")
    pascal_parts = []

    for part in parts:
        if part:  # Skip empty parts
            # Capitalize first letter, preserve the rest
            pascal_parts.append(
                part[0].upper() + part[1:] if len(part) > 1 else part.upper()
            )

    return "".join(pascal_parts)


def generate_agent_class_name(agent_type: str) -> str:
    """
    Generate proper PascalCase class name for agent.

    Converts to PascalCase and adds 'Agent' suffix only if not already present.

    Examples:
        >>> generate_agent_class_name("test")
        'TestAgent'
        >>> generate_agent_class_name("input")
        'InputAgent'
        >>> generate_agent_class_name("some_class")
        'SomeClassAgent'
        >>> generate_agent_class_name("test_agent")
        'TestAgent'
        >>> generate_agent_class_name("ThisNamedAgent")
        'ThisNamedAgent'

    Args:
        agent_type: Agent type from CSV (may be any case, with underscores or hyphens)

    Returns:
        Properly formatted agent class name in PascalCase with Agent suffix
    """
    if not agent_type:
        return "Agent"

    # Convert to PascalCase
    pascal_case_name = to_pascal_case(agent_type)

    # Only add Agent suffix if not already present
    if not pascal_case_name.endswith("Agent"):
        pascal_case_name += "Agent"

    return pascal_case_name
