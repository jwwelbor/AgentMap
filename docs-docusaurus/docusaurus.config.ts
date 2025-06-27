import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import type * as Plugin from '@docusaurus/types';

const config: Config = {
  title: 'AgentMap - Agentic AI Workflows & Multi-Agent Systems',
  tagline: 'Build Autonomous Multi-Agent AI Systems with CSV Files',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://jwwelbor.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/AgentMap/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'jwwelbor', // Usually your GitHub org/user name.
  projectName: 'AgentMap', // Usually your repo name.

  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  // SEO Configuration
  headTags: [
    {
      tagName: 'meta',
      attributes: {
        name: 'keywords',
        content: 'agentic AI workflows, multi-agent systems, RAG AI, retrieval augmented generation, LLM orchestration, autonomous AI agents, vector database integration, agent framework, multi-agent AI, agentic workflows',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        property: 'og:type',
        content: 'website',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'twitter:card',
        content: 'summary_large_image',
      },
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'canonical',
        href: 'https://jwwelbor.github.io/AgentMap/',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'author',
        content: 'AgentMap Team',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'robots',
        content: 'index, follow',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        property: 'og:site_name',
        content: 'AgentMap Documentation',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'twitter:site',
        content: '@agentmap',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'theme-color',
        content: '#2e8555',
      },
    },
    {
      tagName: 'script',
      attributes: {
        type: 'application/ld+json',
      },
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: 'AgentMap - Agentic AI Workflows & Multi-Agent Systems',
        description: 'Build autonomous multi-agent AI workflows with CSV files. RAG AI support, vector databases, LLM orchestration, and custom agentic AI development.',
        url: 'https://jwwelbor.github.io/AgentMap/',
        applicationCategory: 'DeveloperApplication',
        operatingSystem: 'Cross-platform',
        softwareVersion: '1.0.0',
        author: {
          '@type': 'Organization',
          name: 'AgentMap Team',
        },
        offers: {
          '@type': 'Offer',
          price: '0',
          priceCurrency: 'USD',
        },
      }),
    },
  ],

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  markdown: {
    mermaid: true,
  },
  themes: [
    '@docusaurus/theme-mermaid', 
    '@docusaurus/theme-live-codeblock',
    [
      '@easyops-cn/docusaurus-search-local',
      {
        // Basic options
        indexDocs: true,
        indexBlog: true,
        indexPages: false,
        language: "en",
        searchResultLimits: 8,
        searchResultContextMaxLength: 50,
        hashed: true,
      },
    ],
  ],

  plugins: [
    [
      '@docusaurus/plugin-client-redirects',
      {
        redirects: [
          {
            from: '/usage/agentmap_cli_documentation.md',
            to: '/docs/reference/cli-commands',
          },
          {
            from: '/usage/agentmap_cli_documentation',
            to: '/docs/reference/cli-commands',
          },
          {
            from: '/getting-started',
            to: '/docs/getting-started/quick-start',
          },
          {
            from: '/quickstart',
            to: '/docs/getting-started/quick-start',
          },
          {
            from: '/tutorials',
            to: '/docs/tutorial/intro',
          },
          {
            from: '/examples',
            to: '/docs/examples/',
          },
          {
            from: '/api',
            to: '/docs/reference/agent-types',
          },
          {
            from: '/reference',
            to: '/docs/reference/csv-schema',
          },
          {
            from: '/docs.md',
            to: '/docs/intro',
          },
          {
            from: '/documentation',
            to: '/docs/intro',
          },
          {
            from: '/agents',
            to: '/docs/playground',
          },
          {
            from: '/agent-catalog',
            to: '/docs/playground',
          },
          // Legacy usage documentation redirects
          {
            from: '/usage/agentmap_features.md',
            to: '/docs/overview/core-features',
          },
          {
            from: '/usage/agentmap_features',
            to: '/docs/overview/core-features',
          },
          {
            from: '/usage/agentmap_csv_schema_documentation.md',
            to: '/docs/reference/csv-schema',
          },
          {
            from: '/usage/agentmap_csv_schema_documentation',
            to: '/docs/reference/csv-schema',
          },
          {
            from: '/usage/agentmap_agent_types.md',
            to: '/docs/reference/agent-types',
          },
          {
            from: '/usage/agentmap_agent_types',
            to: '/docs/reference/agent-types',
          },
          {
            from: '/usage/agentmap_example_workflows.md',
            to: '/docs/tutorial/intro',
          },
          {
            from: '/usage/agentmap_example_workflows',
            to: '/docs/tutorial/intro',
          },
          {
            from: '/usage/advanced_agent_types.md',
            to: '/docs/guides/advanced/advanced-agent-types',
          },
          {
            from: '/usage/advanced_agent_types',
            to: '/docs/guides/advanced/advanced-agent-types',
          },
          {
            from: '/usage/state_management_and_data_flow.md',
            to: '/docs/guides/state-management',
          },
          {
            from: '/usage/state_management_and_data_flow',
            to: '/docs/guides/state-management',
          },
          {
            from: '/usage/memory_management_in_agentmap.md',
            to: '/docs/guides/advanced/memory-and-orchestration/memory-management',
          },
          {
            from: '/usage/memory_management_in_agentmap',
            to: '/docs/guides/advanced/memory-and-orchestration/memory-management',
          },
          {
            from: '/usage/agentmap_execution_tracking.md',
            to: '/docs/guides/operations/execution-tracking',
          },
          {
            from: '/usage/agentmap_execution_tracking',
            to: '/docs/guides/operations/execution-tracking',
          },
          {
            from: '/usage/CLI_INSPECT_GRAPH_DOCS.md',
            to: '/docs/reference/cli-graph-inspector',
          },
          {
            from: '/usage/CLI_INSPECT_GRAPH_DOCS',
            to: '/docs/reference/cli-graph-inspector',
          },
          {
            from: '/usage/TESTING_PATTERNS.md',
            to: '/docs/guides/operations/testing-patterns',
          },
          {
            from: '/usage/TESTING_PATTERNS',
            to: '/docs/guides/operations/testing-patterns',
          },
          {
            from: '/usage/storage_services.md',
            to: '/docs/guides/infrastructure/storage-services-overview',
          },
          {
            from: '/usage/storage_services',
            to: '/docs/guides/infrastructure/storage-services-overview',
          },
          {
            from: '/usage/agentmap_cloud_storage.md',
            to: '/docs/guides/infrastructure/cloud-storage-integration',
          },
          {
            from: '/usage/agentmap_cloud_storage',
            to: '/docs/guides/infrastructure/cloud-storage-integration',
          },
          {
            from: '/usage/host-service-integration.md',
            to: '/docs/guides/advanced/host-service-integration',
          },
          {
            from: '/usage/host-service-integration',
            to: '/docs/guides/advanced/host-service-integration',
          },
          {
            from: '/usage/service_injection.md',
            to: '/docs/guides/advanced/service-injection-patterns',
          },
          {
            from: '/usage/service_injection',
            to: '/docs/guides/advanced/service-injection-patterns',
          },
          {
            from: '/usage/agent_contract.md',
            to: '/docs/guides/advanced/agent-development-contract',
          },
          {
            from: '/usage/agent_contract',
            to: '/docs/guides/advanced/agent-development-contract',
          },
          {
            from: '/usage/orchestration_agent.md',
            to: '/docs/guides/advanced/memory-and-orchestration/orchestration-patterns',
          },
          {
            from: '/usage/orchestration_agent',
            to: '/docs/guides/advanced/memory-and-orchestration/orchestration-patterns',
          },
          {
            from: '/usage/prompt_management_in_agentmap.md',
            to: '/docs/guides/advanced/memory-and-orchestration/prompt-management',
          },
          {
            from: '/usage/prompt_management_in_agentmap',
            to: '/docs/guides/advanced/memory-and-orchestration/prompt-management',
          },
          {
            from: '/usage/langchain_memory_in_agentmap.md',
            to: '/docs/guides/advanced/memory-and-orchestration/langchain-memory-integration',
          },
          {
            from: '/usage/langchain_memory_in_agentmap',
            to: '/docs/guides/advanced/memory-and-orchestration/langchain-memory-integration',
          },
          {
            from: '/usage/host_service_registry.md',
            to: '/docs/guides/infrastructure/service-registry-patterns',
          },
          {
            from: '/usage/host_service_registry',
            to: '/docs/guides/infrastructure/service-registry-patterns',
          },
          {
            from: '/usage/agentmap-quickstart.md',
            to: '/docs/getting-started/quick-start',
          },
          {
            from: '/usage/agentmap-quickstart',
            to: '/docs/getting-started/quick-start',
          },
          {
            from: '/usage/index.md',
            to: '/docs/intro',
          },
          {
            from: '/usage/index',
            to: '/docs/intro',
          },
          {
            from: '/usage/',
            to: '/docs/intro',
          },
        ],
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/jwwelbor/AgentMap/tree/main/docs-docusaurus/',
          // Versioning configuration (ready for activation)
          // lastVersion: 'current',
          // versions: {
          //   current: {
          //     label: 'Next 🚧',
          //     path: 'next',
          //   },
          // },
          // includeCurrentVersion: true,
        },
        blog: {
          showReadingTime: true,
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/jwwelbor/AgentMap/tree/main/docs-docusaurus/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
        sitemap: {
          changefreq: 'weekly',
          priority: 0.5,
          ignorePatterns: ['/tags/**', '/blog/archive/**'],
          filename: 'sitemap.xml',
          createSitemapItems: async (params) => {
            const {defaultCreateSitemapItems, ...rest} = params;
            const items = await defaultCreateSitemapItems(rest);
            return items.map((item) => {
              // Higher priority for key pages
              if (item.url.includes('/docs/intro') || 
                  item.url.includes('/docs/getting-started/quick-start')) {
                return {
                  ...item,
                  priority: 1.0,
                  changefreq: 'daily',
                };
              }
              if (item.url.includes('/docs/tutorials/') || 
                  item.url.includes('/docs/reference/')) {
                return {
                  ...item,
                  priority: 0.8,
                  changefreq: 'weekly',
                };
              }
              if (item.url.includes('/docs/guides/')) {
                return {
                  ...item,
                  priority: 0.7,
                  changefreq: 'weekly',
                };
              }
              return item;
            });
          },
        },
        gtag: {
          trackingID: 'G-XXXXXXXXXX', // Replace with your Google Analytics 4 tracking ID
          anonymizeIP: true,
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/agentmap-hero.png',
    
    // Algolia DocSearch configuration (UNCOMMENT WHEN APPROVED)
    // Note: Apply for free DocSearch at https://docsearch.algolia.com/apply/
    // algolia: {
    //   appId: 'YOUR_APP_ID',
    //   apiKey: 'YOUR_SEARCH_API_KEY',
    //   indexName: 'agentmap',
    //   contextualSearch: true,
    //   searchParameters: {
    //     facetFilters: ['language:en'],
    //   },
    //   searchPagePath: 'search',
    //   insights: true, // Enable search analytics
    // },
    
    navbar: {
      title: 'AgentMap',
      logo: {
        alt: 'AgentMap Logo',
        src: 'img/secret_agent.png',
      },
      items: [
        {
          to: '/docs/intro',
          label: 'Documentation',
          position: 'left',
        },
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Tutorials',
        },
        {
          type: 'docSidebar',
          sidebarId: 'toolsSidebar',
          position: 'left',
          label: 'Tools',
        },
        {to: '/blog', label: 'Blog', position: 'left'},
        // Version dropdown (ready for activation when versioning is enabled)
        // {
        //   type: 'docsVersionDropdown',
        //   position: 'left',
        //   dropdownActiveClassDisabled: true,
        // },
        {
          href: 'https://github.com/jwwelbor/AgentMap',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Tutorial',
              to: '/docs/intro',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/jwwelbor/AgentMap',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'Blog',
              to: '/blog',
            },
            {
              label: 'GitHub',
              href: 'https://github.com/jwwelbor/AgentMap',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} AgentMap. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
    colorMode: {
      defaultMode: 'light',
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;