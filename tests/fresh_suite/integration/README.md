# GraphScaffoldService Integration Tests

This directory contains comprehensive integration tests for GraphScaffoldService that complement the existing excellent unit tests.

## What's New

### 🧪 **Integration Tests Added**
- **Real CSV Processing**: Tests using actual `gm_orchestration_2.csv` structure
- **Template Integration**: Tests actual template file processing with service dependencies
- **File System Operations**: Tests real file creation and directory management
- **CLI Workflow Integration**: Tests the actual scaffold command workflow
- **Service Dependency Verification**: Tests generated agents have correct service protocols

### 📁 **File Structure**
```
tests/fresh_suite/integration/
├── test_graph_scaffold_integration.py      # Main integration tests
├── test_graph_scaffold_cli_integration.py  # CLI workflow tests
└── ...

# Test runners (in project root)
├── run_scaffold_tests.py                   # Comprehensive test runner
└── verify_scaffold_tests.py                # Quick verification script
```

## 🚀 **Quick Start**

### 1. Verify Everything Works
```bash
python verify_scaffold_tests.py
```
This checks imports, dependencies, and basic functionality.

### 2. Run All Scaffold Tests
```bash
python run_scaffold_tests.py
```
This runs both existing unit tests and new integration tests.

### 3. Run Specific Test Suites
```bash
# Existing unit tests only
python -m pytest tests/fresh_suite/unit/services/test_graph_scaffold_service.py -v

# New integration tests only  
python -m pytest tests/fresh_suite/integration/test_graph_scaffold_integration.py -v

# CLI integration tests
python -m pytest tests/fresh_suite/integration/test_graph_scaffold_cli_integration.py -v
```

## 🎯 **Test Coverage**

### **Existing Unit Tests** ✅
- Service initialization and configuration
- Service requirement parsing (all 8 service types)
- CSV data collection with mocked data
- Agent/function scaffolding with mocked templates
- Error handling and edge cases
- Template variable preparation

### **New Integration Tests** 🆕
- **Real CSV Processing**: Tests with actual CSV structure like `gm_orchestration_2.csv`
- **Service Dependencies**: Verifies LLM, node_registry, CSV, memory services are properly injected
- **Template Integration**: Tests actual template file processing and variable substitution
- **File System Operations**: Tests real directory creation and file writing
- **Error Recovery**: Tests partial failure scenarios and graceful error handling
- **Performance Testing**: Tests with realistic graph sizes
- **CLI Workflow**: Tests the actual scaffold command integration

## 📊 **Real-World Test Scenarios**

### 1. **GM Orchestration CSV Structure**
Tests the exact structure from your `gm_orchestration_2.csv`:
```python
def test_scaffold_from_real_gm_orchestration_csv(self):
    # Creates input_agent.py, orchestrator_agent.py, combat_router_agent.py
    # Verifies service dependencies: llm, node_registry, csv, memory
```

### 2. **Service Dependency Injection**
```python
def test_agent_template_service_dependency_injection(self):
    # Tests that agents get correct service protocols:
    # - LLMServiceUser, CSVServiceUser, VectorServiceUser, etc.
    # - Proper service attributes and usage examples
```

### 3. **Template Variable Substitution**
```python
def test_template_variable_comprehensive_substitution(self):
    # Tests all template variables are properly substituted
    # No {variable} patterns remain in generated files
```

### 4. **CLI Workflow Integration**
```python
def test_scaffold_service_integration_isolated(self):
    # Tests the workflow your CLI command uses:
    # CSV → Service → Template → File Creation
```

## 🔧 **Integration with Your Workflow**

These tests directly support your real-world usage:

```bash
# Your command that creates builtin agent stubs
poetry run agentmap scaffold -g gm_orchestration --config agentmap_local_config.yaml --csv examples\gm_orchestration_2.csv
```

The integration tests verify:
1. ✅ `input_agent.py` is created correctly
2. ✅ `orchestrator_agent.py` has LLM and node_registry services
3. ✅ Service protocols are properly injected
4. ✅ Template variables are fully substituted
5. ✅ File system operations work correctly
6. ✅ Error handling is graceful

## 🛠️ **Troubleshooting**

### If `verify_scaffold_tests.py` fails:
1. Check that MockServiceFactory is working: `python -c "from tests.utils.mock_service_factory import MockServiceFactory; print('OK')"`
2. Check AgentMap imports: `python -c "from agentmap.services.graph_scaffold_service import GraphScaffoldService; print('OK')"`
3. Check dependencies are installed: `poetry install`

### If integration tests fail:
1. Run verification first: `python verify_scaffold_tests.py`
2. Check specific test output: `python -m pytest tests/fresh_suite/integration/test_graph_scaffold_integration.py::TestGraphScaffoldServiceIntegration::test_scaffold_from_real_gm_orchestration_csv -v -s`
3. Check file permissions in temp directories

### Common Issues:
- **Import errors**: Ensure AgentMap is properly installed with `poetry install`
- **Path issues**: Run tests from the AgentMap project root directory
- **Temp directory errors**: Check disk space and permissions

## 🎉 **Success Indicators**

When tests pass, you'll see:
```
✅ PASSED - Existing Unit Tests (MockServiceFactory patterns)
✅ PASSED - New Integration Tests (Real file operations)  
✅ PASSED - CLI Integration Tests (Service workflow)
✅ PASSED - Combined Unit + Integration Tests

🎯 Overall: 4/4 test suites passed
🎉 All GraphScaffoldService tests are working!
```

This means your scaffold command will:
- ✅ Create proper agent files
- ✅ Inject correct service dependencies 
- ✅ Handle errors gracefully
- ✅ Work with real CSV files like `gm_orchestration_2.csv`

## 💡 **Next Steps**

After tests pass:
1. Run your actual scaffold command
2. Verify generated agent files have expected content
3. Check that service dependencies are properly configured
4. Test the generated agents in your workflow

The integration tests ensure the scaffold service works correctly in real-world scenarios, not just with mocked data!
