# AgentMap Testing Patterns

This single reference merges the most useful ideas from **TESTING_PATTERNS.md** and **testing-patterns.md**, removing duplicate sections while preserving every unique insight.

---

## 0&nbsp;. Core Principles & Configuration Lens  
- **Pure `unittest.Mock` everywhere** – no custom mock classes or ad-hoc `@patch` trees.  
- Central **`MockServiceFactory`** for consistent, realistic service doubles.  
- **Centralised Path‑mocking utilities** to avoid read‑only `Path.exists/stat` traps.  
- **Security‑first mindset**: never test bypasses; authentication must be config‑driven.  
- **Real DI container** in container tests; keep infra pure (`ConfigService`), domain logic in `AppConfigService`, and fail‑fast `StorageConfigService`.  

---

## 1&nbsp;. Pure Mock Architecture with `MockServiceFactory`

```python
from tests.utils.mock_service_factory import MockServiceFactory

mock_logging  = MockServiceFactory.create_mock_logging_service()
mock_config   = MockServiceFactory.create_mock_app_config_service()
mock_registry = MockServiceFactory.create_mock_node_registry_service()
```

*Always inject these mocks directly; no module‑level patching needed.*

---

## 2&nbsp;. Service Test Template (canonical)

```python
class TestMyService(unittest.TestCase):
    def setUp(self):
        self.mock_cfg = MockServiceFactory.create_mock_app_config_service(
            {"my_config": {"enabled": True, "timeout": 30}}
        )
        MockServiceConfigHelper.configure_app_config_service(
            self.mock_cfg,
            {"csv_path": "graphs", "compiled_graphs_path": "compiled"}
        )
        self.mock_log = MockServiceFactory.create_mock_logging_service()
        self.service  = MyService(app_config_service=self.mock_cfg,
                                  logging_service=self.mock_log)
        self.logger   = self.service.logger
```

Focus each test on public behaviour; verify via `self.logger.calls` rather than private state.

---

## 3&nbsp;. Path & File‑System Mocking Patterns  

### 3.1 Preferred: Central Utilities  
Use the helpers in `tests.utils.path_mocking_utils`:

```python
with mock_compilation_currency(out_path, csv_path, is_current=True):
    self.assertTrue(self.service._is_compilation_current(...))
```

Or the fluent `PathOperationsMocker` for complex setups.

### 3.2 Fallback: Module‑Level `Path` Patching  
When a service builds fresh `Path()` objects internally, patch **that service’s import**, not `pathlib.Path`:

```python
with patch('agentmap.services.graph_builder_service.Path',
           side_effect=lambda *p, **k: mock_path):
    ...
```

> **Rule of thumb:** utilities first; only drop to manual patching when the service constructs its own `Path` instances.

---

## 4&nbsp;. `MockServiceFactory` Usage Snippets  
* Logging mocks expose `.calls` for “info / debug / error” tuples.  
* Config mocks accept override dicts or custom `side_effect` to model dynamic config.  
* Storage, LLM, registry, etc. have similar helpers—extend the factory instead of inventing new mocks.

---

## 5&nbsp;. Mock vs MagicMock  
Use bare **Mock** for services; reserve **MagicMock** for objects needing dunder support (e.g., dict‑like containers). The factory returns `Mock` by default.

---

## 6&nbsp;. Configuration Flexibility  
Override behaviour via `side_effect` functions, not `return_value`, because the factory already wires its own defaults.

---

## 6.1&nbsp;. Python 3.11 Mock Protocol Detection Issue ⚠️

**CRITICAL:** This is a recurring issue that causes tests to pass locally (Python 3.12+) but fail on CI (Python 3.11).

### The Problem

Python 3.11's `isinstance()` checking with `@runtime_checkable` protocols is more aggressive with `Mock` objects:

```python
@runtime_checkable
class NodeRegistryUser(Protocol):
    node_registry: Dict[str, Dict[str, Any]]
```

**Python 3.11**: `Mock()` objects can accidentally implement protocols due to dynamic attribute access
**Python 3.12+**: More conservative protocol detection

### Symptoms
- Tests pass locally but fail on CI with confusing errors
- Unexpected orchestrator detection (6 instead of 1)
- `add_edge` not called because mocks detected as orchestrators
- Error: `AssertionError: Expected 'add_edge' to be called once. Called 0 times.`

### ❌ BROKEN Pattern (causes CI failures):
```python
# DON'T DO THIS - Mock can accidentally implement NodeRegistryUser
mock_agent = Mock()
mock_agent.run = Mock(return_value={"result": "output"})
# isinstance(mock_agent, NodeRegistryUser) might return True on Python 3.11!
```

### ✅ FIXED Pattern (works on all Python versions):
```python
# DO THIS - Use create_autospec for constrained mocks
from unittest.mock import create_autospec

class BasicAgent:
    """Basic agent that explicitly does NOT implement NodeRegistryUser."""
    def run(self, state):
        return {"result": "output"}

# Constrained mock - only has BasicAgent attributes
mock_agent = create_autospec(BasicAgent, instance=True)
mock_agent.run.return_value = {"result": "output"}
# isinstance(mock_agent, NodeRegistryUser) will always be False
```

### For Real Protocol Implementations:
```python
# When you actually NEED a NodeRegistryUser, use a real class
class MockOrchestratorAgent:
    def __init__(self):
        self.node_registry: Dict[str, Dict[str, Any]] = {}  # Proper type
        
    def run(self, state):
        return {"result": "orchestrator_output"}

# Use the real class, not Mock
orchestrator = MockOrchestratorAgent()
```

### Key Rules:
1. **Use `create_autospec()` for non-protocol mocks** (agents, services)
2. **Use real classes for protocol implementations** (orchestrators)
3. **Ensure test isolation** - reset service state between tests
4. **Watch for CI vs local differences** - usually indicates this issue

### Test Isolation Pattern:
```python
def setUp(self):
    # ... create service ...
    
    # CRITICAL: Ensure clean state for each test
    self.assembly_service.orchestrator_nodes = []
    self.assembly_service.injection_stats = {
        "orchestrators_found": 0,
        "orchestrators_injected": 0,
        "injection_failures": 0
    }
```

**Remember:** If tests pass locally but fail on CI with protocol-related errors, this is likely the issue!

---

## 7&nbsp;. Advanced Patterns  
* **Stateful mocks** via closures to count calls.  
* **Exception testing**: raise from the mock, assert proper logging and wrapping.  
* **Multi‑service coordination**: inject several mocks and assert interactions.  

---

## 8&nbsp;. Security & Authentication Testing  
Follow the **config‑only, no header bypass** doctrine:

```python
auth = self.create_api_key_auth_service(valid_key)
headers = {"X-AgentMap-Embedded": "true"}        # has NO effect
resp = self.client.get('/info/cache', headers=headers)
self.assertEqual(resp.status_code, 401)
```

Key checklist: test enabled/disabled states, 401 vs 503 codes, permission matrices, and always restore the original container in `finally`.

---

## 9&nbsp;. CLI Testing Patterns  
Use `BaseCLITest`, real temp files, and mock only the service layer:

```python
with self.patch_container_creation(mock_container):
    result = self.run_cli_command(['compile', '--graph', 'demo'])
self.assert_cli_success(result)
```

Cover success, error, and end‑to‑end workflows; assert no stack traces leak to users.

---

## 10&nbsp;. Migration Guide (Old → New)

| Area            | Legacy                                   | New Pattern                                         |
|-----------------|------------------------------------------|-----------------------------------------------------|
| Imports         | `migration_utils.MockLoggingService`     | `MockServiceFactory` + Path utilities               |
| Path mocking    | Direct `Path.exists = Mock()`            | `PathOperationsMocker` / `mock_compilation_currency`|
| Auth tests      | Header bypass checks                     | Config‑driven tests with `set_app_container`        |
| Protocol mocks  | `Mock()` objects                         | `create_autospec()` for non-protocols               |

---

## 11&nbsp;. Anti‑Patterns to Avoid  
* Direct attribute assignment on `Path` objects.  
* Mixed `@patch` plus container swapping.  
* Adding business logic to **ConfigService**.  
* Writing tests that validate *insecure* behaviour.  
* **Using `Mock()` for agents** - use `create_autospec()` instead (Python 3.11 compatibility)  

---

## 12&nbsp;. Troubleshooting Quick Hits  
* **“AttributeError: WindowsPath attribute ‘exists’ is read‑only”** → use the utilities, not direct assignment.  
* **Mock call mismatch** → print `mock.method.call_args_list`.  
* **Factory config override ignored** → replace side‑effect, not return‑value.  
* **Tests pass locally but fail on CI** → likely Python 3.11 Mock protocol detection issue (see section 6.1)
* **Unexpected orchestrator count** → check for accidental `NodeRegistryUser` protocol implementation  

---

## 13&nbsp;. Testing Best Practices  
Organise tests by behaviour, reset mocks between tests, and feed **realistic data** to keep scenarios meaningful.  

---

## 14&nbsp;. Future Development Guidelines  
When adding a new service:  
1. Start with factory mocks.  
2. Copy the canonical test template.  
3. **Use `create_autospec()` for agent mocks** to avoid protocol detection issues.
4. Document any new pattern here to keep the guide authoritative.  

---

## 15&nbsp;. Summary Checklist  

- [ ] Use `MockServiceFactory` for every dependency.  
- [ ] Prefer `Path` utilities; patch service‑level `Path` only when unavoidable.  
- [ ] No security bypass tests; configuration decides auth.  
- [ ] Leverage `BaseCLITest` for CLI, realistic temp files, and service mocks.  
- [ ] Maintain clean separation of infra vs domain logic.  
- [ ] **Use `create_autospec()` for agent mocks** to prevent Python 3.11 protocol detection issues.
- [ ] Reset service state in `setUp()` for test isolation.
- [ ] Keep this guide updated with new patterns.

*Follow these consolidated patterns to keep the AgentMap test suite fast, reliable, secure, and maintainable.*
