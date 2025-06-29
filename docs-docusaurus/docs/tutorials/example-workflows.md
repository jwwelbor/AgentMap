---
sidebar_position: 6
title: Example Workflows - Real-World Patterns & Templates
description: Comprehensive collection of AgentMap workflow patterns including linear flows, branching logic, error handling, LLM chains, document processing, and parallel execution examples.
keywords: [workflow examples, AgentMap patterns, CSV workflow templates, linear workflow, branching workflow, error handling, LLM chains, parallel processing, document processing, API integration]
image: /img/agentmap-hero.png
---

import CSVTable from '@site/src/components/CSVTable';

# Example Workflows - Real-World Patterns & Templates

## Overview

This comprehensive guide provides **ready-to-use workflow patterns** demonstrating key AgentMap concepts through practical examples. Each workflow illustrates different architectural patterns and can serve as templates for your projects.

**What You'll Learn:**
- ✅ **Linear Workflow Patterns** - Sequential processing chains
- ✅ **Branching & Conditional Logic** - Decision-based routing
- ✅ **Error Handling Strategies** - Robust failure management
- ✅ **LLM Integration Patterns** - AI-powered processing with memory
- ✅ **Document Processing Workflows** - File handling and analysis
- ✅ **Parallel Processing** - Concurrent execution patterns
- ✅ **External Service Integration** - API and data source connections

## 🎯 Pattern Categories

| Pattern Type | Complexity | Use Cases |
|--------------|------------|-----------|
| [Linear Workflow](#linear-workflow-pattern) | **Beginner** | Sequential processing, data transformation |
| [Branching Logic](#branching-workflow-with-error-handling) | **Beginner** | Conditional routing, validation flows |
| [LLM Chains](#llm-chain-with-memory) | **Intermediate** | Conversational AI, context-aware processing |
| [Document Processing](#document-processing-workflow) | **Intermediate** | File analysis, content extraction |
| [Data Pipelines](#data-processing-pipeline) | **Intermediate** | ETL operations, data analysis |
| [API Integration](#integration-with-external-services) | **Advanced** | Service orchestration, external data |
| [Parallel Execution](#parallel-processing-with-join) | **Advanced** | Concurrent processing, performance optimization |

---

## Linear Workflow Pattern {#linear-workflow-pattern}

**Use Case**: Sequential data processing where each step depends on the previous one.

**Pattern**: Start → Process → Transform → Output

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
LinearFlow,Start,,Starting node,echo,Process,,input,initial_data,,Capture initial input data
LinearFlow,Process,,Processing node,default,Transform,,initial_data,processed_data,Processing: {initial_data},Transform the input data
LinearFlow,Transform,,Transform processed data,default,End,,processed_data,final_data,Transforming: {processed_data},Apply final transformations
LinearFlow,End,,Final output node,echo,,,final_data,output,,Display final results`}
  title="Linear Workflow Pattern"
  filename="linear_workflow"
/>

**Real-World Applications**:
- Data transformation pipelines
- Content processing workflows
- Simple automation tasks
- Input validation and formatting

---

## Branching Workflow with Error Handling {#branching-workflow-with-error-handling}

**Use Case**: Conditional processing with robust error handling and recovery.

**Pattern**: Input → Validate → Branch (Success/Failure) → Process/Handle → Output

<CSVTable 
  csvContent={`GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
BranchFlow,Start,,Starting node,echo,Validate,,input,initial_data,,Capture and echo input
BranchFlow,Validate,,Validate input data,default,Process,ErrorHandler,initial_data,validation_result,Validating input: {initial_data},Check data validity and format
BranchFlow,Process,,Process valid data,default,End,ErrorHandler,initial_data,processed_data,Processing valid data: {initial_data},Transform validated data
BranchFlow,End,,Completion node,echo,,,processed_data,final_output,,Display successful results
BranchFlow,ErrorHandler,,Handle validation errors,echo,End,,initial_data,error_message,❌ Validation failed for: {initial_data},Provide error feedback to user`}
  title="Branching Workflow with Error Handling"
  filename="branching_workflow"
/>

**Key Features**:
- **Conditional Routing**: Success/failure paths based on validation
- **Error Recovery**: Graceful handling of invalid inputs
- **User Feedback**: Clear error messages for troubleshooting

**Real-World Applications**:
- Form validation workflows
- Data quality checks
- User input processing
- API request validation

---

## LLM Chain with Memory {#llm-chain-with-memory}

**Use Case**: Conversational AI that maintains context across multiple interactions.

**Pattern**: Input → Process → LLM (with memory) → Format → Loop

```csv title="chat_workflow.csv"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
ChatFlow,UserInput,,{"memory_key":"chat_memory","max_memory_messages":10},input,Process,ErrorHandler,"",user_message,💬 Enter your message:,Capture user input for conversation
ChatFlow,Process,,Process user input,echo,Respond,ErrorHandler,"user_message|chat_memory",processed_input,,Prepare input for LLM processing
ChatFlow,Respond,,{"provider": "openai", "model": "gpt-3.5-turbo", "temperature": 0.7},llm,Format,ErrorHandler,"processed_input|chat_memory",ai_response,"You are a helpful assistant with memory of our conversation. User: {processed_input}",Generate contextual AI response
ChatFlow,Format,,Format the response,default,UserInput,ErrorHandler,"ai_response|chat_memory",formatted_response,🤖 Assistant: {ai_response},Format response for display
ChatFlow,ErrorHandler,,Handle conversation errors,echo,UserInput,,"error",error_message,❌ Error in conversation: {error},Handle errors gracefully and continue
```

**Memory Configuration**:
- **`memory_key`**: Identifies the memory store
- **`max_memory_messages`**: Limits context size for performance
- **Context Preservation**: Maintains conversation history across turns

**Real-World Applications**:
- Customer support chatbots
- Interactive assistance systems
- Educational tutoring bots
- Content generation workflows

---

## Document Processing Workflow {#document-processing-workflow}

**Use Case**: Analyze documents and generate summaries using AI.

**Pattern**: Load → Validate → Process → Analyze → Save → Report

```csv title="document_processing.csv"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
DocFlow,ReadFile,,{"should_split": true, "chunk_size": 1000},file_reader,ValidateContent,ErrorHandler,"file_path",documents,,Load and split document into manageable chunks
DocFlow,ValidateContent,,Validate document structure,default,Summarize,ErrorHandler,"documents",validation_result,Validating document content and structure,Ensure document is processable
DocFlow,Summarize,,{"provider": "openai", "model": "gpt-3.5-turbo", "temperature": 0.3},llm,SaveSummary,ErrorHandler,"documents",summary,"Analyze and summarize the following document content: {documents}",Generate AI-powered document summary
DocFlow,SaveSummary,,Save the summary,file_writer,ReportComplete,ErrorHandler,"summary",write_result,outputs/summary.md,Save summary to markdown file
DocFlow,ReportComplete,,Report completion,echo,,,"write_result",completion_message,✅ Document analysis complete. Summary saved to: {write_result},Confirm successful processing
DocFlow,ErrorHandler,,Handle processing errors,echo,End,,"error",error_message,❌ Error processing document: {error},Provide detailed error information
DocFlow,End,,Workflow complete,echo,,,"completion_message|error_message",final_output,,Display final status
```

**Document Processing Features**:
- **Chunking**: Splits large documents for efficient processing
- **Validation**: Ensures document integrity before analysis
- **AI Analysis**: Uses LLM for intelligent content summarization
- **Output Management**: Saves results in structured format

**Supported File Types**:
- PDF documents
- Text files (.txt, .md)
- Word documents (.docx)
- CSV and structured data

**Real-World Applications**:
- Legal document analysis
- Research paper summarization
- Content audit workflows
- Knowledge base creation

---

## Data Processing Pipeline {#data-processing-pipeline}

**Use Case**: ETL operations with validation, transformation, and analysis.

**Pattern**: Load → Validate → Transform → Analyze → Save → Report

```csv title="data_pipeline.csv"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
DataFlow,LoadData,,Load CSV data,csv_reader,ValidateStructure,ErrorHandler,"file_path",raw_data,,Read CSV file and parse data structure
DataFlow,ValidateStructure,,Validate data integrity,default,Transform,ErrorHandler,"raw_data",validation_status,Checking data structure and quality: {raw_data},Verify data meets processing requirements
DataFlow,Transform,,Transform and clean data,default,Analyze,ErrorHandler,"raw_data",transformed_data,Transforming data: {raw_data},Apply cleaning and transformation rules
DataFlow,Analyze,,{"provider": "openai", "model": "gpt-3.5-turbo", "temperature": 0.2},llm,SaveResults,ErrorHandler,"transformed_data",analysis_insights,"Analyze this dataset and provide key insights, trends, and recommendations: {transformed_data}",Generate data analysis insights
DataFlow,SaveResults,,Save analysis results,csv_writer,ReportAnalysis,ErrorHandler,"analysis_insights|transformed_data",save_status,outputs/analysis_results.csv,Export processed data and insights
DataFlow,ReportAnalysis,,Generate analysis report,default,End,ErrorHandler,"analysis_insights|save_status",final_report,📊 Data analysis complete. Results: {analysis_insights},Create comprehensive analysis summary
DataFlow,ErrorHandler,,Handle data processing errors,echo,End,,"error",error_message,❌ Data processing error: {error},Provide specific error context
DataFlow,End,,Pipeline complete,echo,,,"final_report|error_message",output,,Display pipeline results
```

**Pipeline Capabilities**:
- **Data Validation**: Quality checks and structure verification
- **Transformation**: Cleaning, formatting, and enrichment
- **AI Analysis**: Intelligent pattern recognition and insights
- **Export Options**: Multiple output formats (CSV, JSON, reports)

**Real-World Applications**:
- Business intelligence workflows
- Data quality auditing
- Automated reporting pipelines
- Research data analysis

---

## Integration with External Services {#integration-with-external-services}

**Use Case**: Connect to APIs and external services with error handling.

**Pattern**: Input → Prepare → API Call → Process → Format → Output

```csv title="api_integration.csv"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
APIFlow,GetRequest,,Get user input,input,PrepareRequest,ErrorHandler,"",user_query,🔍 Enter your search query:,Capture user search request
APIFlow,PrepareRequest,,Prepare API parameters,default,MakeAPICall,ErrorHandler,"user_query",api_params,Preparing API request for: {user_query},Format request parameters
APIFlow,MakeAPICall,,{"timeout": 30, "retry_count": 3},custom:APIClientAgent,ProcessResponse,ErrorHandler,"api_params",api_response,,Make HTTP request to external service
APIFlow,ProcessResponse,,Process API response,default,FormatResults,ErrorHandler,"api_response",processed_data,Processing API response: {api_response},Extract and structure response data
APIFlow,FormatResults,,Format for display,default,End,ErrorHandler,"processed_data|user_query",formatted_output,📋 Results for "{user_query}": {processed_data},Create user-friendly output format
APIFlow,End,,Display results,echo,,,"formatted_output",final_output,,Present final results to user
APIFlow,ErrorHandler,,Handle API errors,echo,End,,"error",error_message,❌ API Error: {error},Provide helpful error context
```

**API Integration Features**:
- **Timeout Management**: Prevents hanging requests
- **Retry Logic**: Handles temporary service issues
- **Error Classification**: Different handling for different error types
- **Response Processing**: Structured data extraction

**Common Integration Patterns**:
- REST API consumption
- Authentication handling
- Rate limiting compliance
- Response caching strategies

---

## Parallel Processing with Join {#parallel-processing-with-join}

**Use Case**: Execute multiple operations concurrently and combine results.

**Pattern**: Split → Parallel Branches → Join → Summarize

```csv title="parallel_workflow.csv"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
ParallelFlow,Initialize,,Initialize workflow,echo,SplitTasks,ErrorHandler,"input",initial_data,,Prepare data for parallel processing
ParallelFlow,SplitTasks,,Split into parallel tasks,default,ProcessBranchA|ProcessBranchB|ProcessBranchC,ErrorHandler,"initial_data",task_data,Splitting work into parallel branches: {initial_data},Distribute work across branches
ParallelFlow,ProcessBranchA,,Process first branch,default,JoinResults,ErrorHandler,"task_data.branch_a",result_a,Processing branch A: {task_data.branch_a},Handle branch A operations
ParallelFlow,ProcessBranchB,,Process second branch,default,JoinResults,ErrorHandler,"task_data.branch_b",result_b,Processing branch B: {task_data.branch_b},Handle branch B operations  
ParallelFlow,ProcessBranchC,,Process third branch,default,JoinResults,ErrorHandler,"task_data.branch_c",result_c,Processing branch C: {task_data.branch_c},Handle branch C operations
ParallelFlow,JoinResults,,Combine all results,default,SummarizeResults,ErrorHandler,"result_a|result_b|result_c",combined_results,Joining results from all branches,Merge parallel processing results
ParallelFlow,SummarizeResults,,{"provider": "openai", "model": "gpt-3.5-turbo"},llm,End,ErrorHandler,"combined_results",final_summary,"Summarize and analyze these parallel processing results: {combined_results}",Create comprehensive summary
ParallelFlow,End,,Workflow complete,echo,,,"final_summary",output,,Display final combined results
ParallelFlow,ErrorHandler,,Handle processing errors,echo,End,,"error",error_message,❌ Parallel processing error: {error},Manage errors from any branch
```

**Parallel Processing Benefits**:
- **Performance**: Concurrent execution reduces total time
- **Scalability**: Distribute work across multiple resources
- **Fault Isolation**: Errors in one branch don't stop others
- **Result Aggregation**: Intelligent combination of parallel outputs

**Real-World Applications**:
- Multi-source data collection
- Parallel document processing
- Distributed analysis tasks
- Performance-critical workflows

---

## Custom Function Integration {#custom-function-integration}

**Use Case**: Integrate custom Python functions for specialized processing.

**Pattern**: Input → Custom Function → Process → Output

```csv title="custom_function_workflow.csv"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
FunctionFlow,Start,,Initialize workflow,echo,ApplyFunction,ErrorHandler,"input",initial_data,,Prepare input for custom processing
FunctionFlow,ApplyFunction,,Apply custom function,func:custom_processor,ValidateOutput,ErrorHandler,"initial_data",processed_data,,Execute custom business logic
FunctionFlow,ValidateOutput,,Validate function output,default,FormatResults,ErrorHandler,"processed_data",validation_status,Validating processed data: {processed_data},Ensure output meets requirements
FunctionFlow,FormatResults,,Format final output,default,End,ErrorHandler,"processed_data",formatted_output,✅ Processing complete: {processed_data},Create user-friendly output
FunctionFlow,End,,Workflow complete,echo,,,"formatted_output",final_output,,Display final results
FunctionFlow,ErrorHandler,,Handle function errors,echo,End,,"error",error_message,❌ Custom function error: {error},Handle custom function failures
```

### Custom Function Implementation

Create your custom function in the `functions/` directory:

```python title="functions/custom_processor.py"
def custom_processor(inputs):
    """
    Custom processing function with business-specific logic.
    
    Args:
        inputs: Dictionary containing input values from workflow
        
    Returns:
        Processed data according to business requirements
    """
    # Extract input data
    data = inputs.get("initial_data", {})
    
    # Apply custom transformation logic
    if isinstance(data, str):
        # Example: Custom text processing
        processed = {
            "original": data,
            "length": len(data),
            "uppercase": data.upper(),
            "word_count": len(data.split()),
            "processed_at": datetime.now().isoformat()
        }
    elif isinstance(data, (list, dict)):
        # Example: Custom data structure processing
        processed = {
            "original_type": type(data).__name__,
            "size": len(data),
            "processed_data": transform_data_structure(data),
            "metadata": extract_metadata(data)
        }
    else:
        # Handle other data types
        processed = {
            "original": str(data),
            "type": type(data).__name__,
            "processed": True
        }
    
    return processed

def transform_data_structure(data):
    """Helper function for data transformation."""
    # Implement your custom transformation logic
    return data

def extract_metadata(data):
    """Helper function for metadata extraction."""
    # Implement your metadata extraction logic
    return {"processed": True}
```

**Custom Function Benefits**:
- **Business Logic**: Implement domain-specific processing
- **Reusability**: Share functions across multiple workflows
- **Performance**: Optimized Python code for intensive operations
- **Integration**: Seamless integration with AgentMap workflows

---

## 🛠️ Implementation Templates

### Quick Start Templates

Download ready-to-use workflow templates:

```bash
# Clone the complete examples repository
git clone https://github.com/jwwelbor/AgentMap-Examples.git
cd AgentMap-Examples/workflow-patterns

# Or download specific patterns
curl -O https://raw.githubusercontent.com/jwwelbor/AgentMap-Examples/main/patterns/linear_workflow.csv
curl -O https://raw.githubusercontent.com/jwwelbor/AgentMap-Examples/main/patterns/branching_workflow.csv
curl -O https://raw.githubusercontent.com/jwwelbor/AgentMap-Examples/main/patterns/chat_workflow.csv
```

### Testing Your Workflows

Use AgentMap's built-in testing capabilities:

```bash
# Validate workflow structure
agentmap validate --csv your_workflow.csv

# Test with sample data
agentmap run --graph YourFlow --csv your_workflow.csv --input test_data.json

# Debug workflow execution
agentmap inspect --csv your_workflow.csv --verbose
```

---

## 🎯 Pattern Selection Guide

### Choose Based on Your Use Case

| **If you need...** | **Use this pattern** | **Key benefits** |
|---------------------|----------------------|------------------|
| Simple data transformation | [Linear Workflow](#linear-workflow-pattern) | Easy to understand, reliable |
| Input validation & routing | [Branching Workflow](#branching-workflow-with-error-handling) | Robust error handling |
| Conversational AI | [LLM Chain with Memory](#llm-chain-with-memory) | Context preservation |
| Document analysis | [Document Processing](#document-processing-workflow) | File handling, AI analysis |
| Data analysis & ETL | [Data Pipeline](#data-processing-pipeline) | Comprehensive data operations |
| External service integration | [API Integration](#integration-with-external-services) | Reliable service communication |
| Performance optimization | [Parallel Processing](#parallel-processing-with-join) | Concurrent execution |
| Custom business logic | [Custom Functions](#custom-function-integration) | Specialized processing |

### Complexity Progression

1. **Start with**: Linear workflows for basic automation
2. **Add**: Branching logic for robust error handling  
3. **Integrate**: LLM capabilities for intelligent processing
4. **Scale**: Parallel processing for performance
5. **Customize**: Custom functions for specialized needs

---

## 🔗 Related Documentation

### 📖 **Core Concepts**
- **[Understanding Workflows](../guides/understanding-workflows)**: Learn workflow fundamentals
- **[CSV Schema Reference](../reference/csv-schema)**: Complete format specification
- **[State Management](../guides/state-management)**: Data flow between agents

### 🤖 **Agent Development**
- **[Agent Types Reference](../reference/agent-types)**: All available agent types
- **[Advanced Agent Types](../guides/advanced/advanced-agent-types)**: Custom agent development
- **[Agent Development Contract](../guides/advanced/agent-development-contract)**: Agent interface requirements

### 🏗️ **Advanced Patterns**
- **[Memory Management](../guides/advanced/memory-and-orchestration/memory-management)**: Persistent state patterns
- **[Orchestration Patterns](../guides/advanced/memory-and-orchestration/orchestration-patterns)**: Complex workflow coordination
- **[Service Injection](../guides/advanced/service-injection-patterns)**: Dependency injection patterns

### 🔧 **Tools & Development**
- **[CLI Commands](../reference/cli-commands)**: Complete command reference
- **[CLI Graph Inspector](../reference/cli-graph-inspector)**: Workflow debugging tools
- **[Interactive Playground](../playground)**: Test workflows in browser

### 📚 **Complete Tutorials**
- **[Weather Bot Tutorial](./weather-bot)**: API integration with custom agents
- **[Data Processing Pipeline](./data-processing-pipeline)**: ETL and analysis workflows
- **[Customer Support Bot](./customer-support-bot)**: Multi-agent coordination
- **[Document Analyzer](./document-analyzer)**: File processing with AI

---

## 💡 Best Practices & Tips

### **🎯 Workflow Design**
- **Start Simple**: Begin with linear patterns and add complexity incrementally
- **Error Handling**: Always include error paths and recovery mechanisms
- **State Management**: Use meaningful field names and document data flow
- **Modularity**: Design reusable components for common operations

### **⚡ Performance Optimization**
- **Parallel Processing**: Use concurrent patterns for independent operations
- **Memory Management**: Configure appropriate memory limits for LLM agents
- **Caching**: Implement caching for expensive operations
- **Timeouts**: Set reasonable timeouts for external service calls

### **🔒 Security & Reliability**
- **Input Validation**: Validate all external inputs before processing
- **API Security**: Use secure authentication for external services
- **Error Messages**: Provide helpful but not sensitive error information
- **Logging**: Implement comprehensive logging for debugging

### **📋 Maintenance**
- **Documentation**: Document business logic and decision points
- **Testing**: Create test cases for all workflow paths
- **Versioning**: Use version control for workflow evolution
- **Monitoring**: Track workflow performance and success rates

---

**🎉 Ready to Build?** These patterns provide a solid foundation for most AgentMap workflows. Start with the pattern that matches your use case, then customize and extend as needed!

### **🚀 Next Steps**
- **Explore [Interactive Playground](../playground)**: Test these patterns in your browser
- **Build [Weather Bot](./weather-bot)**: Complete tutorial with custom agents
- **Learn [Advanced Patterns](../guides/advanced/memory-and-orchestration/orchestration-patterns)**: Complex coordination techniques
