---
sidebar_position: 1
title: AgentMap Workflow Templates - Ready-to-Use AI Workflow Examples
description: Browse and download ready-to-use AgentMap workflow templates. Weather bots, data processing, customer support, and more. Start building AI workflows instantly.
keywords: [AgentMap templates, workflow templates, AI workflow examples, CSV templates, ready-to-use workflows, weather bot template, data processing template, customer support template]
image: /img/agentmap-hero.png
---

# Agentic AI Workflow Templates

Get started quickly with AgentMap using our curated collection of **ready-to-use agentic AI workflow templates**. Each template demonstrates autonomous agent behavior, multi-agent collaboration, and intelligent decision-making patterns that you can customize for your specific use cases.

import TemplateLibrary from '@site/src/components/TemplateLibrary';

<TemplateLibrary />

## 📥 Quick Download Templates

Download these essential workflow templates to get started immediately:

<div className="download-section">

### 🌟 **Starter Templates**

import DownloadButton from '@site/src/components/DownloadButton';

<div className="template-downloads">

**🚀 Basic Agentic Workflow Template**  
Perfect for beginners - autonomous agents with intelligent error handling  
*Autonomous Input → Reasoning → Output with Agent Collaboration*

<DownloadButton 
  filename="basic_workflow_template.csv"
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
BasicWorkflow,Start,,Begin workflow,input,Process,,collection,user_input,Enter your input:
BasicWorkflow,Process,,Process user input,llm,Output,ErrorHandler,user_input,processed_result,Process this input and provide a helpful response: {user_input}
BasicWorkflow,Output,,Display result,echo,End,,processed_result,final_output,
BasicWorkflow,End,,Complete workflow,echo,,,final_output,completion_msg,Workflow completed successfully!
BasicWorkflow,ErrorHandler,,Handle errors,echo,End,,error,error_msg,An error occurred: {error}`}
>
  📥 Download Basic Template
</DownloadButton>

**🌤️ Multi-Agent Weather System**  
Demonstrates agent specialization and LLM orchestration  
*Features: Custom API agents, LLM reasoning agents, intelligent routing*

<DownloadButton 
  filename="weather_bot_template.csv"
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
WeatherBot,GetLocation,,Get user location,input,FetchWeather,,collection,location,Enter your location (e.g. New York, NY):
WeatherBot,FetchWeather,,Fetch weather data,echo,AnalyzeWeather,ErrorHandler,location,weather_data,Fetching weather for {location}...
WeatherBot,AnalyzeWeather,,"{'temperature': 0.7, 'model': 'gpt-3.5-turbo'}",llm,FormatResponse,ErrorHandler,weather_data,analysis,Analyze this weather data and provide a helpful summary with recommendations: {weather_data}
WeatherBot,FormatResponse,,Format final response,echo,End,,analysis,formatted_response,
WeatherBot,End,,Weather report complete,echo,,,formatted_response,final_msg,Weather report delivered successfully!
WeatherBot,ErrorHandler,,Handle weather errors,echo,End,,error,error_msg,Unable to get weather data: {error}`}
>
  🌤️ Download Weather Template
</DownloadButton>

**📊 Agentic Data Pipeline**  
Autonomous ETL with intelligent validation and decision-making  
*Capabilities: Self-validating agents, AI transformation, adaptive processing*

<DownloadButton 
  filename="data_processing_template.csv"
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataPipeline,LoadData,,"{'format': 'records'}",csv_reader,ValidateData,ErrorHandler,collection,raw_data,data/input.csv
DataPipeline,ValidateData,,"{'temperature': 0.2}",llm,TransformData,ErrorHandler,raw_data,validation_result,Validate this data for completeness and identify any issues: {raw_data}
DataPipeline,TransformData,,"{'temperature': 0.3}",llm,SaveResults,ErrorHandler,raw_data|validation_result,transformed_data,Transform and clean this data based on validation results: {raw_data}. Validation: {validation_result}
DataPipeline,SaveResults,,"{'format': 'records', 'mode': 'write'}",csv_writer,End,ErrorHandler,transformed_data,save_result,data/output.csv
DataPipeline,End,,Pipeline complete,echo,,,save_result,final_msg,Data processing pipeline completed successfully!
DataPipeline,ErrorHandler,,Handle processing errors,echo,End,,error,error_msg,Data processing failed: {error}`}
>
  📊 Download Data Pipeline Template
</DownloadButton>

**🎯 Multi-Agent Customer Support**  
Sophisticated intent classification with specialized handler agents  
*Architecture: Intent agents, routing logic, specialized response agents, interaction logging*

<DownloadButton 
  filename="customer_support_template.csv"
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
CustomerSupport,ReceiveQuery,,Receive customer query,input,ClassifyIntent,,collection,customer_query,What can I help you with today?
CustomerSupport,ClassifyIntent,,"{'temperature': 0.2}",llm,RouteToHandler,ErrorHandler,customer_query,intent_classification,Classify this customer query into one of these categories: Technical Support, Billing, General Inquiry, Complaint. Query: {customer_query}
CustomerSupport,RouteToHandler,,Route based on intent,branching,HandleTechnical,HandleGeneral,intent_classification,routing_decision,
CustomerSupport,HandleTechnical,,"{'temperature': 0.5}",llm,LogInteraction,ErrorHandler,customer_query,support_response,Provide technical support for this query: {customer_query}
CustomerSupport,HandleGeneral,,"{'temperature': 0.7}",llm,LogInteraction,ErrorHandler,customer_query,support_response,Provide general customer service response for: {customer_query}
CustomerSupport,LogInteraction,,Log customer interaction,echo,End,,customer_query|support_response,logged_interaction,Interaction logged successfully
CustomerSupport,End,,Support session complete,echo,,,support_response,final_response,
CustomerSupport,ErrorHandler,,Handle support errors,echo,End,,error,error_msg,I apologize, but I'm experiencing technical difficulties: {error}`}
>
  🎯 Download Support Template
</DownloadButton>

</div>

:::tip Quick Start with Agentic AI Templates
1. **Right-click** any template link above → **Save link as...**
2. **Save** the CSV file to your AgentMap project directory
3. **Run** with: `agentmap run --csv your_agentic_workflow.csv`
4. **Customize** agent behaviors and routing for your specific use case
:::

</div>

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
- **Quick Start**: Review the [Quick Start Guide](/docs/getting-started) for AgentMap basics
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
