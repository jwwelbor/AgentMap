---
title: Docusaurus ID System Guide
---

# Understanding Docusaurus Document IDs

## How Document IDs Make Links Resilient

### The ID System

When you reference a document by ID, Docusaurus searches for it across your entire docs folder:

```markdown
<!-- Using ID (survives file moves!) -->
[Learn about agents](basic-agents-tutorial)

<!-- Using file path (breaks if file moves) -->
[Learn about agents](./guides/learning/basic-agents.md)

<!-- Using URL (breaks if structure changes) -->
[Learn about agents](/docs/guides/learning/01-basic-agents)
```

### Setting Custom IDs

```markdown
---
id: my-custom-id          # This becomes the document's unique identifier
slug: /my-custom-url      # This controls the URL path
title: My Document
---
```

## Benefits of Using IDs

### 1. **Survive File Reorganization**
```
Before: docs/tutorials/basic/agents.md
After:  docs/guides/learning/basic-agents.md

Links using ID 'basic-agents' still work! ✅
```

### 2. **Stable References**
```markdown
<!-- In any document -->
[See basic agents guide](guides/learning/01-basic-agents)

<!-- In sidebars.ts -->
items: ['basic-agents']

<!-- In docusaurus.config.ts -->
to: '/docs/basic-agents'  // URL generated from ID
```

### 3. **Easier Refactoring**
Move files around without updating dozens of links!

## Best Practices for Document IDs

### 1. **Use Meaningful IDs**
```markdown
---
# Good IDs
id: agent-development-guide
id: csv-schema-reference
id: deployment-cli

# Bad IDs  
id: guide1
id: new-page
id: temp
---
```

### 2. **Create an ID Convention**
```markdown
---
# Feature guides
id: guide-{feature-name}

# References
id: ref-{topic}

# Tutorials  
id: tutorial-{name}

# API docs
id: api-{endpoint}
---
```

### 3. **Document Your IDs**
Create a master list:

```markdown
<!-- docs/doc-ids.md -->
# Document ID Reference

| Document | ID | Path |
|----------|-----|------|
| Introduction | `intro` | `/docs/intro.md` |
| Agent Development | `guide-agent-dev` | `/docs/guides-development-best-practicesagents.md` |
| CSV Schema | `ref-csv-schema` | `/docs/reference/csv-schema.md` |
```

## Migration Strategy

### Step 1: Add IDs to All Documents
```bash
# Add IDs to all existing documents
for file in $(find docs -name "*.md"); do
  # Extract filename without extension and path
  filename=$(basename "$file" .md)
  # Add ID to frontmatter if not present
  # ... script to add ID
done
```

### Step 2: Update All Internal Links
```markdown
<!-- Change from -->
[Link](../guides/learning/basic-agents.md)
[Link](/docs/guides/learning/01-basic-agents)

<!-- To -->
[Link](basic-agents-tutorial)
```

### Step 3: Use ID-based Sidebar
```typescript
// sidebars.ts
const sidebars = {
  docs: [
    'intro',                    // ID reference
    'getting-started',          // ID reference
    {
      type: 'category',
      label: 'Guides',
      items: [
        'guide-agent-dev',      // ID reference
        'guide-deployment',     // ID reference
      ],
    },
  ],
};
```

## Example: Making AgentMap Docs Resilient

### Current (Fragile) Structure:
```
sidebars.ts:
- 'guides/learning/basic-agents'
- 'guides/development/agents/agent-development'

Links:
[See guide](../../guides/learning/basic-agents.md)
```

### Improved (Resilient) Structure:
```markdown
<!-- In docs/guides/learning/basic-agents.md -->
---
id: tutorial-basic-agents
---

<!-- In docs/guides/development/agents/agent-development.md -->
---
id: guide-agent-development  
---
```

```typescript
// sidebars.ts
items: [
  'tutorial-basic-agents',
  'guide-agent-development',
]
```

```markdown
<!-- In any document -->
[See guide](tutorial-basic-agents)
[Learn development](guide-agent-development)
```

## URL Control with Slugs

You can even control URLs independently:

```markdown
---
id: my-guide              # Internal ID for references
slug: /guides/awesome     # URL will be /docs/guides/awesome
---
```

This gives you:
- Stable internal references via `id`
- Custom URL structure via `slug`
- Complete reorganization freedom!

## Quick Implementation

1. **Add IDs to key documents first**:
```markdown
---
id: intro
---

---
id: csv-schema
---

---
id: agent-types
---
```

2. **Update critical links**:
```markdown
<!-- High-traffic pages -->
[Get Started](intro)
[CSV Schema](reference/csv-schema)
[Agent Types](reference/agent-types)
```

3. **Update sidebars**:
```typescript
items: ['intro', 'csv-schema', 'agent-types']
```

This way, you can reorganize your file structure anytime without breaking links!