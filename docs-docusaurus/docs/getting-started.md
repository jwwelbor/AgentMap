---
sidebar_position: 1
title: AgentMap Quick Start - Build Your First AI Workflow in 5 Minutes
description: Step-by-step guide to building your first AI workflow with AgentMap. Create a weather bot using CSV files - no coding required. Get started with AgentMap today.
keywords: [AgentMap quick start, AI workflow tutorial, CSV automation guide, weather bot example, no-code AI]
image: /img/agentmap-hero.png
---

# Quick Start Guide

This guide walks you through building workflows from scratch using AgentMap, demonstrating the complete process from CSV definition to execution.

:::tip Try it Live!
🎮 **Want to experiment immediately?** Try our [Interactive Playground](/docs/playground) to build and test workflows in your browser without any setup!
:::

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';
import DownloadButton from '@site/src/components/DownloadButton';
import CSVTable from '@site/src/components/CSVTable';

## Prerequisites

- Python 3.8+
- AgentMap installed (`pip install agentmap`)
- API keys for any services you plan to use (OpenAI, weather API, etc.)

## Example 1: Weather Report Workflow

Let's build a workflow that fetches weather data from an API and generates a natural language report using an LLM.

### Step 1: Create the CSV with Custom Agents

<Tabs>
<TabItem value="csv" label="CSV Workflow" default>

Create a file `weather_workflow.csv`:

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
WeatherFlow,GetLocation,,Get user location,input,FetchWeather,ErrorHandler,,location,Enter the city name for weather report:
WeatherFlow,FetchWeather,,Fetch weather data from API,custom:WeatherAPIAgent,GenerateReport,ErrorHandler,location,weather_data,
WeatherFlow,GenerateReport,,"{'provider': 'openai', 'temperature': 0.7}",llm,FormatOutput,ErrorHandler,weather_data|location,weather_report,Generate a friendly weather report for {location} based on this data: {weather_data}
WeatherFlow,FormatOutput,,Format the final output,default,End,ErrorHandler,weather_report,final_report,Weather Report Generated
WeatherFlow,ErrorHandler,,Handle errors,echo,End,,error,error_message,
WeatherFlow,End,,Complete workflow,echo,,,final_report|error_message,output,`}
  title="Weather Workflow CSV"
  filename="weather_workflow"
/>

<DownloadButton 
  filename="weather_workflow.csv" 
  content={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
WeatherFlow,GetLocation,,Get user location,input,FetchWeather,ErrorHandler,,location,Enter the city name for weather report:
WeatherFlow,FetchWeather,,Fetch weather data from API,custom:WeatherAPIAgent,GenerateReport,ErrorHandler,location,weather_data,
WeatherFlow,GenerateReport,,{"provider": "openai", "temperature": 0.7},llm,FormatOutput,ErrorHandler,weather_data|location,weather_report,Generate a friendly weather report for {location} based on this data: {weather_data}
WeatherFlow,FormatOutput,,Format the final output,default,End,ErrorHandler,weather_report,final_report,Weather Report Generated
WeatherFlow,ErrorHandler,,Handle errors,echo,End,,error,error_message,
WeatherFlow,End,,Complete workflow,echo,,,final_report|error_message,output,`}>
  📄 Download weather_workflow.csv
</DownloadButton>

</TabItem>
<TabItem value="breakdown" label="Step-by-Step Breakdown">

### Node Flow Analysis

1. **GetLocation** (Input Agent)
   - **Purpose**: Capture user input for city name
   - **Success**: Routes to FetchWeather
   - **Output**: `location` field with city name

2. **FetchWeather** (Custom Agent)
   - **Purpose**: API call to weather service
   - **Input**: Uses `location` from previous step
   - **Success**: Routes to GenerateReport
   - **Output**: `weather_data` with API response

3. **GenerateReport** (LLM Agent)
   - **Purpose**: Natural language generation
   - **Provider**: OpenAI with 0.7 temperature for creativity
   - **Input**: Both `weather_data` and `location`
   - **Output**: `weather_report` with friendly description

4. **FormatOutput** (Default Agent)
   - **Purpose**: Final formatting and completion message
   - **Input**: `weather_report`
   - **Output**: `final_report`

5. **ErrorHandler** (Echo Agent)
   - **Purpose**: Catch and display any errors
   - **Fallback**: All nodes route here on failure

6. **End** (Echo Agent)
   - **Purpose**: Final output display
   - **Input**: Either success or error results

</TabItem>
<TabItem value="troubleshooting" label="Common Issues">

### Troubleshooting This Workflow

**Issue**: "WeatherAPIAgent not found"  
**Solution**: Ensure you've run `agentmap scaffold --csv weather_workflow.csv` first

**Issue**: API key errors  
**Solution**: Set environment variables:
```bash
export OPENWEATHER_API_KEY="your_key_here"
export OPENAI_API_KEY="your_openai_key"
```

**Issue**: "Invalid location" errors  
**Solution**: Use specific city names like "London" or "New York" instead of abbreviations

**Issue**: Workflow hangs at GenerateReport  
**Solution**: Check OpenAI API key and rate limits

### Debugging Tips

- Use `--log-level DEBUG` for detailed execution logs
- Test the WeatherAPIAgent separately first
- Verify API responses with a simple curl command
- Check the custom agent's `_get_child_service_info()` method

</TabItem>
</Tabs>

### Step 2: Scaffold the Custom Agent

Run the scaffold command to generate the custom agent template:

```bash
agentmap scaffold --csv weather_workflow.csv
```

This creates `custom_agents/weather_api_agent.py` with a starter template.

### Step 3: Implement the Weather API Agent

Edit `custom_agents/weather_api_agent.py`:

```python
from typing import Dict, Any, Optional
import requests
import os
from agentmap.agents.base_agent import BaseAgent

class WeatherAPIAgent(BaseAgent):
    """
    Fetches weather data from OpenWeatherMap API.
    
    Node: FetchWeather
    Input Fields: location
    Output Field: weather_data
    """
    
    def __init__(self, name, prompt, context=None, logger=None, 
                 execution_tracker_service=None, state_adapter_service=None):
        """Initialize WeatherAPIAgent."""
        super().__init__(name, prompt, context, logger, 
                         execution_tracker_service, state_adapter_service)
        
        # Get API key from environment or context
        self.api_key = self.context.get("api_key", os.getenv("OPENWEATHER_API_KEY"))
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Fetch weather data for the given location.
        
        Args:
            inputs: Dictionary containing 'location' key
            
        Returns:
            Weather data dictionary
        """
        location = inputs.get("location", "").strip()
        
        if not location:
            return {"error": "No location provided", "success": False}
        
        if not self.api_key:
            return {"error": "No API key configured", "success": False}
        
        try:
            # Make API request
            params = {
                "q": location,
                "appid": self.api_key,
                "units": "metric"  # Use Celsius
            }
            
            self.log_info(f"Fetching weather for: {location}")
            response = requests.get(self.base_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract relevant weather information
                weather_info = {
                    "location": data.get("name", location),
                    "country": data.get("sys", {}).get("country", ""),
                    "temperature": data.get("main", {}).get("temp", 0),
                    "feels_like": data.get("main", {}).get("feels_like", 0),
                    "humidity": data.get("main", {}).get("humidity", 0),
                    "description": data.get("weather", [{}])[0].get("description", ""),
                    "wind_speed": data.get("wind", {}).get("speed", 0),
                    "pressure": data.get("main", {}).get("pressure", 0)
                }
                
                self.log_info(f"Successfully fetched weather for {location}")
                return weather_info
                
            else:
                error_msg = f"API error: {response.status_code} - {response.text}"
                self.log_error(error_msg)
                return {"error": error_msg, "success": False}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg, "success": False}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg, "success": False}
    
    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """Provide debugging information."""
        return {
            "api_configured": bool(self.api_key),
            "base_url": self.base_url
        }
```

### Step 4: Set Up Environment

Create a `.env` file or set environment variables:

```bash
export OPENWEATHER_API_KEY="your_api_key_here"
export OPENAI_API_KEY="your_openai_key_here"
```

### Step 5: Execute the Workflow

Run the workflow:

```bash
agentmap run --graph WeatherFlow --csv weather_workflow.csv
```

The workflow will:
1. Prompt for a city name
2. Fetch weather data from the API
3. Generate a natural language report using OpenAI
4. Display the formatted result

### Example Output

```
Enter the city name for weather report: London

Weather Report Generated:

Good morning! Here's your weather report for London, UK:

Currently, it's 18°C (64°F) with partly cloudy skies. The temperature feels like 
17°C due to a gentle breeze blowing at 5.2 m/s. Humidity is at a comfortable 65%, 
and the atmospheric pressure is steady at 1013 hPa.

It's a pleasant day for outdoor activities, though you might want to keep a light 
jacket handy for the evening. Enjoy your day in London!
```

## Example 2: Multi-Source News Aggregator

This advanced example demonstrates orchestration, parallel processing, and summarization.

### Step 1: Create the CSV

Create `news_aggregator.csv`:

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
NewsFlow,GetTopic,,Get news topic from user,input,RouteToSources,ErrorHandler,,topic,What news topic are you interested in?
NewsFlow,RouteToSources,,"{'nodes':'TechNews|BusinessNews|SportsNews|GeneralNews'}",orchestrator,CollectResults,ErrorHandler,available_nodes|topic,selected_source,
NewsFlow,TechNews,,"{'source': 'techcrunch', 'category': 'technology'}",custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,tech_articles,
NewsFlow,BusinessNews,,"{'source': 'bloomberg', 'category': 'business'}",custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,business_articles,
NewsFlow,SportsNews,,"{'source': 'espn', 'category': 'sports'}",custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,sports_articles,
NewsFlow,GeneralNews,,"{'source': 'reuters', 'category': 'general'}",custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,general_articles,
NewsFlow,CollectResults,,"{'format': '{key}:\n{value}\n'}",summary,AnalyzeNews,ErrorHandler,tech_articles|business_articles|sports_articles|general_articles,all_articles,
NewsFlow,AnalyzeNews,,"{'provider': 'anthropic', 'model': 'claude-3-sonnet-20240229', 'temperature': 0.3}",llm,GenerateSummary,ErrorHandler,all_articles|topic,news_analysis,Analyze these news articles about {topic} and identify key themes and sentiment
NewsFlow,GenerateSummary,,"{'llm': 'anthropic', 'temperature': 0.5}",summary,FormatReport,ErrorHandler,all_articles|news_analysis,executive_summary,Create a concise executive summary about {topic}
NewsFlow,FormatReport,,Format final report,default,SaveReport,ErrorHandler,executive_summary|news_analysis,formatted_report,News Aggregation Complete
NewsFlow,SaveReport,,"{'format': 'markdown'}",file_writer,End,ErrorHandler,formatted_report|topic,save_result,news_reports/{topic}_report.md
NewsFlow,ErrorHandler,,Handle errors,echo,End,,error,error_message,
NewsFlow,End,,Complete workflow,echo,,,formatted_report|save_result|error_message,output,`}
  title="Multi-Source News Aggregator Workflow"
  filename="news_aggregator"
/>

## Advanced Features

### Using Memory for Conversational Workflows

Add memory to any LLM agent:

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatBot,Chat,,"{'memory_key': 'conversation', 'max_memory_messages': 20}",llm,Chat,,user_input|conversation,response,You are a helpful assistant.`}
  title="Conversational Workflow with Memory"
  filename="chat_with_memory"
/>

### Parallel Processing

Create parallel branches that converge:

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataFlow,Split,,Split into parallel tasks,default,ProcessA|ProcessB|ProcessC,ErrorHandler,data,tasks,
DataFlow,ProcessA,,Process branch A,default,Join,ErrorHandler,tasks,result_a,
DataFlow,ProcessB,,Process branch B,default,Join,ErrorHandler,tasks,result_b,
DataFlow,ProcessC,,Process branch C,default,Join,ErrorHandler,tasks,result_c,
DataFlow,Join,,"{'include_keys': false}",summary,End,ErrorHandler,result_a|result_b|result_c,combined_results,`}
  title="Parallel Processing Workflow"
  filename="parallel_processing"
/>

### Custom Routing Functions

Create `functions/route_by_confidence.py`:

```python
def route_by_confidence(state, high_confidence="DetailedAnalysis", low_confidence="QuickSummary"):
    """Route based on confidence score."""
    confidence = state.get("confidence_score", 0)
    
    if confidence > 0.8:
        return high_confidence
    else:
        return low_confidence
```

Use in CSV:

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
Analysis,CheckConfidence,func:route_by_confidence,"{'high_confidence': 'DetailedAnalysis', 'low_confidence': 'QuickSummary'}",default,,,,confidence_score,`}
  title="Custom Routing Function Example"
  filename="custom_routing"
/>

### Vector Storage for RAG

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
RAG,LoadDocs,,"{'provider': 'chroma', 'collection': 'knowledge_base'}",vector_writer,Search,,documents,load_result,
RAG,Search,,"{'k': 5, 'threshold': 0.7}",vector_reader,Answer,,query,search_results,
RAG,Answer,,"{'provider': 'openai', 'temperature': 0.3}",llm,End,,query|search_results,answer,Answer based on context: {search_results} Question: {query}`}
  title="Vector Storage for RAG Workflow"
  filename="vector_rag"
/>

## Best Practices

1. **Error Handling**: Always include error handler nodes
2. **Logging**: Use appropriate log levels in custom agents
3. **API Keys**: Store sensitive data in environment variables
4. **Testing**: Test agents individually before combining in workflows
5. **Documentation**: Use the Context field to document node purposes
6. **Modularity**: Build reusable agents that can be combined in different workflows

## Troubleshooting

### Common Issues

1. **Agent not found**: Ensure custom agents are in the configured directory
2. **API errors**: Check API keys and rate limits
3. **Routing issues**: Verify node names match exactly in routing fields
4. **Memory errors**: Set reasonable memory limits for conversational agents

### Debugging Tips

- Use `--log-level DEBUG` for detailed execution logs
- Check agent service info with `agent._get_child_service_info()`
- Test individual nodes before full workflow
- Use echo agents to debug data flow

## Next Steps

- Explore [Agent Types Reference](../reference/agent-types.md) for more agent options
- Learn about [CSV Schema Reference](../reference/csv-schema.md) for advanced CSV features
- Read the [Testing Patterns](../guides/development/testing.md) guide for testing workflows
- Check [Infrastructure Guide](../guides/deploying/index.md) for setup and configuration options

## Download All Examples

Get all the example files from this guide:

<div className="download-section">

<DownloadButton 
  filename="agentmap_quickstart_examples.zip" 
  content="ZIP_PLACEHOLDER"
  isZip={true}>
  📦 Complete Quick Start Package
</DownloadButton>

</div>

## Troubleshooting Common Issues

### Setup Issues

<Tabs>
<TabItem value="installation" label="Installation Problems">

**Issue**: `pip install agentmap` fails  
**Solution**: 
```bash
# Try with --upgrade flag
pip install --upgrade agentmap

# Or use specific version
pip install agentmap==1.0.0

# For development version
pip install git+https://github.com/agentic-labs/agentmap.git
```

**Issue**: Python version compatibility  
**Solution**: AgentMap requires Python 3.8+. Check your version:
```bash
python --version
# Should show Python 3.8 or higher
```

</TabItem>
<TabItem value="api-keys" label="API Key Issues">

**Issue**: OpenAI API errors  
**Solution**: 
1. Verify your API key at [OpenAI Platform](https://platform.openai.com/api-keys)
2. Check your billing and usage limits
3. Set the environment variable correctly:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

**Issue**: Weather API not working  
**Solution**: 
1. Sign up for free at [OpenWeatherMap](https://openweathermap.org/api)
2. Get your API key from the dashboard
3. Set environment variable:
   ```bash
   export OPENWEATHER_API_KEY="your_key_here"
   ```

</TabItem>
<TabItem value="execution" label="Execution Problems">

**Issue**: "Graph not found" error  
**Solution**: 
- Ensure the CSV file has the correct GraphName
- Check that the --graph parameter matches exactly
- Verify the CSV file path is correct

**Issue**: Workflow stops unexpectedly  
**Solution**: 
- Enable debug logging: `--log-level DEBUG`
- Check that all nodes have proper Success_Next routing
- Verify agent types are spelled correctly

**Issue**: Custom agents not loading  
**Solution**: 
- Run `agentmap scaffold` command first
- Check that custom agents are in the right directory
- Verify class names match filename (CamelCase)

</TabItem>
</Tabs>

### Getting Help

- **Documentation**: [Complete AgentMap Docs](../intro.md)
- **Examples**: [More Examples](../examples/)
- **Community**: [Discord Server](https://discord.gg/agentmap)
- **Issues**: [GitHub Issues](https://github.com/agentic-labs/agentmap/issues)

---

This quick start guide provides the foundation for building powerful workflows with AgentMap. Start simple and gradually add complexity as you become familiar with the patterns!

:::tip Next Steps
🚀 **Ready for more?** Check out our [Complete Example Workflows](../examples/) for advanced patterns including parallel processing, API integrations, and data pipelines!
:::
