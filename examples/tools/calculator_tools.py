"""
Calculator tools for AgentMap workflows.

Example tools demonstrating mathematical operations using LangChain @tool decorator.
These tools can be referenced in CSV workflows via the ToolSource column.

Usage in CSV:
    ToolSource: examples/tools/calculator_tools.py
    AvailableTools: add|subtract|multiply|divide|power

Example:
    GraphName,Node,AgentType,ToolSource,AvailableTools,Prompt
    Math,Calculate,tool_agent,examples/tools/calculator_tools.py,add|multiply,"Do math"
"""

from langchain_core.tools import tool


@tool
def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number to add
        b: Second number to add

    Returns:
        Sum of a and b

    Example:
        add(5, 3) -> 8
    """
    return a + b


@tool
def subtract(a: int, b: int) -> int:
    """Subtract second number from first number.

    Args:
        a: Number to subtract from
        b: Number to subtract

    Returns:
        Difference of a minus b

    Example:
        subtract(10, 3) -> 7
    """
    return a - b


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers together.

    Args:
        a: First number to multiply
        b: Second number to multiply

    Returns:
        Product of a and b

    Example:
        multiply(4, 5) -> 20
    """
    return a * b


@tool
def divide(a: float, b: float) -> float:
    """Divide first number by second number.

    Args:
        a: Number to be divided (dividend)
        b: Number to divide by (divisor)

    Returns:
        Quotient of a divided by b

    Raises:
        ValueError: If b is zero

    Example:
        divide(10, 2) -> 5.0
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


@tool
def power(base: float, exponent: float) -> float:
    """Raise a number to a power.

    Args:
        base: The base number
        exponent: The power to raise to

    Returns:
        base raised to the power of exponent

    Example:
        power(2, 3) -> 8.0
    """
    return base ** exponent
