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
    {
      type: 'category', 
      label: '📋 Overview',
      items: [
        'overview/core-features',
      ],
    },
    
    // Getting Started - First steps for new users
    {
      type: 'category',
      label: '🚀 Getting Started',
      items: [
        'getting-started/quick-start',
        // These will be added when installation and first-workflow docs are created
        // 'getting-started/installation',
        // 'getting-started/first-workflow',
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
    
    // Guides - Core development guides
    {
      type: 'category',
      label: '📖 Guides',
      items: [
        'guides/index',
        {
          type: 'category',
          label: '🚀 Basics',
          items: [
            'guides/basics/index',
          ],
        },
        'guides/understanding-workflows',
        'guides/state-management',
        {
          type: 'category',
          label: '🎯 Best Practices',
          items: [
            'guides/best-practices/index',
          ],
        },
        {
          type: 'category',
          label: '🔧 Advanced',
          items: [
            'guides/advanced/index',
            'guides/advanced/advanced-agent-types',
            'guides/advanced/agent-development-contract',
            'guides/advanced/host-service-integration',
            {
              type: 'category',
              label: 'Memory and Orchestration',
              items: [
                'guides/advanced/memory-and-orchestration/index',
                'guides/advanced/memory-and-orchestration/memory-management',
                'guides/advanced/memory-and-orchestration/langchain-memory-integration',
                'guides/advanced/memory-and-orchestration/orchestration-patterns',
                'guides/advanced/memory-and-orchestration/prompt-management',
              ],
            },
            'guides/advanced/service-injection-patterns',
          ],
        },
        {
          type: 'category',
          label: '🏗️ Infrastructure',
          items: [
            'guides/infrastructure/index',
            'guides/infrastructure/cloud-storage-integration',
            'guides/infrastructure/service-registry-patterns',
            'guides/infrastructure/storage-services-overview',
          ],
        },
        {
          type: 'category',
          label: '⚙️ Operations',
          items: [
            'guides/operations/index',
            'guides/operations/execution-tracking',
            'guides/operations/testing-patterns',
          ],
        },
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
        'reference/cli-commands',
        'reference/cli-graph-inspector',
        'reference/agent-types',
        'reference/agent-catalog',
        'reference/configuration',
        'reference/dependency-injection',
      ],
    },
    
    // API Documentation
    {
      type: 'category',
      label: '🔌 API',
      items: [
        'api/index',
      ],
    },
    
    // API Documentation (will be added when content is created)
    // {
    //   type: 'category',
    //   label: '🔌 API',
    //   items: [
    //     'api/agent-api',
    //     'api/service-api',
    //     'api/python-api',
    //   ],
    // },
    
    // Tools - Development and debugging utilities
    {
      type: 'category',
      label: '🔧 Tools',
      items: [
        'tools/index',
        'playground',
        'reference/cli-commands',
        'reference/cli-graph-inspector',
      ],
    },
    
    // Advanced Topics - Architecture and contribution
    {
      type: 'category',
      label: '🎯 Advanced',
      items: [
        {
          type: 'category',
          label: 'Architecture',
          items: [
            'advanced/architecture/clean-architecture-overview',
            'advanced/architecture/dependency-injection',
            'advanced/architecture/service-catalog',
            // These will be added when additional architecture docs are created
            // 'advanced/architecture/migration-guide',
          ],
        },
        'contributing',
      ],
    },
  ],

  // Tools sidebar for workflow building and utilities
  toolsSidebar: [
    'guides/understanding-workflows',
    'playground',
  ],

  // Tutorial sidebar for the tutorial section
  tutorialSidebar: [
    'tutorial/intro',                    // Tutorial overview at the top
    'tutorials/weather-bot',             // Individual tutorials
    'tutorials/data-processing-pipeline',
    'tutorials/customer-support-bot',
    'tutorials/document-analyzer', 
    'tutorials/api-integration',
    'tutorials/example-workflows',       // Comprehensive workflow patterns and templates
    // Additional tutorials will be added when content is created
    // 'tutorials/rag-chatbot',
    // 'tutorials/parallel-processing',
  ],
};

export default sidebars;
