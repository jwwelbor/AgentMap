import React, { useState, useMemo } from 'react';
import styles from './CapabilityBrowser.module.css';

interface Capability {
  name: string;
  category: 'Core' | 'Storage' | 'Communication' | 'Advanced';
  description: string;
  serviceInterface: string;
  keyMethods: string[];
  implementationPattern: string;
  contextOptions: string[];
  usageExample: string;
  relatedProtocols?: string[];
}

const CAPABILITIES: Capability[] = [
  {
    name: 'LLMCapableAgent',
    category: 'Core',
    description: 'Enables agents to use language model services for text generation, conversation, and intelligent routing.',
    serviceInterface: 'LLMServiceProtocol',
    keyMethods: ['configure_llm_service()', 'call_llm()', 'get_available_providers()'],
    implementationPattern: `class MyLLMAgent(BaseAgent, LLMCapableAgent):
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        self._llm_service = llm_service
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        messages = [{"role": "user", "content": inputs.get("query", "")}]
        return self.llm_service.call_llm("anthropic", messages)`,
    contextOptions: ['provider', 'model', 'temperature', 'memory_key', 'routing_enabled'],
    usageExample: `# CSV Configuration
context = {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022", 
    "temperature": 0.3,
    "routing_enabled": True
}`,
    relatedProtocols: ['PromptCapableAgent']
  },
  {
    name: 'StorageCapableAgent',
    category: 'Storage',
    description: 'Enables agents to use storage services for data persistence across multiple formats and providers.',
    serviceInterface: 'StorageServiceProtocol',
    keyMethods: ['configure_storage_service()', 'read()', 'write()', 'list_collections()'],
    implementationPattern: `class MyStorageAgent(BaseAgent, StorageCapableAgent):
    def configure_storage_service(self, storage_service: StorageServiceProtocol) -> None:
        self._storage_service = storage_service
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        data = self.storage_service.read(inputs.get("collection"), format="records")
        processed = self.transform_data(data)
        return self.storage_service.write("output", processed)`,
    contextOptions: ['format', 'provider', 'encoding', 'mode', 'id_field'],
    usageExample: `# CSV Configuration
context = {
    "format": "records",
    "provider": "local",
    "encoding": "utf-8",
    "mode": "write"
}`,
    relatedProtocols: ['CSVCapableAgent', 'JSONCapableAgent', 'VectorCapableAgent']
  },
  {
    name: 'PromptCapableAgent',
    category: 'Core',
    description: 'Enables agents to use prompt manager services for template resolution and dynamic prompt generation.',
    serviceInterface: 'PromptManagerServiceProtocol',
    keyMethods: ['configure_prompt_service()', 'resolve_prompt()', 'register_template()'],
    implementationPattern: `class MyPromptAgent(BaseAgent, PromptCapableAgent):
    def configure_prompt_service(self, prompt_service: PromptManagerServiceProtocol) -> None:
        self._prompt_manager_service = prompt_service
        self.resolved_prompt = self._resolve_prompt(self.prompt)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        formatted_prompt = self.resolved_prompt.format(**inputs)
        return self.process_with_prompt(formatted_prompt)`,
    contextOptions: ['template', 'variables', 'format', 'max_length'],
    usageExample: `# CSV Configuration
context = {
    "template": "analysis_template",
    "variables": {"domain": "finance"},
    "format": "markdown"
}`,
    relatedProtocols: ['LLMCapableAgent']
  },
  {
    name: 'VectorCapableAgent',
    category: 'Storage',
    description: 'Enables agents to use vector database services for semantic search and document retrieval.',
    serviceInterface: 'VectorServiceProtocol',
    keyMethods: ['configure_vector_service()', 'similarity_search()', 'embed_and_store()'],
    implementationPattern: `class MyVectorAgent(BaseAgent, VectorCapableAgent):
    def configure_vector_service(self, vector_service: VectorServiceProtocol) -> None:
        self._vector_service = vector_service
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        query = inputs.get("query", "")
        return self.vector_service.similarity_search(
            query=query,
            max_results=self.context.get("max_results", 5)
        )`,
    contextOptions: ['provider', 'embedding_model', 'similarity_threshold', 'max_results', 'collection_name'],
    usageExample: `# CSV Configuration
context = {
    "provider": "chroma",
    "embedding_model": "text-embedding-ada-002",
    "similarity_threshold": 0.8,
    "max_results": 5
}`,
    relatedProtocols: ['StorageCapableAgent']
  },
  {
    name: 'CSVCapableAgent',
    category: 'Storage',
    description: 'Specialized protocol for CSV file operations with pandas integration and flexible data formatting.',
    serviceInterface: 'CSVStorageServiceProtocol',
    keyMethods: ['read_csv()', 'write_csv()', 'query_csv()'],
    implementationPattern: `class MyCSVAgent(BaseAgent, CSVCapableAgent):
    def configure_storage_service(self, storage_service: StorageServiceProtocol) -> None:
        self._storage_service = storage_service.get_service("csv")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        df = self._storage_service.read(inputs.get("collection"), format="dataframe")
        processed_df = self.process_dataframe(df)
        return self._storage_service.write("results", processed_df)`,
    contextOptions: ['delimiter', 'encoding', 'header', 'index_col', 'parse_dates'],
    usageExample: `# CSV Configuration
context = {
    "delimiter": ",",
    "encoding": "utf-8",
    "header": 0,
    "parse_dates": ["date_column"]
}`,
    relatedProtocols: ['StorageCapableAgent']
  },
  {
    name: 'JSONCapableAgent',
    category: 'Storage',
    description: 'Specialized protocol for JSON document operations with path-based queries and structured data management.',
    serviceInterface: 'JSONStorageServiceProtocol',
    keyMethods: ['read_json()', 'write_json()', 'query_path()'],
    implementationPattern: `class MyJSONAgent(BaseAgent, JSONCapableAgent):
    def configure_storage_service(self, storage_service: StorageServiceProtocol) -> None:
        self._storage_service = storage_service.get_service("json")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        doc = self._storage_service.read(inputs.get("collection"), inputs.get("document_id"))
        processed = self.transform_json(doc)
        return self._storage_service.write("output", processed)`,
    contextOptions: ['indent', 'sort_keys', 'ensure_ascii', 'schema_validation'],
    usageExample: `# CSV Configuration
context = {
    "indent": 2,
    "sort_keys": True,
    "schema_validation": True
}`,
    relatedProtocols: ['StorageCapableAgent']
  },
  {
    name: 'FileCapableAgent',
    category: 'Storage',
    description: 'General file handling protocol for various document types with chunking and metadata extraction.',
    serviceInterface: 'FileStorageServiceProtocol',
    keyMethods: ['read_file()', 'write_file()', 'process_document()'],
    implementationPattern: `class MyFileAgent(BaseAgent, FileCapableAgent):
    def configure_storage_service(self, storage_service: StorageServiceProtocol) -> None:
        self._storage_service = storage_service.get_service("file")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        content = self._storage_service.read(inputs.get("collection"))
        chunks = self.chunk_content(content)
        return self.process_chunks(chunks)`,
    contextOptions: ['chunk_size', 'chunk_overlap', 'should_split', 'include_metadata'],
    usageExample: `# CSV Configuration
context = {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "should_split": True,
    "include_metadata": True
}`,
    relatedProtocols: ['StorageCapableAgent', 'VectorCapableAgent']
  },
  {
    name: 'MultiCapabilityAgent',
    category: 'Advanced',
    description: 'Advanced pattern combining multiple protocols for complex workflows like RAG implementations.',
    serviceInterface: 'Multiple Service Protocols',
    keyMethods: ['configure_all_services()', 'orchestrate_workflow()'],
    implementationPattern: `class RAGAgent(BaseAgent, LLMCapableAgent, StorageCapableAgent, VectorCapableAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        # 1. Vector search for context
        docs = self.vector_service.similarity_search(inputs.get("query"))
        
        # 2. Load additional data
        context = self.storage_service.read("context")
        
        # 3. Generate response
        messages = [{"role": "system", "content": f"Context: {docs}"}]
        return self.llm_service.call_llm("anthropic", messages)`,
    contextOptions: ['llm_provider', 'vector_threshold', 'storage_format', 'context_limit'],
    usageExample: `# CSV Configuration for Multi-Capability
context = {
    "llm_provider": "anthropic",
    "vector_threshold": 0.8,
    "storage_format": "records",
    "context_limit": 5
}`,
    relatedProtocols: ['LLMCapableAgent', 'StorageCapableAgent', 'VectorCapableAgent']
  }
];

const CATEGORY_COLORS = {
  Core: '#2196F3',       // Blue
  Storage: '#9C27B0',    // Purple
  Communication: '#4CAF50', // Green
  Advanced: '#FF9800'    // Orange
};

const CATEGORY_ICONS = {
  Core: '⚙️',
  Storage: '💾',
  Communication: '📡',
  Advanced: '🚀'
};

export default function CapabilityBrowser(): JSX.Element {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [copiedExample, setCopiedExample] = useState<string | null>(null);

  const categories = ['All', ...Object.keys(CATEGORY_COLORS)];

  const filteredCapabilities = useMemo(() => {
    return CAPABILITIES.filter(capability => {
      const matchesSearch = 
        capability.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        capability.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        capability.serviceInterface.toLowerCase().includes(searchTerm.toLowerCase()) ||
        capability.keyMethods.some(method => 
          method.toLowerCase().includes(searchTerm.toLowerCase())
        );
      
      const matchesCategory = 
        selectedCategory === 'All' || capability.category === selectedCategory;
      
      return matchesSearch && matchesCategory;
    });
  }, [searchTerm, selectedCategory]);

  const copyToClipboard = async (text: string, capabilityName: string) => {
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
      setCopiedExample(capabilityName);
      setTimeout(() => setCopiedExample(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
      setCopiedExample(capabilityName);
      setTimeout(() => setCopiedExample(null), 1000);
    }
  };

  return (
    <div className={styles.capabilityBrowser}>
      <div className={styles.header}>
        <h1>AgentMap Capability Browser</h1>
        <p>Explore capability protocols with implementation patterns and examples</p>
      </div>

      <div className={styles.controls}>
        <div className={styles.searchContainer}>
          <input
            type="text"
            placeholder="Search capabilities by name, interface, or methods..."
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

      <div className={styles.capabilityGrid}>
        {filteredCapabilities.map((capability) => (
          <div key={capability.name} className={styles.capabilityCard}>
            <div 
              className={styles.categoryBadge}
              style={{ backgroundColor: CATEGORY_COLORS[capability.category] }}
            >
              {CATEGORY_ICONS[capability.category]} {capability.category}
            </div>

            <div className={styles.capabilityHeader}>
              <h3>{capability.name}</h3>
              <div className={styles.serviceInterface}>
                <code>{capability.serviceInterface}</code>
              </div>
            </div>

            <p className={styles.description}>{capability.description}</p>

            <div className={styles.capabilityDetails}>
              <div className={styles.detailRow}>
                <strong>Key Methods:</strong> 
                <span className={styles.tagList}>
                  {capability.keyMethods.map(method => (
                    <span key={method} className={styles.methodTag}>{method}</span>
                  ))}
                </span>
              </div>

              <div className={styles.detailRow}>
                <strong>Context Options:</strong> 
                <span className={styles.tagList}>
                  {capability.contextOptions.map(option => (
                    <span key={option} className={styles.contextTag}>{option}</span>
                  ))}
                </span>
              </div>

              {capability.relatedProtocols && capability.relatedProtocols.length > 0 && (
                <div className={styles.detailRow}>
                  <strong>Related Protocols:</strong> 
                  <span className={styles.tagList}>
                    {capability.relatedProtocols.map(protocol => (
                      <span key={protocol} className={styles.protocolTag}>{protocol}</span>
                    ))}
                  </span>
                </div>
              )}
            </div>

            <div className={styles.implementationSection}>
              <div className={styles.sectionHeader}>
                <strong>Implementation Pattern:</strong>
                <button
                  onClick={() => copyToClipboard(capability.implementationPattern, capability.name + '_impl')}
                  className={styles.copyButton}
                  title="Copy implementation pattern"
                >
                  {copiedExample === capability.name + '_impl' ? '✓ Copied!' : '📋 Copy'}
                </button>
              </div>
              <pre className={styles.codeExample}>{capability.implementationPattern}</pre>
            </div>

            <div className={styles.usageSection}>
              <div className={styles.sectionHeader}>
                <strong>Usage Example:</strong>
                <button
                  onClick={() => copyToClipboard(capability.usageExample, capability.name + '_usage')}
                  className={styles.copyButton}
                  title="Copy usage example"
                >
                  {copiedExample === capability.name + '_usage' ? '✓ Copied!' : '📋 Copy'}
                </button>
              </div>
              <pre className={styles.configExample}>{capability.usageExample}</pre>
            </div>
          </div>
        ))}
      </div>

      {filteredCapabilities.length === 0 && (
        <div className={styles.noResults}>
          <p>No capabilities found matching your search criteria.</p>
          <p>Try adjusting your search term or category filter.</p>
        </div>
      )}

      <div className={styles.footer}>
        <p>
          Found {filteredCapabilities.length} of {CAPABILITIES.length} capabilities. 
          Need help? Check out the{' '}
          <a href="/docs/reference/agents/custom-agents">custom agent development</a> guide or{' '}
          <a href="/docs/contributing/service-injection">service injection patterns</a>.
        </p>
      </div>
    </div>
  );
}
