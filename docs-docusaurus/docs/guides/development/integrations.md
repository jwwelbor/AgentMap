---
title: "Integration Patterns"
description: "Master AgentMap integrations with LangChain memory, custom host services, external APIs, and enterprise systems. Build powerful, extensible AI workflows."
sidebar_position: 5
keywords:
  - integration patterns
  - langchain integration
  - host services
  - external apis
  - custom services
  - protocol integration
  - dependency injection
---

# Integration Patterns

AgentMap provides multiple integration patterns to extend functionality and connect with external systems. This guide covers the major integration approaches: LangChain memory, custom host services, external APIs, and enterprise systems.

:::info Integration Approaches
- **LangChain Memory**: Advanced conversation memory with multiple strategies
- **Host Services**: Custom service injection using protocols
- **External APIs**: HTTP, REST, and GraphQL integrations
- **Enterprise Systems**: Database, message queue, and microservice patterns
:::

---

## LangChain Memory Integration

AgentMap integrates seamlessly with LangChain memory components for sophisticated conversation management.

### Memory Types and Strategies

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
<TabItem value="buffer" label="Buffer Memory" default>

**Buffer Memory** stores complete conversation history without limitations.

```csv title="Buffer Memory Configuration"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatBot,Conversation,,"{'memory':{'type':'buffer','memory_key':'chat_history'}}",claude,Next,Error,user_input|chat_history,response,Human: {user_input}
```

**Best for**: Short conversations where all context is needed

</TabItem>
<TabItem value="window" label="Buffer Window Memory">

**Buffer Window Memory** keeps only the most recent `k` interactions.

```csv title="Window Memory Configuration"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatBot,Conversation,,"{'memory':{'type':'buffer_window','k':10,'memory_key':'chat_history'}}",claude,Next,Error,user_input|chat_history,response,Human: {user_input}
```

**Best for**: Longer conversations where recent context is most important

</TabItem>
<TabItem value="summary" label="Summary Memory">

**Summary Memory** maintains a running summary instead of storing all exchanges.

```csv title="Summary Memory Configuration"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatBot,Conversation,,"{'memory':{'type':'summary','memory_key':'chat_history'}}",claude,Next,Error,user_input|chat_history,response,Human: {user_input}
```

**Best for**: Very long conversations where overall context matters more than specific details

</TabItem>
<TabItem value="token" label="Token Buffer Memory">

**Token Buffer Memory** limits memory based on token count rather than message count.

```csv title="Token Buffer Memory Configuration"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatBot,Conversation,,"{'memory':{'type':'token_buffer','max_token_limit':4000,'memory_key':'chat_history'}}",claude,Next,Error,user_input|chat_history,response,Human: {user_input}
```

**Best for**: Precise control over token usage and cost optimization

</TabItem>
</Tabs>

### Memory Configuration Reference

| Parameter | Description | Default | Type |
|-----------|-------------|---------|------|
| `type` | Memory strategy | `"buffer"` | `"buffer"`, `"buffer_window"`, `"summary"`, `"token_buffer"` |
| `memory_key` | State field for memory storage | `"conversation_memory"` | String |
| `k` | Window size (buffer_window) | `5` | Integer |
| `max_token_limit` | Token limit (token_buffer) | `2000` | Integer |

### Multi-Agent Memory Sharing

Share memory across multiple agents in a workflow:

```csv title="Shared Memory Workflow"
Support,GetQuery,,Get user query,input,Classify,,query,user_query,How can we help you today?
Support,Classify,,"{'memory':{'type':'buffer_window','k':5,'memory_key':'support_session'}}",claude,RouteQuery,Error,user_query|support_session,query_type,Classify this query: {user_query}
Support,ProductSpecialist,,"{'memory':{'type':'buffer_window','k':5,'memory_key':'support_session'}}",openai,End,Error,user_query|support_session,response,"You are a product specialist. User: {user_query}"
Support,TechSupport,,"{'memory':{'type':'buffer_window','k':5,'memory_key':'support_session'}}",openai,End,Error,user_query|support_session,response,"You are a technical support agent. User: {user_query}"
```

---

## Host Service Integration

Extend AgentMap with custom services using protocol-based dependency injection.

### Protocol Definition

Define service interfaces using Python protocols:

```python title="Custom Service Protocol"
from typing import Protocol, runtime_checkable, Any
from abc import abstractmethod

@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    """Protocol for agents that need database access."""
    
    @abstractmethod
    def configure_database_service(self, database_service: Any) -> None:
        """Configure the agent with a database service."""
        ...
```

### Service Implementation

Create concrete service classes:

```python title="Database Service Implementation"
class DatabaseService:
    """Database service for AgentMap integration."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.connection_string = config.get("connection_string")
        
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute database query and return results."""
        try:
            # Database implementation here
            results = self._execute_sql(query, params)
            return {"success": True, "data": results}
        except Exception as e:
            self.logger.error(f"Database query failed: {e}")
            return {"success": False, "error": str(e)}
```

### Custom Agent with Service

Build agents that implement protocols to receive services:

```python title="Database Agent"
from agentmap.agents.base_agent import BaseAgent

class DatabaseAgent(BaseAgent, DatabaseServiceProtocol):
    """Agent that performs database operations."""
    
    def configure_database_service(self, database_service: Any) -> None:
        """Configure database service (called automatically)."""
        self.database_service = database_service
        self.log_debug("Database service configured")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Execute database operations."""
        if not self.database_service:
            return {"error": "Database service not available"}
        
        operation = inputs.get("operation", "query")
        
        if operation == "get_users":
            return self.database_service.execute_query("SELECT * FROM users")
        elif operation == "insert_user":
            user_data = inputs.get("user_data", {})
            return self.database_service.execute_query(
                "INSERT INTO users (name, email) VALUES (?, ?)",
                (user_data.get("name"), user_data.get("email"))
            )
        
        return {"error": f"Unknown operation: {operation}"}
```

### Service Registration

Register services with AgentMap's dependency injection container:

```python title="Service Registration"
from agentmap.di.containers import ApplicationContainer

def create_database_service(app_config_service, logging_service):
    """Factory function for database service."""
    config = app_config_service.get_host_service_config("database_service")
    logger = logging_service.get_logger("database_service")
    return DatabaseService(config["configuration"], logger)

# Register with AgentMap
container = ApplicationContainer()
container.register_host_factory(
    service_name="database_service",
    factory_function=create_database_service,
    dependencies=["app_config_service", "logging_service"],
    protocols=[DatabaseServiceProtocol]
)

# Register agent
agent_registry = container.agent_registry_service()
agent_registry.register_agent("database", DatabaseAgent)
```

---

## External API Integration

Connect AgentMap workflows to external APIs and services.

### REST API Agent

Build agents that interact with REST APIs:

```python title="REST API Agent"
import requests
from typing import Dict, Any

class RestApiAgent(BaseAgent):
    """Agent for REST API integration."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # API configuration
        self.base_url = self.context.get("base_url", "")
        self.api_key = self.context.get("api_key", "")
        self.timeout = self.context.get("timeout", 30)
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
        }
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Make REST API calls based on inputs."""
        method = inputs.get("method", "GET").upper()
        endpoint = inputs.get("endpoint", "")
        data = inputs.get("data", {})
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
            elif method == "POST":
                response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=self.headers, timeout=self.timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=self.timeout)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            response.raise_for_status()
            
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.content else None,
                "url": url
            }
            
        except requests.RequestException as e:
            self.log_error(f"API request failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
```

### GraphQL Integration

Create agents for GraphQL API interaction:

```python title="GraphQL Agent"
import requests
import json

class GraphQLAgent(BaseAgent):
    """Agent for GraphQL API integration."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Execute GraphQL queries and mutations."""
        query = inputs.get("query", "")
        variables = inputs.get("variables", {})
        
        if not query:
            return {"error": "No GraphQL query provided"}
        
        endpoint = self.context.get("graphql_endpoint", "")
        api_key = self.context.get("api_key", "")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        
        payload = {
            "query": query,
            "variables": variables
        }
        
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.context.get("timeout", 30)
            )
            
            response.raise_for_status()
            result = response.json()
            
            if "errors" in result:
                return {
                    "success": False,
                    "errors": result["errors"],
                    "data": result.get("data")
                }
            
            return {
                "success": True,
                "data": result.get("data"),
                "query": query
            }
            
        except Exception as e:
            self.log_error(f"GraphQL query failed: {e}")
            return {"success": False, "error": str(e)}
```

---

## Enterprise System Integration

Integrate with enterprise systems like databases, message queues, and microservices.

### Database Integration

Advanced database operations with connection pooling:

```python title="Enterprise Database Agent"
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

class EnterpriseDBAgent(BaseAgent):
    """Agent for enterprise database integration."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # Database configuration
        self.connection_string = self.context.get("connection_string", "")
        self.pool_size = self.context.get("pool_size", 5)
        self.max_overflow = self.context.get("max_overflow", 10)
        
        # Create engine with connection pooling
        self.engine = create_engine(
            self.connection_string,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            echo=self.context.get("echo_sql", False)
        )
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Execute database operations with enterprise features."""
        operation = inputs.get("operation", "query")
        
        try:
            with self.engine.connect() as connection:
                if operation == "query":
                    return self._execute_query(connection, inputs)
                elif operation == "transaction":
                    return self._execute_transaction(connection, inputs)
                elif operation == "bulk_insert":
                    return self._bulk_insert(connection, inputs)
                else:
                    return {"error": f"Unknown operation: {operation}"}
                    
        except Exception as e:
            self.log_error(f"Database operation failed: {e}")
            return {"error": str(e)}
    
    def _execute_query(self, connection, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SELECT query."""
        query = inputs.get("query", "")
        params = inputs.get("params", {})
        
        result = connection.execute(text(query), params)
        rows = [dict(row._mapping) for row in result]
        
        return {
            "success": True,
            "data": rows,
            "row_count": len(rows)
        }
    
    def _execute_transaction(self, connection, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multiple operations in a transaction."""
        operations = inputs.get("operations", [])
        
        with connection.begin():
            results = []
            for op in operations:
                result = connection.execute(text(op["query"]), op.get("params", {}))
                results.append({
                    "affected_rows": result.rowcount,
                    "query": op["query"]
                })
        
        return {
            "success": True,
            "transaction_results": results
        }
```

### Message Queue Integration

Connect to message queues for asynchronous processing:

```python title="Message Queue Agent"
import json
import pika
from typing import Dict, Any

class MessageQueueAgent(BaseAgent):
    """Agent for message queue integration (RabbitMQ)."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # RabbitMQ configuration
        self.host = self.context.get("host", "localhost")
        self.port = self.context.get("port", 5672)
        self.username = self.context.get("username", "guest")
        self.password = self.context.get("password", "guest")
        self.virtual_host = self.context.get("virtual_host", "/")
        
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Handle message queue operations."""
        operation = inputs.get("operation", "publish")
        
        try:
            # Establish connection
            credentials = pika.PlainCredentials(self.username, self.password)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    virtual_host=self.virtual_host,
                    credentials=credentials
                )
            )
            channel = connection.channel()
            
            if operation == "publish":
                result = self._publish_message(channel, inputs)
            elif operation == "consume":
                result = self._consume_messages(channel, inputs)
            elif operation == "declare_queue":
                result = self._declare_queue(channel, inputs)
            else:
                result = {"error": f"Unknown operation: {operation}"}
            
            connection.close()
            return result
            
        except Exception as e:
            self.log_error(f"Message queue operation failed: {e}")
            return {"error": str(e)}
    
    def _publish_message(self, channel, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Publish message to queue."""
        queue_name = inputs.get("queue", "")
        message = inputs.get("message", {})
        
        # Declare queue if it doesn't exist
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
        )
        
        return {
            "success": True,
            "queue": queue_name,
            "message": message
        }
    
    def _consume_messages(self, channel, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Consume messages from queue."""
        queue_name = inputs.get("queue", "")
        max_messages = inputs.get("max_messages", 10)
        
        messages = []
        for _ in range(max_messages):
            method_frame, header_frame, body = channel.basic_get(queue=queue_name)
            if method_frame:
                try:
                    message = json.loads(body.decode())
                    messages.append(message)
                    channel.basic_ack(method_frame.delivery_tag)
                except json.JSONDecodeError:
                    messages.append({"raw_body": body.decode()})
                    channel.basic_ack(method_frame.delivery_tag)
            else:
                break
        
        return {
            "success": True,
            "queue": queue_name,
            "messages": messages,
            "count": len(messages)
        }
```

### Microservices Integration

Connect to microservice architectures:

```python title="Microservice Agent"
import requests
import consul
from typing import Dict, Any

class MicroserviceAgent(BaseAgent):
    """Agent for microservice integration with service discovery."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # Consul configuration for service discovery
        consul_host = self.context.get("consul_host", "localhost")
        consul_port = self.context.get("consul_port", 8500)
        self.consul = consul.Consul(host=consul_host, port=consul_port)
        
        # Circuit breaker configuration
        self.circuit_breaker_threshold = self.context.get("circuit_breaker_threshold", 5)
        self.circuit_breaker_timeout = self.context.get("circuit_breaker_timeout", 60)
        self.failed_requests = {}
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Call microservice with service discovery."""
        service_name = inputs.get("service", "")
        endpoint = inputs.get("endpoint", "")
        method = inputs.get("method", "GET")
        data = inputs.get("data", {})
        
        try:
            # Service discovery
            service_url = self._discover_service(service_name)
            if not service_url:
                return {"error": f"Service not found: {service_name}"}
            
            # Circuit breaker check
            if self._is_circuit_open(service_name):
                return {"error": f"Circuit breaker open for {service_name}"}
            
            # Make service call
            url = f"{service_url.rstrip('/')}/{endpoint.lstrip('/')}"
            response = self._make_request(method, url, data)
            
            # Record success
            self._record_success(service_name)
            
            return {
                "success": True,
                "service": service_name,
                "data": response
            }
            
        except Exception as e:
            # Record failure
            self._record_failure(service_name)
            self.log_error(f"Microservice call failed: {e}")
            return {"error": str(e)}
    
    def _discover_service(self, service_name: str) -> str:
        """Discover service URL using Consul."""
        try:
            _, services = self.consul.health.service(service_name, passing=True)
            if services:
                service = services[0]['Service']
                return f"http://{service['Address']}:{service['Port']}"
            return None
        except Exception as e:
            self.log_error(f"Service discovery failed: {e}")
            return None
    
    def _is_circuit_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for service."""
        if service_name not in self.failed_requests:
            return False
        
        failures = self.failed_requests[service_name]
        if failures['count'] >= self.circuit_breaker_threshold:
            time_since_last_failure = time.time() - failures['last_failure']
            return time_since_last_failure < self.circuit_breaker_timeout
        
        return False
    
    def _record_success(self, service_name: str):
        """Record successful request."""
        if service_name in self.failed_requests:
            del self.failed_requests[service_name]
    
    def _record_failure(self, service_name: str):
        """Record failed request."""
        if service_name not in self.failed_requests:
            self.failed_requests[service_name] = {'count': 0, 'last_failure': 0}
        
        self.failed_requests[service_name]['count'] += 1
        self.failed_requests[service_name]['last_failure'] = time.time()
```

---

## Configuration Examples

### LangChain Memory in CSV

```csv title="Memory Configuration Examples"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
# Buffer memory for short conversations
ChatBot,Basic,,"{'memory':{'type':'buffer'}}",claude,Next,Error,user_input|conversation_memory,response,Human: {user_input},Basic chat with full memory
# Window memory for longer conversations  
Support,Agent,,"{'memory':{'type':'buffer_window','k':8}}",openai,Next,Error,query|conversation_memory,response,Support agent: {query},Support with recent context
# Token-limited memory for cost control
Analysis,Agent,,"{'memory':{'type':'token_buffer','max_token_limit':3000}}",openai,Next,Error,data|conversation_memory,analysis,Analyze: {data},Cost-optimized analysis
```

### Host Service Configuration

```yaml title="Host Service Configuration (agentmap_config.yaml)"
host_application:
  enabled: true
  protocol_folders:
    - "protocols"
    - "custom_protocols"
  
  services:
    database_service:
      enabled: true
      configuration:
        connection_string: "${DATABASE_URL}"
        pool_size: 10
        max_overflow: 20
        
    api_service:
      enabled: true
      configuration:
        base_url: "${API_BASE_URL}"
        api_key: "${API_KEY}"
        timeout: 30
        retries: 3
        
    message_queue:
      enabled: true
      configuration:
        host: "${MQ_HOST}"
        port: 5672
        username: "${MQ_USERNAME}"
        password: "${MQ_PASSWORD}"
```

### Integration Workflow Example

```csv title="Complete Integration Workflow"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
DataPipeline,GetQuery,,"{'memory':{'type':'buffer_window','k':5}}",input,FetchData,Error,,user_query,What data do you need?,Collect user requirements
DataPipeline,FetchData,,Get from database,custom:DatabaseAgent,ProcessAPI,Error,user_query|conversation_memory,db_data,,Query database
DataPipeline,ProcessAPI,,"{'base_url':'${API_URL}','timeout':30}",custom:RestApiAgent,AnalyzeData,Error,db_data,api_data,,Enrich with API data
DataPipeline,AnalyzeData,,"{'memory':{'type':'buffer_window','k':5}}",openai,SendMessage,Error,db_data|api_data|conversation_memory,analysis,Analyze this data: {db_data} {api_data},AI analysis
DataPipeline,SendMessage,,"{'queue':'results'}",custom:MessageQueueAgent,End,Error,analysis,message_sent,,Send to queue
DataPipeline,Error,,Handle errors,echo,End,,error,error_message,,Error handling
DataPipeline,End,,Complete workflow,echo,,,analysis|error_message,result,,Workflow complete
```

---

## Best Practices

### Integration Design

1. **Start Simple**: Begin with basic integrations and add complexity gradually
2. **Handle Failures**: Always include error handling and recovery mechanisms
3. **Use Protocols**: Leverage protocol-based injection for clean architecture
4. **Monitor Performance**: Track integration performance and bottlenecks

### Memory Management

1. **Choose Appropriate Types**: Select memory strategy based on conversation length
2. **Share Memory Wisely**: Use same memory key for related agents
3. **Limit Memory Size**: Prevent unlimited growth in long conversations
4. **Test Memory Behavior**: Verify memory works as expected in workflows

### Service Integration

1. **Configuration Management**: Use environment variables for sensitive data
2. **Connection Pooling**: Use connection pools for database and network resources
3. **Circuit Breakers**: Implement circuit breakers for external service calls
4. **Graceful Degradation**: Provide fallback behavior when services fail

### Security Considerations

1. **Secret Management**: Never hardcode API keys or passwords
2. **Input Validation**: Validate all inputs to prevent injection attacks
3. **Network Security**: Use HTTPS and proper authentication
4. **Access Control**: Implement proper authorization and access controls

---

## Related Documentation

### **Core Concepts**
- **[Custom Agent Development](/docs/guides/development/agents/custom-agents)** - Building agents that use integrations
- **[Service Injection](/docs/contributing/service-injection)** - Understanding dependency injection patterns
- **[Memory Management](/docs/guides/development/agent-memory/memory-management)** - Basic memory concepts

### **Advanced Topics**
- **[Orchestration Patterns](./orchestration)** - Dynamic routing with memory
- **[Testing Strategies](./testing)** - Testing integrated workflows
- **[Best Practices](./best-practices)** - Development guidelines

### **Production**
- **[Deployment](/docs/guides/deploying/deployment)** - Deploying integrated workflows
- **[Monitoring](/docs/guides/deploying/monitoring)** - Monitoring integrations
- **[Security](/docs/guides/deploying/deployment)** - Securing integrated systems

---

*💡 **Pro Tip**: Start with LangChain memory for conversational features, then add custom services as your needs grow. The protocol-based approach makes it easy to add new integrations without changing existing code.*

**Last updated: June 28, 2025**
