---
sidebar_position: 2
title: Build an AI Weather Bot - API Integration & LLM Tutorial
description: Build an intelligent weather bot using AgentMap workflows with API integration, custom agents, and LLM-powered reporting. Learn fundamental agent patterns.
keywords: [weather bot tutorial, API integration, custom agents, LLM integration, AgentMap workflow, intelligent automation, AI weather reporting]
image: /img/agentmap-hero.png
---

import CSVTable from '@site/src/components/CSVTable';

# Build an AI Weather Bot with API Integration

## What We're Building

Create an **intelligent weather reporting system** that demonstrates key AgentMap concepts:
- ✅ **Custom Agent Development** - Build a specialized weather API agent
- ✅ **API Integration** - Connect to external services with error handling
- ✅ **LLM Integration** - Generate natural language reports from structured data
- ✅ **Workflow Orchestration** - Chain agents together for end-to-end automation
- ✅ **Error Handling** - Graceful failure management and user feedback

**Estimated Time**: 30 minutes  
**Difficulty**: Beginner  
**Learning Goals**: Custom agent development, API integration, LLM workflows, error handling patterns

## Prerequisites

- Python 3.8+ with AgentMap installed (`pip install agentmap`)
- OpenWeatherMap API key ([Get free key](https://openweathermap.org/api))
- OpenAI API key ([Get key](https://platform.openai.com/api-keys))
- Basic understanding of CSV files

## Workflow Overview

```mermaid
graph TD
    A[Get City Name] --> B[Fetch Weather Data]
    B --> C[Generate AI Report]
    C --> D[Format Output]
    D --> E[Display Result]
    
    B -->|Error| F[Error Handler]
    C -->|Error| F
    D -->|Error| F
    F --> E
    
    style A fill:#e1f5fe
    style B fill:#fff3e0
    style C fill:#e8f5e8
    style D fill:#f3e5f5
    style E fill:#fff8e1
    style F fill:#ffebee
```

## Step 1: Create the Workflow CSV

Create a file called `weather_bot.csv`:

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
WeatherFlow,GetLocation,,Get user location,input,FetchWeather,ErrorHandler,,location,Enter the city name for weather report:,Prompts user for city name
WeatherFlow,FetchWeather,,Fetch weather data from API,custom:WeatherAPIAgent,GenerateReport,ErrorHandler,location,weather_data,,Fetches real weather data from OpenWeatherMap
WeatherFlow,GenerateReport,,{'provider': 'openai', 'model': 'gpt-3.5-turbo', 'temperature': 0.7},llm,FormatOutput,ErrorHandler,weather_data|location,weather_report,Generate a friendly and informative weather report for {location} based on this data: {weather_data},Creates natural language weather report
WeatherFlow,FormatOutput,,Format the final output,default,End,ErrorHandler,weather_report,final_report,✅ Weather Report Generated Successfully,Formats the final output message
WeatherFlow,ErrorHandler,,Handle any errors gracefully,echo,End,,error,error_message,,Displays error messages to user
WeatherFlow,End,,Complete workflow,echo,,,final_report|error_message,output,,Final output node`}
  title="Weather Bot Workflow"
  filename="weather_bot"
/>

## Step 2: Generate Custom Agent Template

Run the scaffolding command to create the weather agent:

```bash
agentmap scaffold --csv weather_bot.csv
```

This creates `custom_agents/weather_api_agent.py` with a starter template.

## Step 3: Implement the Weather API Agent

Replace the generated file with this complete implementation:

```python title="custom_agents/weather_api_agent.py"
from typing import Dict, Any, Optional
import requests
import os
from agentmap.agents.base_agent import BaseAgent

class WeatherAPIAgent(BaseAgent):
    """
    Fetches weather data from OpenWeatherMap API.
    
    Provides comprehensive weather information including temperature,
    conditions, humidity, wind speed, and more.
    """
    
    def __init__(self, name, prompt, context=None, logger=None, 
                 execution_tracker_service=None, state_adapter_service=None):
        """Initialize WeatherAPIAgent with API configuration."""
        super().__init__(name, prompt, context, logger, 
                         execution_tracker_service, state_adapter_service)
        
        # Get API key from environment or context
        self.api_key = self.context.get("api_key", os.getenv("OPENWEATHER_API_KEY"))
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        
        # Configuration options
        self.units = self.context.get("units", "metric")  # metric, imperial, kelvin
        self.language = self.context.get("language", "en")
        self.timeout = self.context.get("timeout", 10)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Fetch weather data for the specified location.
        
        Args:
            inputs: Dictionary containing 'location' key
            
        Returns:
            Dictionary with comprehensive weather information or error details
        """
        location = inputs.get("location", "").strip()
        
        # Validate input
        if not location:
            self.log_error("No location provided")
            return {
                "error": "Please provide a valid city name",
                "success": False,
                "location": "Unknown"
            }
        
        if not self.api_key:
            self.log_error("No API key configured")
            return {
                "error": "Weather service not configured. Please set OPENWEATHER_API_KEY environment variable.",
                "success": False,
                "location": location
            }
        
        try:
            # Prepare API request parameters
            params = {
                "q": location,
                "appid": self.api_key,
                "units": self.units,
                "lang": self.language
            }
            
            self.log_info(f"Fetching weather for: {location}")
            
            # Make API request
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract and structure weather information
                weather_info = {
                    "success": True,
                    "location": data.get("name", location),
                    "country": data.get("sys", {}).get("country", ""),
                    "coordinates": {
                        "latitude": data.get("coord", {}).get("lat", 0),
                        "longitude": data.get("coord", {}).get("lon", 0)
                    },
                    "temperature": {
                        "current": round(data.get("main", {}).get("temp", 0), 1),
                        "feels_like": round(data.get("main", {}).get("feels_like", 0), 1),
                        "min": round(data.get("main", {}).get("temp_min", 0), 1),
                        "max": round(data.get("main", {}).get("temp_max", 0), 1)
                    },
                    "weather": {
                        "main": data.get("weather", [{}])[0].get("main", ""),
                        "description": data.get("weather", [{}])[0].get("description", ""),
                        "icon": data.get("weather", [{}])[0].get("icon", "")
                    },
                    "atmosphere": {
                        "humidity": data.get("main", {}).get("humidity", 0),
                        "pressure": data.get("main", {}).get("pressure", 0),
                        "visibility": data.get("visibility", 0) / 1000  # Convert to km
                    },
                    "wind": {
                        "speed": data.get("wind", {}).get("speed", 0),
                        "direction": data.get("wind", {}).get("deg", 0),
                        "gust": data.get("wind", {}).get("gust", 0)
                    },
                    "clouds": data.get("clouds", {}).get("all", 0),
                    "timestamps": {
                        "data_time": data.get("dt", 0),
                        "sunrise": data.get("sys", {}).get("sunrise", 0),
                        "sunset": data.get("sys", {}).get("sunset", 0)
                    },
                    "units": self.units
                }
                
                self.log_info(f"Successfully fetched weather for {weather_info['location']}")
                return weather_info
                
            elif response.status_code == 404:
                error_msg = f"City '{location}' not found. Please check the spelling and try again."
                self.log_warning(error_msg)
                return {"error": error_msg, "success": False, "location": location}
                
            elif response.status_code == 401:
                error_msg = "Invalid API key. Please check your OpenWeatherMap API key."
                self.log_error(error_msg)
                return {"error": error_msg, "success": False, "location": location}
                
            else:
                error_msg = f"Weather API error: {response.status_code} - {response.text}"
                self.log_error(error_msg)
                return {"error": error_msg, "success": False, "location": location}
                
        except requests.exceptions.Timeout:
            error_msg = "Weather service timeout. Please try again."
            self.log_error(error_msg)
            return {"error": error_msg, "success": False, "location": location}
            
        except requests.exceptions.ConnectionError:
            error_msg = "Unable to connect to weather service. Check your internet connection."
            self.log_error(error_msg)
            return {"error": error_msg, "success": False, "location": location}
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg, "success": False, "location": location}
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg, "success": False, "location": location}
    
    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """Provide debugging information about the agent configuration."""
        return {
            "api_configured": bool(self.api_key),
            "base_url": self.base_url,
            "units": self.units,
            "language": self.language,
            "timeout": self.timeout
        }
```

## Step 4: Set Up Environment Variables

Create a `.env` file in your project directory:

```bash title=".env"
# OpenWeatherMap API Key (required)
OPENWEATHER_API_KEY=your_openweather_api_key_here

# OpenAI API Key (required)
OPENAI_API_KEY=your_openai_api_key_here

# Optional: AgentMap logging level
AGENTMAP_LOG_LEVEL=INFO
```

Alternatively, set environment variables directly:

```bash
export OPENWEATHER_API_KEY="your_openweather_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"
```

## Step 5: Configure AgentMap

Create `agentmap_config.yaml`:

```yaml title="agentmap_config.yaml"
# AgentMap Configuration for Weather Bot
llm:
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}
      models:
        - gpt-3.5-turbo
        - gpt-4
      default_model: gpt-3.5-turbo
      temperature: 0.7

paths:
  workflows: ./
  custom_agents: ./custom_agents
  functions: ./functions
  data: ./data
  outputs: ./outputs

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

execution:
  tracking_enabled: true
  default_timeout: 30
```

## Step 6: Run the Weather Bot

Execute your weather bot workflow:

```bash
agentmap run --graph WeatherFlow --csv weather_bot.csv
```

## Expected Output

When you run the workflow, you'll see:

```
Enter the city name for weather report: London

✅ Weather Report Generated Successfully

🌤️ Weather Report for London, GB

Good afternoon! Here's your current weather report for London:

**Current Conditions:**
- Temperature: 18°C (feels like 17°C)
- Weather: Partly cloudy skies
- Humidity: 65%
- Wind: Light breeze from the southwest at 5.2 m/s

**Additional Details:**
- Daily range: 15°C - 22°C
- Atmospheric pressure: 1013 hPa
- Visibility: 10 km
- Cloud coverage: 40%

**Perfect Day Summary:**
It's a pleasant day in London with partly cloudy conditions. The temperature 
is comfortable for outdoor activities, though you might want to keep a light 
jacket handy for the evening. The gentle breeze makes it feel quite refreshing!

Have a wonderful day in London! 🇬🇧
```

## Common Issues & Solutions

### 🚨 Issue: "No API key configured"
**Solution**: Ensure you've set the `OPENWEATHER_API_KEY` environment variable:
```bash
export OPENWEATHER_API_KEY="your_actual_api_key"
```

### 🚨 Issue: "City not found"
**Solution**: Try different city name formats:
- Use English names: "Rome" instead of "Roma"
- Include country codes: "London,GB" or "London,UK"
- Try major city names in the region

### 🚨 Issue: "OpenAI API errors"
**Solution**: 
- Verify your OpenAI API key is valid
- Check your API usage limits
- Ensure you have sufficient credits

### 🚨 Issue: "Agent not found"
**Solution**: 
- Run `agentmap scaffold --csv weather_bot.csv` to generate the agent
- Ensure the custom_agents directory is in the correct location
- Check the agent file name matches the expected pattern

### 🚨 Issue: "Timeout errors"
**Solution**: 
- Check your internet connection
- Increase timeout value in the agent context
- Try again during off-peak hours

## Enhancements & Next Steps

### 🎯 **Beginner Enhancements**
1. **Add more cities**: Modify to ask for multiple cities
2. **Different units**: Add Fahrenheit option 
3. **Weather icons**: Include emoji weather icons in output
4. **Save reports**: Add file output to save weather reports

### 🎯 **Intermediate Enhancements**
1. **5-day forecast**: Extend to show weather forecast
2. **Weather alerts**: Add severe weather warnings
3. **Location suggestions**: Implement city name auto-complete
4. **Historical data**: Compare with yesterday's weather

### 🎯 **Advanced Enhancements**
1. **Multiple providers**: Add backup weather services
2. **Caching**: Implement weather data caching
3. **Scheduling**: Set up automated daily weather reports
4. **Integration**: Connect to Slack/Discord for notifications

## Weather Bot API Integration {#weather-bot-api-integration}

The weather bot demonstrates sophisticated **API integration patterns** that you can apply to any external service:

### 🔌 **Multi-Provider API Strategy**
Extend your weather bot to use multiple weather services for redundancy:

```python
# Advanced API integration with fallback providers
class MultiProviderWeatherAgent(WeatherAPIAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.providers = [
            {"name": "openweather", "url": "https://api.openweathermap.org/data/2.5/weather"},
            {"name": "weatherapi", "url": "https://api.weatherapi.com/v1/current.json"},
            {"name": "accuweather", "url": "https://dataservice.accuweather.com/currentconditions/v1/"}
        ]
    
    def process(self, inputs):
        for provider in self.providers:
            try:
                result = self._fetch_from_provider(provider, inputs)
                if result.get("success"):
                    return result
            except Exception as e:
                self.log_warning(f"Provider {provider['name']} failed: {e}")
                continue
        
        return self._fallback_response(inputs)
```

### 🔄 **Rate Limiting & Caching**
Implement intelligent request management:

```python
# Add to WeatherAPIAgent
from functools import lru_cache
import time

class CachedWeatherAgent(WeatherAPIAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_request_time = 0
        self.request_interval = 1.0  # Minimum seconds between requests
    
    @lru_cache(maxsize=100)
    def _cached_weather_request(self, location, timestamp_hour):
        # Cache results for 1 hour by including hour in cache key
        return self._make_api_request(location)
    
    def process(self, inputs):
        # Rate limiting
        current_time = time.time()
        if current_time - self.last_request_time < self.request_interval:
            time.sleep(self.request_interval - (current_time - self.last_request_time))
        
        # Use cached request with hourly granularity
        timestamp_hour = int(time.time() // 3600)
        result = self._cached_weather_request(inputs.get("location"), timestamp_hour)
        
        self.last_request_time = time.time()
        return result
```

### 🌐 **Global API Integration Patterns**
These patterns work for any external API:

- **Authentication Management**: Secure API key rotation and management
- **Error Classification**: Distinguish between temporary and permanent failures  
- **Response Transformation**: Normalize data from different API schemas
- **Monitoring Integration**: Track API performance and usage metrics

## Download Starter Files

```bash
# Clone the complete weather bot example
git clone https://github.com/jwwelbor/AgentMap-Examples.git
cd AgentMap-Examples/weather-bot

# Or download individual files
curl -O https://raw.githubusercontent.com/jwwelbor/AgentMap-Examples/main/weather-bot/weather_bot.csv
curl -O https://raw.githubusercontent.com/jwwelbor/AgentMap-Examples/main/weather-bot/custom_agents/weather_api_agent.py
```

## Related Documentation

### 📖 **Core Concepts**
- **[Understanding Workflows](../guides/understanding-workflows)**: Learn workflow fundamentals with interactive examples
- **[CSV Schema Reference](../reference/csv-schema)**: Complete workflow format specification
- **[State Management](../guides/state-management)**: How data flows between agents

### 🤖 **Agent Development**
- **[Agent Types Reference](../reference/agent-types)**: Complete list of available agents
- **[Advanced Agent Types](../guides/advanced/advanced-agent-types)**: Build custom agents
- **[Agent Development Contract](../guides/advanced/agent-development-contract)**: Agent interface requirements
- **[Service Injection Patterns](../guides/advanced/service-injection-patterns)**: Dependency injection in custom agents

### 🔧 **Tools & Development**
- **[CLI Commands](../reference/cli-commands)**: Complete command-line reference
- **[CLI Graph Inspector](../reference/cli-graph-inspector)**: Debug and analyze workflows
- **[Interactive Playground](../playground)**: Test workflows in your browser

### 📚 **Related Tutorials**
- **[Data Processing Pipeline](./data-processing-pipeline)**: Learn data transformation and ETL patterns
- **[Customer Support Bot](./customer-support-bot)**: Build conversational agents with routing
- **[API Integration](./api-integration)**: Connect to multiple external services
- **[Document Analyzer](./document-analyzer)**: Process files with AI analysis
- **[Example Workflows](./example-workflows)**: Real-world workflow patterns and templates

### 🏗️ **Advanced Topics**
- **[Memory Management](../guides/advanced/memory-and-orchestration/memory-management)**: Persistent state across runs
- **[Testing Patterns](../guides/operations/testing-patterns)**: Testing and quality assurance
- **[Performance Optimization](../guides/advanced/performance)**: Scale workflows efficiently

## Troubleshooting

Having issues? Check our comprehensive resources:
- **[CLI Graph Inspector](../reference/cli-graph-inspector)**: Diagnose workflow issues
- **[Testing Patterns](../guides/operations/testing-patterns)**: Validate your workflows
- **[Community Discussions](https://github.com/jwwelbor/AgentMap/discussions)**: Get help from the community

---

**🎉 Congratulations!** You've built your first AI-powered weather bot with AgentMap! This tutorial covered the fundamentals:

### **🎆 What You've Learned**
- **👨‍💻 Custom Agent Development**: Built a specialized WeatherAPIAgent from scratch
- **🔗 API Integration**: Connected to external services with robust error handling
- **🤖 LLM Workflows**: Used AI to transform data into natural language
- **🔄 Workflow Orchestration**: Chained multiple agents for end-to-end automation

### **🚀 Next Steps**
Ready for more advanced patterns? Check out our **[Multi-Agent Customer Support System](./customer-support-bot)** to see how multiple specialized agents can work together in sophisticated coordination!
