# Algolia DocSearch Application Guide

This guide explains how to apply for free Algolia DocSearch for the AgentMap documentation.

## Prerequisites

1. Your documentation must be publicly available
2. It should be primarily documentation (not a marketing site)
3. The project should be open source or a technical project

## Application Process

### Step 1: Apply Online

1. Visit: https://docsearch.algolia.com/apply/
2. Fill out the application form with these details:

**Website URL:** `https://jwwelbor.github.io/AgentMap/`
**Email:** [Your email address]
**Repository:** `https://github.com/jwwelbor/AgentMap`

**Description:**
```
AgentMap is an open-source framework for building AI workflows using simple CSV files. Our documentation helps developers build complex AI agent orchestrations without coding. The site includes tutorials, API references, interactive examples, and comprehensive guides for both beginners and advanced users.

Key documentation sections:
- Getting Started guides
- Interactive playground
- Tutorial workflows  
- API reference
- Agent type documentation
- Best practices and patterns

The documentation is built with Docusaurus and serves a technical developer audience looking to implement AI workflows.
```

### Step 2: Wait for Approval

- Algolia typically responds within a few business days
- They may ask for clarification or additional information
- Once approved, you'll receive configuration details

### Step 3: Configure Search

Once approved, you'll receive:
- Application ID (`appId`)
- Search API Key (`apiKey`) 
- Index Name (`indexName`)

Update the `docusaurus.config.ts` file by uncommenting and filling in the Algolia configuration:

```typescript
algolia: {
  appId: 'YOUR_APP_ID',
  apiKey: 'YOUR_SEARCH_API_KEY', 
  indexName: 'agentmap',
  contextualSearch: true,
  searchParameters: {},
  searchPagePath: 'search',
},
```

### Step 4: Test Search

1. Build and deploy your documentation
2. Wait for Algolia to crawl and index your content (may take a few hours)
3. Test the search functionality
4. Monitor search analytics in your Algolia dashboard

## Alternative Options

If DocSearch application is denied or delayed, consider these alternatives:

### Option 1: Local Search Plugin
```bash
npm install --save @easyops-cn/docusaurus-search-local
```

### Option 2: Manual Algolia Setup
- Create a free Algolia account
- Set up manual indexing with Algolia Crawler
- Configure search manually

## Configuration Details

The current configuration in `docusaurus.config.ts` includes:

- **contextualSearch**: Enables scoped search based on current page context
- **searchParameters**: Additional Algolia search parameters
- **searchPagePath**: Custom search results page route

## Troubleshooting

### Common Issues:

1. **Search not working**: Check API keys and index name
2. **No results**: Verify content has been crawled and indexed
3. **Styling issues**: Check CSS customization in `custom.css`

### Contact Support:

- Algolia DocSearch GitHub: https://github.com/algolia/docsearch
- Community forum: https://discourse.algolia.com/c/docsearch/16

## Expected Timeline

- **Application**: 1-3 business days
- **Initial crawl**: 2-24 hours after approval
- **Re-crawling**: Weekly (automatic)

This free service will significantly improve the search experience for AgentMap documentation users!
