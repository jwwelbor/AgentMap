# AgentMap API Service Specification

## Overview

The API Service feature adds HTTP API integration capabilities to AgentMap, enabling CSV-driven workflows to interact with external REST APIs. This follows AgentMap's clean architecture principles with proper separation of concerns between models, services, and agents.

## Architecture Design

### Core Components

```
Models (Data Containers)
├── APIRequest - HTTP request configuration
├── APIResponse - HTTP response data
├── AuthConfig - Authentication configuration
└── APIError - Error information

Services (Business Logic)
├── AuthService - Authentication handling
├── APIService - HTTP operations
└── APIConfigService - API configuration management

Agents (Execution Units)
└── APIAgent - CSV-configurable API calls
```

### Dependencies
- **requests** library for HTTP operations
- **pydantic** for request/response validation (optional)
- Existing AgentMap services (logging, state management, etc.)

## Technical Specifications

### 1. Data Models (`/models/api/`)

#### APIRequest Model
```python
@dataclass
class APIRequest:
    """Pure data container for HTTP API requests."""
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Any] = None
    timeout: float = 30.0
    
    def add_header(self, key: str, value: str) -> None:
        """Add a header to the request."""
        self.headers[key] = value
    
    def add_param(self, key: str, value: Any) -> None:
        """Add a query parameter."""
        self.params[key] = value
```

#### APIResponse Model
```python
@dataclass
class APIResponse:
    """Pure data container for HTTP API responses."""
    status_code: int
    headers: Dict[str, str]
    content: str
    json_data: Optional[Dict[str, Any]] = None
    success: bool = False
    error_message: Optional[str] = None
    request_duration: float = 0.0
    
    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return 200 <= self.status_code < 300
```

#### AuthConfig Model
```python
@dataclass
class AuthConfig:
    """Pure data container for authentication configuration."""
    auth_type: str  # "none", "api_key", "bearer", "basic"
    api_key: Optional[str] = None
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    header_name: str = "Authorization"
    key_location: str = "header"  # "header", "query", "body"
```

### 2. Authentication Service (`/services/auth_service.py`)

```python
class AuthService:
    """Handles different authentication patterns for API requests."""
    
    def __init__(self, logging_service: LoggingService):
        self.logger = logging_service.get_class_logger(self)
    
    def apply_authentication(
        self, 
        request: APIRequest, 
        auth_config: AuthConfig
    ) -> APIRequest:
        """Apply authentication to request based on config."""
        
    def _apply_api_key_auth(self, request: APIRequest, auth_config: AuthConfig) -> APIRequest:
        """Apply API key authentication."""
        
    def _apply_bearer_token_auth(self, request: APIRequest, auth_config: AuthConfig) -> APIRequest:
        """Apply Bearer token authentication."""
        
    def _apply_basic_auth(self, request: APIRequest, auth_config: AuthConfig) -> APIRequest:
        """Apply Basic authentication."""
```

### 3. API Service (`/services/api_service.py`)

```python
class APIService:
    """Core HTTP API calling service with error handling and logging."""
    
    def __init__(
        self, 
        auth_service: AuthService,
        app_config_service: AppConfigService,
        logging_service: LoggingService
    ):
        self.auth_service = auth_service
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self._session = None
    
    def call_api(
        self, 
        request: APIRequest, 
        auth_config: Optional[AuthConfig] = None
    ) -> APIResponse:
        """Make HTTP API call with proper error handling."""
        
    def _create_session(self) -> requests.Session:
        """Create configured requests session."""
        
    def _make_request(self, request: APIRequest) -> APIResponse:
        """Execute the actual HTTP request."""
        
    def _handle_response(self, response: requests.Response, start_time: float) -> APIResponse:
        """Convert requests.Response to APIResponse."""
        
    def _extract_json_safely(self, content: str) -> Optional[Dict[str, Any]]:
        """Safely extract JSON from response content."""
```

### 4. API Agent (`/agents/builtins/api_agent.py`)

```python
class APIAgent(BaseAgent):
    """Agent for making HTTP API calls configured via CSV."""
    
    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
        execution_tracking_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
        )
        self._api_service = None
    
    def configure_api_service(self, api_service: APIServiceProtocol) -> None:
        """Configure API service (called by DI container)."""
        self._api_service = api_service
        
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process API call based on CSV configuration and state."""
        
    def _build_request_from_inputs(self, inputs: Dict[str, Any]) -> APIRequest:
        """Build API request from CSV inputs and state."""
        
    def _substitute_variables(self, template: str, inputs: Dict[str, Any]) -> str:
        """Replace {variable} placeholders with actual values."""
        
    def _extract_response_data(
        self, 
        response: APIResponse, 
        extract_path: Optional[str] = None
    ) -> Any:
        """Extract specific data from API response."""
```

## CSV Configuration Format

### Basic API Agent CSV Columns

| Column | Required | Description | Example |
|--------|----------|-------------|---------|
| `name` | Yes | Node name | `fetch_user` |
| `agent_type` | Yes | Must be `api_agent` | `api_agent` |
| `api_url` | Yes | API endpoint URL | `https://api.example.com/users/{user_id}` |
| `api_method` | No | HTTP method (default: GET) | `POST` |
| `auth_type` | No | Authentication type | `bearer_token` |
| `auth_key` | No | API key/token value | `sk-1234567890` |
| `response_field` | No | JSON path to extract | `user.email` |
| `timeout` | No | Request timeout in seconds | `30` |

### Example CSV Configurations

#### Simple GET Request
```csv
name,agent_type,api_url,method,auth_type,auth_key,response_field
get_weather,api_agent,https://api.openweathermap.org/data/2.5/weather?q=Chicago,GET,api_key,abc123,weather[0].description
```

#### POST with Dynamic Data
```csv
name,agent_type,api_url,method,auth_type,auth_key,request_body
create_user,api_agent,https://api.example.com/users,POST,bearer_token,sk-123,{"name": "{user_name}", "email": "{user_email}"}
```

#### Webhook Call
```csv
name,agent_type,api_url,method,request_body
notify_slack,api_agent,https://hooks.slack.com/services/T00/B00/XXX,POST,{"text": "Process completed: {result}"}
```

## Variable Substitution

### Supported Placeholder Formats
- `{variable_name}` - Replace with value from state
- `{input.field_name}` - Replace with specific input field
- `{response.previous_node.field}` - Replace with data from previous node response

### Examples
```python
# URL substitution
"https://api.example.com/users/{user_id}/posts/{post_id}"

# Header substitution  
"Authorization: Bearer {auth_token}"

# Body substitution
'{"user_id": "{user_id}", "message": "{user_message}"}'
```

## Authentication Patterns

### 1. No Authentication
```csv
auth_type,auth_key
none,
```

### 2. API Key in Header
```csv
auth_type,auth_key
api_key,your-api-key-here
```
Results in: `X-API-Key: your-api-key-here`

### 3. Bearer Token
```csv
auth_type,auth_key
bearer_token,your-token-here
```
Results in: `Authorization: Bearer your-token-here`

### 4. Basic Authentication
```csv
auth_type,auth_key
basic_auth,username:password
```
Results in: `Authorization: Basic base64(username:password)`

## Error Handling Strategy

### Error Categories
1. **Configuration Errors** - Invalid CSV setup
2. **Network Errors** - Connection timeouts, DNS failures
3. **HTTP Errors** - 4xx/5xx status codes
4. **Authentication Errors** - Invalid credentials
5. **Response Parsing Errors** - Invalid JSON, missing fields

### Error Response Format
```python
{
    "success": False,
    "error_type": "http_error",
    "error_message": "API returned 404: User not found",
    "status_code": 404,
    "response_body": "...",
    "request_url": "https://api.example.com/users/123"
}
```

## Security Considerations

### 1. Credential Management
- **Never store credentials in CSV files directly**
- Use environment variables: `{env:API_KEY}`
- Reference auth configs by name: `auth_config:production_api`
- Support external credential stores

### 2. Input Validation
- Validate URLs to prevent SSRF attacks
- Sanitize user inputs before substitution
- Limit allowed domains (configurable whitelist)

### 3. Logging Security
- Never log full request/response bodies containing sensitive data
- Mask authentication headers in logs
- Configurable log levels for debugging vs production

## Implementation Phases

### Phase 1: MVP (Core Functionality)
**Scope:** Basic GET/POST with simple authentication
- [x] Data models (APIRequest, APIResponse, AuthConfig)
- [x] AuthService with API key and Bearer token support
- [x] APIService with basic HTTP operations  
- [x] APIAgent with CSV configuration
- [x] Variable substitution for URLs and headers
- [x] Basic error handling and logging

**Supported Features:**
- GET and POST methods only
- API key and Bearer token authentication
- JSON response parsing
- Simple variable substitution
- Basic error handling

### Phase 2: Enhanced Features
**Scope:** Production-ready capabilities
- [ ] All HTTP methods (PUT, DELETE, PATCH)
- [ ] Request/response middleware
- [ ] Retry logic with exponential backoff
- [ ] Rate limiting compliance
- [ ] Response caching
- [ ] Request/response logging configuration

### Phase 3: Advanced Integration
**Scope:** Complex workflows and enterprise features
- [ ] OAuth2 support (authorization code flow)
- [ ] Pagination handling
- [ ] Bulk operations
- [ ] Request batching
- [ ] WebSocket support
- [ ] GraphQL support

### Phase 4: Enterprise Features
**Scope:** Production deployment and management
- [ ] External credential stores (AWS Secrets Manager, HashiCorp Vault)
- [ ] API usage analytics and monitoring
- [ ] Circuit breaker pattern
- [ ] Load balancing across API endpoints
- [ ] Request/response transformation pipelines

## Testing Strategy

### Unit Tests
- Mock all HTTP calls using `responses` library
- Test authentication application
- Test variable substitution
- Test error handling scenarios

### Integration Tests
- Use httpbin.org for real HTTP testing
- Test against public APIs (with rate limiting consideration)
- Test authentication flows end-to-end

### Example Test Cases
```python
def test_api_key_authentication():
    """Test API key is properly added to headers."""
    
def test_variable_substitution_in_url():
    """Test {variable} replacement in URLs."""
    
def test_json_response_parsing():
    """Test JSON response extraction."""
    
def test_network_error_handling():
    """Test behavior when API is unavailable."""
    
def test_rate_limit_handling():
    """Test 429 status code handling."""
```

## Usage Examples

### Example 1: Weather Integration
```csv
name,agent_type,api_url,method,auth_type,auth_key,response_field
get_weather,api_agent,https://api.openweathermap.org/data/2.5/weather?q={city},GET,api_key,your-key,weather[0].description
```

### Example 2: CRM Integration Workflow
```csv
name,agent_type,api_url,method,auth_type,auth_key,request_body,response_field
check_user,api_agent,https://api.crm.com/users/{email},GET,bearer_token,sk-123,,user.id
create_user,api_agent,https://api.crm.com/users,POST,bearer_token,sk-123,"{""email"":""{email}"",""name"":""{name}""}",user.id
update_status,api_agent,https://api.crm.com/users/{user_id}/status,PUT,bearer_token,sk-123,"{""status"":""active""}",success
```

### Example 3: Slack Notification
```csv
name,agent_type,api_url,method,request_body
notify_team,api_agent,https://hooks.slack.com/services/T00/B00/XXX,POST,"{""text"":""User {user_name} has been processed successfully""}"
```

## Configuration Reference

### API Service Configuration (`config.yaml`)
```yaml
api:
  default_timeout: 30
  max_retries: 3
  retry_delay: 1.0
  max_response_size: 10485760  # 10MB
  allowed_domains:
    - "api.example.com"
    - "hooks.slack.com"
    - "api.github.com"
  
  # Security settings
  security:
    validate_ssl: true
    max_redirects: 5
    allow_private_ips: false
  
  # Logging settings  
  logging:
    log_requests: true
    log_responses: true
    mask_headers:
      - "Authorization"
      - "X-API-Key"
    max_body_log_size: 1000
```

## Future Considerations

### Potential Extensions
1. **GraphQL Support** - Query building and response parsing
2. **WebSocket Integration** - Real-time API communication
3. **API Mocking** - Built-in mock server for testing
4. **API Documentation Generation** - Auto-generate API docs from CSV configs
5. **Performance Monitoring** - Track API response times and success rates

### Integration Opportunities
1. **LLM Integration** - Use LLMs to generate API requests or parse responses
2. **Storage Integration** - Save API responses to CSV/JSON automatically
3. **Workflow Orchestration** - Complex API call sequences with conditional logic

## Implementation Checklist

### Phase 1 Tasks
- [ ] Create data models in `/models/api/`
- [ ] Implement AuthService in `/services/`
- [ ] Implement APIService in `/services/`
- [ ] Create APIAgent in `/agents/builtins/`
- [ ] Add API protocols to `/services/protocols.py`
- [ ] Update DI container with new services
- [ ] Create comprehensive unit tests
- [ ] Write integration tests with httpbin.org
- [ ] Document CSV configuration format
- [ ] Create example workflows

### Documentation Required
- [ ] API Service user guide
- [ ] Authentication setup guide  
- [ ] CSV configuration reference
- [ ] Common API integration examples
- [ ] Troubleshooting guide
- [ ] Security best practices

This specification provides a comprehensive roadmap for implementing API integration capabilities in AgentMap while maintaining the project's clean architecture principles and CSV-first philosophy.