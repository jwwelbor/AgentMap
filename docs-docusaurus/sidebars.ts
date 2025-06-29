import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  // Main documentation sidebar following user journey
  agentmapSidebar: [
    // Introduction
    'intro',
    
    // Overview - Core concepts and features  
    'core-features',
    
    // Getting Started - First steps for new users
    'getting-started',
    
    // Learning Paths - Structured learning journeys
    {
      type: 'category',
      label: '🎓 Learning Paths',
      items: [
        'guides/learning-paths/index',
        'guides/learning-paths/agentmap-basics', 
        'guides/learning-paths/understanding-workflows',
        'guides/learning-paths/advanced-learning-path',
        {
          type: 'category',
          label: 'Core Concepts',
          items: [
            'guides/learning-paths/core/fundamentals',
            'guides/learning-paths/core/workflows', 
            'guides/learning-paths/core/state-management',
            'guides/learning-paths/core/csv-schema',
          ],
        },
      ],
    },
    
    // Templates - Ready-to-use workflow templates
    {
      type: 'category',
      label: '📄 Templates',
      items: [
        'templates/index',
      ],
    },
    
    // Guides - Development and deployment
    {
      type: 'category',
      label: '📖 Guides',
      items: [
        {
          type: 'category',
          label: '⚙️ Development',
          items: [
            'guides/development/index',
            'guides/development/best-practices',
            'guides/development/integrations',
            'guides/development/orchestration',
            'guides/development/prompt-management',
            'guides/development/testing',
            {
              type: 'category',
              label: 'Agents',
              items: [
                'guides/development/agents/agent-development',
                'guides/development/agents/custom-agents',
                'guides/development/agents/advanced-agent-types',
                'guides/development/agents/host-service-integration',
              ],
            },
            {
              type: 'category',
              label: 'Agent Memory',
              items: [
                'guides/development/agent-memory/memory-management',
                'guides/development/agent-memory/langchain-memory-integration',
              ],
            },
            {
              type: 'category',
              label: 'Services',
              items: [
                'guides/development/services/service-registry-patterns',
                {
                  type: 'category',
                  label: 'Storage',
                  items: [
                    'guides/development/services/storage/index',
                    'guides/development/services/storage/storage-services-overview',
                    'guides/development/services/storage/cloud-storage-integration',
                  ],
                },
              ],
            },
          ],
        },
        {
          type: 'category',
          label: '🚀 Deployment',
          items: [
            'guides/deploying/index',
            'guides/deploying/deployment',
            'guides/deploying/monitoring',
          ],
        },
      ],
    },
    
    // Tutorials - Step-by-step walkthroughs
    {
      type: 'category',
      label: '📚 Tutorials',
      items: [
        'tutorials/index',
        'tutorials/weather-bot',
        'tutorials/data-processing-pipeline', 
        'tutorials/customer-support-bot',
        'tutorials/document-analyzer',
        'tutorials/building-custom-agents',
        'tutorials/api-integration',
        'tutorials/rag-chatbot',
        'tutorials/multi-agent-research',
        'tutorials/example-workflows',
      ],
    },
    
    // Examples - Real-world use cases
    {
      type: 'category',
      label: '💡 Examples',
      items: [
        'examples/index',
      ],
    },
    
    // Reference - Complete documentation
    {
      type: 'category',
      label: '📚 Reference',
      items: [
        'reference/index',
        'reference/csv-schema',
        'reference/agent-types',
        'reference/agent-catalog',
        'reference/service-catalog',
        'reference/cli-commands',
        'reference/cli-graph-inspector',
        'reference/configuration',
        'reference/dependency-injection',
      ],
    },
    
    // API Documentation
    {
      type: 'category',
      label: '🔌 API',
      items: [
        'api',
      ],
    },
    
    // Tools - Development and debugging utilities
    {
      type: 'category',
      label: '🔧 Tools',
      items: [
        'tools/index',
        'playground',
      ],
    },
    
    // Contributing - Architecture and contribution
    {
      type: 'category',
      label: '🤝 Contributing',
      items: [
        'contributing/index',
        'contributing/clean-architecture-overview',
        'contributing/dependency-injection',
        'contributing/service-injection',
        'contributing/state-management',
      ],
    },
  ],

  // Tutorial sidebar for hands-on learning
  tutorialSidebar: [
    'tutorials/index',                    // Tutorial overview at the top
    'tutorials/weather-bot',             // Basic API integration
    'tutorials/data-processing-pipeline', // Data transformation
    'tutorials/customer-support-bot',    // AI-powered routing
    'tutorials/document-analyzer',       // Document processing
    'tutorials/building-custom-agents',  // Custom agent development
    'tutorials/api-integration',         // External service integration
    'tutorials/rag-chatbot',            // RAG AI implementation
    'tutorials/multi-agent-research',   // Multi-agent coordination
    'tutorials/example-workflows',      // Comprehensive patterns
  ],

  // Tools sidebar for utilities and development
  toolsSidebar: [
    'tools/index',
    'playground',
    'reference/cli-commands',
    'reference/cli-graph-inspector',
  ],
};

export default sidebars;