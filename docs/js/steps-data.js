/**
 * Data for the workflow steps.
 * Each step contains title, description, details, code, and visual representation.
 */
const stepsData = [
    {
        title: "What is AgentMap?",
        description: "Build AI workflows using simple CSV files - no complex coding required!",
        details: "AgentMap is a declarative orchestration framework that lets you create sophisticated AI workflows by defining agents and their connections in CSV files. Perfect for rapid prototyping, production workflows, and everything in between.",
        code: null,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TD
                    User[You] -->|Write| CSV[Simple CSV File]
                    CSV -->|Run| AgentMap[AgentMap]
                    AgentMap -->|Creates| Workflow[AI Workflow]
                    
                    Workflow --> API[API Calls]
                    Workflow --> LLM[LLM Processing]
                    Workflow --> Storage[File Operations]
                    Workflow --> Vector[Vector Search]
                    
                    API --> Results[Results]
                    LLM --> Results
                    Storage --> Results
                    Vector --> Results
                    
                    classDef user fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    classDef csv fill:#F3F4F6,stroke:#9CA3AF,color:#4B5563
                    classDef system fill:#DBEAFE,stroke:#3B82F6,color:#1E40AF
                    classDef workflow fill:#E0F2FE,stroke:#0EA5E9,color:#0C4A6E
                    classDef capability fill:#FCE7F3,stroke:#EC4899,color:#9D174D
                    classDef result fill:#A7F3D0,stroke:#059669,color:#064E3B
                    
                    class User user
                    class CSV csv
                    class AgentMap system
                    class Workflow workflow
                    class API,LLM,Storage,Vector capability
                    class Results result
                </pre>
            </div>
        `
    },
    {
        title: "1. Define Your Workflow in CSV",
        description: "Start by creating a simple CSV file that describes your workflow.",
        details: "Each row in the CSV represents a step in your workflow. You specify what type of agent to use, how they connect, and what prompts or data they need.",
        code: `# weather_workflow.csv - A simple weather report generator

GraphName,Node,AgentType,Success_Next,Input_Fields,Output_Field,Prompt
WeatherFlow,GetCity,input,FetchWeather,,city,What city would you like weather for?
WeatherFlow,FetchWeather,custom:WeatherAPI,GenerateReport,city,weather_data,
WeatherFlow,GenerateReport,openai,ShowResult,weather_data|city,report,Write a friendly weather report for {city}: {weather_data}
WeatherFlow,ShowResult,echo,,,report,`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart LR
                        GetCity[Get City<br/>Input Agent] --> FetchWeather[Fetch Weather<br/>Custom API Agent]
                        FetchWeather --> GenerateReport[Generate Report<br/>OpenAI Agent]
                        GenerateReport --> ShowResult[Show Result<br/>Echo Agent]

                        classDef input fill:#164E63,stroke:#22D3EE,color:#A5F3FC
                        classDef api fill:#854D0E,stroke:#FCD34D,color:#FCD34D
                        classDef llm fill:#065F46,stroke:#6EE7B7,color:#6EE7B7
                        classDef output fill:#374151,stroke:#6B7280,color:#9CA3AF

                        class GetCity input
                        class FetchWeather api
                        class GenerateReport llm
                        class ShowResult output
                </pre>
            </div>

            <h3 class="section-title">What Each Column Means</h3>
            <ul class="feature-list">
                <li><strong>GraphName</strong>: Name of your workflow</li>
                <li><strong>Node</strong>: Unique name for each step</li>
                <li><strong>AgentType</strong>: What kind of agent to use (input, openai, custom, etc.)</li>
                <li><strong>Success_Next</strong>: Which node to go to next</li>
                <li><strong>Input_Fields</strong>: What data this node needs (from previous nodes)</li>
                <li><strong>Output_Field</strong>: Where to store this node's result</li>
                <li><strong>Prompt</strong>: Instructions or prompts for the agent</li>
            </ul>
        `
    },
    {
        title: "2. Create Custom Agents (If Needed)",
        description: "AgentMap automatically generates starter code for any custom agents you define.",
        details: "Just run 'agentmap scaffold' and it creates Python files for your custom agents with all the boilerplate code ready to go.",
        code: `# Run the scaffold command
$ agentmap scaffold --csv weather_workflow.csv

# This generates: custom_agents/weather_api_agent.py

from agentmap.agents.base_agent import BaseAgent
import requests

class WeatherAPIAgent(BaseAgent):
    """Fetch weather data from OpenWeatherMap API."""
    
    def process(self, inputs):
        city = inputs.get("city")
        
        # Your API call logic here
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": self.api_key}
        )
        
        weather_data = response.json()
        return {
            "temperature": weather_data["main"]["temp"],
            "description": weather_data["weather"][0]["description"],
            "humidity": weather_data["main"]["humidity"]
        }`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TB
                    
                    CSV[CSV File] -->|agentmap scaffold| Scaffold[Scaffold Command]
                    Scaffold -->|Generates| CustomAgent[weather_api_agent.py]
                    
                    CustomAgent --> Code[Starter Code with:]
                    Code --> Boilerplate[✓ All imports]
                    Code --> Structure[✓ Class structure]  
                    Code --> Methods[✓ Required methods]
                    Code --> Docs[✓ Documentation]
                    
                    You[You] -->|Just fill in| Logic[Business Logic]
                    
                    classDef command fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    classDef file fill:#FCE7F3,stroke:#EC4899,color:#9D174D
                    classDef generated fill:#DBEAFE,stroke:#3B82F6,color:#1E40AF
                    classDef user fill:#A7F3D0,stroke:#059669,color:#064E3B
                    
                    class CSV,CustomAgent file
                    class Scaffold command
                    class Code,Boilerplate,Structure,Methods,Docs generated
                    class You,Logic user
                </pre>
            </div>
        `
    },
    {
        title: "3. Use Built-in Agents",
        description: "AgentMap comes with powerful built-in agents for common tasks.",
        details: "No coding required! Just specify the agent type in your CSV and configure it with context parameters.",
        code: `# Built-in agents you can use immediately:

# LLM Agents - Use any major LLM provider
GraphName,Node,AgentType,Context,Prompt
Chat,Assistant,openai,{"model":"gpt-4","temperature":0.7},You are a helpful assistant
Chat,Claude,anthropic,{"model":"claude-3-sonnet"},Analyze this data: {input}
Chat,Gemini,google,{"model":"gemini-pro"},Summarize this text: {document}

# Storage Agents - Read/write files and data
Data,ReadCSV,csv_reader,,"data/customers.csv"
Data,SaveJSON,json_writer,{"indent":2},"output/results.json"
Data,LoadDocs,file_reader,{"chunk_size":1000},"documents/*.pdf"

# Specialized Agents
Search,VectorSearch,vector_reader,{"k":5,"collection":"knowledge_base"},
Flow,RouteIntent,orchestrator,{"nodes":"Support|Sales|Technical"},
Process,Summarize,summary,{"llm":"anthropic"},Create executive summary`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TB
                    
                    subgraph "Built-in Agent Library"
                        subgraph "LLM Agents"
                            OpenAI[OpenAI/GPT]
                            Anthropic[Anthropic/Claude]
                            Google[Google/Gemini]
                        end
                        
                        subgraph "Storage Agents"
                            CSV[CSV Reader/Writer]
                            JSON[JSON Reader/Writer]
                            File[File Reader/Writer]
                            Vector[Vector Storage]
                        end
                        
                        subgraph "Control Agents"
                            Input[Input Agent]
                            Echo[Echo Agent]
                            Orchestrator[Orchestrator]
                            Summary[Summary Agent]
                        end
                    end
                    
                    CSV --> YourWorkflow[Your Workflow]
                    JSON --> YourWorkflow
                    OpenAI --> YourWorkflow
                    Orchestrator --> YourWorkflow
                    
                    classDef llm fill:#065F46,stroke:#6EE7B7,color:#6EE7B7
                    classDef storage fill:#854D0E,stroke:#FCD34D,color:#FCD34D
                    classDef control fill:#164E63,stroke:#22D3EE,color:#A5F3FC
                    classDef workflow fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    
                    class OpenAI,Anthropic,Google llm
                    class CSV,JSON,File,Vector storage
                    class Input,Echo,Orchestrator,Summary control
                    class YourWorkflow workflow
                </pre>
            </div>
        `
    },
    {
        title: "4. Run Your Workflow",
        description: "Execute your workflow with a simple command.",
        details: "AgentMap handles all the complexity - state management, error handling, service injection, and execution flow. You just run one command.",
        code: `# Run your workflow
$ agentmap run --graph WeatherFlow --csv weather_workflow.csv

# With initial state
$ agentmap run --graph DataProcessor --state '{"file": "data.csv"}'

# What happens when you run:
# 1. AgentMap reads your CSV
# 2. Creates and configures all agents
# 3. Builds the workflow graph
# 4. Executes each step in order
# 5. Manages data flow between steps
# 6. Returns the final results

# Example execution:
What city would you like weather for? London

Fetching weather data...
Generating report with OpenAI...

Result:
"Good morning! Here's your weather report for London:
Currently 18°C with partly cloudy skies. It's a pleasant day
with 65% humidity and gentle winds. Perfect for a walk in the park!"`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart LR
                    
                    CLI[$ agentmap run] --> Load[Load CSV]
                    Load --> Build[Build Workflow]
                    Build --> Execute[Execute Nodes]
                    Execute --> Results[Get Results]
                    
                    Execute --> Node1[GetCity: "London"]
                    Node1 --> Node2[FetchWeather: API Call]
                    Node2 --> Node3[GenerateReport: LLM]
                    Node3 --> Node4[ShowResult: Display]
                    
                    classDef command fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    classDef process fill:#DBEAFE,stroke:#3B82F6,color:#1E40AF
                    classDef execution fill:#FCE7F3,stroke:#EC4899,color:#9D174D
                    classDef result fill:#A7F3D0,stroke:#059669,color:#064E3B
                    
                    class CLI command
                    class Load,Build,Execute process
                    class Node1,Node2,Node3,Node4 execution
                    class Results,Node4 result
                </pre>
            </div>
        `
    },
    {
        title: "5. Advanced Features",
        description: "Scale up with powerful features as your needs grow.",
        details: "AgentMap supports advanced patterns like parallel processing, memory management, conditional routing, and complex orchestration - all still defined in simple CSV files.",
        code: `# Parallel Processing - Multiple branches execute simultaneously
GraphName,Node,Success_Next
DataPipeline,LoadData,ProcessA|ProcessB|ProcessC
DataPipeline,ProcessA,Combine
DataPipeline,ProcessB,Combine
DataPipeline,ProcessC,Combine
DataPipeline,Combine,Summarize

# Memory Management - Maintain conversation context
Chatbot,Chat,{"memory_key":"conversation","max_messages":20}

# Smart Routing - Route based on content
Router,Analyze,{"routing_enabled":true,"task_type":"classification"}

# Orchestration - Dynamic workflow selection
Support,RouteTicket,{"nodes":"Billing|Technical|General"}

# Vector Search - RAG workflows
RAG,SearchDocs,{"provider":"chroma","k":5,"threshold":0.8}`,
        visual: `
            <div class="mermaid-wrapper">
                <pre class="mermaid">
                    flowchart TB
                    
                    subgraph "Advanced Patterns"
                        subgraph "Parallel"
                            Split --> PA[Process A]
                            Split --> PB[Process B]  
                            Split --> PC[Process C]
                            PA --> Join
                            PB --> Join
                            PC --> Join
                        end
                        
                        subgraph "Memory"
                            User --> ChatMemory[Chat + Memory]
                            ChatMemory --> Response
                            Response --> ChatMemory
                        end
                        
                        subgraph "Orchestration"
                            Intent --> Orchestrator
                            Orchestrator --> Technical
                            Orchestrator --> Billing
                            Orchestrator --> Support
                        end
                    end
                    
                    classDef parallel fill:#F3E8FF,stroke:#A855F7,color:#6B21A8
                    classDef memory fill:#065F46,stroke:#6EE7B7,color:#6EE7B7
                    classDef orchestration fill:#854D0E,stroke:#FCD34D,color:#FCD34D
                    
                    class Split,PA,PB,PC,Join parallel
                    class User,ChatMemory,Response memory
                    class Intent,Orchestrator,Technical,Billing,Support orchestration
                </pre>
            </div>
        `
    }
];


/**
 * Documentation files available in the project
 */
const documentationFiles = [
    // Getting Started - FIRST!
    {
        "path": "./usage/agentmap_quick_start.md",
        "title": "🚀 Quick Start Guide - Build Your First Workflow!"
    },
    
    // Core Documentation
    {
        "path": "README.md",
        "title": "Main README"
    },
    {
        "path": "./usage/index.md",
        "title": "Usage Documentation Index"
    },
    
    // Workflow Building
    {
        "path": "./usage/agentmap_csv_schema_documentation.md",
        "title": "CSV Schema Documentation"
    },
    {
        "path": "./usage/agentmap_example_workflows.md",
        "title": "Example Workflows"
    },
    {
        "path": "./usage/agentmap_cli_documentation.md",
        "title": "CLI Documentation"
    },
    
    // Agent Types
    {
        "path": "./usage/agentmap_agent_types.md",
        "title": "Built-in Agent Types"
    },
    {
        "path": "./usage/advanced_agent_types.md",
        "title": "Advanced Agent Types"
    },
    
    // Features
    {
        "path": "./usage/prompt_management_in_agentmap.md",
        "title": "Prompt Management"
    },
    {
        "path": "./usage/storage_services.md",
        "title": "Storage Services"
    },
    {
        "path": "./usage/orchestration_agent.md",
        "title": "Orchestration Agent"
    },
    
    // Advanced Topics
    {
        "path": "./usage/langchain_memory_in_agentmap.md",
        "title": "Memory Management"
    },
    {
        "path": "./usage/state_management_and_data_flow.md",
        "title": "State Management and Data Flow"
    },
    {
        "path": "./usage/host-service-integration.md",
        "title": "Custom Service Integration"
    },
    
    // Architecture (for those who want to dig deeper)
    {
        "path": "./architecture/clean_architecture_overview.md",
        "title": "Architecture Overview (Advanced)"
    },
    {
        "path": "./architecture/service_catalog.md",
        "title": "Service Catalog (Advanced)"
    },
    {
        "path": "./usage/agentmap_execution_tracking.md",
        "title": "Execution Tracking and Monitoring"
    }
];