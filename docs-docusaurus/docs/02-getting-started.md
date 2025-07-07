---
title: Getting Started with AgentMap
sidebar_position: 2
description: Get up and running with AgentMap in 5 minutes. Learn how to install, configure, and create your first AI workflow.
keywords: [getting started, quickstart, installation, setup, first workflow]
---

# Getting Started with AgentMap

Welcome to AgentMap! This guide will help you get up and running in just 5 minutes.

## 🚀 Quick Start

### 1. Installation

Install AgentMap using pip:

```bash
pip install agentmap
```

### 2. Set Up Your Environment

Create a `.env` file with your AI provider credentials:

```bash
# OpenAI
OPENAI_API_KEY=your-api-key-here

# Or Anthropic
ANTHROPIC_API_KEY=your-api-key-here

# Or Google
GOOGLE_API_KEY=your-api-key-here
```

### 3. Create Your First Workflow

Create a simple CSV file called `hello_world.csv`:

```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field
HelloWorld,start,input,greet,,,user_input
HelloWorld,greet,default,end,"Say hello to {user_input}",user_input,greeting
HelloWorld,end,echo,,,greeting,final_output
```

### 4. Run Your Workflow

```bash
agentmap run --graph HelloWorld --state '{"user_input": "World"}'
```

You should see:
```
Hello World!
```

## 📚 Next Steps

Now that you have AgentMap running, explore these resources:

### Learn the Fundamentals
- [Basic Agents Tutorial](guides/learning/01-basic-agents) - Understand the core agent types
- [Custom Prompts Guide](guides/learning/02-custom-prompts) - Create sophisticated AI behaviors
- [CSV Schema Reference](reference/csv-schema) - Master the workflow definition format

### Build Real Applications
- [Example Workflows](templates/) - Ready-to-use templates for common tasks
- [Agent Catalog](reference/agent-catalog) - Explore all available agent types
- [Integration Guide](guides/development/integrations) - Connect to external services

### Deploy to Production
- [FastAPI Integration](deployment/fastapi-integration) - Build REST APIs
- [CLI Commands](deployment/cli-commands) - Master the command-line interface
- [Best Practices](guides/development/best-practices) - Production-ready patterns

## 🎯 Common Use Cases

### Data Processing Pipeline
```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field
DataPipeline,start,input,extract,,,raw_data
DataPipeline,extract,default,transform,"Extract key info from: {raw_data}",raw_data,extracted
DataPipeline,transform,default,save,"Clean and format: {extracted}",extracted,cleaned
DataPipeline,save,csv_writer,end,,cleaned,result
DataPipeline,end,echo,,,result,final_output
```

### Multi-Agent Research Assistant
```csv
graph_name,node_name,agent_type,next_on_success,prompt,input_fields,output_field
Research,start,input,researcher,,,query
Research,researcher,default,summarizer,"Research this topic: {query}",query,research
Research,summarizer,default,end,"Summarize findings: {research}",research,summary
Research,end,echo,,,summary,final_output
```

## 🛠️ Configuration Options

AgentMap supports multiple AI providers:

```python
# config.py
AI_PROVIDERS = {
    "openai": {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": "gpt-4"
    },
    "anthropic": {
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "model": "claude-3-opus-20240229"
    }
}
```

## 🤝 Getting Help

- **Documentation**: You're here! Explore the sidebar for more guides
- **GitHub Issues**: [Report bugs or request features](https://github.com/jwwelbor/AgentMap/issues)
- **Discussions**: [Join the community](https://github.com/jwwelbor/AgentMap/discussions)

## 🎉 Ready to Build?

You now have everything you need to start building AI workflows with AgentMap. Check out the [Learning Path](guides/learning/) for a structured journey through all features.

Happy building! 🚀