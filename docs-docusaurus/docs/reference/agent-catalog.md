---
sidebar_position: 4
title: Agent Catalog
description: Interactive catalog of all available AgentMap agent types
---

import AgentCatalog from '@site/src/components/AgentCatalog';

# Agent Catalog

Explore all available AgentMap agent types in this interactive catalog. Use the search and filters to find the perfect agent for your workflow needs.

<AgentCatalog />

## Quick Reference

### Agent Categories

- **🏗️ Core Agents** - Basic building blocks for workflow control and data flow
- **🧠 LLM Agents** - AI-powered agents using language models from various providers  
- **💾 Storage Agents** - Data persistence and retrieval from various storage systems
- **📁 File Agents** - File operations for reading and writing documents
- **🔧 Specialized Agents** - Advanced workflow orchestration and data processing

### Usage Tips

1. **Copy CSV Examples** - Click the copy button on any agent card to get ready-to-use CSV configuration
2. **Search by Capability** - Use keywords like "LLM", "storage", "file", or "routing" to find relevant agents
3. **Filter by Category** - Use category buttons to narrow down to specific agent types
4. **Check Context Options** - Review the context configuration options to understand customization possibilities

### Next Steps

- **[Quick Start Guide](../getting-started/quick-start)** - Build your first workflow using these agents
- **[CSV Schema Reference](./csv-schema)** - Learn the complete CSV format for defining workflows
- **[CLI Commands](./cli-commands)** - Use scaffolding to generate custom agent templates
- **[Agent Development](../guides/advanced/custom-agents)** - Create your own custom agents

## Common Agent Combinations

### Data Processing Pipeline
```csv
Pipeline,ReadData,,Read input data,csv_reader,ProcessData,Error,collection,raw_data,data/input.csv
Pipeline,ProcessData,,Transform the data,llm,WriteData,Error,raw_data,processed_data,Clean and format this data: {raw_data}
Pipeline,WriteData,,Save processed data,csv_writer,End,Error,processed_data,result,data/output.csv
```

### Interactive Chatbot
```csv
ChatBot,GetInput,,Get user question,input,ProcessQuestion,End,,question,Enter your question:
ChatBot,ProcessQuestion,,Process with AI,llm,GetInput,Error,question,response,You are a helpful assistant. Answer: {question}
```

### Document Analysis
```csv
Analysis,LoadDoc,,Load document,file_reader,AnalyzeDoc,Error,collection,document,
Analysis,AnalyzeDoc,,Analyze content,llm,SaveSummary,Error,document,analysis,Analyze and summarize: {document}
Analysis,SaveSummary,,Save results,json_writer,End,Error,analysis,result,results/analysis.json
```

These examples show how different agent types work together to create powerful workflows. Each agent handles a specific task while passing data seamlessly to the next step.
