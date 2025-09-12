---
sidebar_position: 4
title: Agent Catalog
description: Interactive catalog of all available AgentMap agent types
---

import AgentCatalog from '@site/src/components/AgentCatalog';

# Agent Catalog

Explore all available AgentMap agent types in this interactive catalog. Use the search and filters to find the perfect agent for your workflow needs.

<AgentCatalog />

## Quick Reference

### Agent Categories

- **🏗️ Core Agents** - Basic building blocks for workflow control and data flow
- **🧠 LLM Agents** - AI-powered agents using language models from various providers  
- **💾 Storage Agents** - Data persistence and retrieval from various storage systems
- **📁 File Agents** - File operations for reading and writing documents
- **☁️ Cloud Storage** - Azure, AWS, GCP, and local file system connectors
- **🔍 Vector Search** - Semantic search with embedding models (Chroma, FAISS)
- **🔧 Specialized Agents** - Advanced workflow orchestration and data processing

### Usage Tips

1. **Copy CSV Examples** - Click the copy button on any agent card to get ready-to-use CSV configuration
2. **Search by Capability** - Use keywords like "LLM", "storage", "file", or "routing" to find relevant agents
3. **Filter by Category** - Use category buttons to narrow down to specific agent types
4. **Check Context Options** - Review the context configuration options to understand customization possibilities

### Next Steps

- **[Quick Start Guide](/docs/getting-started)** - Build your first workflow using these agents
- **[CSV Schema Reference](reference/csv-schema)** - Learn the complete CSV format for defining workflows
- **[CLI Commands](deployment/cli-commands)** - Use scaffolding to generate custom agent templates
- **[Agent Development](../tutorials/building-custom-agents)** - Create your own custom agents

## Common Agent Combinations

### Data Processing Pipeline
```csv
Pipeline,ReadData,,Read input data,csv_reader,ProcessData,Error,collection,raw_data,data/input.csv
Pipeline,ProcessData,,Transform the data,llm,WriteData,Error,raw_data,processed_data,Clean and format this data: {raw_data}
Pipeline,WriteData,,Save processed data,csv_writer,End,Error,processed_data,result,data/output.csv
```

### Interactive Chatbot with Memory
```csv
ChatBot,GetInput,,Get user question,input,ProcessQuestion,End,,question,Enter your question:
ChatBot,ProcessQuestion,{"memory_key":"conversation","max_memory_messages":10},Process with AI,llm,GetInput,Error,question|conversation,response,You are a helpful assistant. Answer: {question}
```

### Document Analysis with Summarization
```csv
Analysis,LoadDoc,,Load document,file_reader,AnalyzeDoc,Error,collection,document,
Analysis,AnalyzeDoc,,Analyze content,llm,CreateSummary,Error,document,analysis,Analyze and extract key insights: {document}
Analysis,CreateSummary,{"llm":"anthropic"},Create executive summary,summary,SaveResults,Error,analysis|document,executive_summary,Create a concise executive summary of the analysis
Analysis,SaveResults,,Save results,json_writer,End,Error,executive_summary,result,results/analysis.json
```

### Intelligent Request Routing
```csv
Router,GetUserInput,,Get user request,input,RouteRequest,End,message,user_input,What can I help you with?
Router,RouteRequest,{"nodes":"WeatherService|NewsService|CalculatorService"},Route to appropriate service,orchestrator,DefaultHandler,Error,available_nodes|user_input,selected_node,Route the user request to the appropriate service
Router,WeatherService,,Get weather information,default,FormatResponse,Error,user_input,weather_data,Getting weather information
Router,NewsService,,Get latest news,default,FormatResponse,Error,user_input,news_data,Getting latest news
Router,CalculatorService,,Perform calculations,default,FormatResponse,Error,user_input,calc_result,Performing calculation
Router,FormatResponse,{"format":"{key}: {value}"},Format final response,summary,End,Error,weather_data|news_data|calc_result,formatted_response,
Router,DefaultHandler,,Handle unrecognized requests,default,End,Error,user_input,error_response,I don't understand that request
Router,End,,Complete the workflow,echo,,,formatted_response|error_response,final_output,
```

### Parallel Processing with Consolidation
```csv
Parallel,SplitWork,,Split work into parallel tasks,default,TaskA|TaskB|TaskC,Error,input_data,split_data,
Parallel,TaskA,,Process part A,default,Consolidate,Error,split_data,result_a,Processing part A
Parallel,TaskB,,Process part B,default,Consolidate,Error,split_data,result_b,Processing part B
Parallel,TaskC,,Process part C,default,Consolidate,Error,split_data,result_c,Processing part C
Parallel,Consolidate,{"separator":"\n\n---\n\n"},Combine all results,summary,End,Error,result_a|result_b|result_c,final_result,
Parallel,End,,Output final results,echo,,,final_result,output,
```

### Multi-Step LLM Analysis with Context
```csv
Analysis,LoadData,,Load source data,file_reader,ExtractEntities,Error,collection,raw_data,
Analysis,ExtractEntities,{"task_type":"analysis","routing_enabled":true},Extract key entities,llm,AnalyzeSentiment,Error,raw_data,entities,Extract all important entities and concepts from: {raw_data}
Analysis,AnalyzeSentiment,{"provider":"anthropic"},Analyze sentiment,llm,GenerateInsights,Error,raw_data|entities,sentiment,Analyze the sentiment of this content: {raw_data}
Analysis,GenerateInsights,{"temperature":0.3},Generate insights,llm,CreateReport,Error,entities|sentiment|raw_data,insights,Based on entities {entities} and sentiment {sentiment}, generate key insights about: {raw_data}
Analysis,CreateReport,{"llm":"anthropic"},Create final report,summary,SaveReport,Error,entities|sentiment|insights,executive_report,Create a comprehensive executive report combining all analysis
Analysis,SaveReport,,Save final report,file_writer,End,Error,executive_report,saved_report,reports/analysis_report Analysis,End,,Analysis complete,echo,,,saved_report,completion_status,
```

### Cloud Storage Integration with Vector Search
```csv
CloudSearch,LoadFromS3,{"provider":"aws","bucket":"company-data"},Fetch documents from S3,blob_reader,ProcessDocuments,Error,path,documents,reports/quarterly/
CloudSearch,ProcessDocuments,{"chunk_size":1000,"should_split":true},Process documents,file_reader,IndexInVector,Error,documents,processed_docs,
CloudSearch,IndexInVector,{"provider":"chroma","embedding_model":"text-embedding-ada-002"},Index in vector database,vector_writer,SearchReady,Error,processed_docs,index_status,
CloudSearch,SearchReady,,Ready to search,echo,GetQuery,End,index_status,ready_message,Vector search system is ready for queries
CloudSearch,GetQuery,,Get search query,input,PerformSearch,End,message,search_query,Enter your search query:
CloudSearch,PerformSearch,{"provider":"chroma","similarity_threshold":0.75,"max_results":5},Search for similar content,vector_reader,AnalyzeResults,Error,search_query,search_results,
CloudSearch,AnalyzeResults,{"routing_enabled":true,"task_type":"analysis"},Analyze search results,llm,DisplayResults,Error,search_query|search_results,analysis,Analyze these search results for the query: {search_query}
CloudSearch,DisplayResults,,Show results,echo,GetQuery,End,analysis,final_output,
```

### Interactive Schema Validator

Want to validate your CSV before running it? Try this interactive validator workflow:

```csv
Validator,GetCSV,,Get CSV to validate,input,ValidateSchema,End,csv_content,Enter your CSV content:
Validator,ValidateSchema,,Validate CSV structure,default,ShowResults,Error,csv_content,validation_result,Validating CSV schema and structure
Validator,ShowResults,,Display validation results,echo,GetCSV,End,validation_result,results,
```

These examples demonstrate the power and flexibility of AgentMap's agent system. Each workflow shows different patterns:

- **Linear Processing**: Simple step-by-step data transformation
- **Parallel Processing**: Multiple tasks running simultaneously with consolidation
- **Interactive Flows**: User input driving workflow decisions
- **Intelligent Routing**: AI-powered decision making for request handling
- **Memory Management**: Maintaining context across interactions
- **Multi-Modal Analysis**: Combining different types of AI analysis
- **Cloud Integration**: Connecting to cloud storage and vector databases

## Advanced Configuration Examples

### Vector Search with Document Processing
```csv
VectorSearch,LoadDocs,{"chunk_size":1000,"should_split":true},Load documents for indexing,file_reader,IndexDocs,Error,collection,documents,
VectorSearch,IndexDocs,{"provider":"chroma","embedding_model":"text-embedding-ada-002"},Index documents in vector store,vector_writer,SearchReady,Error,documents,index_result,
VectorSearch,SearchReady,,Ready for search queries,echo,ProcessQuery,End,index_result,ready_message,Vector search system ready
VectorSearch,ProcessQuery,,Get search query,input,PerformSearch,ProcessQuery,message,search_query,Enter your search query:
VectorSearch,PerformSearch,{"similarity_threshold":0.8,"max_results":5},Search for similar content,vector_reader,AnalyzeResults,Error,search_query,search_results,
VectorSearch,AnalyzeResults,{"routing_enabled":true,"task_type":"analysis"},Analyze search results,llm,DisplayResults,Error,search_query|search_results,analysis,Analyze these search results for query "{search_query}": {search_results}
VectorSearch,DisplayResults,,Display final results,echo,ProcessQuery,End,analysis,final_output,
```

### Multi-Provider LLM Comparison
```csv
Comparison,GetPrompt,,Get prompt to compare,input,RunOpenAI|RunAnthropic|RunGoogle,End,message,prompt,Enter prompt to compare across providers:
Comparison,RunOpenAI,{"provider":"openai","model":"gpt-4"},Run with OpenAI,llm,CollectResults,Error,prompt,openai_result,{prompt}
Comparison,RunAnthropic,{"provider":"anthropic","model":"claude-3-5-sonnet-20241022"},Run with Anthropic,llm,CollectResults,Error,prompt,anthropic_result,{prompt}
Comparison,RunGoogle,{"provider":"google","model":"gemini-1.0-pro"},Run with Google,llm,CollectResults,Error,prompt,google_result,{prompt}
Comparison,CollectResults,{"format":"**{key}**:\n{value}\n\n"},Collect all results,summary,AnalyzeComparison,Error,openai_result|anthropic_result|google_result,all_results,
Comparison,AnalyzeComparison,{"routing_enabled":true},Analyze differences,llm,DisplayComparison,Error,prompt|all_results,comparison_analysis,Compare and analyze the differences between these LLM responses to "{prompt}": {all_results}
Comparison,DisplayComparison,,Show final comparison,echo,GetPrompt,End,comparison_analysis,final_comparison,
```

### Cross-Cloud Storage Processing Workflow
```csv
CloudSync,GetSource,,Select source storage,input,PrepareSync,End,message,source_provider,Enter source cloud provider (aws, azure, gcp, local):
CloudSync,PrepareSync,,{"nodes":"AWSReader|AzureReader|GCPReader|LocalReader"},Route to source reader,orchestrator,GetDestination,Error,available_nodes|source_provider,selected_reader,Route to the appropriate storage reader
CloudSync,AWSReader,{"provider":"aws","bucket":"source-bucket"},Read from AWS S3,blob_reader,GetDestination,Error,path,source_data,data/to-sync/
CloudSync,AzureReader,{"provider":"azure","container":"source-container"},Read from Azure,blob_reader,GetDestination,Error,path,source_data,data/to-sync/
CloudSync,GCPReader,{"provider":"gcp","bucket":"source-bucket"},Read from GCP,blob_reader,GetDestination,Error,path,source_data,data/to-sync/
CloudSync,LocalReader,{"provider":"local"},Read from local filesystem,blob_reader,GetDestination,Error,path,source_data,data/to-sync/
CloudSync,GetDestination,,Select destination storage,input,RouteDestination,End,message,destination_provider,Enter destination cloud provider (aws, azure, gcp, local):
CloudSync,RouteDestination,,{"nodes":"AWSWriter|AzureWriter|GCPWriter|LocalWriter"},Route to destination writer,orchestrator,SyncComplete,Error,available_nodes|destination_provider,selected_writer,Route to the appropriate storage writer
CloudSync,AWSWriter,{"provider":"aws","bucket":"destination-bucket"},Write to AWS S3,blob_writer,SyncComplete,Error,source_data,sync_result,data/synced/
CloudSync,AzureWriter,{"provider":"azure","container":"destination-container"},Write to Azure,blob_writer,SyncComplete,Error,source_data,sync_result,data/synced/
CloudSync,GCPWriter,{"provider":"gcp","bucket":"destination-bucket"},Write to GCP,blob_writer,SyncComplete,Error,source_data,sync_result,data/synced/
CloudSync,LocalWriter,{"provider":"local"},Write to local filesystem,blob_writer,SyncComplete,Error,source_data,sync_result,data/synced/
CloudSync,SyncComplete,,Sync complete,echo,End,End,sync_result,final_status,
CloudSync,End,,End workflow,echo,,,final_status,result,
```

### Advanced Vector Database Configuration
```csv
VectorConfig,ChooseProvider,,Select vector database provider,input,RouteProvider,End,message,provider_choice,Choose vector database provider (chroma or faiss):
VectorConfig,RouteProvider,,{"nodes":"ConfigureChroma|ConfigureFAISS"},Route to configuration,orchestrator,End,Error,available_nodes|provider_choice,selected_config,Route to the appropriate vector configuration
VectorConfig,ConfigureChroma,,{"provider":"chroma","embedding_model":"text-embedding-ada-002","persist_directory":"./chroma_db","collection_name":"semantic_search"},Configure Chroma,vector_writer,TestSearch,Error,documents,setup_result,
VectorConfig,ConfigureFAISS,,{"provider":"faiss","embedding_model":"text-embedding-ada-002","persist_directory":"./faiss_index","collection_name":"embeddings"},Configure FAISS,vector_writer,TestSearch,Error,documents,setup_result,
VectorConfig,TestSearch,,{"similarity_threshold":0.8,"max_results":10,"metadata_keys":["source","author","date"]},Test search configuration,vector_reader,End,Error,query,search_results,
```
