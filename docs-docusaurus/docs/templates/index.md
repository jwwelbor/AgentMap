---
sidebar_position: 1
---

# Workflow Templates

Get started quickly with AgentMap using our curated collection of ready-to-use workflow templates. Each template is designed to showcase specific capabilities and can be customized for your unique use cases.

import TemplateLibrary from '@site/src/components/TemplateLibrary';

<TemplateLibrary />

## How to Use Templates

### 1. Choose Your Template
Browse the template library above to find a workflow that matches your needs. Use the category and difficulty filters to narrow down your options.

### 2. Copy the CSV Content
Click the **"📋 Copy CSV"** button on any template to copy the workflow definition to your clipboard.

### 3. Load into AgentMap
Paste the CSV content into AgentMap using one of these methods:

- **Command Line**: Save as a `.csv` file and run:
  ```bash
  agentmap execute your_workflow.csv
  ```

- **Python API**: Load directly in your code:
  ```python
  from agentmap import AgentMap
  
  # Paste CSV content here
  csv_content = """GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
  ..."""
  
  agent_map = AgentMap()
  result = agent_map.execute_from_csv_string(csv_content)
  ```

- **Playground**: Use the **"🚀 Open in Playground"** button to launch the template directly in the AgentMap web interface.

### 4. Customize Configuration
Most templates include configuration notes with specific customization instructions. Common customizations include:

- **File Paths**: Update input/output paths for your directory structure
- **API Keys**: Configure LLM providers and external services
- **Prompts**: Modify prompts to match your specific domain or tone
- **Agent Parameters**: Adjust temperature, model selection, and other agent settings

## Template Categories

### 🤖 Automation
Workflows that automate repetitive tasks and processes:
- **Weather Notification Bot**: Daily weather alerts with intelligent notifications
- **Email Classifier**: Automatic email categorization and priority routing

### 📊 Data Processing
Templates for data transformation, analysis, and reporting:
- **Daily Report Generator**: Automated data collection and report generation
- **Data ETL Pipeline**: Extract, transform, and load data between systems

### 🧠 AI/LLM
AI-powered workflows leveraging language models:
- **Customer Feedback Analyzer**: Sentiment analysis and issue categorization
- **Document Summarizer**: Multi-level document processing and summarization
- **Translation Workflow**: Multi-language translation with quality assurance
- **Content Moderator**: AI-powered content moderation and compliance

### 👁️ Monitoring
Real-time monitoring and alerting systems:
- **Social Media Monitor**: Track mentions with sentiment analysis and alerts
- **API Health Checker**: Monitor endpoint health with automated reporting

### 🔗 Integration
Templates for connecting different systems and services:
- **Data ETL Pipeline**: Seamless data movement between formats

### 🛠️ Utility
General-purpose workflows for common tasks:
- Various utility templates for file processing, data validation, and more

## Difficulty Levels

### 🟢 Beginner
Perfect for new users learning AgentMap:
- Simple, linear workflows
- Basic agent types (echo, input, llm)
- Minimal configuration required
- Clear documentation and examples

### 🟡 Intermediate
For users comfortable with AgentMap basics:
- Multi-step workflows with branching
- Multiple agent types and data formats
- Some external integrations
- Customizable parameters

### 🔴 Advanced
Complex workflows for experienced users:
- Sophisticated routing and orchestration
- Multiple data sources and outputs
- External API integrations
- Advanced error handling

## Customization Guide

### Modifying Prompts
LLM agent prompts can be customized to match your specific needs:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
MyWorkflow,Analyzer,,"{'temperature': 0.3}",llm,Next,,input,analysis,"Analyze this data for trends and insights: {input}. Focus on actionable recommendations."
```

**Tips for prompt customization:**
- Be specific about the desired output format
- Include examples of good responses
- Set the appropriate tone (formal, casual, technical)
- Use field placeholders like `{input}` for dynamic content

### Configuring Agent Context
Many agents accept context parameters for fine-tuning:

```csv
Context
"{'temperature': 0.7, 'model': 'gpt-4', 'max_tokens': 500}"
"{'format': 'records', 'encoding': 'utf-8'}"
"{'chunk_size': 1000, 'should_split': true}"
```

**Common context options:**
- **LLM agents**: `temperature`, `model`, `max_tokens`
- **File agents**: `encoding`, `mode`, `chunk_size`
- **CSV agents**: `format`, `delimiter`, `id_field`

### Adding Error Handling
Robust workflows include proper error handling:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
MyWorkflow,ProcessData,,Process the data,llm,SaveResult,ErrorHandler,input,result,"Process: {input}"
MyWorkflow,ErrorHandler,,Handle errors gracefully,echo,End,,error,error_msg,"Error occurred: {error}"
```

### File Path Configuration
Update file paths to match your directory structure:

```csv
# Input files
"data/input.csv"
"config/settings.json"

# Output files  
"reports/daily_summary.md"
"output/processed_data.csv"
```

## Best Practices

### 1. Start Simple
Begin with beginner templates and gradually work up to more complex workflows as you become comfortable with AgentMap concepts.

### 2. Test Incrementally
When customizing templates:
- Make small changes at a time
- Test each modification before adding more
- Use the error messages to guide troubleshooting

### 3. Organize Your Files
Create a clear directory structure for your workflows:
```
my_agentmap_project/
├── workflows/
│   ├── daily_reports.csv
│   ├── content_moderation.csv
│   └── data_processing.csv
├── data/
│   ├── input/
│   └── output/
├── config/
│   └── settings.json
└── reports/
```

### 4. Version Control
Keep your customized workflows in version control to track changes and collaborate with team members.

### 5. Document Customizations
When modifying templates, document your changes:
- What was changed and why
- Any new dependencies or requirements
- Expected input/output formats

## Troubleshooting

### Common Issues

**CSV Format Errors**
- Ensure all rows have the same number of columns
- Check for unescaped commas in text fields
- Verify column headers match expected format

**Agent Configuration**
- Validate JSON syntax in Context fields
- Check that required agent types are available
- Ensure file paths exist and are accessible

**Missing Dependencies**
- Install required Python packages
- Configure API keys for external services
- Verify file permissions for input/output directories

### Getting Help

Need assistance with templates?

- **Documentation**: Check the [Agent Types Reference](/docs/reference/agent-types) for detailed agent documentation
- **Quick Start**: Review the [Quick Start Guide](/docs/getting-started/quick-start) for AgentMap basics
- **Examples**: Explore additional examples in the [Examples Directory](/docs/examples)
- **Community**: Join discussions in our community forums

## Contributing Templates

Have a useful workflow template to share? We welcome contributions!

### Template Requirements
- Well-documented use case and configuration
- Tested and working example
- Clear setup instructions
- Appropriate difficulty classification

### Submission Process
1. Create your template following our format
2. Test thoroughly with sample data
3. Document configuration requirements
4. Submit via pull request with description

See our [Contributing Guide](/docs/contributing) for detailed submission instructions.

---

**Ready to get started?** Choose a template above that matches your use case and start building your first AgentMap workflow!
