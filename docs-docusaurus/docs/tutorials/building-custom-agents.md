---
sidebar_position: 3
title: Building Custom Agents
description: Learn how to build custom agents in AgentMap with Python classes, custom logic, and integration patterns.
keywords: [custom agents, agent development, Python agents, AgentMap development, custom logic, agent classes]
---

# Building Custom Agents

Learn how to create powerful custom agents in AgentMap that extend beyond the built-in agent types. Custom agents allow you to implement specialized business logic, integrate with external systems, and create reusable components for your workflows.

## Agent Development Fundamentals

### Basic Agent Structure

Every custom agent in AgentMap inherits from the base `Agent` class and implements the `execute` method:

```python
from agentmap.agents import BaseAgent

class CustomAgent(BaseAgent):
    def execute(self, input_data, context=None):
        """
        Execute the agent logic
        
        Args:
            input_data: Data passed from previous agent or workflow input
            context: Optional context parameters from CSV configuration
            
        Returns:
            Processed output data
        """
        # Your custom logic here
        result = self.process_data(input_data)
        return result
    
    def process_data(self, data):
        # Implement your custom processing logic
        return f"Processed: {data}"
```

### Agent Registration

Register your custom agent with AgentMap to use it in CSV workflows:

```python
from agentmap import AgentMap

# Create AgentMap instance
agent_map = AgentMap()

# Register your custom agent
agent_map.register_agent_type('custom', CustomAgent)

# Now you can use 'custom' as an AgentType in your CSV
```

## Building Practical Custom Agents

### Example 1: Email Sender Agent

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailSenderAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        # Get email configuration from services or environment
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.username = os.getenv('EMAIL_USERNAME')
        self.password = os.getenv('EMAIL_PASSWORD')
    
    def execute(self, input_data, context=None):
        """
        Send email based on input data
        
        Expected input_data format:
        {
            'to': 'recipient@example.com',
            'subject': 'Email subject',
            'body': 'Email body content'
        }
        """
        if not self.username or not self.password:
            raise ValueError("Email credentials not configured")
        
        # Parse input data
        if isinstance(input_data, str):
            # Simple text input - create basic email
            email_data = {
                'to': context.get('default_recipient', 'admin@example.com'),
                'subject': context.get('default_subject', 'AgentMap Notification'),
                'body': input_data
            }
        else:
            email_data = input_data
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = email_data['to']
        msg['Subject'] = email_data['subject']
        
        # Add body
        msg.attach(MIMEText(email_data['body'], 'plain'))
        
        # Send email
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            
            text = msg.as_string()
            server.sendmail(self.username, email_data['to'], text)
            server.quit()
            
            return {
                'status': 'success',
                'message': f"Email sent to {email_data['to']}",
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Failed to send email: {str(e)}",
                'timestamp': datetime.now().isoformat()
            }
```

### Example 2: Database Query Agent

```python
import psycopg2
import json

class DatabaseQueryAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        # Try to get database service from dependency injection
        self.db_service = self.get_service('database') if services else None
    
    def execute(self, input_data, context=None):
        """
        Execute database queries
        
        Context parameters:
        - query: SQL query to execute
        - connection_string: Database connection (if no service injected)
        - query_type: 'select' or 'execute'
        """
        query = context.get('query')
        query_type = context.get('query_type', 'select')
        
        if not query:
            raise ValueError("Database query not specified in context")
        
        # Get database connection
        if self.db_service:
            # Use injected database service
            if query_type == 'select':
                result = self.db_service.query(query, input_data)
            else:
                result = self.db_service.execute(query, input_data)
        else:
            # Use direct connection
            connection_string = context.get('connection_string')
            if not connection_string:
                raise ValueError("No database service or connection string provided")
            
            with psycopg2.connect(connection_string) as conn:
                with conn.cursor() as cursor:
                    # Replace placeholders in query with input data
                    if isinstance(input_data, dict):
                        formatted_query = query.format(**input_data)
                    else:
                        formatted_query = query.replace('{input}', str(input_data))
                    
                    cursor.execute(formatted_query)
                    
                    if query_type == 'select':
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        result = [dict(zip(columns, row)) for row in rows]
                    else:
                        result = {'affected_rows': cursor.rowcount}
        
        return result
```

### Example 3: API Integration Agent

```python
import requests
import json
from typing import Dict, Any

class APIIntegrationAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.session = requests.Session()
        # Get HTTP client service if available
        self.http_client = self.get_service('http_client') if services else None
    
    def execute(self, input_data, context=None):
        """
        Make API calls to external services
        
        Context parameters:
        - url: API endpoint URL
        - method: HTTP method (GET, POST, PUT, DELETE)
        - headers: Additional headers
        - auth_type: Authentication type (bearer, basic, api_key)
        - auth_value: Authentication credential
        """
        url = context.get('url')
        method = context.get('method', 'GET').upper()
        headers = context.get('headers', {})
        auth_type = context.get('auth_type')
        auth_value = context.get('auth_value')
        
        if not url:
            raise ValueError("API URL not specified in context")
        
        # Setup authentication
        if auth_type == 'bearer':
            headers['Authorization'] = f'Bearer {auth_value}'
        elif auth_type == 'api_key':
            headers['X-API-Key'] = auth_value
        elif auth_type == 'basic':
            # auth_value should be base64 encoded username:password
            headers['Authorization'] = f'Basic {auth_value}'
        
        # Prepare request data
        request_kwargs = {
            'headers': headers,
            'timeout': context.get('timeout', 30)
        }
        
        if method in ['POST', 'PUT', 'PATCH']:
            if isinstance(input_data, (dict, list)):
                request_kwargs['json'] = input_data
            else:
                request_kwargs['data'] = str(input_data)
        elif method == 'GET' and isinstance(input_data, dict):
            request_kwargs['params'] = input_data
        
        try:
            # Make API call
            if self.http_client:
                # Use injected HTTP client service
                if method == 'GET':
                    response = self.http_client.get(url, **request_kwargs)
                elif method == 'POST':
                    response = self.http_client.post(url, **request_kwargs)
                # Add other methods as needed
            else:
                # Use requests directly
                response = self.session.request(method, url, **request_kwargs)
                response.raise_for_status()
            
            # Process response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = response.text
            
            return {
                'status_code': response.status_code,
                'data': response_data,
                'headers': dict(response.headers),
                'success': True
            }
        
        except requests.exceptions.RequestException as e:
            return {
                'status_code': getattr(e.response, 'status_code', None),
                'error': str(e),
                'success': False
            }
```

## Advanced Agent Patterns

### Stateful Agents

```python
class StatefulAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.state = {}
        self.execution_count = 0
    
    def execute(self, input_data, context=None):
        self.execution_count += 1
        
        # Maintain state between executions
        state_key = context.get('state_key', 'default')
        if state_key not in self.state:
            self.state[state_key] = []
        
        self.state[state_key].append(input_data)
        
        return {
            'current_input': input_data,
            'execution_count': self.execution_count,
            'state_history': self.state[state_key],
            'state_size': len(self.state[state_key])
        }
```

### Async Agent

```python
import asyncio
import aiohttp

class AsyncAPIAgent(BaseAgent):
    async def execute_async(self, input_data, context=None):
        """Async version of execute method"""
        urls = input_data if isinstance(input_data, list) else [input_data]
        
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_url(session, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'total_requests': len(urls),
            'results': results,
            'successful': len([r for r in results if not isinstance(r, Exception)])
        }
    
    async def fetch_url(self, session, url):
        try:
            async with session.get(url) as response:
                return {
                    'url': url,
                    'status': response.status,
                    'data': await response.text()
                }
        except Exception as e:
            return {'url': url, 'error': str(e)}
    
    def execute(self, input_data, context=None):
        """Sync wrapper for async execution"""
        return asyncio.run(self.execute_async(input_data, context))
```

### Decorator-Based Agents

```python
from functools import wraps
import time

def retry(max_attempts=3, delay=1):
    """Decorator to add retry logic to agent execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, input_data, context=None):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(self, input_data, context)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                    continue
            
            raise last_exception
        return wrapper
    return decorator

def measure_execution_time(func):
    """Decorator to measure agent execution time"""
    @wraps(func)
    def wrapper(self, input_data, context=None):
        start_time = time.time()
        result = func(self, input_data, context)
        execution_time = time.time() - start_time
        
        if isinstance(result, dict):
            result['execution_time'] = execution_time
        else:
            result = {
                'data': result,
                'execution_time': execution_time
            }
        
        return result
    return wrapper

class RobustAgent(BaseAgent):
    @retry(max_attempts=3, delay=1)
    @measure_execution_time
    def execute(self, input_data, context=None):
        # Potentially failing operation
        if random.random() < 0.3:  # 30% chance of failure
            raise Exception("Random failure for testing")
        
        return f"Successfully processed: {input_data}"
```

## Using Custom Agents in CSV Workflows

### CSV Configuration

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
EmailWorkflow,ProcessData,,Process incoming data,custom,SendEmail,,input,processed_data,
EmailWorkflow,SendEmail,,"{'default_recipient': 'admin@company.com', 'default_subject': 'Data Processing Complete'}",email_sender,End,ErrorHandler,processed_data,email_result,
EmailWorkflow,End,,Workflow complete,echo,,,email_result,final_message,Email notification sent successfully!
EmailWorkflow,ErrorHandler,,Handle errors,echo,End,,error,error_message,Error in email workflow: {error}
```

### Registration and Execution

```python
from agentmap import AgentMap

# Create AgentMap instance
agent_map = AgentMap()

# Register all custom agents
agent_map.register_agent_type('email_sender', EmailSenderAgent)
agent_map.register_agent_type('database_query', DatabaseQueryAgent)
agent_map.register_agent_type('api_integration', APIIntegrationAgent)
agent_map.register_agent_type('custom', CustomAgent)

# Execute workflow
result = agent_map.execute_csv('email_workflow.csv', initial_input="Sample data to process")
print(result)
```

## Testing Custom Agents

### Unit Testing

```python
import unittest
from unittest.mock import Mock, patch

class TestEmailSenderAgent(unittest.TestCase):
    def setUp(self):
        self.agent = EmailSenderAgent()
    
    @patch('smtplib.SMTP')
    def test_email_sending_success(self, mock_smtp):
        # Setup mock
        mock_server = Mock()
        mock_smtp.return_value = mock_server
        
        # Test data
        input_data = {
            'to': 'test@example.com',
            'subject': 'Test Subject',
            'body': 'Test Body'
        }
        
        # Execute
        result = self.agent.execute(input_data)
        
        # Verify
        self.assertEqual(result['status'], 'success')
        mock_server.sendmail.assert_called_once()
    
    def test_missing_credentials(self):
        # Test without credentials
        with patch.dict('os.environ', {}, clear=True):
            agent = EmailSenderAgent()
            with self.assertRaises(ValueError):
                agent.execute({'to': 'test@example.com', 'subject': 'Test', 'body': 'Test'})
```

### Integration Testing

```python
class TestDatabaseQueryAgentIntegration(unittest.TestCase):
    def setUp(self):
        # Setup test database
        self.test_db_url = "postgresql://test:test@localhost:5432/test_db"
        self.agent = DatabaseQueryAgent()
    
    def test_select_query(self):
        context = {
            'query': 'SELECT * FROM test_table WHERE id = {id}',
            'query_type': 'select',
            'connection_string': self.test_db_url
        }
        
        input_data = {'id': 1}
        result = self.agent.execute(input_data, context)
        
        self.assertIsInstance(result, list)
        # Additional assertions based on expected data
```

## Best Practices

### 1. Error Handling
Always implement proper error handling in your custom agents:

```python
def execute(self, input_data, context=None):
    try:
        # Your logic here
        result = self.process_data(input_data)
        return result
    except ValueError as e:
        return {'error': f'Invalid input: {str(e)}', 'success': False}
    except Exception as e:
        self.logger.error(f"Unexpected error in {self.__class__.__name__}: {str(e)}")
        return {'error': 'Internal processing error', 'success': False}
```

### 2. Input Validation
Validate input data structure and types:

```python
def validate_input(self, input_data):
    required_fields = ['field1', 'field2']
    if isinstance(input_data, dict):
        missing_fields = [field for field in required_fields if field not in input_data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
    else:
        raise ValueError("Input must be a dictionary")
```

### 3. Logging
Use proper logging for debugging and monitoring:

```python
import logging

class CustomAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute(self, input_data, context=None):
        self.logger.info(f"Executing {self.__class__.__name__} with input: {input_data}")
        
        try:
            result = self.process_data(input_data)
            self.logger.info(f"Successfully processed data, result size: {len(str(result))}")
            return result
        except Exception as e:
            self.logger.error(f"Error processing data: {str(e)}")
            raise
```

### 4. Configuration Management
Use context parameters for agent configuration:

```python
def execute(self, input_data, context=None):
    # Get configuration with defaults
    timeout = context.get('timeout', 30)
    max_retries = context.get('max_retries', 3)
    batch_size = context.get('batch_size', 100)
    
    # Use configuration in processing logic
    # ...
```

### 5. Resource Management
Properly manage resources like connections and files:

```python
def execute(self, input_data, context=None):
    connection = None
    try:
        connection = self.get_connection()
        result = self.process_with_connection(connection, input_data)
        return result
    finally:
        if connection:
            connection.close()
```

## Advanced Topics

### Custom Agent Dependencies
For agents that depend on external libraries, create optional dependencies:

```python
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

class DataFrameAgent(BaseAgent):
    def __init__(self, services=None):
        if not HAS_PANDAS:
            raise ImportError("pandas is required for DataFrameAgent")
        super().__init__(services)
    
    def execute(self, input_data, context=None):
        df = pd.DataFrame(input_data)
        # Process with pandas
        return df.to_dict('records')
```

### Plugin Architecture
Create a plugin system for dynamic agent loading:

```python
import importlib
import os

class AgentLoader:
    @staticmethod
    def load_agents_from_directory(directory):
        agents = {}
        for filename in os.listdir(directory):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                spec = importlib.util.spec_from_file_location(
                    module_name, 
                    os.path.join(directory, filename)
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find agent classes in module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseAgent) and 
                        attr != BaseAgent):
                        agents[attr_name.lower()] = attr
        
        return agents
```

For more advanced agent development patterns and examples, see the [Agent Development Contract Guide](/docs/guides/advanced/agent-development-contract).
