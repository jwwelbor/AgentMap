# AgentMap Host Integration Example

This example shows how to extend AgentMap with **your own custom agents and services** using host application integration.

## 🎯 What This Demonstrates

**Your Custom Services** → **Injected Into** → **Your Custom Agents** → **Used in Workflows**

Instead of being limited to AgentMap's built-in agents, you can:
- Define your own service interfaces (protocols)
- Implement services for your domain (database, email, etc.)
- Create agents that use these services automatically
- Run workflows with your enhanced agents

## 🚀 Quick Start

### 1. Run the Example
```bash
cd examples/host_integration
python integration_example.py
```

### 2. See Your Services in Action
Watch as:
- ✅ Your database service gets injected into database agents
- ✅ Your email service gets injected into email agents  
- ✅ Your agents coordinate multiple services
- ✅ Everything works through AgentMap's workflow system

## 📁 Key Files

### **Core Integration Files**
- **`host_protocols.py`** - Define service interfaces (what agents expect)
- **`host_services.py`** - Implement actual services (what gets injected) 
- **`custom_agents.py`** - Agents that use your services
- **`agentmap_config.yaml`** - Clean, focused configuration

### **Examples & Tests**
- **`integration_example.py`** - Complete working example
- **`test_basic_integration.py`** - Simple verification
- **`test_host_integration.py`** - Comprehensive tests

## 🏗️ How It Works

### 1. **Define Service Interface**
```python
# host_protocols.py
@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    @abstractmethod
    def configure_database_service(self, database_service: Any) -> None:
        """Agents implementing this get database services automatically"""
        ...
```

### 2. **Implement Your Service**
```python
# host_services.py
class DatabaseService:
    def execute_query(self, query: str) -> List[Dict]:
        # Your actual database logic here
        return self.connection.execute(query).fetchall()
```

### 3. **Create Agents That Use It**
```python
# custom_agents.py
class DatabaseAgent(BaseAgent, DatabaseServiceProtocol):
    def configure_database_service(self, database_service):
        self.database_service = database_service  # Auto-injected!
    
    def run(self, state):
        # Use your service
        users = self.database_service.execute_query("SELECT * FROM users")
        return {"users": users}
```

### 4. **Register & Configure**
```yaml
# agentmap_config.yaml
host_application:
  enabled: true
  services:
    database_service:
      enabled: true
      configuration:
        database_path: "my_app.db"
```

### 5. **AgentMap Handles the Magic**
- Automatically discovers your protocols
- Instantiates your services with configuration
- Injects services into compatible agents
- Runs workflows normally with enhanced agents

## 🔧 Customization

### Add Your Own Service

1. **Define Protocol**
```python
@runtime_checkable
class MyCustomServiceProtocol(Protocol):
    @abstractmethod
    def configure_my_custom_service(self, service: Any) -> None:
        pass
```

2. **Implement Service**
```python
class MyCustomService:
    def do_something(self):
        return "Hello from my service!"
```

3. **Create Agent**
```python
class MyCustomAgent(BaseAgent, MyCustomServiceProtocol):
    def configure_my_custom_service(self, service):
        self.my_service = service
    
    def run(self, state):
        result = self.my_service.do_something()
        return {"result": result}
```

4. **Configure It**
```yaml
host_application:
  services:
    my_custom_service:
      enabled: true
      configuration:
        my_setting: "value"
```

## 🎯 Key Benefits

- **🔌 Plug & Play** - Define once, use everywhere
- **🏗️ Clean Architecture** - Services separated from agents
- **⚙️ Auto-Injection** - No manual wiring needed
- **🔄 Reusable** - Same service, multiple agent types
- **🛡️ Type Safe** - Protocol-based validation
- **📈 Scalable** - Add services without touching existing code

## 📝 Configuration Options

### Minimal Setup
```yaml
host_application:
  enabled: true
  services:
    my_service:
      enabled: true
```

### With Custom Configuration
```yaml
host_application:
  enabled: true
  protocol_folders: ["my_protocols/"]
  services:
    my_service:
      enabled: true
      configuration:
        api_key: "${MY_API_KEY}"
        timeout: 30
        retries: 3
```

## 🧪 Testing

```bash
# Quick verification
python test_basic_integration.py

# Full test suite
python test_host_integration.py
```

## 🚀 Next Steps

1. **Adapt the example** to your domain
2. **Replace example services** with your real services
3. **Create agents** for your specific use cases
4. **Define workflows** using your custom agents
5. **Deploy** with your application

## 💡 Common Patterns

### Multi-Service Agents
```python
class CoordinatorAgent(BaseAgent, DatabaseServiceProtocol, EmailServiceProtocol):
    # Gets both database AND email services injected
    def run(self, state):
        # Use both services together
        data = self.database_service.get_data()
        self.email_service.send_report(data)
```

### Conditional Services
```python
def run(self, state):
    if hasattr(self, 'database_service'):
        # Use database if available
        return self.database_service.get_data()
    else:
        # Graceful fallback
        return {"message": "Database not available"}
```

### Service Composition
```python
@runtime_checkable
class FullStackProtocol(DatabaseServiceProtocol, EmailServiceProtocol, NotificationServiceProtocol, Protocol):
    pass  # Agent gets all three services!
```

This example provides a **complete foundation** for extending AgentMap with your own domain-specific services and agents! 🎉
