"""Name generation utilities for scaffolding."""


def to_pascal_case(text: str) -> str:
    """Convert text to PascalCase."""
    if not text:
        return ""
    if "_" not in text and "-" not in text and text[0].isupper():
        return text
    parts = text.replace("-", "_").split("_")
    return "".join(part[0].upper() + part[1:] if len(part) > 1 else part.upper() for part in parts if part)


def generate_agent_class_name(agent_type: str) -> str:
    """Generate proper PascalCase class name for agent."""
    if not agent_type:
        return "Agent"
    pascal_case_name = to_pascal_case(agent_type)
    if not pascal_case_name.endswith("Agent"):
        pascal_case_name += "Agent"
    return pascal_case_name
