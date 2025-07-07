import React from 'react';
import CSVTable from './CSVTable';

/**
 * Example usage of the enhanced CSVTable component
 * This demonstrates validation features and proper Pydantic syntax
 */
const CSVTableExample: React.FC = () => {
  // Correct Python dictionary syntax example
  const correctSampleCSV = `graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
WeatherBot,GetWeather,,Get current weather data,input,AnalyzeWeather,,location,weather_data,Enter your location (e.g. New York City):
WeatherBot,AnalyzeWeather,,"{'provider': 'openai', 'temperature': 0.7, 'model': 'gpt-3.5-turbo'}",llm,FormatNotification,ErrorHandler,weather_data,analysis,Analyze this weather data and provide practical advice: {weather_data}
WeatherBot,FormatNotification,,Format the final notification,echo,End,,analysis,notification,
WeatherBot,End,,Weather notification complete,echo,,,notification,final_message,Weather update sent successfully!
WeatherBot,ErrorHandler,,Handle errors gracefully,echo,End,,error,error_message,Unable to get weather data. Please try again later.`;

  // Example with validation issues (JSON syntax instead of Python dict)
  const invalidSampleCSV = `graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
ChatBot,GetInput,,Get user input,input,ProcessInput,,message,user_message,Enter your message:
ChatBot,ProcessInput,,"{"provider": "openai", "temperature": 0.7, "enabled": true}",llm,RespondToUser,ErrorHandler,user_message,ai_response,You are a helpful assistant. Respond to: {user_message}
ChatBot,RespondToUser,,Display the response,echo,GetInput,,ai_response,final_response,
ChatBot,ErrorHandler,,Handle any errors,echo,GetInput,,error,error_message,Sorry, something went wrong.`;

  // Advanced workflow with proper Python dictionary syntax
  const advancedWorkflowCSV = `graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
AdvancedFlow,GetInput,,Collect user requirements,input,RouteByType,ErrorHandler,,requirements,Describe your task:,User input collection
AdvancedFlow,RouteByType,,"{'analysis_types': ['sentiment', 'summary', 'extraction']}",routing,AnalyzeSentiment|CreateSummary|ExtractData,ErrorHandler,requirements,route_decision,,Dynamic routing
AdvancedFlow,AnalyzeSentiment,,"{'provider': 'openai', 'temperature': 0.3, 'max_tokens': 150}",llm,FormatResults,ErrorHandler,requirements,sentiment_analysis,Analyze sentiment: {requirements},Sentiment analysis
AdvancedFlow,CreateSummary,,"{'provider': 'anthropic', 'model': 'claude-3-sonnet', 'max_tokens': 200}",llm,FormatResults,ErrorHandler,requirements,summary,Summarize: {requirements},Text summarization
AdvancedFlow,ExtractData,,"{'provider': 'openai', 'temperature': 0.1, 'output_format': 'json'}",llm,FormatResults,ErrorHandler,requirements,extracted_data,Extract entities from: {requirements},Data extraction
AdvancedFlow,FormatResults,,"{'template': 'markdown', 'include_metadata': True}",formatter,SaveResults,ErrorHandler,sentiment_analysis|summary|extracted_data,formatted_output,,Format results
AdvancedFlow,SaveResults,,"{'directory': 'outputs', 'timestamp': True, 'backup': True}",file_writer,End,ErrorHandler,formatted_output,save_path,results_{timestamp}.md,Save results
AdvancedFlow,ErrorHandler,,Handle errors gracefully,echo,End,,error,error_message,,Error handling
AdvancedFlow,End,,Workflow completion,echo,,,formatted_output|save_path|error_message,final_output,,Final output`;

  const projectTasksCSV = `Task,Owner,Status,Priority,Due Date,Notes
Setup API Integration,Alice,In Progress,High,2024-01-15,Working on authentication
Create Database Schema,Bob,Completed,Medium,2024-01-10,Tables created successfully
Write Unit Tests,Charlie,Pending,Medium,2024-01-20,Waiting for API completion
Deploy to Staging,Alice,Pending,High,2024-01-25,After testing complete
Performance Testing,Bob,Not Started,Low,2024-01-30,Optional optimization phase`;

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '2rem', color: '#1976d2' }}>Enhanced CSVTable Component Examples</h1>
      
      <div style={{ marginBottom: '3rem' }}>
        <h2 style={{ color: '#2e7d32', marginBottom: '1rem' }}>✅ Correct: Python Dictionary Syntax</h2>
        <p style={{ marginBottom: '1rem', color: '#666' }}>
          This example shows proper Python dictionary syntax in the Context column, which is compatible with AgentMap's Pydantic models.
        </p>
        <CSVTable 
          csvContent={correctSampleCSV}
          title="Weather Bot Workflow (Correct Syntax)"
          filename="weather-bot-workflow"
          showLineNumbers={true}
          validatePydantic={true}
          showValidation={true}
        />
      </div>
      
      <div style={{ marginBottom: '3rem' }}>
        <h2 style={{ color: '#d32f2f', marginBottom: '1rem' }}>❌ Validation Issues: JSON Syntax</h2>
        <p style={{ marginBottom: '1rem', color: '#666' }}>
          This example demonstrates validation warnings when JSON syntax is used instead of Python dictionary syntax.
        </p>
        <CSVTable 
          csvContent={invalidSampleCSV}
          title="Chat Bot Workflow (With Validation Issues)"
          filename="chat-bot-workflow"
          showLineNumbers={true}
          validatePydantic={true}
          showValidation={true}
        />
      </div>
      
      <div style={{ marginBottom: '3rem' }}>
        <h2 style={{ color: '#1976d2', marginBottom: '1rem' }}>🚀 Advanced Workflow Example</h2>
        <p style={{ marginBottom: '1rem', color: '#666' }}>
          A complex workflow demonstrating multiple agent types, routing, and proper Python dictionary configurations.
        </p>
        <CSVTable 
          csvContent={advancedWorkflowCSV}
          title="Advanced Multi-Agent Workflow"
          filename="advanced-workflow"
          showLineNumbers={true}
          validatePydantic={true}
          showValidation={true}
        />
      </div>
      
      <div style={{ marginBottom: '3rem' }}>
        <h2 style={{ color: '#7b1fa2', marginBottom: '1rem' }}>📊 Non-AgentMap Data Example</h2>
        <p style={{ marginBottom: '1rem', color: '#666' }}>
          The component also works well with general CSV data, with validation disabled for non-AgentMap use cases.
        </p>
        <CSVTable 
          csvContent={projectTasksCSV}
          title="Project Task List"
          filename="project-tasks"
          maxRows={10}
          validatePydantic={false}
          showValidation={false}
        />
      </div>
      
      <div style={{ marginBottom: '3rem' }}>
        <h2 style={{ color: '#ef6c00', marginBottom: '1rem' }}>📝 Simple Example</h2>
        <p style={{ marginBottom: '1rem', color: '#666' }}>
          Basic usage with minimal configuration.
        </p>
        <CSVTable 
          csvContent="Name,Age,City\nJohn,25,New York\nJane,30,San Francisco\nBob,35,Chicago"
          filename="simple-data"
          validatePydantic={false}
        />
      </div>
      
      <div style={{ 
        background: '#f5f5f5', 
        padding: '1.5rem', 
        borderRadius: '8px', 
        border: '1px solid #ddd',
        marginTop: '2rem'
      }}>
        <h3 style={{ marginTop: 0, color: '#1976d2' }}>💡 Key Features</h3>
        <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
          <li><strong>Pydantic Validation:</strong> Automatically detects and warns about JSON syntax that should be Python dictionaries</li>
          <li><strong>Enhanced Parsing:</strong> Better handling of nested braces and complex CSV structures</li>
          <li><strong>Visual Feedback:</strong> Clear validation messages with error, warning, and info categories</li>
          <li><strong>Copy & Download:</strong> Easy export functionality with proper filenames</li>
          <li><strong>Responsive Design:</strong> Works well on desktop and mobile devices</li>
          <li><strong>Line Numbers:</strong> Optional line numbering for debugging</li>
          <li><strong>Performance:</strong> Handles large CSV files with row limiting</li>
        </ul>
      </div>
    </div>
  );
};

export default CSVTableExample;
