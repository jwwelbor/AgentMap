# AgentMap — Azure Functions Starter

## Files
- `main.py` — thin adapter that delegates to AgentMap's Azure handlers
- `function.json` — Service Bus trigger binding
- `http_function.json` — HTTP trigger binding (optional testing)
- `requirements.txt` — AgentMap + Azure libs

## Deploy (Service Bus queue)
1. Create a Function App (Python 3.12) and Service Bus.
2. Set `ServiceBusConnection` app setting with connection string.
3. Deploy these files (via Azure Functions Core Tools or VS Code).

### Using Core Tools
```bash
func init . --python
func new --name servicebus_entry --template "Azure Service Bus Queue trigger" --language Python
# Replace generated files with the ones here (or set scriptFile to main.py).
func azure functionapp publish <YourFunctionAppName>
```

## Message Shape
JSON:
```json
{"graph":"Demo","state":{"hello":"world"},"action":"run"}
```
