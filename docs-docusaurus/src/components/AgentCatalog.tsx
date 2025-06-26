import React, { useState, useMemo } from 'react';
import styles from './AgentCatalog.module.css';

interface Agent {
  name: string;
  type: string;
  aliases?: string[];
  category: 'Core' | 'LLM' | 'Storage' | 'File' | 'Specialized';
  description: string;
  inputFields: string;
  outputField: string;
  promptUsage: string;
  csvExample: string;
  contextOptions?: string[];
  protocols?: string[];
  businessServices?: string[];
}

const AGENTS: Agent[] = [
  // Core Agents
  {
    name: 'DefaultAgent',
    type: 'default',
    category: 'Core',
    description: 'The simplest agent that logs its execution and returns a message with the prompt.',
    inputFields: 'Any (unused)',
    outputField: 'Returns a message including the agent\'s prompt',
    promptUsage: 'Included in output message',
    csvExample: 'TestGraph,Start,,Basic node,default,Next,,input,output,Hello World',
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  },
  {
    name: 'EchoAgent',
    type: 'echo',
    category: 'Core',
    description: 'Simply returns the input data unchanged.',
    inputFields: 'Returns the first input field it finds',
    outputField: 'The input data unchanged',
    promptUsage: 'Ignored',
    csvExample: 'TestGraph,Echo,,Echo node,echo,Next,,message,response,',
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  },
  {
    name: 'BranchingAgent',
    type: 'branching',
    category: 'Core',
    description: 'Used for testing conditional routing. Checks for success/failure indicators in inputs.',
    inputFields: 'Looks for success, should_succeed, succeed, or branch fields',
    outputField: 'Message describing the branching decision',
    promptUsage: 'Included in output message',
    csvExample: 'TestGraph,Branch,,Decision point,branching,SuccessPath,FailurePath,input,decision,Make a choice',
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  },
  {
    name: 'SuccessAgent',
    type: 'success',
    category: 'Core',
    description: 'Testing agent that always succeeds.',
    inputFields: 'Any (unused)',
    outputField: 'Confirmation message',
    promptUsage: 'Included in output message',
    csvExample: 'TestGraph,AlwaysSucceed,,Success node,success,Next,,input,result,I always succeed',
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  },
  {
    name: 'FailureAgent',
    type: 'failure',
    category: 'Core',
    description: 'Testing agent that always fails.',
    inputFields: 'Any (unused)',
    outputField: 'Confirmation message',
    promptUsage: 'Included in output message',
    csvExample: 'TestGraph,AlwaysFail,,Failure node,failure,Next,,input,result,I always fail',
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  },
  {
    name: 'InputAgent',
    type: 'input',
    category: 'Core',
    description: 'Prompts for user input during execution.',
    inputFields: 'Any (unused)',
    outputField: 'User\'s input response',
    promptUsage: 'Shown to user as input prompt',
    csvExample: 'TestGraph,GetInput,,User input node,input,Process,,message,user_input,Please enter your name:',
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  },
  
  // LLM Agents
  {
    name: 'LLMAgent',
    type: 'llm',
    category: 'LLM',
    description: 'Uses configurable LLM providers for text generation with intelligent routing support.',
    inputFields: 'Used to format the prompt template',
    outputField: 'LLM response',
    promptUsage: 'Used as prompt template or system message',
    csvExample: 'QAGraph,Question,{"routing_enabled": true, "task_type": "analysis"},Ask a question,llm,Answer,,question,response,Answer this question: {question}',
    contextOptions: ['routing_enabled', 'task_type', 'provider', 'model', 'temperature', 'memory_key'],
    protocols: ['LLMCapableAgent', 'PromptCapableAgent'],
    businessServices: ['LLMService']
  },
  {
    name: 'OpenAIAgent',
    type: 'openai',
    aliases: ['gpt', 'chatgpt'],
    category: 'LLM',
    description: 'Backward compatibility wrapper for LLMAgent with OpenAI provider.',
    inputFields: 'Used to format the prompt template',
    outputField: 'LLM response',
    promptUsage: 'Used as prompt template',
    csvExample: 'QAGraph,Question,{"model": "gpt-4", "temperature": 0.7},Ask a question,openai,Answer,,question,response,Answer this question: {question}',
    contextOptions: ['model', 'temperature', 'max_tokens'],
    protocols: ['LLMCapableAgent'],
    businessServices: ['LLMService (OpenAI)']
  },
  {
    name: 'AnthropicAgent',
    type: 'claude',
    aliases: ['claude'],
    category: 'LLM',
    description: 'Backward compatibility wrapper for LLMAgent with Anthropic provider.',
    inputFields: 'Used to format the prompt template',
    outputField: 'LLM response',
    promptUsage: 'Used as prompt template',
    csvExample: 'QAGraph,Summarize,{"model": "claude-3-sonnet-20240229"},Summarize text,claude,Next,,text,summary,Summarize this text in 3 bullet points: {text}',
    contextOptions: ['model', 'temperature', 'max_tokens'],
    protocols: ['LLMCapableAgent'],
    businessServices: ['LLMService (Anthropic)']
  },
  {
    name: 'GoogleAgent',
    type: 'gemini',
    aliases: ['gemini'],
    category: 'LLM',
    description: 'Backward compatibility wrapper for LLMAgent with Google provider.',
    inputFields: 'Used to format the prompt template',
    outputField: 'LLM response',
    promptUsage: 'Used as prompt template',
    csvExample: 'QAGraph,Generate,{"model": "gemini-1.0-pro"},Generate content,gemini,Next,,prompt,content,Generate content based on: {prompt}',
    contextOptions: ['model', 'temperature', 'max_tokens'],
    protocols: ['LLMCapableAgent'],
    businessServices: ['LLMService (Google)']
  },
  
  // Storage Agents
  {
    name: 'CSVReaderAgent',
    type: 'csv_reader',
    category: 'Storage',
    description: 'Read from CSV files using the unified storage system.',
    inputFields: 'Must contain collection (file path), optional document_id, query, path',
    outputField: 'CSV data',
    promptUsage: 'Optional CSV path override',
    csvExample: 'DataGraph,ReadCustomers,{"format": "records", "id_field": "customer_id"},Read customer data,csv_reader,Process,,collection,customers,data/customers.csv',
    contextOptions: ['format', 'id_field', 'encoding', 'delimiter'],
    protocols: ['StorageCapableAgent', 'CSVCapableAgent'],
    businessServices: ['StorageService']
  },
  {
    name: 'CSVWriterAgent',
    type: 'csv_writer',
    category: 'Storage',
    description: 'Write to CSV files using the unified storage system.',
    inputFields: 'Must contain data and collection (file path)',
    outputField: 'Operation result',
    promptUsage: 'Optional CSV path override',
    csvExample: 'DataGraph,WriteResults,{"format": "records", "mode": "write"},Write processed data,csv_writer,End,,data,result,data/output.csv',
    contextOptions: ['format', 'mode', 'encoding', 'delimiter'],
    protocols: ['StorageCapableAgent', 'CSVCapableAgent'],
    businessServices: ['StorageService']
  },
  {
    name: 'JSONDocumentReaderAgent',
    type: 'json_reader',
    category: 'Storage',
    description: 'Read from JSON files using the unified storage system.',
    inputFields: 'Must contain collection (file path), optional document_id, path',
    outputField: 'JSON data',
    promptUsage: 'Optional JSON path override',
    csvExample: 'ConfigGraph,ReadConfig,{"format": "dict", "encoding": "utf-8"},Read configuration,json_reader,Process,,collection,config,config/app.json',
    contextOptions: ['format', 'encoding'],
    protocols: ['StorageCapableAgent', 'JSONCapableAgent'],
    businessServices: ['StorageService']
  },
  {
    name: 'JSONDocumentWriterAgent',
    type: 'json_writer',
    category: 'Storage',
    description: 'Write to JSON files using the unified storage system.',
    inputFields: 'Must contain data and collection (file path)',
    outputField: 'Operation result',
    promptUsage: 'Optional JSON path override',
    csvExample: 'ConfigGraph,SaveState,{"format": "dict", "indent": 2},Save application state,json_writer,End,,state,result,data/state.json',
    contextOptions: ['format', 'indent', 'encoding'],
    protocols: ['StorageCapableAgent', 'JSONCapableAgent'],
    businessServices: ['StorageService']
  },
  {
    name: 'VectorReaderAgent',
    type: 'vector_reader',
    category: 'Storage',
    description: 'Work with vector databases for semantic search and document retrieval.',
    inputFields: 'query for similarity search',
    outputField: 'Retrieved documents',
    promptUsage: 'Optional configuration override',
    csvExample: 'VectorGraph,Search,{"similarity_threshold": 0.8, "max_results": 5},Search for similar documents,vector_reader,Process,,query,search_results,',
    contextOptions: ['provider', 'embedding_model', 'similarity_threshold', 'max_results'],
    protocols: ['StorageCapableAgent', 'VectorCapableAgent'],
    businessServices: ['StorageService']
  },
  {
    name: 'VectorWriterAgent',
    type: 'vector_writer',
    category: 'Storage',
    description: 'Work with vector databases for embedding and storing documents.',
    inputFields: 'document data',
    outputField: 'Operation status',
    promptUsage: 'Optional configuration override',
    csvExample: 'VectorGraph,LoadDocs,{"provider": "chroma", "embedding_model": "text-embedding-ada-002"},Load documents into vector store,vector_writer,Search,,documents,load_result,',
    contextOptions: ['provider', 'embedding_model', 'collection_name'],
    protocols: ['StorageCapableAgent', 'VectorCapableAgent'],
    businessServices: ['StorageService']
  },
  
  // File Agents
  {
    name: 'FileReaderAgent',
    type: 'file_reader',
    category: 'File',
    description: 'Reads and processes various document types with optional chunking and filtering.',
    inputFields: 'collection (file path), optional document_id, query, path, format',
    outputField: 'Document data with metadata',
    promptUsage: 'Not used',
    csvExample: 'DocGraph,ReadDocs,{"chunk_size": 1000, "chunk_overlap": 200, "should_split": true},Read documents,file_reader,Process,,collection,documents,',
    contextOptions: ['chunk_size', 'chunk_overlap', 'should_split', 'include_metadata'],
    protocols: ['StorageCapableAgent', 'FileCapableAgent'],
    businessServices: ['StorageService']
  },
  {
    name: 'FileWriterAgent',
    type: 'file_writer',
    category: 'File',
    description: 'Writes content to various text-based formats with different write modes.',
    inputFields: 'collection (file path), data (content), optional mode',
    outputField: 'Write operation result',
    promptUsage: 'Not used',
    csvExample: 'DocGraph,WriteFile,{"mode": "write", "encoding": "utf-8"},Write document,file_writer,Next,,data,result,path/to/output.txt',
    contextOptions: ['mode', 'encoding'],
    protocols: ['StorageCapableAgent', 'FileCapableAgent'],
    businessServices: ['StorageService']
  },
  
  // Specialized Agents
  {
    name: 'OrchestrationAgent',
    type: 'orchestrator',
    category: 'Specialized',
    description: 'Routes execution to one or more nodes based on context configuration.',
    inputFields: 'available_nodes and routing data',
    outputField: 'selected nodes',
    promptUsage: 'Not used',
    csvExample: 'WorkflowGraph,Router,{"nodes": "ProcessA|ProcessB|ProcessC"},Route to processors,orchestrator,Collect,Error,available_nodes|data,selected_nodes,',
    contextOptions: ['nodes'],
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  },
  {
    name: 'SummaryAgent',
    type: 'summary',
    category: 'Specialized',
    description: 'Combines multiple inputs into a structured summary.',
    inputFields: 'Multiple input fields to combine',
    outputField: 'Combined summary result',
    promptUsage: 'Not used',
    csvExample: 'DataGraph,Combine,{"format": "{key}: {value}\\n"},Combine results,summary,Next,Error,result_a|result_b|result_c,combined,',
    contextOptions: ['format', 'include_keys'],
    protocols: ['BaseAgent'],
    businessServices: ['None required']
  }
];

const CATEGORY_COLORS = {
  Core: '#4CAF50',      // Green
  LLM: '#2196F3',       // Blue  
  Storage: '#FF9800',   // Orange
  File: '#9C27B0',      // Purple
  Specialized: '#607D8B' // Blue Grey
};

const CATEGORY_ICONS = {
  Core: '⚙️',
  LLM: '🧠',
  Storage: '💾',
  File: '📁',
  Specialized: '🔧'
};

export default function AgentCatalog(): JSX.Element {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [copiedExample, setCopiedExample] = useState<string | null>(null);

  const categories = ['All', ...Object.keys(CATEGORY_COLORS)];

  const filteredAgents = useMemo(() => {
    return AGENTS.filter(agent => {
      const matchesSearch = 
        agent.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        agent.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
        agent.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (agent.aliases && agent.aliases.some(alias => 
          alias.toLowerCase().includes(searchTerm.toLowerCase())
        ));
      
      const matchesCategory = 
        selectedCategory === 'All' || agent.category === selectedCategory;
      
      return matchesSearch && matchesCategory;
    });
  }, [searchTerm, selectedCategory]);

  const copyToClipboard = async (text: string, agentName: string) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
          document.execCommand('copy');
        } catch (fallbackErr) {
          console.error('Fallback copy failed: ', fallbackErr);
        }
        document.body.removeChild(textArea);
      }
      setCopiedExample(agentName);
      setTimeout(() => setCopiedExample(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
      // Still show feedback even if copy failed
      setCopiedExample(agentName);
      setTimeout(() => setCopiedExample(null), 1000);
    }
  };

  return (
    <div className={styles.agentCatalog}>
      <div className={styles.header}>
        <h1>AgentMap Agent Catalog</h1>
        <p>Browse all available agent types with examples and configurations</p>
      </div>

      <div className={styles.controls}>
        <div className={styles.searchContainer}>
          <input
            type="text"
            placeholder="Search agents by name, type, or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={styles.searchInput}
          />
        </div>

        <div className={styles.categoryFilters}>
          {categories.map(category => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={`${styles.categoryButton} ${
                selectedCategory === category ? styles.active : ''
              }`}
              style={{
                backgroundColor: selectedCategory === category 
                  ? (category !== 'All' ? CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] : '#333')
                  : 'transparent',
                borderColor: category !== 'All' 
                  ? CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] 
                  : '#333'
              }}
            >
              {category !== 'All' && CATEGORY_ICONS[category as keyof typeof CATEGORY_ICONS]} {category}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.agentGrid}>
        {filteredAgents.map((agent) => (
          <div key={agent.name} className={styles.agentCard}>
            <div 
              className={styles.categoryBadge}
              style={{ backgroundColor: CATEGORY_COLORS[agent.category] }}
            >
              {CATEGORY_ICONS[agent.category]} {agent.category}
            </div>

            <div className={styles.agentHeader}>
              <h3>{agent.name}</h3>
              <div className={styles.agentType}>
                <code>{agent.type}</code>
                {agent.aliases && agent.aliases.length > 0 && (
                  <span className={styles.aliases}>
                    (aliases: {agent.aliases.map(alias => <code key={alias}>{alias}</code>)})
                  </span>
                )}
              </div>
            </div>

            <p className={styles.description}>{agent.description}</p>

            <div className={styles.agentDetails}>
              <div className={styles.detailRow}>
                <strong>Input Fields:</strong> <span>{agent.inputFields}</span>
              </div>
              <div className={styles.detailRow}>
                <strong>Output Field:</strong> <span>{agent.outputField}</span>
              </div>
              <div className={styles.detailRow}>
                <strong>Prompt Usage:</strong> <span>{agent.promptUsage}</span>
              </div>
              {agent.protocols && agent.protocols.length > 0 && (
                <div className={styles.detailRow}>
                  <strong>Protocols:</strong> 
                  <span className={styles.tagList}>
                    {agent.protocols.map(protocol => (
                      <span key={protocol} className={styles.tag}>{protocol}</span>
                    ))}
                  </span>
                </div>
              )}
              {agent.businessServices && agent.businessServices.length > 0 && (
                <div className={styles.detailRow}>
                  <strong>Services:</strong> 
                  <span className={styles.tagList}>
                    {agent.businessServices.map(service => (
                      <span key={service} className={styles.tag}>{service}</span>
                    ))}
                  </span>
                </div>
              )}
              {agent.contextOptions && agent.contextOptions.length > 0 && (
                <div className={styles.detailRow}>
                  <strong>Context Options:</strong> 
                  <span className={styles.tagList}>
                    {agent.contextOptions.map(option => (
                      <span key={option} className={styles.tag}>{option}</span>
                    ))}
                  </span>
                </div>
              )}
            </div>

            <div className={styles.csvExample}>
              <div className={styles.exampleHeader}>
                <strong>CSV Example:</strong>
                <button
                  onClick={() => copyToClipboard(agent.csvExample, agent.name)}
                  className={styles.copyButton}
                  title="Copy CSV example"
                >
                  {copiedExample === agent.name ? '✓ Copied!' : '📋 Copy'}
                </button>
              </div>
              <pre className={styles.csvCode}>{agent.csvExample}</pre>
            </div>
          </div>
        ))}
      </div>

      {filteredAgents.length === 0 && (
        <div className={styles.noResults}>
          <p>No agents found matching your search criteria.</p>
          <p>Try adjusting your search term or category filter.</p>
        </div>
      )}

      <div className={styles.footer}>
        <p>
          Found {filteredAgents.length} of {AGENTS.length} agents. 
          Need help? Check out the{' '}
          <a href="/docs/reference/agent-types">detailed agent documentation</a> or{' '}
          <a href="/docs/getting-started/quick-start">quick start guide</a>.
        </p>
      </div>
    </div>
  );
}
