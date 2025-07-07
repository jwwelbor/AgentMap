---
sidebar_position: 6
title: Dependency Injection Reference
description: Complete guide to AgentMap's dependency injection system for custom services, databases, and external integrations.
keywords: [dependency injection, service injection, AgentMap services, custom services, database injection, external services]
---

# Dependency Injection Reference

AgentMap provides a powerful dependency injection system that allows you to inject custom services, databases, and external integrations into your agent workflows. This enables clean separation of concerns and testable, maintainable code.

## Overview

The dependency injection system allows you to:
- Inject custom services into agents
- Provide database connections and storage services
- Configure external API clients
- Enable mocking and testing
- Maintain clean architecture patterns

## Basic Service Injection

### Registering Services

```python
from agentmap import AgentMap
from agentmap.services import ServiceContainer

# Create service container
container = ServiceContainer()

# Register a simple service
container.register('logger', logging.getLogger('agentmap'))

# Register with factory function
def create_database():
    return DatabaseConnection(url='postgresql://localhost:5432/agentmap')

container.register('database', create_database)

# Use container with AgentMap
agent_map = AgentMap(services=container)
```

### Using Services in Agents

```python
from agentmap.agents import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.logger = self.get_service('logger')
        self.database = self.get_service('database')
    
    def execute(self, input_data):
        self.logger.info(f"Processing: {input_data}")
        result = self.database.query("SELECT * FROM data")
        return result
```

## Service Types

### Database Services

```python
# PostgreSQL Service
class PostgreSQLService:
    def __init__(self, connection_string):
        self.conn = psycopg2.connect(connection_string)
    
    def query(self, sql, params=None):
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    
    def execute(self, sql, params=None):
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
        self.conn.commit()

# Registration
container.register('postgres', PostgreSQLService, 
                  connection_string='postgresql://localhost:5432/agentmap')
```

### Cache Services

```python
# Redis Cache Service
class RedisCacheService:
    def __init__(self, redis_url):
        self.redis = redis.from_url(redis_url)
    
    def get(self, key):
        return self.redis.get(key)
    
    def set(self, key, value, ttl=None):
        return self.redis.set(key, value, ex=ttl)
    
    def delete(self, key):
        return self.redis.delete(key)

# Registration
container.register('cache', RedisCacheService,
                  redis_url='redis://localhost:6379')
```

### External API Services

```python
# HTTP Client Service
class HTTPClientService:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})
    
    def get(self, endpoint, params=None):
        response = self.session.get(f"{self.base_url}{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint, data=None):
        response = self.session.post(f"{self.base_url}{endpoint}", json=data)
        response.raise_for_status()
        return response.json()

# Registration
container.register('api_client', HTTPClientService,
                  base_url='https://api.example.com',
                  api_key=os.getenv('API_KEY'))
```

## Advanced Service Patterns

### Service Interfaces

```python
from abc import ABC, abstractmethod

# Define service interface
class StorageInterface(ABC):
    @abstractmethod
    def save(self, key: str, data: any) -> bool:
        pass
    
    @abstractmethod
    def load(self, key: str) -> any:
        pass

# Implement concrete services
class FileStorageService(StorageInterface):
    def __init__(self, storage_path):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
    
    def save(self, key: str, data: any) -> bool:
        file_path = self.storage_path / f"{key}.json"
        with open(file_path, 'w') as f:
            json.dump(data, f)
        return True
    
    def load(self, key: str) -> any:
        file_path = self.storage_path / f"{key}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return None

class S3StorageService(StorageInterface):
    def __init__(self, bucket_name, aws_access_key, aws_secret_key):
        self.s3 = boto3.client('s3',
                              aws_access_key_id=aws_access_key,
                              aws_secret_access_key=aws_secret_key)
        self.bucket = bucket_name
    
    def save(self, key: str, data: any) -> bool:
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{key}.json",
            Body=json.dumps(data)
        )
        return True
    
    def load(self, key: str) -> any:
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=f"{key}.json")
            return json.loads(response['Body'].read())
        except self.s3.exceptions.NoSuchKey:
            return None
```

### Factory Pattern

```python
# Service Factory
class ServiceFactory:
    @staticmethod
    def create_storage_service(storage_type: str, **kwargs):
        if storage_type == 'file':
            return FileStorageService(kwargs.get('storage_path', './data'))
        elif storage_type == 's3':
            return S3StorageService(
                kwargs.get('bucket_name'),
                kwargs.get('aws_access_key'),
                kwargs.get('aws_secret_key')
            )
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")

# Registration with factory
container.register('storage', ServiceFactory.create_storage_service,
                  storage_type='file', storage_path='./data')
```

### Scoped Services

```python
# Singleton Service
class SingletonService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

# Per-workflow scoped service
class WorkflowScopedService:
    def __init__(self, workflow_id):
        self.workflow_id = workflow_id
        self.data = {}

# Registration with scopes
container.register('singleton_service', SingletonService, scope='singleton')
container.register('workflow_service', WorkflowScopedService, scope='workflow')
```

## Configuration-Based Injection

### Service Configuration

```yaml
# services.yaml
services:
  database:
    type: postgresql
    connection_string: postgresql://localhost:5432/agentmap
    pool_size: 10
    
  cache:
    type: redis
    url: redis://localhost:6379
    ttl: 3600
    
  storage:
    type: s3
    bucket_name: agentmap-storage
    region: us-west-2
    
  api_clients:
    weather:
      base_url: https://api.weather.com
      api_key: ${WEATHER_API_KEY}
    
    analytics:
      base_url: https://api.analytics.com
      api_key: ${ANALYTICS_API_KEY}
```

### Loading from Configuration

```python
import yaml
from agentmap.services import ServiceLoader

# Load services from configuration
with open('services.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create container from config
container = ServiceLoader.load_from_config(config['services'])

# Use with AgentMap
agent_map = AgentMap(services=container)
```

## Service Injection in CSV Workflows

### Accessing Services in Agent Context

```csv
graph_name,node_name,next_node,context,agent_type,next_on_success,next_on_failure,input_fields,output_field,prompt
DataWorkflow,LoadData,,"{'service': 'database'}",custom,ProcessData,,collection,raw_data,
DataWorkflow,ProcessData,,"{'services': ['cache', 'storage']}",custom,SaveResults,,raw_data,processed_data,
DataWorkflow,SaveResults,,"{'service': 'storage'}",custom,End,,processed_data,save_result,
```

### Custom Agent with Service Injection

```python
from agentmap.agents import Agent

class DataProcessingAgent(Agent):
    def execute(self, input_data, context=None):
        # Get services from context
        service_names = context.get('services', [])
        if isinstance(service_names, str):
            service_names = [service_names]
        
        services = {name: self.get_service(name) for name in service_names}
        
        # Use injected services
        if 'database' in services:
            db_data = services['database'].query("SELECT * FROM source_table")
        
        if 'cache' in services:
            cached_result = services['cache'].get(f"processed_{hash(str(input_data))}")
            if cached_result:
                return cached_result
        
        # Process data
        result = self.process_data(input_data)
        
        # Cache result
        if 'cache' in services:
            services['cache'].set(f"processed_{hash(str(input_data))}", result, ttl=3600)
        
        # Store result
        if 'storage' in services:
            services['storage'].save(f"result_{datetime.now().isoformat()}", result)
        
        return result
```

## Testing with Dependency Injection

### Mock Services

```python
import unittest
from unittest.mock import Mock

class TestAgentWithMocks(unittest.TestCase):
    def setUp(self):
        # Create mock services
        self.mock_database = Mock()
        self.mock_cache = Mock()
        self.mock_storage = Mock()
        
        # Create test container
        self.container = ServiceContainer()
        self.container.register('database', lambda: self.mock_database)
        self.container.register('cache', lambda: self.mock_cache)
        self.container.register('storage', lambda: self.mock_storage)
        
        # Create agent with mock services
        self.agent = DataProcessingAgent(services=self.container)
    
    def test_data_processing_with_cache_hit(self):
        # Setup mock responses
        self.mock_cache.get.return_value = "cached_result"
        
        # Execute agent
        result = self.agent.execute("test_input")
        
        # Verify behavior
        self.assertEqual(result, "cached_result")
        self.mock_cache.get.assert_called_once()
        self.mock_database.query.assert_not_called()
```

### Integration Testing

```python
# Test with real services in isolated environment
class TestAgentIntegration(unittest.TestCase):
    def setUp(self):
        # Setup test database
        self.test_db = create_test_database()
        
        # Create container with test services
        self.container = ServiceContainer()
        self.container.register('database', lambda: self.test_db)
        self.container.register('cache', InMemoryCacheService)
        self.container.register('storage', TempFileStorageService)
        
        self.agent_map = AgentMap(services=self.container)
    
    def test_full_workflow_integration(self):
        # Load test CSV
        result = self.agent_map.execute_csv('test_workflow.csv')
        
        # Verify results
        self.assertIsNotNone(result)
        # Additional assertions...
```

## Performance Considerations

### Service Connection Pooling

```python
# Database connection pool
class PooledDatabaseService:
    def __init__(self, connection_string, pool_size=10):
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            1, pool_size, connection_string
        )
    
    def get_connection(self):
        return self.pool.getconn()
    
    def return_connection(self, conn):
        self.pool.putconn(conn)
    
    def query(self, sql, params=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            self.return_connection(conn)
```

### Lazy Loading

```python
# Lazy service initialization
class LazyService:
    def __init__(self, factory_func, *args, **kwargs):
        self._factory = factory_func
        self._args = args
        self._kwargs = kwargs
        self._instance = None
    
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = self._factory(*self._args, **self._kwargs)
        return getattr(self._instance, name)

# Register lazy service
container.register('expensive_service', LazyService, 
                  ExpensiveService, connection_string='...')
```

## Best Practices

### 1. Interface Segregation
- Define clear interfaces for services
- Keep service interfaces focused and minimal
- Use dependency inversion principle

### 2. Service Lifecycle Management
- Properly manage service connections and resources
- Implement cleanup methods for services
- Use appropriate service scopes

### 3. Configuration Management
- Use configuration files for service setup
- Externalize connection strings and credentials
- Support environment-specific configurations

### 4. Error Handling
- Implement proper error handling in services
- Use circuit breaker patterns for external services
- Provide fallback mechanisms

### 5. Testing
- Design services to be easily mockable
- Use dependency injection for testability
- Separate unit tests from integration tests

## Common Patterns

### Repository Pattern

```python
class UserRepository:
    def __init__(self, database):
        self.db = database
    
    def find_by_id(self, user_id):
        return self.db.query("SELECT * FROM users WHERE id = %s", [user_id])
    
    def create(self, user_data):
        return self.db.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s)",
            [user_data['name'], user_data['email']]
        )

# Register repository
container.register('user_repository', UserRepository, 
                  database=container.get('database'))
```

### Service Layer Pattern

```python
class UserService:
    def __init__(self, user_repository, email_service):
        self.user_repo = user_repository
        self.email_service = email_service
    
    def create_user(self, user_data):
        user = self.user_repo.create(user_data)
        self.email_service.send_welcome_email(user['email'])
        return user
    
    def get_user(self, user_id):
        return self.user_repo.find_by_id(user_id)

# Register service layer
container.register('user_service', UserService,
                  user_repository=container.get('user_repository'),
                  email_service=container.get('email_service'))
```

For more advanced dependency injection patterns and examples, see the [Service Injection Patterns Guide](/docs/contributing/service-injection).
