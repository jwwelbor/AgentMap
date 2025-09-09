import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  agentmapSidebar: [
    // Introduction
    'intro',
    
    // Getting Started - Flat structure, no confusing nesting
    {
      type: 'category',
      label: 'Getting Started',
      collapsible: true,
      collapsed: false, // Keep open for easy access
      items: [
        {
          type: 'doc',
          id: 'getting-started/index',
          label: 'Overview',  // Custom label instead of "Getting Started"
        },
        'getting-started/introduction', // What is AgentMap?
        'getting-started/installation', // Installation guide
        'getting-started/quick-start',  // 5-minute quickstart
        'getting-started/first-workflow', // Build something real
      ],
    },
    
    // Tutorials - Step-by-step learning progression
    {
      type: 'category',
      label: 'Tutorials',
      collapsible: true,
      collapsed: true,
      items: [
        'learning/basic-agents',
        'learning/custom-prompts',
        'learning/custom-agent',
        'learning/orchestration',
        'learning/human-summary',
      ],
    },

    // Guides - Practical how-to documentation organized by domain
    {
      type: 'category',
      label: 'Guides',
      collapsible: true,
      collapsed: true,
      items: [
        // Agent Configuration and Management
        {
          type: 'category',
          label: 'Agents',
          collapsible: true,
          collapsed: true,
          items: [
            'agents/index',
            'agents/built-in-agents',
            'agents/custom-agents',
            'agents/human_agent',
            'agents/blob-storage-agents',
          ],
        },
        
        // System Configuration
        {
          type: 'category', 
          label: 'Configuration',
          collapsible: true,
          collapsed: true,
          items: [
            'configuration/index',
            'configuration/main-config',
            'configuration/auth-config',
            'configuration/environment-variables',
            'configuration/storage-config',
            'configuration/examples',
            'configuration/troubleshooting',
          ],
        },

        // Deployment and Operations
        {
          type: 'category',
          label: 'Deployment',
          collapsible: true,
          collapsed: true,
          items: [
            'deployment/index',
            
            // FastAPI Integration
            {
              type: 'category',
              label: 'FastAPI Integration',
              collapsible: true,
              collapsed: true,
              items: [
                'deployment/fastapi-standalone',
                'deployment/fastapi-integration',
              ],
            },
            
            // CLI Tools
            {
              type: 'category',
              label: 'CLI Tools',
              collapsible: true,
              collapsed: true,
              items: [
                'deployment/cli-commands',
                'deployment/cli-pretty-output',
                'deployment/cli-validation',
                'deployment/cli-diagnostics',
                'deployment/cli-resume',
              ],
            },
          ],
        },
      ],
    },

    // Reference - Comprehensive feature, API, and architecture documentation
    {
      type: 'category',
      label: 'Reference',
      collapsible: true,
      collapsed: true,
      items: [
        'reference/features',
        'reference/api',
        {
          type: 'doc',
          id: 'reference/architecture',
          label: 'Architecture Overview',
        },
      ],
    },
  ],
};

export default sidebars;