import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import type * as Plugin from '@docusaurus/types';

const config: Config = {
  title: 'AgentMap',
  tagline: 'Build AI Workflows with Simple CSV Files',
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
        content: 'AI workflows, CSV automation, no-code AI, agent orchestration, data pipelines, business automation',
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
  themes: ['@docusaurus/theme-mermaid', '@docusaurus/theme-live-codeblock'],

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
          ignorePatterns: ['/tags/**'],
          filename: 'sitemap.xml',
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
    
    // Algolia DocSearch configuration
    // Note: Apply for free DocSearch at https://docsearch.algolia.com/apply/
    // algolia: {
    //   appId: 'YOUR_APP_ID',
    //   apiKey: 'YOUR_SEARCH_API_KEY',
    //   indexName: 'agentmap',
    //   contextualSearch: true,
    //   searchParameters: {},
    //   searchPagePath: 'search',
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
