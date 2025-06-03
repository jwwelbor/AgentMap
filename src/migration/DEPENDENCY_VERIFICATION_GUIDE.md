# AgentMap Migration Dependency Verification Guide

## Overview

This guide provides tools and procedures to verify dependency hierarchy compliance during AgentMap migrations. Following these procedures prevents test failures and integration issues.

## Dependency Hierarchy Levels

```
Level 1: Models (Foundation)
├── Node ✅
├── Graph ✅ 
├── ExecutionSummary ✅
└── Validation Models ✅

Level 2: Services (Business Logic)
├── GraphBuilderService ✅ (depends on: Graph, Node)
├── CompilationService ✅ (depends on: Graph, GraphBuilderService)
├── GraphRunnerService ⏳ (depends on: Graph, ExecutionSummary, CompilationService)
└── ValidationService ⏳ (depends on: Validation Models)

Level 3: Core (Application Entry Points)
├── CLI Handlers ⏳ (depends on: All Services)
├── API Endpoints ⏳ (depends on: All Services)
└── Serverless Handlers ⏳ (depends on: All Services)

Level 4: Integration (End-to-End)
├── E2E Tests ⏳ (depends on: All Levels)
└── Deployment Scripts ⏳ (depends on: All Levels)
```

## Pre-Migration Verification Checklist

### ✅ Step 1: Dependency Analysis

Before migrating any component, verify:

- [ ] All imported dependencies are already migrated
- [ ] No circular dependencies will be introduced
- [ ] Component belongs to correct architecture layer
- [ ] Import paths follow established patterns

### ✅ Step 2: Import Path Verification

**Correct Import Patterns:**
```python
# Models
from agentmap.models import Node, Graph, ExecutionSummary
from agentmap.models.node import Node

# Services
from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.services.compilation_service import CompilationService

# Migration utilities
from agentmap.migration_utils import MockLoggingService
```

**❌ Incorrect Patterns to Avoid:**
```python
# DON'T use src_new prefix
from src_new.agentmap.models import Node  # WRONG

# DON'T import upward in hierarchy
from agentmap.services.graph_builder_service import GraphBuilderService  # In models - WRONG

# DON'T create circular dependencies
from agentmap.models.node import Node  # In GraphBuilderService - OK
from agentmap.services.graph_builder_service import GraphBuilderService  # In Node model - WRONG
```

### ✅ Step 3: Test Pattern Verification

**Required Mock Service Patterns:**
```python
class TestMyService(unittest.TestCase):
    def setUp(self):
        # Use migration-safe mock services
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        
        # Create service with mocked dependencies
        self.service = MyService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_config_service
        )
    
    def test_service_logs_correctly(self):
        # Correct logger verification pattern
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "Expected message" 
                          for call in logger_calls if call[0] == "info"))
        
        # ❌ DON'T use self.mock_logger.info.assert_called_with()
```

### ✅ Step 4: Integration Test Patterns

**For Integration Tests:**
```python
class TestMyServiceIntegration(unittest.TestCase):
    def test_with_real_dependencies(self):
        # Use patch for mock functions that need return_value
        with patch.object(self.node_registry_service, 'prepare_for_assembly') as mock_prepare:
            mock_prepare.return_value = {"node": "config"}
            
            # Test logic here
            
            # Verify mock was called
            mock_prepare.assert_called_once()
```

## Automated Verification Tools

### Tool 1: Import Path Checker

```python
# Check import paths in a file
import ast
import sys
from pathlib import Path

def check_import_paths(file_path):
    """Check that file uses correct import paths."""
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read())
    
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith('src_new.'):
                errors.append(f"Line {node.lineno}: Don't use 'src_new.' prefix: {node.module}")
    
    return errors

# Usage: python check_imports.py path/to/file.py
```

### Tool 2: Dependency Hierarchy Validator

```python
def validate_dependency_hierarchy(component_path, component_type):
    """Validate that component follows dependency hierarchy rules."""
    
    LEVEL_RESTRICTIONS = {
        'models': [],  # Models can't import from other levels
        'services': ['models', 'migration_utils'],  # Services can import models and utils
        'core': ['models', 'services', 'migration_utils'],  # Core can import models and services
        'infrastructure': ['models']  # Infrastructure can only import models
    }
    
    allowed_imports = LEVEL_RESTRICTIONS.get(component_type, [])
    
    # Check imports in file
    with open(component_path, 'r') as f:
        content = f.read()
    
    # Look for agentmap imports
    import re
    agentmap_imports = re.findall(r'from agentmap\.(\w+)', content)
    
    violations = []
    for imp in agentmap_imports:
        if imp not in allowed_imports:
            violations.append(f"{component_type} cannot import from {imp}")
    
    return violations
```

### Tool 3: Mock Pattern Checker

```python
def check_mock_patterns(test_file_path):
    """Check that test file follows proper mock patterns."""
    with open(test_file_path, 'r') as f:
        content = f.read()
    
    issues = []
    
    # Check for anti-patterns
    if 'self.mock_logger.' in content:
        issues.append("Found 'self.mock_logger' - use 'self.service.logger.calls' pattern")
    
    if '.return_value =' in content and 'patch.object' not in content:
        issues.append("Found '.return_value' without patch.object - may be setting on real method")
    
    if 'src_new.agentmap' in content:
        issues.append("Found 'src_new.agentmap' import - use 'agentmap' directly")
    
    return issues
```

## Quick Verification Commands

### Command 1: Basic Import Check
```bash
cd C:\Users\jwwel\Documents\code\AgentMap

# Verify core imports work
python -c "
try:
    from agentmap.models import Node, Graph, ExecutionSummary
    print('✅ Models import OK')
except ImportError as e:
    print(f'❌ Models import failed: {e}')

try:
    from agentmap.services.graph_builder_service import GraphBuilderService
    from agentmap.services.compilation_service import CompilationService
    print('✅ Services import OK')
except ImportError as e:
    print(f'❌ Services import failed: {e}')
"
```

### Command 2: Test Pattern Check
```bash
# Run unit tests and check for mock-related failures
python -m pytest tests/unit/ -v --tb=short -k "not integration"

# Check for common mock issues
grep -r "self.mock_logger" tests/ && echo "❌ Found mock_logger anti-pattern" || echo "✅ No mock_logger issues"
grep -r "src_new.agentmap" tests/ && echo "❌ Found src_new import issues" || echo "✅ No src_new imports"
```

### Command 3: Circular Dependency Check
```bash
# Simple circular dependency check
python -c "
import sys
try:
    import agentmap
    print('✅ No circular dependencies detected')
except ImportError as e:
    print(f'❌ Possible circular dependency: {e}')
"
```

## Migration Workflow

### Before Starting Any Migration Task:

1. **Run Pre-Migration Checks**
   ```bash
   # Quick verification
   python check_dependencies.py --component [component-name] --type [models|services|core]
   ```

2. **Review Current State**
   ```bash
   cat src_new/migration/current-state.md
   cat src_new/migration/ARCHITECTURE.md  # Review dependency section
   ```

3. **Verify Prerequisites**
   - All dependencies already migrated
   - Tests use proper mock patterns
   - No circular dependencies

4. **Execute Migration**
   - Follow task-specific guidelines
   - Maintain dependency hierarchy
   - Use established patterns

5. **Post-Migration Validation**
   ```bash
   # Verify new component works
   python -c "from agentmap.[new-component] import [NewClass]; print('Import OK')"
   
   # Run affected tests
   python -m pytest tests/unit/test_[new-component].py -v
   ```

## Common Issues and Solutions

### Issue 1: `AttributeError: 'method' object has no attribute 'return_value'`

**Cause**: Trying to set `return_value` on a real method instead of a Mock
**Solution**: Use `patch.object()` to create a proper Mock:

```python
# ❌ Wrong
self.node_registry_service.prepare_for_assembly.return_value = {...}

# ✅ Correct
with patch.object(self.node_registry_service, 'prepare_for_assembly') as mock_method:
    mock_method.return_value = {...}
```

### Issue 2: `ModuleNotFoundError: No module named 'src_new.agentmap'`

**Cause**: Using incorrect import path with `src_new.` prefix
**Solution**: Remove `src_new.` prefix from imports:

```python
# ❌ Wrong
from src_new.agentmap.models import Node

# ✅ Correct
from agentmap.models import Node
```

### Issue 3: Circular Import Errors

**Cause**: Violating dependency hierarchy (e.g., models importing services)
**Solution**: Restructure imports to follow hierarchy:

```python
# ❌ Wrong (models importing services)
# In models/node.py
from agentmap.services.graph_builder_service import GraphBuilderService

# ✅ Correct (services importing models)  
# In services/graph_builder_service.py
from agentmap.models.node import Node
```

## Documentation Updates

When completing a migration:

1. **Update Current State**: Mark component as completed in `current-state.md`
2. **Update Dependency Graph**: Update status in `ARCHITECTURE.md`
3. **Document Patterns**: Add any new patterns to `TESTING_PATTERNS.md`
4. **Track Issues**: Note any issues encountered for future reference

---

*This verification guide ensures consistent, error-free migrations that maintain the integrity of the AgentMap architecture.*
