# AgentMap Documentation Versioning Strategy

## Current Status
**Phase: Foundation Ready** - Versioning infrastructure is configured but not yet activated.

## Versioning Strategy

### When to Create Versions
Create a new documentation version when you reach any of these milestones:
- **User Growth**: 10+ GitHub stars or active users asking version-specific questions
- **Breaking Changes**: Planning changes that break backward compatibility
- **Enterprise Users**: Users needing to reference specific versions
- **Time-based**: 6+ months after first stable release

### Version Naming Convention
- **Current/Next**: Development version (labeled "Next 🚧")
- **Stable Releases**: Follow semantic versioning (e.g., "1.0.0", "1.1.0")
- **Major Releases**: Create versions for major releases (1.x, 2.x)
- **Minor Releases**: Version for significant feature additions

### Implementation Plan

#### Phase 1: Activate Versioning (when ready)
1. **Uncomment versioning config** in `docusaurus.config.ts`
2. **Activate version dropdown** in navbar
3. **Create first version snapshot**:
   ```bash
   npm run docusaurus docs:version 1.0.0
   ```

#### Phase 2: Version Management
1. **Configure search** to be version-aware (Algolia integration)
2. **Add version banners** for older versions
3. **Create upgrade guides** between versions
4. **Set up automated versioning** in CI/CD

### File Structure (when activated)
```
docs-docusaurus/
├── docs/                     # Current/Next version
├── versioned_docs/
│   ├── version-1.0.0/       # Stable version
│   └── version-1.1.0/       # Previous version
├── versioned_sidebars/
│   ├── version-1.0.0-sidebars.json
│   └── version-1.1.0-sidebars.json
└── versions.json             # Version registry
```

### Configuration Details

#### Docusaurus Config (ready to uncomment)
```typescript
docs: {
  lastVersion: 'current',
  versions: {
    current: {
      label: 'Next 🚧',
      path: 'next',
    },
  },
  includeCurrentVersion: true,
}
```

#### Navbar Version Dropdown (ready to uncomment)
```typescript
{
  type: 'docsVersionDropdown',
  position: 'left',
  dropdownActiveClassDisabled: true,
}
```

### Search Integration
When versioning is activated, update Algolia configuration:
```typescript
algolia: {
  // ... existing config
  contextualSearch: true, // This enables version-aware search
  searchParameters: {
    facetFilters: ['version:VERSION'], // Automatically set by Docusaurus
  },
}
```

### Maintenance Guidelines
- **Keep versions minimal** - only version when necessary
- **Sunset old versions** - document end-of-life for old versions
- **Cross-link versions** - help users navigate between versions
- **Update automation** - use CI/CD for consistent versioning

## Ready-to-Execute Commands

### Create First Version
```bash
cd docs-docusaurus
npm run docusaurus docs:version 1.0.0
```

### Activate Configuration
1. Uncomment versioning config in `docusaurus.config.ts`
2. Uncomment version dropdown in navbar
3. Test locally: `npm run start`
4. Deploy: `npm run build && npm run deploy`

## Success Metrics
- ✅ Version dropdown appears and functions
- ✅ Old versions preserved and accessible
- ✅ Search respects version context
- ✅ Upgrade guides are clear and helpful
- ✅ No broken links between versions

---
*Last Updated: 2025-06-26*
*Next Review: When first version milestone is reached*
