---
sidebar_position: 4
title: CSV Schema Deep Dive - Workflow Configuration Guide
description: Master the CSV schema for defining AgentMap workflows. Learn the 10 essential columns, configuration patterns, and best practices for building robust AI workflows.
keywords: [CSV schema, workflow configuration, AgentMap CSV, agent definition, workflow structure]
---

import CSVTable from '@site/src/components/CSVTable';
import DownloadButton from '@site/src/components/DownloadButton';
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# CSV Schema Deep Dive

The CSV schema is the foundation of AgentMap workflows. This guide covers everything you need to know to effectively define workflows using the 10 essential columns and build robust, maintainable AI agent systems.

:::info Why CSV for Workflows?
**CSV is perfect for workflow definition because it's:**
- ✅ **Collaborative** - Teams can edit workflows in familiar spreadsheet tools
- ✅ **Version Control Friendly** - Easy to track changes and collaborate
- ✅ **Visual** - See your entire workflow structure at a glance
- ✅ **Accessible** - No programming required to design sophisticated workflows
- ✅ **Tool Compatible** - Works with Excel, Google Sheets, Pandas, and more
:::

---

## The 10 Essential Columns

Every AgentMap CSV workflow uses these 10 columns to define agent behavior and connections:

| Column | Required | Purpose | Example |
|--------|----------|---------|---------|
| `GraphName` | ✅ | Workflow identifier | `WeatherBot` |
| `Node` | ✅ | Unique agent name | `GetLocation` |
| `Edge` | ❌ | Simple linear connection | `GetLocation->FetchWeather` |
| `Context` | ❌ | Agent configuration | `{'temperature': 0.7}` |
| `AgentType` | ❌ | Type of agent | `input`, `openai`, `custom:MyAgent` |
| `Success_Next` | ❌ | Next node on success | `ProcessData` |
| `Failure_Next` | ❌ | Next node on failure | `HandleError` |
| `Input_Fields` | ❌ | Required state fields | `location\|api_key` |
| `Output_Field` | ❌ | Field where output is stored | `weather_data` |
| `Prompt` | ❌ | LLM prompt or instructions | `Get weather for {location}` |
| `Description` | ❌ | Human-readable documentation | `Fetches weather data from API` |

---

## Column Details & Examples

### 1. GraphName & Node
**Purpose**: Identify and organize your workflow

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
WeatherBot,GetLocation,,,input,FetchWeather,Error,,location,What city?,Start of weather workflow
WeatherBot,FetchWeather,,,weather_api,CreateReport,Error,location,weather_data,,Get current weather
WeatherBot,CreateReport,,,openai,End,Error,location|weather_data,report,Create weather report,Generate summary
```

**Best Practices:**
- **GraphName**: Use descriptive names like `CustomerSupport`, `DataPipeline`, `ChatBot`
- **Node**: Use action-oriented names like `GetUserInput`, `ProcessData`, `SendEmail`
- **Consistency**: Keep naming conventions consistent across your workflow

### 2. Routing: Edge vs Success_Next/Failure_Next

You can define connections two ways:

<Tabs>
<TabItem value="edge" label="Simple Linear (Edge)" default>

Use `Edge` for simple, sequential workflows:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
Pipeline,Step1,Step2,,processor,,,input,output1,,First step
Pipeline,Step2,Step3,,processor,,,output1,output2,,Second step  
Pipeline,Step3,,,processor,,,output2,final,,Final step
```

</TabItem>
<TabItem value="conditional" label="Conditional Routing">

Use `Success_Next` and `Failure_Next` for branching workflows:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
RobustBot,ProcessData,,,processor,FormatOutput,HandleError,raw_data,processed_data,,Process user data
RobustBot,FormatOutput,,,formatter,End,HandleError,processed_data,formatted_data,,Format results
RobustBot,HandleError,,,error_handler,End,,error,error_message,,Handle any errors
RobustBot,End,,,echo,,,formatted_data|error_message,final_output,,Output results
```

</TabItem>
</Tabs>

:::warning Routing Rules
**⚠️ Important:** Never use both `Edge` and `Success_Next`/`Failure_Next` in the same row. This will cause an error.

Choose one approach:
- `Edge` for simple linear flows
- `Success_Next`/`Failure_Next` for conditional branching
:::

### 3. Context Configuration

The `Context` column configures agent behavior:

<Tabs>
<TabItem value="simple" label="Simple Text" default>

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
MyBot,Welcome,,Welcome message,echo,GetInput,,message,welcome,
MyBot,GetInput,,Collect user input,input,Process,Error,,user_input,
```

</TabItem>
<TabItem value="json" label="JSON Configuration">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
AIBot,Generate,,"{'model': 'gpt-4', 'temperature': 0.7, 'max_tokens': 500}",openai,Respond,Error,user_input,ai_response,
APIBot,FetchData,,"{'timeout': 30, 'retries': 3, 'base_url': 'https://api.example.com'}",custom:APIClient,Process,Error,query,api_data,
```

**⚠️ Use Python Dictionary Syntax**: `{'key': 'value'}` not `{"key": "value"}`

</TabItem>
<TabItem value="advanced" label="Advanced Features">

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
MemoryBot,Chat,,"{'memory_type': 'buffer', 'memory_key': 'chat_history'}",openai,Continue,Error,user_input,response,
FileBot,SaveData,,"{'directory': 'outputs', 'timestamp': True, 'format': 'json'}",file_writer,End,Error,processed_data,file_path,
```

</TabItem>
</Tabs>

### 4. Agent Types

Choose the right agent type for each task:

| Agent Type | Purpose | Example Context |
|------------|---------|-----------------|
| `input` | Collect user input | N/A |
| `echo` | Pass-through/formatting | N/A |
| `openai` | OpenAI LLM processing | `{'model': 'gpt-4', 'temperature': 0.7}` |
| `anthropic` | Anthropic LLM processing | `{'model': 'claude-3-sonnet'}` |
| `custom:ClassName` | Your custom logic | `{'param1': 'value1'}` |
| `branching` | Conditional routing | `{'condition_field': 'status'}` |

### 5. Input/Output Fields

Control data flow between agents:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
DataFlow,GetUser,,,input,EnrichUser,Error,,user_id,Enter user ID:,
DataFlow,EnrichUser,,,database,AddPrefs,Error,user_id,user_profile,,
DataFlow,AddPrefs,,,preferences,CreateReport,Error,user_id,user_preferences,,
DataFlow,CreateReport,,,openai,End,Error,user_profile|user_preferences,report,Create user report,
```

**Input Field Patterns:**
- **Single field**: `location`
- **Multiple fields**: `location|api_key|timeout`
- **All available**: `*` (use sparingly)

---

## Essential Workflow Patterns

### 1. Basic Linear Workflow

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
SimpleBot,Start,,Get user input,input,Process,Error,,user_input,What can I help you with?,
SimpleBot,Process,,Process the request,openai,End,Error,user_input,response,You are a helpful assistant. User: {user_input},
SimpleBot,End,,Show final result,echo,,,response,final_output,,
SimpleBot,Error,,Handle errors,echo,,,error,error_message,,`}
  title="Basic Linear Workflow"
  filename="basic_linear_workflow"
/>

### 2. Error Handling Workflow

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
RobustBot,GetInput,,Collect user data,input,ValidateInput,HandleError,,user_input,Enter your request:,
RobustBot,ValidateInput,,Validate user input,validator,ProcessData,HandleError,user_input,validated_input,,
RobustBot,ProcessData,,"{'timeout': 30}",processor,FormatOutput,HandleError,validated_input,processed_data,,
RobustBot,FormatOutput,,Format the results,formatter,End,HandleError,processed_data,formatted_result,,
RobustBot,HandleError,,Handle any errors gracefully,error_handler,End,,error,error_message,,
RobustBot,End,,Display final results,echo,,,formatted_result|error_message,output,,`}
  title="Error Handling Workflow"
  filename="error_handling_workflow"
/>

### 3. Branching Workflow

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
SupportBot,GetQuery,,Collect support request,input,ClassifyIntent,Error,,user_query,How can we help you?,
SupportBot,ClassifyIntent,,Classify the request type,openai,RouteToHandler,Error,user_query,intent,"Classify this as: billing|technical|general: {user_query}",
SupportBot,RouteToHandler,,Route to appropriate handler,branching,BillingHandler|TechnicalHandler|GeneralHandler,Error,intent,route_decision,,
SupportBot,BillingHandler,,Handle billing questions,billing_specialist,FinalResponse,Error,user_query,billing_response,,
SupportBot,TechnicalHandler,,Handle technical issues,tech_specialist,FinalResponse,Error,user_query,tech_response,,
SupportBot,GeneralHandler,,Handle general questions,general_specialist,FinalResponse,Error,user_query,general_response,,
SupportBot,FinalResponse,,Present the final answer,echo,End,,billing_response|tech_response|general_response,final_answer,,
SupportBot,Error,,Handle errors,echo,End,,error,error_message,,
SupportBot,End,,Complete the workflow,echo,,,final_answer|error_message,result,,`}
  title="Branching Support Bot"
  filename="branching_support_bot"
/>

---

## Configuration Best Practices

### JSON Configuration Rules

AgentMap uses **Python dictionary syntax** in CSV files:

✅ **Correct Format:**
```csv
AIBot,Generate,,"{'model': 'gpt-4', 'temperature': 0.7, 'max_tokens': 500}",openai,End,Error,input,output,
```

❌ **Wrong Format:**
```csv
AIBot,Generate,,"{\"model\": \"gpt-4\", \"temperature\": 0.7, \"max_tokens\": 500}",openai,End,Error,input,output,
```

### Environment Variables

Reference environment variables safely:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
SecureBot,CallAPI,,"{'api_key': 'env:OPENAI_API_KEY', 'base_url': 'env:API_BASE_URL'}",custom:APIClient,Process,Error,query,api_response,,
```

### Memory Configuration

For conversational agents:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
ChatBot,Converse,,"{'memory_type': 'buffer', 'max_token_limit': 2000}",openai,Continue,Error,user_input,ai_response,You are a helpful assistant,
```

---

## Validation & Debugging

### Common CSV Errors

1. **Routing Conflicts**: Using both `Edge` and `Success_Next`
2. **Missing Nodes**: Referencing nodes that don't exist  
3. **Invalid JSON**: Malformed configuration in `Context`
4. **Field Mismatches**: Expecting input fields that aren't available

### Validation Commands

```bash
# Validate CSV structure
agentmap validate --csv workflow.csv

# Visualize workflow
agentmap graph --csv workflow.csv --output diagram.png

# Test with debug output
agentmap run --csv workflow.csv --debug
```

### Debug Tips

1. **Start Simple**: Build incrementally, test frequently
2. **Use Echo Agents**: Add echo agents to inspect state flow
3. **Check References**: Ensure all node references exist
4. **Validate JSON**: Test complex configurations separately

---

## Quick Start Templates

Get started quickly with these tested templates:

<Tabs>
<TabItem value="chatbot" label="Chat Bot" default>

<DownloadButton 
  filename="chatbot_template.csv" 
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
ChatBot,GetInput,,Collect user message,input,GenerateResponse,Error,,user_message,What can I help you with?,
ChatBot,GenerateResponse,,"{'model': 'gpt-4', 'temperature': 0.7}",openai,End,Error,user_message,ai_response,You are a helpful assistant. User: {user_message},
ChatBot,End,,Display response,echo,,,ai_response,final_response,,
ChatBot,Error,,Handle errors,echo,,,error,error_message,,`}>
  💬 Download Chat Bot Template
</DownloadButton>

</TabItem>
<TabItem value="api" label="API Integration">

<DownloadButton 
  filename="api_integration_template.csv" 
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
APIBot,GetQuery,,Collect search parameters,input,FetchData,Error,,search_query,Enter your search:,
APIBot,FetchData,,"{'timeout': 30, 'retries': 3}",custom:APIClient,ProcessResponse,Error,search_query,api_response,,
APIBot,ProcessResponse,,"{'model': 'gpt-4'}",openai,FormatOutput,Error,api_response|search_query,processed_data,Analyze this data: {api_response},
APIBot,FormatOutput,,Format results nicely,formatter,End,Error,processed_data,formatted_output,,
APIBot,Error,,Handle API errors,echo,End,,error,error_message,,
APIBot,End,,Display results,echo,,,formatted_output|error_message,final_result,,`}>
  🔌 Download API Integration Template
</DownloadButton>

</TabItem>
<TabItem value="pipeline" label="Data Pipeline">

<DownloadButton 
  filename="data_pipeline_template.csv" 
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
Pipeline,LoadData,,Load input data,data_loader,ValidateData,Error,,raw_data,,
Pipeline,ValidateData,,Validate data quality,validator,TransformData,Error,raw_data,validated_data,,
Pipeline,TransformData,,Apply transformations,transformer,EnrichData,Error,validated_data,transformed_data,,
Pipeline,EnrichData,,"{'sources': ['api1', 'api2']}",enricher,SaveResults,Error,transformed_data,enriched_data,,
Pipeline,SaveResults,,"{'format': 'json', 'backup': True}",data_saver,End,Error,enriched_data,save_result,,
Pipeline,Error,,Handle pipeline errors,error_handler,End,,error,error_summary,,
Pipeline,End,,Pipeline complete,echo,,,save_result|error_summary,final_status,,`}>
  📊 Download Data Pipeline Template
</DownloadButton>

</TabItem>
</Tabs>

---

## Advanced Patterns

### Multi-Route Branching

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
Router,Classify,,,classifier,Route,Error,input,classification,,
Router,Route,,,branching,PathA|PathB|PathC|PathD,Error,classification,route_decision,,
Router,PathA,,,handler_a,Merge,Error,input,result_a,,
Router,PathB,,,handler_b,Merge,Error,input,result_b,,
Router,PathC,,,handler_c,Merge,Error,input,result_c,,
Router,PathD,,,handler_d,Merge,Error,input,result_d,,
Router,Merge,,,aggregator,End,Error,result_a|result_b|result_c|result_d,final_result,,
```

### Retry Logic

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
RetryBot,AttemptTask,,"{'max_retries': 3}",processor,Success,CheckRetries,input,result,,
RetryBot,CheckRetries,,,retry_checker,AttemptTask|FinalFailure,FinalFailure,retry_count,should_retry,,
RetryBot,Success,,,echo,End,,result,success_output,,
RetryBot,FinalFailure,,,echo,End,,error,failure_output,,
RetryBot,End,,,echo,,,success_output|failure_output,final_result,,
```

---

## Related Documentation

### **Core Concepts**
- **[Fundamentals](./fundamentals)** - Basic AgentMap concepts and philosophy
- **[Workflows](./workflows)** - Workflow design patterns and best practices
- **[State Management](/docs/guides/learning-paths/core/state-management)** - How data flows between agents

### **Complete Reference**
- **[CSV Schema Reference](/docs/reference/csv-schema)** - Complete specification with all options
- **[Agent Types Reference](/docs/reference/agent-types)** - All available agent types and configurations
- **[CLI Commands](/docs/reference/cli-commands)** - Command-line tools for CSV workflows

### **Development**
- **[Custom Agents](/docs/guides/development/agents/custom-agents)** - Building your own agent types
- **[Testing Strategies](/docs/guides/development/testing)** - Testing CSV workflows effectively
- **[Best Practices](/docs/guides/development/best-practices)** - Development patterns and guidelines

### **Tools & Tutorials**
- **[Interactive Playground](/docs/playground)** - Test CSV workflows in your browser
- **[Quick Start Guide](/docs/getting-started)** - Build your first workflow
- **[Weather Bot Tutorial](/docs/tutorials/weather-bot)** - Complete example walkthrough

---

*💡 **Pro Tip**: Start with one of the templates above, then gradually customize it for your specific use case. The CSV format is forgiving - you can always add complexity incrementally!*

**Last updated: June 28, 2025**
