# AgentMap Testing Patterns

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

---

## 11&nbsp;. Anti‑Patterns to Avoid  
* Direct attribute assignment on `Path` objects.  
* Mixed `@patch` plus container swapping.  
* Adding business logic to **ConfigService**.  
* Writing tests that validate *insecure* behaviour.  

---

## 12&nbsp;. Troubleshooting Quick Hits  
* **“AttributeError: WindowsPath attribute ‘exists’ is read‑only”** → use the utilities, not direct assignment.  
* **Mock call mismatch** → print `mock.method.call_args_list`.  
* **Factory config override ignored** → replace side‑effect, not return‑value.  

---

## 13&nbsp;. Testing Best Practices  
Organise tests by behaviour, reset mocks between tests, and feed **realistic data** to keep scenarios meaningful.  

---

## 14&nbsp;. Future Development Guidelines  
When adding a new service:  
1. Start with factory mocks.  
2. Copy the canonical test template.  
3. Document any new pattern here to keep the guide authoritative.  

---

## 15&nbsp;. Summary Checklist  

- [ ] Use `MockServiceFactory` for every dependency.  
- [ ] Prefer `Path` utilities; patch service‑level `Path` only when unavoidable.  
- [ ] No security bypass tests; configuration decides auth.  
- [ ] Leverage `BaseCLITest` for CLI, realistic temp files, and service mocks.  
- [ ] Maintain clean separation of infra vs domain logic.  
- [ ] Keep this guide updated with new patterns.

*Follow these consolidated patterns to keep the AgentMap test suite fast, reliable, secure, and maintainable.*
