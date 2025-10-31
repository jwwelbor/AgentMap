# AgentMap Tool Support Examples

This directory contains examples demonstrating how to use tools in AgentMap workflows.

## Overview

AgentMap supports LangChain/LangGraph standard tool-calling patterns through:
- **Tool Modules**: Python files with `@tool` decorated functions
- **CSV Configuration**: Declarative tool binding via `ToolSource` and `AvailableTools` columns
- **ToolAgent**: Built-in agent type that intelligently selects and executes tools

## Quick Start

### 1. Simple Calculator Example

The simplest tool workflow - single tool, direct execution:

```bash
agentmap run examples/tools/simple_calculator.csv::SimpleCalc
```

**What it demonstrates:**
- Loading tools from a module (`calculator_tools.py`)
- Single tool optimization (bypasses selection)
- Basic tool execution

**CSV snippet:**
```csv
Node,AgentType,ToolSource,AvailableTools
Calculate,tool_agent,examples/tools/calculator_tools.py,add
```

### 2. Text Processor Example

Multiple tools in sequence, building a processing pipeline:

```bash
agentmap run examples/tools/text_processor.csv::TextFlow
```

**What it demonstrates:**
- Multiple tool agents in a workflow
- Chaining tool results
- Different tools from same module

**CSV snippet:**
```csv
Node,AgentType,ToolSource,AvailableTools
ToUpper,tool_agent,examples/tools/string_tools.py,uppercase
Reverse,tool_agent,examples/tools/string_tools.py,reverse
```

### 3. Mixed Workflow Example

Combines tools with regular agents, shows error handling:

```bash
agentmap run examples/tools/mixed_workflow.csv::MixedDemo
```

**What it demonstrates:**
- Mixing tool agents with regular agents (echo, input)
- Tool selection with inline descriptions
- Error handling with Failure_Next routing
- Multiple tool modules in one workflow

**CSV snippet:**
```csv
Node,AgentType,ToolSource,AvailableTools
ProcessNumber,tool_agent,examples/tools/calculator_tools.py,"add(""adds"")|multiply(""multiplies"")"
ProcessText,tool_agent,examples/tools/string_tools.py,"uppercase(""uppercase"")|reverse(""reverse"")"
```

## CSV Column Reference

### ToolSource Column

Specifies where tools are defined:

| Value | Meaning | Example |
|-------|---------|---------|
| `{path}.py` | Python module with @tool functions | `examples/tools/calculator_tools.py` |
| `toolnode` | Special keyword (advanced usage) | `toolnode` |

### AvailableTools Column

Specifies which tools the agent can use:

**Format 1: Simple (Auto-extraction)**
```csv
AvailableTools: add|subtract|multiply
```
- Tool names separated by pipe `|`
- Descriptions extracted from tool definitions

**Format 2: Inline Descriptions (CSV Override)**
```csv
AvailableTools: "add(""adds numbers"")|subtract(""subtracts numbers"")"
```
- Custom descriptions override tool descriptions
- Use for better tool selection accuracy
- Format: `toolname("description")|toolname2("description2")`

### Context Column

Configure tool selection strategy:

```csv
Context: "{""matching_strategy"": ""algorithm"", ""confidence_threshold"": 0.8}"
```

**Available strategies:**
- `algorithm`: Fast keyword-based matching (default for single tool)
- `llm`: Use LLM for intelligent selection
- `tiered`: Combine algorithm + LLM (default for multiple tools)

**Additional context options:**
- `confidence_threshold`: Minimum confidence for selection (0.0-1.0)
- `llm_type`: LLM provider ("openai", "anthropic", "google")
- `temperature`: Temperature for LLM selection (0.0-1.0, default 0.2)

## Creating Tool Modules

### Basic Tool Module

Create a Python file with `@tool` decorated functions:

```python
# my_tools.py
from langchain_core.tools import tool

@tool
def my_function(param: str) -> str:
    """Description of what this tool does.

    This description is used for tool selection.
    Make it clear and descriptive!
    """
    # Your implementation
    return f"Processed: {param}"
```

### Tool Best Practices

1. **Clear Descriptions**: Write descriptive docstrings for accurate selection
2. **Type Hints**: Include type annotations for parameters and return values
3. **Error Handling**: Raise clear exceptions with helpful messages
4. **Single Responsibility**: Each tool should do one thing well
5. **Reusability**: Design tools to be useful across multiple workflows

### Tool Module Template

```python
"""
{Module Name} tools for AgentMap workflows.

Brief description of what these tools do.

Usage in CSV:
    ToolSource: path/to/this/module.py
    AvailableTools: tool1|tool2|tool3
"""

from langchain_core.tools import tool


@tool
def tool_name(param: str) -> str:
    """Clear description for tool selection.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Example:
        tool_name("input") -> "output"
    """
    # Implementation
    return result
```

## Example Tool Modules

### calculator_tools.py
Mathematical operations:
- `add(a, b)` - Add two numbers
- `subtract(a, b)` - Subtract numbers
- `multiply(a, b)` - Multiply numbers
- `divide(a, b)` - Divide numbers
- `power(base, exponent)` - Raise to power

### string_tools.py
Text manipulation:
- `uppercase(text)` - Convert to uppercase
- `lowercase(text)` - Convert to lowercase
- `reverse(text)` - Reverse characters
- `count_words(text)` - Count words
- `trim(text)` - Remove whitespace
- `capitalize_words(text)` - Title case
- `count_characters(text)` - Count characters

## Workflow Patterns

### Pattern 1: Single Tool Agent

When you only need one tool, no selection is needed:

```csv
Node,AgentType,ToolSource,AvailableTools
Process,tool_agent,my_tools.py,single_tool
```

**Behavior:** Bypasses selection, directly executes the tool

### Pattern 2: Multiple Tools with Selection

Let the agent select the best tool:

```csv
Node,AgentType,ToolSource,AvailableTools,Context
Process,tool_agent,my_tools.py,tool1|tool2|tool3,"{""matching_strategy"": ""tiered""}"
```

**Behavior:** Uses OrchestratorService to select best tool based on input

### Pattern 3: Custom Descriptions for Better Selection

Override tool descriptions for clearer selection:

```csv
Node,AgentType,ToolSource,AvailableTools
Process,tool_agent,my_tools.py,"add(""adds numbers"")|mult(""multiplies"")"
```

**Behavior:** Uses your descriptions instead of tool docstrings

### Pattern 4: Tool Chain Pipeline

Chain multiple tools together:

```csv
Node,AgentType,ToolSource,AvailableTools,Success_Next
Step1,tool_agent,tools.py,tool1,Step2
Step2,tool_agent,tools.py,tool2,Step3
Step3,tool_agent,tools.py,tool3,Done
```

**Behavior:** Each tool's output becomes next tool's input

## Common Use Cases

### API Integration
Create tools that wrap external APIs:
```python
@tool
def fetch_user_data(user_id: str) -> dict:
    """Fetch user data from external API."""
    response = requests.get(f"api.example.com/users/{user_id}")
    return response.json()
```

### Data Transformation
Build tools for data processing:
```python
@tool
def parse_json(json_string: str) -> dict:
    """Parse JSON string to dictionary."""
    return json.loads(json_string)
```

### File Operations
Tools for reading/writing files:
```python
@tool
def read_file(path: str) -> str:
    """Read contents of a file."""
    with open(path, 'r') as f:
        return f.read()
```

## Troubleshooting

### Tool Module Not Found
**Error:** `Tool module not found: my_tools.py`

**Solution:**
- Use absolute path or relative path from workflow directory
- Verify file exists: `ls examples/tools/my_tools.py`
- Check ToolSource column value in CSV

### No Tools Found in Module
**Error:** `No @tool decorated functions found in: my_tools.py`

**Solution:**
- Ensure functions use `@tool` decorator
- Import decorator: `from langchain_core.tools import tool`
- Check module loads without errors: `python my_tools.py`

### Tool Not Selected
**Issue:** Wrong tool being selected or no tool selected

**Solution:**
- Add inline descriptions: `tool1("clear description")`
- Increase confidence_threshold in Context
- Use `llm` strategy instead of `algorithm`
- Make tool descriptions more distinct

### Service Not Configured
**Error:** `OrchestratorService not configured`

**Solution:**
- This is a framework error - OrchestratorService should auto-inject
- Report as bug if you see this error

## Advanced Topics

### Tool Description Priority

AgentMap resolves tool descriptions with this priority:

1. **CSV Inline Descriptions** (highest priority)
   - Format: `tool("custom description")`
   - Use for optimizing tool selection

2. **Tool Decorator Description**
   - From `@tool` decorator's description parameter
   - Standard LangChain pattern

3. **Function Docstring** (lowest priority)
   - First line of function docstring
   - Fallback if no description provided

### Selection Strategies

**Algorithm Strategy** (Fast, Deterministic)
- Uses keyword matching with 4-level scoring
- Sub-10ms selection time
- Best for: Small tool sets, clear tool names

**LLM Strategy** (Intelligent, Context-Aware)
- Uses LLM to understand input and select tool
- Slower but more accurate
- Best for: Complex tool sets, ambiguous inputs

**Tiered Strategy** (Balanced, Default)
- Tries algorithm first
- Falls back to LLM if confidence too low
- Best for: General use, production workflows

## Next Steps

1. **Try the examples**: Run the three example workflows
2. **Create your own tools**: Start with simple utility functions
3. **Build a workflow**: Combine tools with regular agents
4. **Share your tools**: Create reusable tool libraries for your team

## Resources

- [LangChain Tools Documentation](https://python.langchain.com/docs/modules/agents/tools/)
- [AgentMap Main Documentation](../../docs-docusaurus/docs/)
- [Tool Support Architecture](../../docs/plan/adding-tools/AGM-TOOLS-001/)

## Contributing

Have ideas for example tools or workflows? Submit a PR!

**Ideas for new examples:**
- Weather API integration
- Database query tools
- Email sending tools
- File system operations
- Data validation tools
