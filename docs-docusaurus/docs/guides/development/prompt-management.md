---
sidebar_position: 4
title: Prompt Management
description: Master AgentMap's prompt management system for organizing, maintaining, and reusing prompts across workflows
keywords: [agentmap, prompt management, templates, prompt registry, yaml prompts, file prompts]
---

# Prompt Management in AgentMap

AgentMap includes a robust prompt management system that helps you organize, maintain, and reuse prompts across your workflows. This system makes it easy to separate prompt content from application logic and provides a centralized way to manage prompts for better maintainability and collaboration.

:::info Key Benefits
- **Centralized Management**: Store all prompts in a single, organized location
- **Reusability**: Share prompts across multiple workflows and agents
- **Version Control**: Track prompt changes and maintain prompt history
- **Flexible Storage**: Support for registry, file-based, and YAML-structured prompts
:::

## Prompt Reference Types

The PromptManager supports three types of prompt references, each optimized for different use cases:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
<TabItem value="registry" label="Registry Prompts" default>

### Registry Prompts

Reference prompts that are stored in a central registry:

```
prompt:prompt_name
```

Registry prompts are managed through the `prompts/registry.yaml` file (configurable) and provide a simple way to reuse common prompts across workflows.

**Example registry.yaml:**
```yaml
system_instructions: |
  You are a helpful AI assistant. Be concise and accurate.
  Always ask for clarification if a request is ambiguous.

customer_service: |
  You are a customer service representative. Be polite, helpful, and professional.
  Always aim to resolve the customer's issue or escalate appropriately.

technical_support: |
  You are a technical support specialist. Provide step-by-step solutions.
  Ask for relevant system information when troubleshooting.
```

**Usage in CSV:**
```csv
GraphName,Node,Edge,AgentType,Input_Fields,Output_Field,Prompt,Context
Support,Agent,,claude,user_query,response,prompt:customer_service,
```

</TabItem>
<TabItem value="file" label="File Prompts">

### File Prompts

Reference prompts stored in separate files:

```
file:path/to/prompt.txt
```

File prompts are ideal for longer prompts or those that include complex formatting. Paths can be absolute or relative to the prompts directory.

**Example file structure:**
```
prompts/
├── registry.yaml
├── system/
│   ├── assistant.txt
│   └── specialist.txt
└── templates/
    ├── interview.txt
    └── evaluation.txt
```

**Example assistant.txt:**
```text
You are an AI assistant helping users with various tasks.

Guidelines:
1. Be helpful and accurate
2. Ask clarifying questions when needed
3. Provide step-by-step instructions for complex tasks
4. Admit when you don't know something

Current conversation context: {conversation_history}
User request: {user_input}

Please provide a helpful response.
```

**Usage in CSV:**
```csv
GraphName,Node,Edge,AgentType,Input_Fields,Output_Field,Prompt,Context
Assistant,Helper,,claude,user_input|conversation_history,response,file:system/assistant.txt,
```

</TabItem>
<TabItem value="yaml" label="YAML Key Prompts">

### YAML Key Prompts

Reference specific keys within YAML files:

```
yaml:path/to/file.yaml#key.path
```

YAML key prompts allow you to organize multiple related prompts in a structured YAML document and reference specific sections.

**Example workflows.yaml:**
```yaml
interview:
  welcome: |
    Welcome to the interview process! I'll be asking you several questions
    to assess your qualifications for this position.
  
  technical_question: |
    I'm going to ask you a technical question about {topic}.
    Please explain your approach step by step.
  
  behavioral_question: |
    Tell me about a time when you {scenario}.
    Use the STAR method (Situation, Task, Action, Result).

support:
  greeting: |
    Thank you for contacting support. I'm here to help you with {issue_type}.
    
  troubleshooting: |
    Let's work through this step by step. First, can you tell me:
    1. When did this issue first occur?
    2. What were you trying to do when it happened?
    3. Have you tried any solutions already?

  escalation: |
    I understand this is a complex issue. I'm going to escalate this
    to our specialized team who can provide more detailed assistance.
```

**Usage in CSV:**
```csv
GraphName,Node,Edge,AgentType,Input_Fields,Output_Field,Prompt,Context
Interview,Welcome,,claude,candidate_name,welcome_message,yaml:workflows.yaml#interview.welcome,
Interview,TechQuestion,,claude,topic,question,yaml:workflows.yaml#interview.technical_question,
Support,Greeting,,claude,issue_type,greeting,yaml:workflows.yaml#support.greeting,
```

</TabItem>
</Tabs>

## Using Prompt References in AgentMap

You can use prompt references in the `Prompt` field of your CSV:

```csv
GraphName,Node,Edge,AgentType,Input_Fields,Output_Field,Prompt,Context
MyFlow,LLMNode,,openai,input,response,prompt:system_instructions,
```

Or directly in your code:

```python
from agentmap.prompts import resolve_prompt

# Resolve a prompt reference
prompt_text = resolve_prompt("prompt:customer_service")

# Resolve a file prompt
file_prompt = resolve_prompt("file:templates/interview.txt")

# Resolve a YAML key prompt
yaml_prompt = resolve_prompt("yaml:workflows.yaml#support.greeting")
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

# Get the global PromptManager instance
manager = get_prompt_manager()

# Resolve a prompt reference
prompt_text = manager.resolve_prompt("file:prompts/system.txt")

# Register a new prompt
manager.register_prompt("greeting", "Hello, I'm an AI assistant.", save=True)

# Get all registered prompts
registry = manager.get_registry()

# Update an existing prompt
manager.update_prompt("greeting", "Hi there! I'm your AI assistant.", save=True)

# Check if a prompt exists
if manager.has_prompt("custom_prompt"):
    prompt = manager.get_prompt("custom_prompt")
```

## Prompt Organization Strategies

### 1. By Function

Organize prompts based on their functional purpose:

```
prompts/
├── registry.yaml
├── system/
│   ├── assistant.txt
│   ├── specialist.txt
│   └── moderator.txt
├── tasks/
│   ├── analysis.txt
│   ├── summarization.txt
│   └── translation.txt
└── workflows/
    ├── customer_service.yaml
    ├── technical_support.yaml
    └── sales.yaml
```

### 2. By Agent Type

Group prompts by the agents that use them:

```
prompts/
├── registry.yaml
├── claude/
│   ├── general.yaml
│   └── technical.yaml
├── openai/
│   ├── creative.yaml
│   └── analytical.yaml
└── shared/
    ├── system_messages.yaml
    └── templates.yaml
```

### 3. By Project or Domain

Organize by business domain or project:

```
prompts/
├── registry.yaml
├── ecommerce/
│   ├── product_support.yaml
│   ├── order_management.yaml
│   └── customer_service.yaml
├── healthcare/
│   ├── patient_intake.yaml
│   ├── symptom_analysis.yaml
│   └── appointment_scheduling.yaml
└── education/
    ├── tutoring.yaml
    ├── assessment.yaml
    └── feedback.yaml
```

## Advanced Prompt Patterns

### Template Variables

Use template variables for dynamic prompts:

```yaml
# In registry.yaml or YAML files
dynamic_response: |
  You are helping a {user_role} with {task_type}.
  Current context: {context}
  
  Guidelines for {user_role}:
  - Be {tone} and {style}
  - Focus on {priority_area}
  
  User request: {user_input}
```

### Conditional Prompts

Create prompts that adapt based on context:

```yaml
adaptive_support: |
  {% if user_type == "premium" %}
  Welcome to premium support! I'll prioritize your request.
  {% else %}
  Thank you for contacting support. I'll help you as quickly as possible.
  {% endif %}
  
  Issue category: {issue_category}
  {% if issue_category == "urgent" %}
  I understand this is urgent. Let me escalate this immediately.
  {% endif %}
```

### Multi-Language Prompts

Support multiple languages in your prompts:

```yaml
greetings:
  en: "Hello! How can I help you today?"
  es: "¡Hola! ¿Cómo puedo ayudarte hoy?"
  fr: "Bonjour! Comment puis-je vous aider aujourd'hui?"
  de: "Hallo! Wie kann ich Ihnen heute helfen?"

support_responses:
  en:
    initial: "Thank you for contacting support."
    escalation: "Let me escalate this to a specialist."
  es:
    initial: "Gracias por contactar con soporte."
    escalation: "Permíteme escalarlo a un especialista."
```

Usage with language detection:

```csv
GraphName,Node,Edge,AgentType,Input_Fields,Output_Field,Prompt,Context
Support,Greeting,,claude,user_input|language,greeting,yaml:prompts.yaml#greetings.{language},
```

## Prompt Versioning and Management

### Version Control Integration

Track prompt changes with Git:

```bash
# Initialize prompts repository
cd prompts/
git init
git add .
git commit -m "Initial prompt templates"

# Create branches for different prompt versions
git checkout -b v2-customer-service
# Make changes to customer service prompts
git commit -m "Enhanced customer service prompts"

# Tag stable versions
git tag v1.0 -m "Production-ready prompts v1.0"
```

### Prompt Validation

Validate prompts before deployment:

```python
from agentmap.prompts import get_prompt_manager

def validate_prompts():
    manager = get_prompt_manager()
    
    # Check all registry prompts exist
    registry = manager.get_registry()
    for prompt_name in registry:
        try:
            prompt = manager.resolve_prompt(f"prompt:{prompt_name}")
            assert prompt.strip(), f"Empty prompt: {prompt_name}"
        except Exception as e:
            print(f"Invalid prompt {prompt_name}: {e}")
    
    # Validate file prompts
    file_prompts = ["system/assistant.txt", "workflows/support.yaml"]
    for file_path in file_prompts:
        try:
            prompt = manager.resolve_prompt(f"file:{file_path}")
            assert prompt.strip(), f"Empty file prompt: {file_path}"
        except Exception as e:
            print(f"Invalid file prompt {file_path}: {e}")

# Run validation
validate_prompts()
```

## Integration with Memory and Orchestration

### Memory-Aware Prompts

Create prompts that work well with memory systems:

```yaml
conversational_agent: |
  You are a helpful assistant with memory of our conversation.
  
  Conversation history:
  {conversation_memory}
  
  Current user input: {user_input}
  
  Instructions:
  - Reference previous conversation when relevant
  - Maintain conversation continuity
  - Ask for clarification if context is unclear

memory_summarizer: |
  Summarize the key points from this conversation segment:
  
  {conversation_segment}
  
  Focus on:
  - Main topics discussed
  - Decisions made
  - Action items identified
  - Important details to remember
```

### Orchestration-Ready Prompts

Design prompts for use with OrchestratorAgent:

```yaml
router_prompt: |
  Analyze the user's request and select the most appropriate handler.
  
  User input: {user_input}
  Available handlers: {available_nodes}
  
  Consider:
  - Primary intent of the request
  - Required expertise level
  - Urgency indicators
  - Context from conversation

handler_descriptions:
  technical_support: |
    I specialize in technical troubleshooting, system configuration,
    and resolving complex technical issues.
  
  customer_service: |
    I handle general inquiries, account questions, billing issues,
    and provide friendly customer assistance.
  
  sales_support: |
    I help with product information, pricing questions, purchasing
    decisions, and sales-related inquiries.
```

## Best Practices for Prompt Management

### 1. Use Descriptive Names

Choose clear, purpose-oriented names for registry prompts:

```yaml
# Good
customer_service_greeting: "Welcome to our support team..."
technical_troubleshooting_start: "Let's diagnose this technical issue..."
sales_product_inquiry: "I'd be happy to help you learn about our products..."

# Avoid
prompt1: "Hello..."
help: "I can help..."
text: "Please tell me..."
```

### 2. Organize Prompt Files Logically

Group related prompts in the same directory and use consistent naming:

```
prompts/
├── customer_service/
│   ├── greetings.yaml
│   ├── troubleshooting.yaml
│   └── escalation.yaml
├── sales/
│   ├── product_info.yaml
│   ├── pricing.yaml
│   └── demos.yaml
└── technical/
    ├── diagnostics.yaml
    ├── solutions.yaml
    └── documentation.yaml
```

### 3. Use YAML for Complex Prompt Sets

Organize related prompts in YAML files with clear hierarchies:

```yaml
customer_onboarding:
  welcome:
    new_user: |
      Welcome to our platform! I'm excited to help you get started.
    returning_user: |
      Welcome back! Let's continue where we left off.
  
  setup:
    account_creation: |
      Let's set up your account step by step.
    profile_completion: |
      Now let's complete your profile to personalize your experience.

support_workflows:
  initial_contact:
    greeting: |
      Thank you for contacting support. How can I help you today?
    
  issue_classification:
    technical: |
      I'll help you resolve this technical issue.
    billing: |
      Let me assist you with your billing question.
```

### 4. Include Version Info

Add version information in prompt files for tracking changes:

```yaml
# Version: 2.1
# Last updated: 2024-01-15
# Author: Support Team
# Changes: Enhanced error handling prompts

customer_service:
  greeting: |
    Welcome to our enhanced support experience!
    # v2.1: Added personalization
```

### 5. Document Prompt Parameters

Note any template parameters in comments:

```yaml
dynamic_support: |
  # Parameters: user_name, issue_type, urgency_level, previous_tickets
  Hello {user_name}, I see you're experiencing a {issue_type} issue.
  {% if urgency_level == "high" %}
  I'll prioritize this as a high-urgency request.
  {% endif %}
  {% if previous_tickets > 0 %}
  I notice you've contacted us before. Let me review your history.
  {% endif %}
```

## Troubleshooting

### Common Issues

| Issue | Possible Solution |
|-------|-------------------|
| Prompt not found | Check file paths and ensure prompts directory is correctly configured |
| YAML parsing errors | Validate YAML syntax and escape special characters properly |
| Template variables not resolving | Ensure all required variables are provided in the agent context |
| Cache issues | Clear the prompt cache or disable caching during development |

### Debugging Tips

1. **Enable Debug Logging**: Set logging level to DEBUG to see prompt resolution details
2. **Validate Prompt Syntax**: Use YAML validators for YAML-based prompts
3. **Test Prompt Resolution**: Use the PromptManager API to test prompt resolution directly
4. **Check File Permissions**: Ensure the prompts directory is readable
5. **Verify Template Variables**: Test prompts with sample data to ensure variables resolve correctly

## Related Guides

- [Memory Management](/docs/guides/development/agent-memory/memory-management) - Using prompts with memory systems
- [LangChain Memory Integration](/docs/guides/development/agent-memory/langchain-memory-integration) - Advanced memory and prompt integration
- [Orchestration Patterns](/docs/guides/development/orchestration) - Prompts for dynamic routing
- [Agent Development Contract](/docs/guides/development/agents/agent-development-contract) - Custom agent prompt patterns

## Conclusion

AgentMap's prompt management system provides a flexible and powerful way to organize, maintain, and reuse prompts across your workflows. By leveraging registry prompts, file-based prompts, and YAML structures, you can create maintainable prompt libraries that scale with your applications.

Effective prompt management is crucial for building robust AgentMap workflows. By following the patterns and best practices outlined in this guide, you can create prompt systems that are easy to maintain, version, and share across your team and projects.
