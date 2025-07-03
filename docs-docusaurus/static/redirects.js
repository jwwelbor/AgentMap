// URL Redirects Configuration for AgentMap Documentation
// This file contains mappings from old documentation URLs to new Docusaurus URLs

const redirects = [
  // Old CLI documentation redirects
  {
    from: '/usage/agentmap_cli_documentation.md',
    to: '/docs/reference/cli-commands',
  },
  {
    from: '/usage/agentmap_cli_documentation',
    to: '/docs/reference/cli-commands',
  },
  
  // Old getting started redirects  
  {
    from: '/getting-started',
    to: '/docs/getting-started',
  },
  {
    from: '/quickstart',
    to: '/docs/getting-started',
  },
  
  // Old tutorial redirects
  {
    from: '/tutorials',
    to: '/docs/tutorials',
  },
  {
    from: '/examples',
    to: '/docs/guides/examples',
  },
  
  // Old API documentation redirects
  {
    from: '/api',
    to: '/docs/api',
  },
  {
    from: '/reference',
    to: '/docs/reference',
  },
  
  // Legacy documentation paths
  {
    from: '/docs.md',
    to: '/docs/intro',
  },
  {
    from: '/documentation',
    to: '/docs/intro',
  },
  
  // Agent-specific redirects
  {
    from: '/agents',
    to: '/docs/playground',
  },
  {
    from: '/agent-catalog',
    to: '/docs/playground',
  },
];

module.exports = redirects;
