# Environment Variable Resolution Example

This example demonstrates and verifies `env:` prefix syntax in `agentmap_config.yaml`.

## Quick Verification

Run the verification script to prove that `env:` values are resolved at config load time:

```bash
uv run python examples/env_resolution/verify_env_resolution.py
```

Expected output:

```
  [PASS] env:VAR (present): 'sk-test-openai-12345' == 'sk-test-openai-12345'
  [PASS] env:VAR (present): 'sk-ant-test-anthropic-67890' == 'sk-ant-test-anthropic-67890'
  [PASS] env:VAR:default (missing var): 'default-google-key' == 'default-google-key'
  [PASS] env:VAR:default (missing var): 'gemini-2.5-flash' == 'gemini-2.5-flash'
  [PASS] plain string (no env:): 'gpt-4.1-mini' == 'gpt-4.1-mini'

All checks passed.
```

## Usage in Your App

1. Copy `.env.example` to `.env` and fill in your API keys
2. Load `.env` into `os.environ` before AgentMap initializes:

```python
from dotenv import load_dotenv
load_dotenv()

from agentmap import run_workflow
result = run_workflow("MyWorkflow", initial_state={"message": "Hello!"})
```

## Syntax

| Pattern | Behavior |
|---------|----------|
| `env:VAR_NAME` | Resolves from `os.environ`; empty string if not set |
| `env:VAR_NAME:default` | Resolves from `os.environ`; uses `default` if not set |

The default value can contain colons (e.g., `env:ENDPOINT:http://localhost:8080`).
