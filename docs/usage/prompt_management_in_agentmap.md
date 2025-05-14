# Prompt Management in AgentMap

AgentMap includes a robust prompt management system that helps you organize, maintain, and reuse prompts across your workflows. This system makes it easy to separate prompt content from application logic and provides a centralized way to manage prompts.

## Prompt Reference Types

The PromptManager supports three types of prompt references:

### 1. Registry Prompts

Reference prompts that are stored in a central registry:

```
prompt:prompt_name
```

Registry prompts are managed through the `prompts/registry.yaml` file (configurable) and provide a simple way to reuse common prompts across workflows.

### 2. File Prompts

Reference prompts stored in separate files:

```
file:path/to/prompt.txt
```

File prompts are ideal for longer prompts or those that include complex formatting. Paths can be absolute or relative to the prompts directory.

### 3. YAML Key Prompts

Reference specific keys within YAML files:

```
yaml:path/to/file.yaml#key.path
```

YAML key prompts allow you to organize multiple related prompts in a structured YAML document and reference specific sections.

## Using Prompt References in AgentMap

You can use prompt references in the `Prompt` field of your CSV:

```csv
GraphName,LLMNode,,Process user input,OpenAI,NextNode,,input,response,prompt:system_instructions
```

Or directly in your code:

```python
from agentmap.prompts import resolve_prompt

### Resolve a prompt reference
prompt_text = resolve_prompt("prompt:customer_service")
```

## Configuration Options

Prompt management can be configured in your `agentmap_config.yaml`:

```yaml
prompts:
  directory: "prompts"  # Directory for prompt files
  registry_file: "prompts/registry.yaml"  # Registry file location
  enable_cache: true  # Cache resolved prompts for performance
```

Or using environment variables:

```bash
export AGENTMAP_PROMPTS_DIR="my_prompts"
export AGENTMAP_PROMPT_REGISTRY="my_prompts/registry.yaml"
export AGENTMAP_PROMPT_CACHE="true"
```

## Using the PromptManager API

For more advanced use cases, you can use the PromptManager directly:

```python
from agentmap.prompts import get_prompt_manager

### Get the global PromptManager instance
manager = get_prompt_manager()

### Resolve a prompt reference
prompt_text = manager.resolve_prompt("file:prompts/system.txt")

### Register a new prompt
manager.register_prompt("greeting", "Hello, I'm an AI assistant.", save=True)

### Get all registered prompts
registry = manager.get_registry()
```

## Best Practices for Prompt Management

1. **Use descriptive prompt names** - Choose clear, purpose-oriented names for registry prompts
2. **Organize prompt files logically** - Group related prompts in the same directory
3. **Use YAML for complex prompt sets** - Organize related prompts in YAML files
4. **Include version info** - Add version information in prompt files for tracking changes
5. **Document prompt parameters** - Note any template parameters in comments
---

---

[↑ Back to Index](index.md) | [← Previous: AgentMap CSV Schema Documentation](agentmap_csv_schema_documentation.md) | [Next: AgentMap Agent Types →](agentmap_agent_types.md)