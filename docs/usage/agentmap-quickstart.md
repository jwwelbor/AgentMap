# AgentMap Quick Start Guide

This guide walks you through building workflows from scratch using AgentMap, demonstrating the complete process from CSV definition to execution.

## Prerequisites

- Python 3.8+
- AgentMap installed (`pip install agentmap`)
- API keys for any services you plan to use (OpenAI, weather API, etc.)

## Example 1: Weather Report Workflow

Let's build a workflow that fetches weather data from an API and generates a natural language report using an LLM.

### Step 1: Create the CSV with Custom Agents

Create a file `weather_workflow.csv`:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
WeatherFlow,GetLocation,,Get user location,input,FetchWeather,ErrorHandler,,location,Enter the city name for weather report:
WeatherFlow,FetchWeather,,Fetch weather data from API,custom:WeatherAPIAgent,GenerateReport,ErrorHandler,location,weather_data,
WeatherFlow,GenerateReport,,{"provider": "openai", "temperature": 0.7},llm,FormatOutput,ErrorHandler,weather_data|location,weather_report,Generate a friendly weather report for {location} based on this data: {weather_data}
WeatherFlow,FormatOutput,,Format the final output,default,End,ErrorHandler,weather_report,final_report,Weather Report Generated
WeatherFlow,ErrorHandler,,Handle errors,echo,End,,error,error_message,
WeatherFlow,End,,Complete workflow,echo,,,final_report|error_message,output,
```

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

## Example 2: Multi-Source News Aggregator with Orchestration

This advanced example demonstrates orchestration, parallel processing, and summarization.

### Step 1: Create the CSV with Orchestrator and Summary Agents

Create `news_aggregator.csv`:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
NewsFlow,GetTopic,,Get news topic from user,input,RouteToSources,ErrorHandler,,topic,What news topic are you interested in?
NewsFlow,RouteToSources,,{"nodes":"TechNews|BusinessNews|SportsNews|GeneralNews"},orchestrator,CollectResults,ErrorHandler,available_nodes|topic,selected_source,
NewsFlow,TechNews,,{"source": "techcrunch", "category": "technology"},custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,tech_articles,
NewsFlow,BusinessNews,,{"source": "bloomberg", "category": "business"},custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,business_articles,
NewsFlow,SportsNews,,{"source": "espn", "category": "sports"},custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,sports_articles,
NewsFlow,GeneralNews,,{"source": "reuters", "category": "general"},custom:NewsAPIAgent,CollectResults,ErrorHandler,topic,general_articles,
NewsFlow,CollectResults,,{"format": "{key}:\n{value}\n"},summary,AnalyzeNews,ErrorHandler,tech_articles|business_articles|sports_articles|general_articles,all_articles,
NewsFlow,AnalyzeNews,,{"provider": "anthropic", "model": "claude-3-sonnet-20240229", "temperature": 0.3},llm,GenerateSummary,ErrorHandler,all_articles|topic,news_analysis,"Analyze these news articles about {topic} and identify key themes, sentiment, and important developments."
NewsFlow,GenerateSummary,,{"llm": "anthropic", "temperature": 0.5},summary,FormatReport,ErrorHandler,all_articles|news_analysis,executive_summary,"Create a concise executive summary of the news about {topic}, highlighting the most important stories and insights from the analysis."
NewsFlow,FormatReport,,Format final report,default,SaveReport,ErrorHandler,executive_summary|news_analysis,formatted_report,News Aggregation Complete
NewsFlow,SaveReport,,{"format": "markdown"},file_writer,End,ErrorHandler,formatted_report|topic,save_result,news_reports/{topic}_report.md
NewsFlow,ErrorHandler,,Handle errors,echo,End,,error,error_message,
NewsFlow,End,,Complete workflow,echo,,,formatted_report|save_result|error_message,output,
```

### Step 2: Scaffold and Implement the News API Agent

Run scaffold:

```bash
agentmap scaffold --csv news_aggregator.csv
```

Implement `custom_agents/news_api_agent.py`:

```python
from typing import Dict, Any, Optional
import requests
import os
from datetime import datetime
from agentmap.agents.base_agent import BaseAgent

class NewsAPIAgent(BaseAgent):
    """
    Fetches news articles from various news sources.
    
    Supports multiple news APIs and sources.
    """
    
    def __init__(self, name, prompt, context=None, logger=None,
                 execution_tracker_service=None, state_adapter_service=None):
        """Initialize NewsAPIAgent."""
        super().__init__(name, prompt, context, logger,
                         execution_tracker_service, state_adapter_service)
        
        # Configure based on context
        self.source = self.context.get("source", "newsapi")
        self.category = self.context.get("category", "general")
        self.api_key = self.context.get("api_key", os.getenv("NEWS_API_KEY"))
        self.max_articles = self.context.get("max_articles", 5)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Fetch news articles for the given topic.
        
        Args:
            inputs: Dictionary containing 'topic' key
            
        Returns:
            List of news articles with metadata
        """
        topic = inputs.get("topic", "").strip()
        
        if not topic:
            return {"error": "No topic provided", "success": False}
        
        if not self.api_key:
            # Return mock data for demo purposes
            return self._get_mock_articles(topic)
        
        try:
            # Make API request (using NewsAPI as example)
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": topic,
                "apiKey": self.api_key,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": self.max_articles
            }
            
            # Add source-specific filtering
            if self.source != "newsapi":
                params["sources"] = self.source
            
            self.log_info(f"Fetching {self.category} news about: {topic}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = []
                
                for article in data.get("articles", [])[:self.max_articles]:
                    articles.append({
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "source": article.get("source", {}).get("name", self.source),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "category": self.category
                    })
                
                self.log_info(f"Found {len(articles)} articles about {topic}")
                return {
                    "source": self.source,
                    "category": self.category,
                    "topic": topic,
                    "count": len(articles),
                    "articles": articles
                }
                
            else:
                error_msg = f"API error: {response.status_code}"
                self.log_error(error_msg)
                return {"error": error_msg, "success": False}
                
        except Exception as e:
            self.log_error(f"Error fetching news: {str(e)}")
            # Return mock data for demo
            return self._get_mock_articles(topic)
    
    def _get_mock_articles(self, topic: str) -> Dict[str, Any]:
        """Generate mock articles for demonstration."""
        mock_articles = {
            "technology": [
                {
                    "title": f"AI Breakthrough in {topic} Analysis",
                    "description": f"Researchers develop new AI model for analyzing {topic} data with 95% accuracy.",
                    "source": "TechCrunch",
                    "published_at": datetime.now().isoformat(),
                    "category": "technology"
                },
                {
                    "title": f"Startup Raises $50M for {topic} Platform",
                    "description": f"New platform promises to revolutionize how businesses handle {topic}.",
                    "source": "TechCrunch",
                    "published_at": datetime.now().isoformat(),
                    "category": "technology"
                }
            ],
            "business": [
                {
                    "title": f"{topic} Market Sees Record Growth",
                    "description": f"Global {topic} market expected to reach $1B by 2025.",
                    "source": "Bloomberg",
                    "published_at": datetime.now().isoformat(),
                    "category": "business"
                }
            ],
            "default": [
                {
                    "title": f"Latest Developments in {topic}",
                    "description": f"Comprehensive overview of recent {topic} trends and insights.",
                    "source": self.source,
                    "published_at": datetime.now().isoformat(),
                    "category": self.category
                }
            ]
        }
        
        articles = mock_articles.get(self.category, mock_articles["default"])
        
        return {
            "source": self.source,
            "category": self.category,
            "topic": topic,
            "count": len(articles),
            "articles": articles
        }
    
    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """Provide debugging information."""
        return {
            "source": self.source,
            "category": self.category,
            "api_configured": bool(self.api_key),
            "max_articles": self.max_articles
        }
```

### Step 3: Configure the Workflow

Create `agentmap_config.yaml`:

```yaml
# AgentMap Configuration
llm:
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}
      models:
        - gpt-4
        - gpt-3.5-turbo
    anthropic:
      api_key: ${ANTHROPIC_API_KEY}
      models:
        - claude-3-sonnet-20240229
        - claude-3-haiku-20240307

paths:
  workflows: ./workflows
  custom_agents: ./custom_agents
  functions: ./functions
  data: ./data
  outputs: ./outputs

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Step 4: Execute the News Aggregator

Run the workflow:

```bash
agentmap run --graph NewsFlow --csv news_aggregator.csv
```

The workflow will:
1. Ask for a news topic
2. Use the orchestrator to route to the most relevant news source
3. Fetch articles from multiple sources (in parallel if configured)
4. Collect and combine all articles
5. Analyze the news using Claude to identify themes
6. Generate an executive summary
7. Save the report as a markdown file

### Example Output

```
What news topic are you interested in? artificial intelligence

News Aggregation Complete

Executive Summary saved to: news_reports/artificial_intelligence_report.md

=== Executive Summary ===

**Artificial Intelligence News Analysis - June 2025**

Key Developments:
1. **Regulatory Progress**: The EU has finalized its AI Act implementation guidelines, 
   setting global precedents for AI governance.

2. **Technical Breakthroughs**: OpenAI and Anthropic announced significant advances 
   in model efficiency, reducing computational requirements by 40%.

3. **Market Growth**: The enterprise AI market reached $150B in Q2 2025, with 
   automation and analytics driving adoption.

Sentiment Analysis: Generally positive with cautious optimism around regulation.

Critical Insights:
- Industry consolidation accelerating as smaller AI startups struggle with compute costs
- Focus shifting from model size to efficiency and specialized applications
- Increased emphasis on AI safety and alignment in commercial deployments
```

## Advanced Features

### Using Memory for Conversational Workflows

Add memory to any LLM agent:

```csv
ChatBot,Chat,,{"memory_key": "conversation", "max_memory_messages": 20},llm,Chat,,user_input|conversation,response,You are a helpful assistant.
```

### Parallel Processing

Create parallel branches that converge:

```csv
DataFlow,Split,,Split into parallel tasks,default,ProcessA|ProcessB|ProcessC,ErrorHandler,data,tasks,
DataFlow,ProcessA,,Process branch A,default,Join,ErrorHandler,tasks,result_a,
DataFlow,ProcessB,,Process branch B,default,Join,ErrorHandler,tasks,result_b,
DataFlow,ProcessC,,Process branch C,default,Join,ErrorHandler,tasks,result_c,
DataFlow,Join,,{"include_keys": false},summary,End,ErrorHandler,result_a|result_b|result_c,combined_results,
```

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

```csv
Analysis,CheckConfidence,func:route_by_confidence,{"high_confidence": "DetailedAnalysis", "low_confidence": "QuickSummary"},default,,,,confidence_score,
```

### Vector Storage for RAG

```csv
RAG,LoadDocs,,{"provider": "chroma", "collection": "knowledge_base"},vector_writer,Search,,documents,load_result,
RAG,Search,,{"k": 5, "threshold": 0.7},vector_reader,Answer,,query,search_results,
RAG,Answer,,{"provider": "openai", "temperature": 0.3},llm,End,,query|search_results,answer,"Answer based on context: {search_results}\n\nQuestion: {query}"
```

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

- Explore [Advanced Agent Types](advanced_agent_types.md) for more complex agents
- Learn about [Service Injection](service_injection.md) for advanced integrations
- Read the [Testing Patterns](TESTING_PATTERNS.md) guide for testing workflows
- Check [Memory Management](memory_management_in_agentmap.md) for conversational apps

This quick start guide provides the foundation for building powerful workflows with AgentMap. Start simple and gradually add complexity as you become familiar with the patterns!
