"""
String manipulation tools for AgentMap workflows.

Example tools for text processing and string operations using LangChain @tool decorator.

Usage in CSV:
    ToolSource: examples/tools/string_tools.py
    AvailableTools: uppercase|lowercase|reverse|count_words|trim

Example:
    GraphName,Node,AgentType,ToolSource,AvailableTools,Prompt
    Text,Process,tool_agent,examples/tools/string_tools.py,uppercase|reverse,"Process text"
"""

from langchain_core.tools import tool


@tool
def uppercase(text: str) -> str:
    """Convert text to uppercase.

    Args:
        text: The text to convert to uppercase

    Returns:
        The text in all uppercase letters

    Example:
        uppercase("hello world") -> "HELLO WORLD"
    """
    return text.upper()


@tool
def lowercase(text: str) -> str:
    """Convert text to lowercase.

    Args:
        text: The text to convert to lowercase

    Returns:
        The text in all lowercase letters

    Example:
        lowercase("HELLO WORLD") -> "hello world"
    """
    return text.lower()


@tool
def reverse(text: str) -> str:
    """Reverse the characters in text.

    Args:
        text: The text to reverse

    Returns:
        The text with characters in reverse order

    Example:
        reverse("hello") -> "olleh"
    """
    return text[::-1]


@tool
def count_words(text: str) -> int:
    """Count the number of words in text.

    Args:
        text: The text to count words in

    Returns:
        The number of words (whitespace-separated tokens)

    Example:
        count_words("hello world test") -> 3
    """
    return len(text.split())


@tool
def trim(text: str) -> str:
    """Remove leading and trailing whitespace from text.

    Args:
        text: The text to trim

    Returns:
        The text with whitespace removed from start and end

    Example:
        trim("  hello world  ") -> "hello world"
    """
    return text.strip()


@tool
def capitalize_words(text: str) -> str:
    """Capitalize the first letter of each word.

    Args:
        text: The text to capitalize

    Returns:
        The text with each word's first letter capitalized

    Example:
        capitalize_words("hello world") -> "Hello World"
    """
    return text.title()


@tool
def count_characters(text: str) -> int:
    """Count the number of characters in text.

    Args:
        text: The text to count characters in

    Returns:
        The total number of characters including spaces

    Example:
        count_characters("hello") -> 5
    """
    return len(text)
