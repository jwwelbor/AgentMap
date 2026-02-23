---
sidebar_position: 3
title: Prompt Manager Service
description: How to store, reference, and format prompts in AgentMap using the registry, file, and YAML backends
keywords: [prompts, prompt management, templates, variable substitution, prompt registry]
---

# Prompt Manager Service

The Prompt Manager Service lets you manage prompt text outside of your CSV workflows and agent code. Instead of hard-coding long prompts into a CSV cell, you give a short reference like `prompt:classify_goal` or `file:agents/llm/code_reviewer.txt` and the service resolves it to the full prompt text at runtime. It also handles variable substitution so your prompts can be dynamic.

## Quick Start

1. Create a prompts directory and registry file:

```
agentmap_data/prompts/
└── registry.yaml
```

2. Add a prompt to the registry:

```yaml
# registry.yaml
welcome: "Hello {username}, welcome to the {workflow_name} workflow!"
```

3. Reference it anywhere you would normally write a prompt:

```csv
GraphName,Node,Description,AgentType,Edge,Edge_Negative,Input,Output,Prompt
MyWorkflow,Greeter,Greet the user,echo,NextStep,,username,greeting,prompt:welcome
```

The service resolves `prompt:welcome` to the full text and substitutes `{username}` from the node's input state at runtime.

## Configuration

The prompts section in `agentmap_config.yaml` controls where the service looks for prompts:

```yaml
prompts:
  directory: "agentmap_data/prompts"          # root directory for prompt files
  registry_file: "agentmap_data/prompts/registry.yaml"  # name-to-text mapping
  enable_cache: true                          # cache resolved prompts in memory
```

| Setting | Default | Purpose |
|---------|---------|---------|
| `directory` | `agentmap_data/prompts` | Base directory for all `file:` and `yaml:` lookups |
| `registry_file` | `agentmap_data/prompts/registry.yaml` | YAML file that maps prompt names to text |
| `enable_cache` | `true` | When enabled, a prompt reference is resolved once and reused on subsequent calls |

## Three Ways to Store Prompts

The service supports three storage backends, each identified by a prefix on the prompt reference string. Any string without a recognized prefix is treated as literal prompt text and passed through unchanged.

### 1. Registry Prompts (`prompt:`)

Best for short-to-medium prompts that you want to manage in a single file.

**How it works:** The service loads `registry.yaml` at startup. When it sees a reference like `prompt:classify_goal`, it looks up the key `classify_goal` in that YAML dictionary and returns the value.

```yaml
# agentmap_data/prompts/registry.yaml

# One-liner
welcome: "Hello {username}, welcome to {workflow_name}!"

# Multi-line (use YAML block scalar)
classify_goal: |
  You are a goal classification expert. Analyze the following goal
  and classify it into ONE category: health, career, education, finance, personal.

  Respond with ONLY the category name.

  Goal: {goal}
```

**Reference:** `prompt:welcome` or `prompt:classify_goal`

### 2. File Prompts (`file:`)

Best for long prompts or when you want to organize prompts into subfolders by domain.

**How it works:** The service reads the text file at the given path, relative to the configured `directory`. Subdirectories work naturally -- just include them in the path.

```
agentmap_data/prompts/
├── agents/
│   ├── llm/
│   │   ├── code_reviewer.txt
│   │   └── data_analyst.txt
│   └── summary/
│       └── executive_brief.txt
└── workflows/
    ├── onboarding/
    │   ├── step1_welcome.txt
    │   └── step2_training.txt
    └── support/
        └── triage.txt
```

**Reference:** `file:agents/llm/code_reviewer.txt` or `file:workflows/onboarding/step1_welcome.txt`

The file contents are returned as-is (leading/trailing whitespace trimmed). Variable placeholders like `{language}` inside the file are substituted when you use `format_prompt`.

Example file (`agents/llm/code_reviewer.txt`):

```text
You are an expert code reviewer. Review the following code for:

1. Correctness - Does the code do what it claims?
2. Security - Are there any vulnerabilities?
3. Performance - Are there obvious inefficiencies?
4. Readability - Is the code clear and well-structured?

Language: {language}
Code:
{code}
```

### 3. YAML Prompts (`yaml:`)

Best when you want to group related prompts in a single structured file, for example all the response templates for a support workflow.

**How it works:** The service loads the YAML file and traverses to the value using a dot-notation key path after the `#` separator.

```yaml
# workflows/support/resolution_template.yaml

responses:
  resolved: |
    Hi {customer_name},

    Your issue ({ticket_id}) has been resolved.
    Resolution: {resolution_summary}

    Best regards,
    {agent_name}

  escalated: |
    Hi {customer_name},

    Your issue ({ticket_id}) has been escalated.
    Reason: {escalation_reason}
    A senior engineer will reach out within {sla_hours} hours.

    Best regards,
    {agent_name}

internal:
  handoff_notes: |
    INTERNAL - Ticket Handoff Notes
    Ticket: {ticket_id}
    Previous handler: {previous_agent}
    Context: {context_summary}
```

**Reference:** `yaml:workflows/support/resolution_template.yaml#responses.resolved`

The part before `#` is the file path (relative to `directory`). The part after `#` is a dot-separated key path into the YAML structure. Nesting is unlimited: `yaml:file.yaml#level1.level2.level3` works.

### 4. Plain Text (no prefix)

Any string that does not start with `prompt:`, `file:`, or `yaml:` is treated as the prompt itself. This is the default behavior -- useful for inline prompts in CSV cells or quick prototyping.

```csv
...,Prompt
...,You are a helpful assistant. Summarize the input.
```

### Reference Format Summary

| Prefix | Format | Resolves from |
|--------|--------|---------------|
| `prompt:` | `prompt:<name>` | Key in `registry.yaml` |
| `file:` | `file:<path>` | Text file relative to prompts directory |
| `yaml:` | `yaml:<path>#<key.path>` | Value inside a YAML file at dot-notation path |
| *(none)* | literal text | Passed through as-is |

## Variable Substitution

All three backends support `{variable}` placeholders. Variables are substituted when the prompt is used at runtime -- the service's `format_prompt` method handles this.

### How Variables Get Their Values

In a CSV workflow, the variable values come from the node's **input state**. The `Input` column in your CSV defines which state keys are available to the node, and those same keys can appear as `{placeholders}` in your prompt.

```csv
GraphName,Node,AgentType,Input,Output,Prompt
Support,Triage,llm,ticket_id;customer_name;issue_description,triage_result,file:workflows/support/triage.txt
```

When the `Triage` node executes, the service resolves `file:workflows/support/triage.txt`, then substitutes `{ticket_id}`, `{customer_name}`, and `{issue_description}` from the current state.

### Formatting from Code

If you're calling the service directly (e.g. from a custom agent or host application), pass variables as a dictionary:

```python
from agentmap.services.prompt_manager_service import PromptManagerService

# Assume `svc` is a configured PromptManagerService instance

# Resolve only (no substitution)
raw = svc.resolve_prompt("prompt:welcome")
# -> "Hello {username}, welcome to {workflow_name}!"

# Resolve + substitute in one call
formatted = svc.format_prompt(
    "prompt:welcome",
    {"username": "Alice", "workflow_name": "OnboardingFlow"}
)
# -> "Hello Alice, welcome to OnboardingFlow!"
```

`format_prompt` accepts any of the four reference formats. It resolves first, then substitutes.

### Missing Variables

If a placeholder has no matching key in the values dictionary, it is left as-is in the output rather than raising an error. This lets you build prompts incrementally or catch missing data in downstream logic.

```python
svc.format_prompt("Hello {name}, score: {score}", {"name": "Bob"})
# -> "Hello Bob, score: {score}"
```

## Fallback Chain

The `get_formatted_prompt` convenience function tries multiple prompt sources in order, which is useful when agents want to support user-provided prompts with sensible defaults:

```python
from agentmap.services.prompt_manager_service import get_formatted_prompt

result = get_formatted_prompt(
    primary_prompt="prompt:custom_greeting",      # try this first
    template_file="file:defaults/greeting.txt",   # fall back to this
    default_template="Hello {name}.",             # last resort
    values={"name": "World"},
    logger=logger,
)
```

If the primary prompt fails to resolve (missing registry key, missing file, etc.), the function moves to the next option. If all three fail, it returns an error string with the raw values for debugging.

## Organizing Prompts at Scale

### Recommended Directory Layout

```
agentmap_data/prompts/
├── registry.yaml              # short, frequently-used prompts
├── agents/                    # prompts organized by agent type
│   ├── llm/
│   │   ├── code_reviewer.txt
│   │   └── data_analyst.txt
│   └── summary/
│       └── executive_brief.txt
├── workflows/                 # prompts organized by workflow
│   ├── onboarding/
│   │   ├── step1_welcome.txt
│   │   └── step2_training.txt
│   └── support/
│       ├── triage.txt
│       └── resolution_template.yaml
└── shared/                    # cross-cutting prompt fragments
    └── safety_preamble.txt
```

### When to Use Each Backend

| Situation | Recommended backend |
|-----------|-------------------|
| Short prompt (1-3 lines) | `prompt:` registry |
| Long prompt with detailed instructions | `file:` text file |
| Family of related templates (e.g. email responses) | `yaml:` file with sections |
| Inline prototype or one-off prompt | Plain text (no prefix) |

### Tips

- **Keep the registry lean.** If a prompt is longer than ~5 lines, move it to a `file:` reference. The registry is easiest to scan when entries are concise.
- **Use subfolders freely.** The `file:` resolver supports arbitrary nesting. Organize by agent type, workflow, domain -- whatever makes prompts easy to find.
- **Use YAML files for template families.** When you have multiple variations of the same prompt (resolved/pending/escalated), a single YAML file with sections is easier to maintain than separate text files.
- **Enable caching in production.** Set `enable_cache: true` to avoid re-reading files on every prompt resolution. Clear the cache at runtime with `svc.clear_cache()` if you update prompts while the application is running.

## Using from a Host Application

If your application imports AgentMap as a library, you can build the service directly:

```python
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.config_service import ConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService

# Build dependencies
config_svc = ConfigService()
app_config = AppConfigService(config_svc, config_path="agentmap_config.yaml")
logging_svc = LoggingService(app_config.get_logging_config())
logging_svc.initialize()

# Create the prompt manager
prompt_mgr = PromptManagerService(app_config, logging_svc)

# Use it
text = prompt_mgr.resolve_prompt("file:workflows/support/triage.txt")
formatted = prompt_mgr.format_prompt("prompt:welcome", {"username": "Alice", "workflow_name": "Demo"})
```

Or, if you're using the full DI container:

```python
from agentmap.di.containers import ApplicationContainer

container = ApplicationContainer()
prompt_mgr = container.prompt_manager_service()

formatted = prompt_mgr.format_prompt("prompt:welcome", {"username": "Alice", "workflow_name": "Demo"})
```

### Diagnostic Info

Call `get_service_info()` to inspect the service state at runtime:

```python
info = prompt_mgr.get_service_info()
# {
#     "service": "PromptManagerService",
#     "config_available": True,
#     "prompts_dir": "agentmap_data/prompts",
#     "registry_path": "agentmap_data/prompts/registry.yaml",
#     "cache_enabled": False,
#     "cache_size": 0,
#     "registry_size": 9,
#     "supported_prefixes": ["prompt:", "file:", "yaml:"]
# }
```

## Complete Example

Sample prompt files showing all three backends are available at:

```
examples/prompt_management/prompts/
├── registry.yaml
├── agents/
│   ├── llm/
│   │   ├── code_reviewer.txt
│   │   └── data_analyst.txt
│   └── summary/
│       └── executive_brief.txt
└── workflows/
    ├── onboarding/
    │   ├── step1_welcome.txt
    │   └── step2_training.txt
    └── support/
        ├── triage.txt
        └── resolution_template.yaml
```

Integration tests covering all features live at:

```bash
uv run pytest tests/fresh_suite/integration/test_prompt_management_integration.py -v
```
