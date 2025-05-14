# AgentMap Example Workflows

This document provides examples of different workflow patterns using AgentMap's CSV format.

## Simple Linear Workflow

A basic workflow where nodes execute in sequence:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
LinearFlow,Start,,Starting node,Echo,Process,,"input",initial_data,
LinearFlow,Process,,Processing node,Default,,,"initial_data",processed_data,Processing: {initial_data}
LinearFlow,End,,Final node,Echo,,,"processed_data",final_output,
```

This workflow:
1. Echoes the input into `initial_data`
2. Processes the data and stores in `processed_data`
3. Echoes the processed data as the final output

## Branching Workflow with Error Handling

A workflow with conditional branching based on success/failure:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
BranchFlow,Start,,Starting node,Echo,Validate,,"input",initial_data,
BranchFlow,Validate,,Validate input data,Branching,Process,ErrorHandler,"initial_data",validation_result,Check if valid
BranchFlow,Process,,Process valid data,Default,End,ErrorHandler,"initial_data",processed_data,Processing: {initial_data}
BranchFlow,End,,Completion node,Echo,,,"processed_data",final_output,
BranchFlow,ErrorHandler,,Handle errors,Echo,End,,"initial_data",error_message,Error occurred
```

This workflow:
1. Echoes the input
2. Validates the data and branches based on result
3. On success, processes the data
4. On failure, goes to error handler
5. Both paths eventually reach the End node

## LLM Chain with Memory

A conversational workflow that maintains memory between interactions:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatFlow,UserInput,,{"memory":{"type":"buffer","memory_key":"chat_memory"}},Input,Process,ErrorHandler,"",user_message,Enter your message:
ChatFlow,Process,,Process user input,Echo,Respond,ErrorHandler,"user_message|chat_memory",processed_input,
ChatFlow,Respond,,Generate response,OpenAI,Format,ErrorHandler,"processed_input|chat_memory",ai_response,"You are a helpful assistant. User: {processed_input}"
ChatFlow,Format,,Format the response,Default,UserInput,ErrorHandler,"ai_response|chat_memory",formatted_response,"Assistant: {ai_response}"
ChatFlow,ErrorHandler,,Handle errors,Echo,UserInput,,"error",error_message,Error: {error}
```

This workflow:
1. Gets user input
2. Processes the input
3. Generates a response with an LLM, preserving conversation memory
4. Formats the response
5. Returns to user input for the next interaction

## Document Processing Workflow with File Agents

A workflow for processing documents:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocFlow,ReadFile,,"{'should_split': true, 'chunk_size': 1000}",file_reader,Summarize,ErrorHandler,"collection",documents,path/to/document.pdf
DocFlow,Summarize,,Generate summary,openai,SaveSummary,ErrorHandler,"documents",summary,"prompt:document_summary"
DocFlow,SaveSummary,,Save the summary,file_writer,End,ErrorHandler,"summary",write_result,output/summary.md
DocFlow,End,,Workflow complete,Echo,,,"write_result",final_message,"Summary saved successfully"
DocFlow,ErrorHandler,,Handle processing errors,Echo,End,,"error",error_message,"Error processing document: {error}"
```

This workflow:
1. Reads a PDF file and splits it into chunks
2. Summarizes the documents using OpenAI with a prompt from the registry
3. Saves the summary to a Markdown file
4. Reports completion or handles errors

## Data Processing Pipeline

A workflow for processing and analyzing data:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataFlow,LoadData,,Load data from CSV,CSVReader,Validate,ErrorHandler,"collection",data_raw,
DataFlow,Validate,,Validate data structure,Branching,Transform,ErrorHandler,"data_raw",validation_result,
DataFlow,Transform,,Transform data,Default,Analyze,ErrorHandler,"data_raw",data_transformed,"Transform raw data"
DataFlow,Analyze,,Analyze transformed data,OpenAI,SaveResults,ErrorHandler,"data_transformed",analysis_results,"Analyze this data and provide insights: {data_transformed}"
DataFlow,SaveResults,,Save results to CSV,CSVWriter,End,ErrorHandler,"analysis_results",save_result,
DataFlow,End,,Workflow complete,Echo,,,"save_result",final_message,"Analysis complete and saved"
DataFlow,ErrorHandler,,Handle processing errors,Echo,End,,"error",error_message,"Error during data processing: {error}"
```

This workflow:
1. Loads data from a CSV file
2. Validates the data structure
3. Transforms the data
4. Analyzes the data using an LLM
5. Saves the results to another CSV
6. Reports completion

## Integration with External Services

A workflow that interacts with external services:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
APIFlow,GetRequest,,Get API request details,Input,Prepare,ErrorHandler,"",request_input,"Enter search query:"
APIFlow,Prepare,,Prepare API request,Default,MakeRequest,ErrorHandler,"request_input",api_params,"Preparing API request"
APIFlow,MakeRequest,,Make API call,HttpClient,ProcessResponse,ErrorHandler,"api_params",api_response,"https://api.example.com/search"
APIFlow,ProcessResponse,,Process API response,Default,Format,ErrorHandler,"api_response",processed_data,"Extracting relevant data"
APIFlow,Format,,Format results for display,Default,End,ErrorHandler,"processed_data",formatted_results,"Formatting results"
APIFlow,End,,Show results,Echo,,,"formatted_results",display_output,
APIFlow,ErrorHandler,,Handle API errors,Echo,End,,"error",error_message,"API Error: {error}"
```

Note: This example assumes an HttpClient agent type, which would be a custom implementation.

## Parallel Processing with Join

A workflow demonstrating parallel processing (functional but not explicit in CSV):

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ParallelFlow,Start,,Start the workflow,Echo,Split,,"input",initial_data,
ParallelFlow,Split,,Split into parallel tasks,func:split_tasks,,,initial_data,tasks,"Split the tasks"
ParallelFlow,ProcessA,,Process first branch,Default,Join,ErrorHandler,"tasks.a",result_a,"Processing branch A"
ParallelFlow,ProcessB,,Process second branch,Default,Join,ErrorHandler,"tasks.b",result_b,"Processing branch B"
ParallelFlow,ProcessC,,Process third branch,Default,Join,ErrorHandler,"tasks.c",result_c,"Processing branch C"
ParallelFlow,Join,,Join results,func:join_results,Summarize,ErrorHandler,"result_a|result_b|result_c",joined_results,"Join the results"
ParallelFlow,Summarize,,Summarize all results,Default,End,ErrorHandler,"joined_results",summary,"Summarize the results"
ParallelFlow,End,,Workflow complete,Echo,,,"summary",final_output,
ParallelFlow,ErrorHandler,,Handle processing errors,Echo,End,,"error",error_message,"Error during processing: {error}"
```

This workflow uses custom functions (`split_tasks` and `join_results`) to implement parallel processing and synchronization.


---

[↑ Back to Index](index.md) | [← Previous: State Management and Data Flow](state_management_and_data_flow.md) | [Next: AgentMap CLI Documentation →](agentmap_cli_documentation.md)