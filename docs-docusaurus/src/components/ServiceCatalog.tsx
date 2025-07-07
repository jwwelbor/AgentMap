import React, { useState, useMemo } from 'react';
import styles from './ServiceCatalog.module.css';

interface Service {
  name: string;
  category: 'Core' | 'Infrastructure' | 'Configuration' | 'Storage' | 'Validation' | 'Execution';
  description: string;
  dependencies: string[];
  keyMethods: string[];
  contextParameters: string[];
  usageExample: string;
  protocols?: string[];
}

const SERVICES: Service[] = [
  // Core Services
  {
    name: 'GraphBuilderService',
    category: 'Core',
    description: 'Builds graph models from CSV files and pandas DataFrames with comprehensive validation.',
    dependencies: ['CSVGraphParserService', 'LoggingService'],
    keyMethods: ['build_from_csv()', 'build_from_dataframe()'],
    contextParameters: ['csv_path', 'graph_name'],
    usageExample: `graph_builder = container.graph_builder_service()
graph = graph_builder.build_from_csv(Path("workflow.csv"))`,
    protocols: ['GraphBuilderProtocol']
  },
  {
    name: 'CompilationService',
    category: 'Core',
    description: 'Compiles graph models into executable LangGraph StateGraphs with state schema support.',
    dependencies: ['GraphAssemblyService', 'GraphBuilderService', 'GraphBundleService', 'LoggingService'],
    keyMethods: ['compile_graph()', 'compile_from_model()'],
    contextParameters: ['state_schema', 'csv_path'],
    usageExample: `compilation = container.compilation_service()
compiled = compilation.compile_graph("MyWorkflow", Path("workflow.csv"))`,
    protocols: ['CompilationProtocol']
  },
  {
    name: 'GraphRunnerService',
    category: 'Core',
    description: 'Orchestrates graph execution with comprehensive tracking, policy evaluation, and state management.',
    dependencies: ['CompilationService', 'ExecutionTrackingService', 'ExecutionPolicyService', 'StateAdapterService', 'LoggingService'],
    keyMethods: ['run_graph()', 'run_compiled_graph()'],
    contextParameters: ['initial_state', 'tracking_enabled'],
    usageExample: `runner = container.graph_runner_service()
result = runner.run_graph("MyWorkflow", {"input": "data"})
print(f"Success: {result.success}, Duration: {result.duration}s")`,
    protocols: ['GraphRunnerProtocol']
  },
  {
    name: 'OrchestratorService',
    category: 'Core',
    description: 'Provides intelligent node selection and workflow routing with multiple matching strategies.',
    dependencies: ['PromptManagerService', 'LoggingService', 'LLMServiceProtocol (optional)'],
    keyMethods: ['select_best_node()', 'parse_node_keywords()'],
    contextParameters: ['strategy', 'confidence_threshold', 'node_filter', 'llm_config'],
    usageExample: `orchestrator = container.orchestrator_service()
selected = orchestrator.select_best_node(
    "I need to process a payment",
    nodes_dict, strategy="tiered", confidence_threshold=0.8
)`,
    protocols: ['OrchestratorProtocol']
  },
  {
    name: 'AgentFactoryService',
    category: 'Core',
    description: 'Creates and configures agent instances with automatic dependency injection based on protocols.',
    dependencies: ['AgentRegistryService', 'LoggingService', 'LLMService (optional)', 'StorageManager', 'NodeRegistryService'],
    keyMethods: ['create_agent()', 'create_agent_by_type()'],
    contextParameters: ['agent_type', 'context_config'],
    usageExample: `factory = container.agent_factory_service()
agent = factory.create_agent(node)
# Agent has all required services automatically injected`,
    protocols: ['AgentFactoryProtocol']
  },
  {
    name: 'GraphAssemblyService',
    category: 'Core',
    description: 'Assembles graph models into LangGraph StateGraphs with agent integration and state schema support.',
    dependencies: ['AgentFactoryService', 'FunctionResolutionService', 'StateAdapterService', 'LoggingService'],
    keyMethods: ['assemble_graph()', 'assemble_with_agents()'],
    contextParameters: ['state_schema', 'agents_config'],
    usageExample: `assembly = container.graph_assembly_service()
state_graph = assembly.assemble_graph(graph_model, StateSchema)
compiled = state_graph.compile()`,
    protocols: ['GraphAssemblyProtocol']
  },

  // Infrastructure Services
  {
    name: 'LoggingService',
    category: 'Infrastructure',
    description: 'Provides structured logging throughout the application with class-specific and agent-specific loggers.',
    dependencies: [],
    keyMethods: ['get_class_logger()', 'get_agent_logger()', 'set_level()'],
    contextParameters: ['log_level', 'log_format'],
    usageExample: `class MyService:
    def __init__(self, logging_service: LoggingService):
        self.logger = logging_service.get_class_logger(self)
        self.logger.info("Service initialized")`,
    protocols: ['LoggingServiceProtocol']
  },
  {
    name: 'StateAdapterService',
    category: 'Infrastructure',
    description: 'Adapts state between different formats including dictionaries, Pydantic models, and custom schemas.',
    dependencies: ['LoggingService'],
    keyMethods: ['adapt_initial_state()', 'extract_value()'],
    contextParameters: ['schema_type', 'validation_mode'],
    usageExample: `adapter = container.state_adapter_service()
adapted = adapter.adapt_initial_state({"input": "data"}, StateSchema)`,
    protocols: ['StateAdapterProtocol']
  },
  {
    name: 'FunctionResolutionService',
    category: 'Infrastructure',
    description: 'Resolves function references for dynamic routing and custom workflow logic.',
    dependencies: ['LoggingService'],
    keyMethods: ['resolve_function()', 'register_function()'],
    contextParameters: ['function_registry', 'resolution_scope'],
    usageExample: `resolver = container.function_resolution_service()
router_func = resolver.resolve_function("func:custom_router")`,
    protocols: ['FunctionResolutionProtocol']
  },

  // Configuration Services
  {
    name: 'AppConfigService',
    category: 'Configuration',
    description: 'Manages application configuration with intelligent defaults and environment-based overrides.',
    dependencies: ['ConfigService'],
    keyMethods: ['get_csv_path()', 'get_llm_config()', 'get_prompts_config()'],
    contextParameters: ['provider', 'environment'],
    usageExample: `config = container.app_config_service()
csv_path = config.get_csv_path()
openai_config = config.get_llm_config("openai")`,
    protocols: ['AppConfigProtocol']
  },
  {
    name: 'StorageConfigService',
    category: 'Configuration',
    description: 'Manages storage service configuration with provider-specific settings and defaults.',
    dependencies: ['ConfigService'],
    keyMethods: ['get_provider_config()', 'get_default_provider()'],
    contextParameters: ['storage_type', 'provider', 'connection_params'],
    usageExample: `storage_config = container.storage_config_service()
csv_config = storage_config.get_provider_config("csv", "local")`,
    protocols: ['StorageConfigProtocol']
  },

  // Storage Services
  {
    name: 'StorageManager',
    category: 'Storage',
    description: 'Unified interface managing all storage services with automatic provider selection and registration.',
    dependencies: ['StorageConfigService', 'Various storage implementations'],
    keyMethods: ['get_service()', 'register_service()'],
    contextParameters: ['storage_type', 'provider', 'connection_config'],
    usageExample: `storage_manager = container.storage_manager()
csv_service = storage_manager.get_service("csv")
json_service = storage_manager.get_service("json", "cloud")`,
    protocols: ['StorageManagerProtocol']
  },
  {
    name: 'CSVStorageService',
    category: 'Storage',
    description: 'High-performance CSV file operations with pandas integration and flexible data format support.',
    dependencies: ['StorageConfigService', 'LoggingService'],
    keyMethods: ['read()', 'write()', 'query()'],
    contextParameters: ['format', 'encoding', 'delimiter', 'id_field'],
    usageExample: `csv_service = storage_manager.get_service("csv")
data = csv_service.read("users", format="records")
result = csv_service.write("users", new_data, mode="append")`,
    protocols: ['StorageServiceProtocol', 'CSVCapableProtocol']
  },
  {
    name: 'JSONStorageService',
    category: 'Storage',
    description: 'JSON document storage with path-based queries and structured data management.',
    dependencies: ['StorageConfigService', 'LoggingService'],
    keyMethods: ['read()', 'write()', 'query_path()'],
    contextParameters: ['indent', 'encoding', 'validation_schema'],
    usageExample: `json_service = storage_manager.get_service("json")
doc = json_service.read("configs", "app_config")
result = json_service.write("configs", {"debug": True}, "app_config")`,
    protocols: ['StorageServiceProtocol', 'JSONCapableProtocol']
  },

  // Validation Services
  {
    name: 'ValidationService',
    category: 'Validation',
    description: 'Comprehensive validation orchestration for CSV files, configurations, and data integrity.',
    dependencies: ['CSVValidationService', 'ConfigValidationService', 'ValidationCacheService', 'LoggingService'],
    keyMethods: ['validate_csv()', 'validate_config()', 'validate_data()'],
    contextParameters: ['validation_level', 'cache_enabled', 'strict_mode'],
    usageExample: `validator = container.validation_service()
result = validator.validate_csv(Path("workflow.csv"))
if not result.is_valid:
    for error in result.errors:
        print(f"Error: {error.message}")`,
    protocols: ['ValidationServiceProtocol']
  },

  // Execution Services
  {
    name: 'ExecutionTrackingService',
    category: 'Execution',
    description: 'Comprehensive workflow execution tracking with metrics, history, and performance analysis.',
    dependencies: ['AppConfigService', 'LoggingService'],
    keyMethods: ['create_tracker()', 'get_tracking_enabled()', 'get_metrics()'],
    contextParameters: ['tracking_enabled', 'metrics_level', 'history_retention'],
    usageExample: `tracking = container.execution_tracking_service()
tracker = tracking.create_tracker("MyWorkflow")
tracker.start()
# ... execution ...
tracker.complete(final_state)
summary = tracker.get_summary()`,
    protocols: ['ExecutionTrackingProtocol']
  },
  {
    name: 'ExecutionPolicyService',
    category: 'Execution',
    description: 'Configurable execution success evaluation with customizable policies and criteria.',
    dependencies: ['AppConfigService', 'LoggingService'],
    keyMethods: ['evaluate_success()', 'get_policy_type()', 'configure_policy()'],
    contextParameters: ['policy_type', 'success_criteria', 'failure_tolerance'],
    usageExample: `policy = container.execution_policy_service()
success = policy.evaluate_success(execution_summary, "MyWorkflow")
print(f"Workflow success: {success}")`,
    protocols: ['ExecutionPolicyProtocol']
  }
];

const CATEGORY_COLORS = {
  Core: '#2196F3',          // Blue
  Infrastructure: '#4CAF50', // Green
  Configuration: '#FF9800',  // Orange
  Storage: '#9C27B0',       // Purple
  Validation: '#F44336',    // Red
  Execution: '#607D8B'      // Blue Grey
};

const CATEGORY_ICONS = {
  Core: '⚙️',
  Infrastructure: '🏗️',
  Configuration: '⚙️',
  Storage: '💾',
  Validation: '✅',
  Execution: '🚀'
};

export default function ServiceCatalog(): JSX.Element {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [copiedExample, setCopiedExample] = useState<string | null>(null);

  const categories = ['All', ...Object.keys(CATEGORY_COLORS)];

  const filteredServices = useMemo(() => {
    return SERVICES.filter(service => {
      const matchesSearch = 
        service.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        service.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        service.dependencies.some(dep => 
          dep.toLowerCase().includes(searchTerm.toLowerCase())
        ) ||
        service.keyMethods.some(method => 
          method.toLowerCase().includes(searchTerm.toLowerCase())
        );
      
      const matchesCategory = 
        selectedCategory === 'All' || service.category === selectedCategory;
      
      return matchesSearch && matchesCategory;
    });
  }, [searchTerm, selectedCategory]);

  const copyToClipboard = async (text: string, serviceName: string) => {
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
      setCopiedExample(serviceName);
      setTimeout(() => setCopiedExample(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
      // Still show feedback even if copy failed
      setCopiedExample(serviceName);
      setTimeout(() => setCopiedExample(null), 1000);
    }
  };

  return (
    <div className={styles.serviceCatalog}>
      <div className={styles.header}>
        <h1>AgentMap Service Catalog</h1>
        <p>Browse all available services with context parameters and usage examples</p>
      </div>

      <div className={styles.controls}>
        <div className={styles.searchContainer}>
          <input
            type="text"
            placeholder="Search services by name, description, or methods..."
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

      <div className={styles.serviceGrid}>
        {filteredServices.map((service) => (
          <div key={service.name} className={styles.serviceCard}>
            <div 
              className={styles.categoryBadge}
              style={{ backgroundColor: CATEGORY_COLORS[service.category] }}
            >
              {CATEGORY_ICONS[service.category]} {service.category}
            </div>

            <div className={styles.serviceHeader}>
              <h3>{service.name}</h3>
            </div>

            <p className={styles.description}>{service.description}</p>

            <div className={styles.serviceDetails}>
              <div className={styles.detailRow}>
                <strong>Dependencies:</strong> 
                <span className={styles.tagList}>
                  {service.dependencies.map(dep => (
                    <span key={dep} className={styles.tag}>{dep}</span>
                  ))}
                </span>
              </div>
              
              <div className={styles.detailRow}>
                <strong>Key Methods:</strong> 
                <span className={styles.tagList}>
                  {service.keyMethods.map(method => (
                    <span key={method} className={styles.methodTag}>{method}</span>
                  ))}
                </span>
              </div>

              <div className={styles.detailRow}>
                <strong>Context Parameters:</strong> 
                <span className={styles.tagList}>
                  {service.contextParameters.map(param => (
                    <span key={param} className={styles.paramTag}>{param}</span>
                  ))}
                </span>
              </div>

              {service.protocols && service.protocols.length > 0 && (
                <div className={styles.detailRow}>
                  <strong>Protocols:</strong> 
                  <span className={styles.tagList}>
                    {service.protocols.map(protocol => (
                      <span key={protocol} className={styles.protocolTag}>{protocol}</span>
                    ))}
                  </span>
                </div>
              )}
            </div>

            <div className={styles.usageExample}>
              <div className={styles.exampleHeader}>
                <strong>Usage Example:</strong>
                <button
                  onClick={() => copyToClipboard(service.usageExample, service.name)}
                  className={styles.copyButton}
                  title="Copy usage example"
                >
                  {copiedExample === service.name ? '✓ Copied!' : '📋 Copy'}
                </button>
              </div>
              <pre className={styles.codeExample}>{service.usageExample}</pre>
            </div>
          </div>
        ))}
      </div>

      {filteredServices.length === 0 && (
        <div className={styles.noResults}>
          <p>No services found matching your search criteria.</p>
          <p>Try adjusting your search term or category filter.</p>
        </div>
      )}

      <div className={styles.footer}>
        <p>
          Found {filteredServices.length} of {SERVICES.length} services. 
          Need help? Check out the{' '}
          <a href="/docs/reference/services/llm-service">service documentation</a> or{' '}
          <a href="/docs/getting-started/quick-start">quick start guide</a>.
        </p>
      </div>
    </div>
  );
}
