---
title: Link Debugging Guide
description: How to fix broken links in Docusaurus
---

# Docusaurus Link Debugging Guide

## Understanding Link Types

### 1. **Markdown Links in Docs**
```markdown
<!-- Relative file path (RECOMMENDED) -->
[Link](../intro.md)                    ✅ Clear and explicit
[Link](./subfolder/page.md)            ✅ Works across folders

<!-- Document ID (FRAGILE) -->
[Link](intro)                          ⚠️  Only works if 'intro' exists
[Link](guides/learning/index)          ⚠️  Breaks if file moves

<!-- Absolute URL -->
[Link](/docs/intro)                    ✅ Always works but hardcoded
```

### 2. **Links in React Components**
```jsx
import Link from '@docusaurus/Link';

// Good - uses the router
<Link to="/docs/intro">Introduction</Link>

// Bad - regular anchor
<a href="/docs/intro">Introduction</a>
```

### 3. **Sidebar References**
```typescript
// sidebars.ts
{
  type: 'doc',
  id: 'intro',          // Must match the document ID exactly
}

// Or reference by path
{
  type: 'doc',
  id: 'guides/learning/index',  // Matches docs/guides/learning/index.md
}
```

## Common Link Problems

### Problem 1: Document ID Mismatch
```
Error: These sidebar document ids do not exist:
- getting-started
```

**Solution**: The file doesn't exist or has a different ID.

### Problem 2: Wrong Base URL
```markdown
[Link](/docs/intro)     ❌ Missing baseUrl
[Link](/AgentMap/docs/intro)  ✅ Includes baseUrl
```

### Problem 3: Index Files
```
docs/guides/learning/index.md

Can be referenced as:
- guides/learning/index  (full ID)
- guides/learning/       (URL)
- guides/learning        (sometimes works)
```

## How to Fix Broken Links Systematically

### Step 1: Find All Links
```bash
# Find all markdown links
grep -r "\[.*\](" docs/ --include="*.md" | grep -v http

# Find all React Link components
grep -r "to=\"" src/ --include="*.tsx" --include="*.jsx"

# Find all sidebar references
grep -r "id:" sidebars.ts
```

### Step 2: Verify Files Exist
```bash
# List all documentation files
find docs -name "*.md" -o -name "*.mdx" | sort

# Compare with sidebar references
```

### Step 3: Use Link Checker
```bash
# After building
npm run build
npm run serve

# Use a link checker
npx linkinator http://localhost:3000/AgentMap/ --recurse
```

## Best Practices

### 1. **Use Relative File Paths**
```markdown
<!-- Good -->
See the [introduction](../intro.md)
Check our [learning guide](./guides/learning/index.md)

<!-- Avoid -->
See the [introduction](intro)
```

### 2. **Create a Link Mapping**
```typescript
// src/utils/links.ts
export const DOCS_LINKS = {
  intro: '/AgentMap/docs/intro',
  gettingStarted: '/AgentMap/docs/guides/learning/',
  api: '/AgentMap/docs/api',
  // ... etc
};
```

### 3. **Use Redirects for Old URLs**
```typescript
// docusaurus.config.ts
redirects: [
  {
    from: '/old-path',
    to: '/new-path',
  },
]
```

### 4. **Validate During Build**
```json
// docusaurus.config.ts
{
  onBrokenLinks: 'throw',        // Fail build on broken links
  onBrokenMarkdownLinks: 'throw', // Fail build on broken markdown links
}
```

## Quick Fix Script

Create this script to find and report broken links:

```javascript
// scripts/check-links.js
const fs = require('fs');
const path = require('path');

function findAllMdFiles(dir) {
  // ... implementation
}

function extractLinks(content) {
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  // ... extract and validate
}

console.log('Checking links...');
// ... run checks
```

## Debugging Specific Issues

### For "Can't render static file" errors:
1. Check if the page exists
2. Check for missing frontmatter
3. Check for syntax errors in MDX
4. Check for missing imports

### For "Can't find sidebar" errors:
1. Verify sidebar ID in docusaurus.config.ts
2. Check sidebars.ts exports
3. Ensure no typos in sidebar references

### For redirect loops:
1. Check redirect chains
2. Ensure no circular redirects
3. Verify baseUrl configuration
