---
title: Authentication Configuration
sidebar_position: 5
description: Complete guide to configuring authentication in AgentMap, including API keys, JWT tokens, permissions, and security settings.
keywords: [authentication, API keys, JWT, security, permissions, configuration]
---

# Authentication Configuration

AgentMap provides a flexible authentication system supporting multiple authentication methods, fine-grained permissions, and configurable security policies. This guide covers the complete authentication configuration including API key management, JWT tokens, Supabase integration, and security best practices.

## 🔐 Authentication Overview

The authentication system supports:

- **API Key Authentication** - Secure API keys with configurable permissions and expiration
- **JWT Token Authentication** - Industry-standard JSON Web Tokens (future implementation)
- **Supabase Integration** - Ready for Supabase authentication service (future implementation)
- **Permission-Based Access Control** - Fine-grained permissions for different user roles
- **Public Endpoints** - Configure which endpoints don't require authentication
- **Embedded Mode** - Special mode for local development and embedded applications

## 🚀 Quick Setup with CLI

The fastest way to set up authentication is using the built-in CLI commands:

### Initialize Authentication Configuration

```bash
# Create new authentication configuration in your config file
agentmap auth init --config agentmap_config.yaml

# Force overwrite existing auth configuration
agentmap auth init --config agentmap_config.yaml --force
```

This command will:
- Generate 4 different API keys with different permission levels
- Create a complete authentication configuration section
- Display the generated API keys and setup instructions

### Update API Keys

```bash
# Regenerate all API keys while preserving other auth settings
agentmap auth update --config agentmap_config.yaml
```

### View Authentication Configuration

```bash
# View configuration with masked API keys (secure)
agentmap auth view --config agentmap_config.yaml

# View configuration with actual API keys (WARNING: keys will be visible)
agentmap auth view --config agentmap_config.yaml --show-keys
```

## 📋 Complete Authentication Configuration

Add this section to your `agentmap_config.yaml` file:

```yaml
authentication:
  # Enable/disable authentication system
  enabled: true
  
  # API key authentication
  api_keys:
    admin:
      key: "your-admin-api-key-here"
      permissions: ["admin"]
      user_id: "admin"
      metadata:
        description: "Admin API key"
        created: "2024-01-15T10:30:00"
        created_by: "agentmap_cli"
    
    readonly:
      key: "your-readonly-api-key-here"  
      permissions: ["read"]
      user_id: "readonly"
      metadata:
        description: "Read-only API key"
        created: "2024-01-15T10:30:00"
        created_by: "agentmap_cli"
    
    executor:
      key: "your-executor-api-key-here"
      permissions: ["read", "execute"]
      user_id: "executor"
      metadata:
        description: "Execution API key"
        created: "2024-01-15T10:30:00"
        created_by: "agentmap_cli"
    
    developer:
      key: "your-developer-api-key-here"
      permissions: ["read", "write"]
      user_id: "developer"
      expires_at: "2024-04-15T10:30:00"  # Optional expiration
      metadata:
        description: "Developer API key with expiration"
        created: "2024-01-15T10:30:00"
        created_by: "agentmap_cli"
  
  # JWT configuration (future implementation)
  jwt:
    secret: "env:JWT_SECRET_KEY"  # Use environment variable
    algorithm: "HS256"
    expiry_hours: 24
  
  # Supabase integration (future implementation)
  supabase:
    url: "env:SUPABASE_URL"
    anon_key: "env:SUPABASE_ANON_KEY"
    jwt_secret: "env:SUPABASE_JWT_SECRET"
  
  # Public endpoints that don't require authentication
  public_endpoints:
    - "/"
    - "/health"
    - "/docs"
    - "/openapi.json"
    - "/redoc"
    - "/favicon.ico"
  
  # Embedded mode configuration
  embedded_mode:
    enabled: true      # Allow embedded mode
    bypass_auth: false # Require auth even in embedded mode
  
  # Permission system configuration
  permissions:
    default_permissions: ["read"]
    admin_permissions: ["read", "write", "execute", "admin"]
    execution_permissions: ["read", "execute"]
```

## 🔑 API Key Authentication

### API Key Structure

Each API key configuration includes:

```yaml
api_keys:
  key_name:
    key: "your-actual-api-key"           # The API key value
    permissions: ["read", "write"]       # List of permissions
    user_id: "unique-user-identifier"    # User identifier
    expires_at: "2024-12-31T23:59:59"   # Optional expiration (ISO format)
    metadata:                           # Optional metadata
      description: "Key description"
      created: "2024-01-15T10:30:00"
      created_by: "admin"
```

### Permission Levels

AgentMap supports four standard permission levels:

#### `read` - Read Access
- View workflows and configurations
- Access documentation and health endpoints
- Query system status and information

#### `write` - Write Access  
- Create and modify workflows
- Update configurations
- All `read` permissions

#### `execute` - Execution Access
- Run workflows and agents
- Execute system operations
- All `read` permissions

#### `admin` - Administrative Access
- All system operations
- User management
- Configuration management
- All `read`, `write`, and `execute` permissions

### Environment Variable API Keys

You can also configure API keys via environment variables:

```bash
# Windows CMD
set AGENTMAP_API_KEY_ADMIN=your-admin-key-here
set AGENTMAP_API_KEY_USER=your-user-key-here

# PowerShell
$env:AGENTMAP_API_KEY_ADMIN="your-admin-key-here"
$env:AGENTMAP_API_KEY_USER="your-user-key-here"

# Linux/macOS
export AGENTMAP_API_KEY_ADMIN="your-admin-key-here"
export AGENTMAP_API_KEY_USER="your-user-key-here"
```

Environment variable API keys automatically get `read` and `write` permissions.

### API Key Security

#### Key Generation
- Use cryptographically secure random generation
- Minimum 32 characters length recommended
- Use URL-safe base64 encoding

#### Key Storage
- API keys are hashed using SHA-256 before storage
- Original keys are never stored in plain text
- Use constant-time comparison to prevent timing attacks

#### Key Expiration
```yaml
developer:
  key: "your-key"
  permissions: ["read", "write"]
  expires_at: "2024-12-31T23:59:59"  # ISO 8601 format
```

## 🎫 JWT Authentication (Future Implementation)

JWT authentication will support:

```yaml
authentication:
  jwt:
    secret: "env:JWT_SECRET_KEY"    # Secret for signing tokens
    algorithm: "HS256"              # Signing algorithm
    expiry_hours: 24               # Token expiration time
    issuer: "agentmap"             # Token issuer
    audience: "agentmap-api"       # Token audience
```

**Security Requirements:**
- JWT secret must be at least 32 characters
- Use environment variables for secrets
- Tokens should have reasonable expiration times

## 🔗 Supabase Integration (Future Implementation)

Supabase authentication will support:

```yaml
authentication:
  supabase:
    url: "env:SUPABASE_URL"
    anon_key: "env:SUPABASE_ANON_KEY"
    jwt_secret: "env:SUPABASE_JWT_SECRET"
    
    # Role mapping
    role_mapping:
      authenticated: ["read", "write"]
      service_role: ["admin"]
      
    # User metadata mapping
    metadata_mapping:
      user_id: "id"
      username: "email"
      role: "role"
```

## 🌐 Public Endpoints

Configure which endpoints are accessible without authentication:

```yaml
authentication:
  public_endpoints:
    - "/"                    # Root endpoint
    - "/health"              # Health check
    - "/docs"                # API documentation
    - "/openapi.json"        # OpenAPI specification
    - "/redoc"               # ReDoc documentation
    - "/favicon.ico"         # Browser favicon
    - "/static/*"            # Static files (if needed)
```

**Security Note:** Be careful when adding public endpoints. Only include endpoints that are safe for unauthenticated access.

## 🏠 Embedded Mode Configuration

Embedded mode allows AgentMap to run in local development environments:

```yaml
authentication:
  embedded_mode:
    enabled: true       # Enable embedded mode
    bypass_auth: false  # Still require authentication in embedded mode
```

### Embedded Mode Options

#### `enabled: true, bypass_auth: true`
- **Use Case**: Local development, testing
- **Security**: No authentication required
- **Risk**: Low (local only)

#### `enabled: true, bypass_auth: false`  
- **Use Case**: Local development with security testing
- **Security**: Full authentication required
- **Risk**: Low (secure local development)

#### `enabled: false`
- **Use Case**: Production deployment
- **Security**: Full authentication required
- **Risk**: Lowest (production ready)

## 🛡️ Security Best Practices

### 1. Environment Variables for Secrets

Never store secrets in configuration files:

```yaml
# ✅ Good - Use environment variables
jwt:
  secret: "env:JWT_SECRET_KEY"

# ❌ Bad - Hardcoded secret
jwt:
  secret: "my-secret-key"
```

### 2. Strong API Keys

Generate secure API keys:

```bash
# Use the CLI to generate secure keys
agentmap auth init --config agentmap_config.yaml

# Or generate manually (32+ characters recommended)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Key Rotation

Regularly rotate API keys:

```bash
# Update all API keys
agentmap auth update --config agentmap_config.yaml

# Set expiration dates for time-limited access
```

### 4. Principle of Least Privilege

Grant minimum required permissions:

```yaml
# ✅ Good - Minimal permissions
analytics_service:
  permissions: ["read"]

# ❌ Bad - Excessive permissions  
analytics_service:
  permissions: ["admin"]
```

### 5. Monitor Authentication

Enable authentication logging and monitoring:

```yaml
logging:
  loggers:
    agentmap.auth_service:
      level: INFO
      handlers: [file]
```

## 🔧 Using Authentication in Applications

### FastAPI Integration

AgentMap automatically provides FastAPI authentication decorators:

```python
from deployment.http.api.dependencies import requires_auth


@app.get("/protected-endpoint")
@requires_auth(permissions=["read"])
async def protected_endpoint():
    """Endpoint requiring 'read' permission."""
    return {"message": "Access granted"}


@app.post("/admin-endpoint")
@requires_auth(permissions=["admin"])
async def admin_endpoint():
    """Endpoint requiring 'admin' permission."""
    return {"message": "Admin access granted"}
```

### API Client Usage

#### Using API Keys

```bash
# Via header
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/api/workflows

# Via query parameter  
curl http://localhost:8000/api/workflows?api_key=your-api-key-here
```

#### Python Client

```python
import requests

# Using headers
headers = {"X-API-Key": "your-api-key-here"}
response = requests.get("http://localhost:8000/api/workflows", headers=headers)

# Using session
session = requests.Session()
session.headers.update({"X-API-Key": "your-api-key-here"})
response = session.get("http://localhost:8000/api/workflows")
```

## 🔍 Configuration Validation

AgentMap automatically validates authentication configuration:

### Validation Checks

1. **Authentication Methods**: Warns if auth is enabled but no methods configured
2. **JWT Security**: Validates JWT secret length (minimum 32 characters)
3. **Public Endpoints**: Ensures public endpoints list is valid
4. **Permissions**: Validates permission structure and values
5. **Expiration Dates**: Checks ISO 8601 format for expiration dates

### Validation Commands

```bash
# Validate authentication configuration
agentmap validate --config agentmap_config.yaml --section authentication

# View validation results  
agentmap auth view --config agentmap_config.yaml
```

### Common Validation Issues

#### Warning: No Auth Methods Configured
```yaml
# Problem
authentication:
  enabled: true
  # No api_keys, jwt, or supabase configured

# Solution  
authentication:
  enabled: true
  api_keys:
    admin:
      key: "your-api-key-here"
      permissions: ["admin"]
```

#### Error: Weak JWT Secret
```yaml
# Problem
jwt:
  secret: "weak"  # Too short

# Solution
jwt:
  secret: "env:JWT_SECRET_KEY"  # Use strong secret from environment
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Authentication Always Fails

**Check:**
- Authentication is enabled: `authentication.enabled: true`
- API key is correctly configured in config file or environment variables
- API key format is correct (no extra spaces, quotes)
- API key has required permissions

**Solution:**
```bash
# Verify auth configuration
agentmap auth view --config agentmap_config.yaml

# Check API key hash matches
agentmap auth view --config agentmap_config.yaml --show-keys
```

#### 2. Can't Access Public Endpoints

**Check:**
- Endpoint is listed in `public_endpoints` configuration
- Endpoint path matches exactly (including leading slash)
- Authentication isn't bypassing public endpoint check

**Solution:**
```yaml
authentication:
  public_endpoints:
    - "/health"     # ✅ Correct format
    - "health"      # ❌ Missing leading slash
```

#### 3. Environment Variables Not Loading

**Check:**
- Environment variable name follows pattern: `AGENTMAP_API_KEY_*`
- Variable is set in current environment
- No typos in variable name

**Solution:**
```bash
# Windows - Verify environment variable
echo %AGENTMAP_API_KEY_ADMIN%

# PowerShell - Verify environment variable  
$env:AGENTMAP_API_KEY_ADMIN

# Set if missing
$env:AGENTMAP_API_KEY_ADMIN="your-key-here"
```

#### 4. Permissions Denied

**Check:**
- User has required permissions for the endpoint
- Permission names are spelled correctly
- Admin users have "admin" permission for full access

**Solution:**
```yaml
# Grant additional permissions
api_keys:
  user:
    key: "user-key"
    permissions: ["read", "execute"]  # Add "execute" permission
```

### Debug Logging

Enable detailed authentication logging:

```yaml
logging:
  loggers:
    agentmap.auth_service:
      level: DEBUG
      handlers: [console]
    agentmap.infrastructure.api.fastapi.middleware.auth:
      level: DEBUG  
      handlers: [console]
```

This will log:
- Authentication attempts
- Permission checks
- API key validation results
- Public endpoint access

## 📖 Next Steps

1. **Set Up Authentication** - Use `agentmap auth init` to create initial configuration
2. **Configure Storage** - Review [Storage Configuration](./storage-config) for data security
3. **Deploy Securely** - Check [Deployment Guide](../deployment/) for production security
4. **Monitor Access** - Set up logging and monitoring for authentication events

## 🔗 Related Documentation

- [Environment Variables](./environment-variables) - Managing secrets securely
- [Storage Configuration](./storage-config) - Data persistence security
- [Deployment Guide](../deployment/) - Production deployment security
- [Troubleshooting](./troubleshooting) - Common configuration issues

Ready to secure your API endpoints? Use the CLI commands to generate your authentication configuration and start protecting your AgentMap deployment.
