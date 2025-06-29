# AgentMap Documentation Link Mapping Reference

**Version**: 1.0  
**Date**: June 28, 2025  
**Purpose**: Comprehensive mapping reference for fixing broken links in AgentMap Docusaurus documentation

## Overview

This document provides the definitive mapping of broken link patterns to their correct file paths in the current Docusaurus structure. Use this as the single source of truth for all link corrections.

## Most Frequently Broken Link Patterns

### 1. Agent Development Contract References
**Pattern**: `agent-development-contract`  
**Target File**: `guides/development/agents/agent-development.md`  
**Frequency**: HIGH (appears in 40+ files)

```
# From docs root level:
../guides/advanced/agent-development-contract → ./guides/development/agents/agent-development
./guides/advanced/agent-development-contract → ./guides/development/agents/agent-development

# From subdirectories:
../guides/advanced/agent-development-contract → ../guides/development/agents/agent-development
../../guides/advanced/agent-development-contract → ../../guides/development/agents/agent-development

# Absolute paths:
/AgentMap/docs/guides/advanced/agent-development → /docs/guides/development/agents/agent-development
```

### 2. Getting Started / Quick Start References
**Pattern**: `getting-started/quick-start`  
**Target File**: `getting-started.md` (at docs root)  
**Frequency**: HIGH (appears in 30+ files)

```
# From docs root level:
./getting-started/quick-start → ./getting-started

# From subdirectories:
../getting-started/quick-start → ../getting-started
../../getting-started/quick-start → ../../getting-started
```

### 3. Memory Management References
**Pattern**: `memory-management`  
**Target File**: `guides/development/agent-memory/memory-management.md`  
**Frequency**: HIGH (appears in 25+ files)

```
# Direct references:
./memory-management → ./guides/development/agent-memory/memory-management
../memory-management → ../guides/development/agent-memory/memory-management

# Nested path references:
../guides/advanced/memory-and-orchestration/memory-management → ../guides/development/agent-memory/memory-management
```

### 4. Service Injection Patterns References
**Pattern**: `service-injection-patterns`  
**Target File**: `contributing/service-injection.md`  
**Frequency**: HIGH (appears in 20+ files)

```
# From docs root level:
./guides/advanced/service-injection-patterns → ./contributing/service-injection

# From subdirectories:
../guides/advanced/service-injection-patterns → ../contributing/service-injection
../../guides/advanced/service-injection-patterns → ../../contributing/service-injection
```

## Directory Reorganization Mappings

### Missing `guides/advanced/` Directory
**Mapped to**: `guides/development/agents/` (for agent-related content)

```
../guides/advanced/advanced-agent-types → ../guides/development/agents/advanced-agent-types
./guides/advanced/advanced-agent-types → ./guides/development/agents/advanced-agent-types
```

### Missing `guides/best-practices/` Directory
**Mapped to**: `guides/development/best-practices.md` (single file)

```
../guides/best-practices/ → ../guides/development/best-practices
./guides/best-practices/ → ./guides/development/best-practices
```

### Missing `guides/infrastructure/` Directory
**Mapped to**: `guides/development/services/` directory

```
# General directory references:
../guides/infrastructure/ → ../guides/development/services/
./guides/infrastructure/ → ./guides/development/services/

# Specific file references:
../guides/infrastructure/storage-services-overview → ../guides/development/services/storage/storage-services-overview
../guides/infrastructure/cloud-storage-integration → ../guides/development/services/storage/cloud-storage-integration
../guides/infrastructure/service-registry-patterns → ../guides/development/services/service-registry-patterns
```

### Missing `guides/operations/` Directory
**Mapped to**: `guides/deploying/` directory

```
# General directory references:
../guides/operations/ → ../guides/deploying/
./guides/operations/ → ./guides/deploying/

# Specific file references:
../guides/operations/testing-patterns → ../guides/development/testing
../guides/operations/execution-tracking → ../guides/deploying/monitoring
```

### Missing `guides/production/` Directory
**Mapped to**: `guides/deploying/` directory

```
# General directory references:
../guides/production/ → ../guides/deploying/
./guides/production/ → ./guides/deploying/

# Specific file references:
../guides/production/deployment → ../guides/deploying/deployment
../guides/production/monitoring → ../guides/deploying/monitoring
../guides/production/security → ../guides/deploying/deployment
../guides/production/performance → ../guides/deploying/deployment
```

## Relative Path Calculation Rules

### Rule 1: Determine Source File Location
1. **Docs Root** (`docs/filename.md`): Use `./` prefix
2. **One Level Deep** (`docs/category/filename.md`): Use `../` prefix  
3. **Two Levels Deep** (`docs/category/subcategory/filename.md`): Use `../../` prefix
4. **Three Levels Deep**: Use `../../../` prefix

### Rule 2: Calculate Target Path
1. Count directory levels between source and target
2. Use appropriate number of `../` to reach common parent
3. Add path from common parent to target file
4. Remove `.md` extension for internal Docusaurus links

### Rule 3: Docusaurus Conventions
- Internal links: Remove `.md` extension
- External links: Keep full extension
- Directory links: End with `/` for directories, without for files
- Case sensitive: Match exact case of file/directory names

## Validation Checklist

When fixing links, verify:

- [ ] **Source File Location**: Correctly identified relative to docs root
- [ ] **Target File Exists**: Confirmed target file exists in expected location
- [ ] **Relative Path Depth**: Correct number of `../` based on source location
- [ ] **Case Sensitivity**: Exact case match of file and directory names
- [ ] **Extension Handling**: `.md` removed for internal links
- [ ] **Directory vs File**: Correct trailing `/` for directories

## Common File Mappings Reference

### Existing File Structure (Verified)
```
docs/
├── api.md
├── core-features.md
├── getting-started.md
├── intro.md
├── playground.md
├── contributing/
│   ├── index.md
│   ├── service-injection.md
│   ├── dependency-injection.md
│   └── state-management.md
├── guides/
│   ├── deploying/
│   │   ├── index.md
│   │   ├── deployment.md
│   │   └── monitoring.md
│   ├── development/
│   │   ├── index.md
│   │   ├── best-practices.md
│   │   ├── testing.md
│   │   ├── agents/
│   │   │   ├── agent-development.md
│   │   │   ├── advanced-agent-types.md
│   │   │   └── custom-agents.md
│   │   ├── agent-memory/
│   │   │   └── memory-management.md
│   │   └── services/
│   │       ├── service-registry-patterns.md
│   │       └── storage/
│   │           ├── index.md
│   │           ├── storage-services-overview.md
│   │           └── cloud-storage-integration.md
│   └── learning-paths/
│       ├── index.md
│       └── core/
├── reference/
│   ├── index.md
│   ├── cli-commands.md
│   ├── csv-schema.md
│   └── agent-types.md
├── tutorials/
│   ├── index.md
│   ├── weather-bot.md
│   └── building-custom-agents.md
└── examples/
    └── index.md
```

## Implementation Priority

### Phase 1: High-Impact Core Files
1. `docs/api.md`
2. `docs/intro.md` 
3. `docs/contributing/index.md`
4. `docs/core-features.md`

### Phase 2: Frequently Referenced Patterns
1. Agent development contract references
2. Service injection patterns  
3. Memory management links
4. Getting started references

### Phase 3: Directory Mappings
1. Best practices directory references
2. Infrastructure directory references  
3. Operations directory references
4. Production directory references

### Phase 4: Cross-References
1. Tutorial cross-references
2. Example cross-references
3. Reference section internal links
4. Learning path navigation

## Testing and Validation

### Build Testing
```bash
# Test for broken links
npm run build

# Check for warnings in build output
# Look for "Broken link" warnings
```

### Manual Navigation Testing
1. **Core Navigation Paths**:
   - Intro → Getting Started → Tutorials
   - Tutorials → Guides → Reference
   - Contributing → Development Guides

2. **Cross-Reference Testing**:
   - Agent development links from tutorials
   - Service injection from contributing
   - Memory management from guides

3. **Directory Navigation**:
   - Best practices from development
   - Infrastructure services navigation
   - Operations/deployment consistency

## Maintenance Notes

- **File Creation**: This process only fixes links to existing files - no new files created
- **Content Preservation**: Only link targets changed, no content modifications
- **Sidebar Compatibility**: All changes maintain compatibility with `sidebars.ts` structure
- **SEO Impact**: Internal link structure maintained for SEO consistency

---

**Last Updated**: June 28, 2025  
**Next Review**: After all link fixes complete  
**Validation Status**: Ready for implementation
