---
title: Configuration Troubleshooting
sidebar_position: 6
description: Common AgentMap configuration issues, validation errors, and debugging solutions with step-by-step resolution guides.
keywords: [troubleshooting, configuration errors, debugging, validation, common issues]
---

# Configuration Troubleshooting

This guide covers common AgentMap configuration issues, validation errors, and debugging techniques with step-by-step solutions. Use this reference to quickly resolve configuration problems and optimize your setup.

## 🚨 Quick Diagnostic Checklist

When experiencing configuration issues, run through this checklist first:

- [ ] **Configuration files exist** - `agentmap_config.yaml` and storage config
- [ ] **Valid YAML syntax** - No indentation or syntax errors
- [ ] **Environment variables set** - Required API keys and credentials
- [ ] **File permissions** - Configuration files are readable
- [ ] **Path accessibility** - All configured directories exist or can be created
- [ ] **Network connectivity** - Can reach external services (LLM providers, storage)

## 🔧 Common Configuration Issues

### YAML Syntax Errors

**Problem:** Configuration file has invalid YAML syntax

**Error Messages:**
```
yaml.parser.ParserError: while parsing a block mapping
yaml.scanner.ScannerError: mapping values are not allowed here
ValidationError: invalid YAML configuration
```

**Common YAML Mistakes:**

```yaml
# ❌ Incorrect indentation (mixing spaces and tabs)
llm:
  openai:
	api_key: "env:OPENAI_API_KEY"  # Tab instead of spaces

# ✅ Correct indentation (consistent spaces)
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"  # 2 or 4 spaces consistently

# ❌ Missing quotes for special characters
api_key: env:KEY:with:colons

# ✅ Proper quoting
api_key: "env:KEY:with:colons"

# ❌ Incorrect list format
task_types: general, code_analysis, creative

# ✅ Correct list format
task_types:
  - general
  - code_analysis
  - creative
```

**Solutions:**
1. **Use a YAML validator**:
   ```bash
   python -c "import yaml; yaml.safe_load(open('agentmap_config.yaml'))"
   ```

2. **Check indentation consistency**:
   ```bash
   # Show whitespace characters
   cat -A agentmap_config.yaml | head -20
   ```

3. **Use proper editor settings**:
   - Set editor to show whitespace
   - Use spaces instead of tabs
   - Set consistent indentation (2 or 4 spaces)

### Environment Variable Issues

**Problem:** Environment variables not loading or incorrect values

**Error Messages:**
```
ValueError: Required environment variable OPENAI_API_KEY is not set
KeyError: 'OPENAI_API_KEY'
AuthenticationError: Invalid API key provided
```

**Diagnostic Steps:**

1. **Check if environment variables are set**:
   ```bash
   # Check specific variable
   echo $OPENAI_API_KEY
   
   # List all AgentMap-related variables
   env | grep -E "(OPENAI|ANTHROPIC|GOOGLE|AGENTMAP)"
   
   # Check if .env file exists
   ls -la .env
   ```

2. **Verify .env file format**:
   ```bash
   # ❌ Incorrect .env format
   OPENAI_API_KEY = sk-1234567890  # Spaces around =
   ANTHROPIC_API_KEY='sk-ant-...' # Mixed quotes
   
   # ✅ Correct .env format
   OPENAI_API_KEY=sk-1234567890abcdef
   ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
   ```

3. **Test environment variable loading**:
   ```python
   from dotenv import load_dotenv
   import os
   
   # Load .env file
   load_dotenv()
   
   # Test variable access
   print(f"OpenAI Key: {os.getenv('OPENAI_API_KEY', 'NOT_FOUND')}")
   print(f"Environment: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
   ```

**Solutions:**

1. **Fix .env file format**:
   ```bash
   # Remove spaces around equals sign
   sed -i 's/ *= */=/g' .env
   
   # Ensure no trailing spaces
   sed -i 's/[[:space:]]*$//' .env
   ```

2. **Set file permissions**:
   ```bash
   chmod 600 .env
   chmod 600 .env.production
   ```

3. **Verify environment variable precedence**:
   ```bash
   # System environment variables override .env file
   export OPENAI_API_KEY=system-level-key
   # This will override any .env file setting
   ```

### API Key Authentication Errors

**Problem:** Invalid or expired API keys

**Error Messages:**
```
openai.error.AuthenticationError: Invalid API key provided
anthropic.AuthenticationError: Invalid API key
google.auth.exceptions.RefreshError: The credentials do not contain the necessary fields
```

**Diagnostic Steps:**

1. **Validate API key format**:
   ```bash
   # OpenAI keys start with 'sk-'
   echo $OPENAI_API_KEY | grep '^sk-'
   
   # Anthropic keys start with 'sk-ant-api03-'
   echo $ANTHROPIC_API_KEY | grep '^sk-ant-api03-'
   
   # Check key length (should be appropriate length)
   echo $OPENAI_API_KEY | wc -c
   ```

2. **Test API connectivity**:
   ```python
   import openai
   import os
   
   # Test OpenAI connection
   openai.api_key = os.getenv("OPENAI_API_KEY")
   try:
       response = openai.Model.list()
       print("✅ OpenAI API key is valid")
   except Exception as e:
       print(f"❌ OpenAI API error: {e}")
   ```

**Solutions:**

1. **Regenerate API keys**:
   - Go to provider dashboard (OpenAI, Anthropic, Google)
   - Generate new API keys
   - Update environment variables

2. **Check API key permissions**:
   - Ensure key has required permissions
   - Check usage limits and quotas
   - Verify billing status

3. **Test with minimal configuration**:
   ```yaml
   # Minimal test configuration
   csv_path: "examples/test.csv"
   llm:
     openai:
       api_key: "env:OPENAI_API_KEY"
       model: "gpt-4o-mini"
   ```

### Storage Connection Issues

**Problem:** Cannot connect to storage providers

**Error Messages:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
pinecone.exceptions.UnauthorizedError: Invalid API key
azure.core.exceptions.ClientAuthenticationError: Authentication failed
FileNotFoundError: Storage directory not accessible
```

**Diagnostic Steps:**

1. **Test storage connectivity**:
   ```python
   # Test Redis connection
   import redis
   r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
   try:
       r.ping()
       print("✅ Redis connection successful")
   except Exception as e:
       print(f"❌ Redis connection failed: {e}")
   
   # Test Pinecone connection
   import pinecone
   pinecone.init(
       api_key=os.getenv("PINECONE_API_KEY"),
       environment=os.getenv("PINECONE_ENVIRONMENT")
   )
   try:
       pinecone.list_indexes()
       print("✅ Pinecone connection successful")
   except Exception as e:
       print(f"❌ Pinecone connection failed: {e}")
   ```

2. **Check local directory permissions**:
   ```bash
   # Check if directories exist and are writable
   mkdir -p data/csv data/json data/files
   touch data/csv/test.csv
   rm data/csv/test.csv
   ```

**Solutions:**

1. **Fix connection strings**:
   ```bash
   # ❌ Incorrect Redis URL format
   REDIS_URL=localhost:6379
   
   # ✅ Correct Redis URL format
   REDIS_URL=redis://localhost:6379/0
   REDIS_URL=redis://user:password@host:port/db
   ```

2. **Create required directories**:
   ```bash
   # Create all required directories
   mkdir -p data/{csv,json,files,vector,kv}
   mkdir -p logs
   mkdir -p compiled
   ```

3. **Test cloud storage authentication**:
   ```python
   # Test Azure connection
   from azure.storage.blob import BlobServiceClient
   
   connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
   if connection_string:
       try:
           blob_service = BlobServiceClient.from_connection_string(connection_string)
           containers = list(blob_service.list_containers())
           print("✅ Azure Blob Storage connection successful")
       except Exception as e:
           print(f"❌ Azure connection failed: {e}")
   ```

### Routing Configuration Issues

**Problem:** LLM routing not working as expected

**Error Messages:**
```
KeyError: 'routing_matrix'
ValueError: Invalid task type 'unknown_task'
AttributeError: 'NoneType' object has no attribute 'get'
```

**Diagnostic Steps:**

1. **Validate routing configuration**:
   ```python
   # Check routing matrix structure
   import yaml
   
   with open('agentmap_config.yaml', 'r') as f:
       config = yaml.safe_load(f)
   
   routing = config.get('routing', {})
   matrix = routing.get('routing_matrix', {})
   
   print("Configured providers:", list(matrix.keys()))
   for provider, complexities in matrix.items():
       print(f"{provider}: {list(complexities.keys())}")
   ```

2. **Test routing logic**:
   ```yaml
   # Minimal routing configuration for testing
   routing:
     enabled: true
     routing_matrix:
       openai:
         low: "gpt-4o-mini"
         medium: "gpt-4-turbo"
     task_types:
       general:
         provider_preference: ["openai"]
         default_complexity: "medium"
   ```

**Solutions:**

1. **Fix routing matrix format**:
   ```yaml
   # ❌ Incorrect routing matrix
   routing_matrix:
     openai: "gpt-4"  # Missing complexity levels
   
   # ✅ Correct routing matrix
   routing_matrix:
     openai:
       low: "gpt-4o-mini"
       medium: "gpt-4-turbo"
       high: "gpt-4"
   ```

2. **Validate task types**:
   ```yaml
   # ❌ Missing required fields
   task_types:
     general: {}
   
   # ✅ Complete task type definition
   task_types:
     general:
       provider_preference: ["openai"]
       default_complexity: "medium"
   ```

### Memory Configuration Issues

**Problem:** Memory system not working or causing errors

**Error Messages:**
```
ValueError: Invalid memory type 'invalid_buffer'
MemoryError: Token limit exceeded
AttributeError: Memory not properly initialized
```

**Solutions:**

1. **Fix memory type configuration**:
   ```yaml
   # ❌ Invalid memory type
   memory:
     default_type: "invalid_buffer"
   
   # ✅ Valid memory types
   memory:
     default_type: "buffer"  # buffer, buffer_window, summary, token_buffer
   ```

2. **Adjust memory limits**:
   ```yaml
   # For large conversations
   memory:
     enabled: true
     default_type: "token_buffer"
     max_token_limit: 8000  # Increase token limit
     buffer_window_size: 10  # Increase window size
   ```

3. **Disable memory for debugging**:
   ```yaml
   # Temporarily disable memory
   memory:
     enabled: false
   ```

## 🔍 Debugging Techniques

### Enable Debug Logging

**Comprehensive debug configuration**:
```yaml
logging:
  version: 1
  disable_existing_loggers: false
  formatters:
    debug:
      format: "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(name)s: %(message)s"
  handlers:
    console:
      class: logging.StreamHandler
      formatter: debug
      level: DEBUG
    debug_file:
      class: logging.FileHandler
      filename: "debug.log"
      formatter: debug
      level: DEBUG
  root:
    level: DEBUG
    handlers: [console, debug_file]
  loggers:
    agentmap:
      level: DEBUG
    agentmap.config:
      level: DEBUG
    agentmap.routing:
      level: DEBUG
    agentmap.storage:
      level: DEBUG
```

### Configuration Validation Script

**Complete validation script**:
```python
#!/usr/bin/env python3
"""
Comprehensive AgentMap Configuration Validator
"""

import os
import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any

class ConfigValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        
    def validate_yaml_syntax(self, file_path: str) -> bool:
        """Validate YAML file syntax."""
        try:
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            print(f"✅ {file_path}: Valid YAML syntax")
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"❌ {file_path}: Invalid YAML syntax - {e}")
            return False
        except FileNotFoundError:
            self.errors.append(f"❌ {file_path}: File not found")
            return False
    
    def validate_required_fields(self, config: Dict[str, Any]) -> bool:
        """Validate required configuration fields."""
        required_fields = {
            'csv_path': str,
            'llm': dict
        }
        
        valid = True
        for field, expected_type in required_fields.items():
            if field not in config:
                self.errors.append(f"❌ Missing required field: {field}")
                valid = False
            elif not isinstance(config[field], expected_type):
                self.errors.append(f"❌ Field '{field}' must be {expected_type.__name__}")
                valid = False
        
        return valid
    
    def validate_llm_config(self, llm_config: Dict[str, Any]) -> bool:
        """Validate LLM provider configuration."""
        if not llm_config:
            self.errors.append("❌ No LLM providers configured")
            return False
        
        valid_providers = ['openai', 'anthropic', 'google']
        configured_providers = []
        
        for provider in llm_config:
            if provider not in valid_providers:
                self.warnings.append(f"⚠️  Unknown LLM provider: {provider}")
            else:
                configured_providers.append(provider)
                
                # Check required fields for each provider
                provider_config = llm_config[provider]
                if 'api_key' not in provider_config:
                    self.errors.append(f"❌ Missing api_key for {provider}")
        
        if configured_providers:
            print(f"✅ LLM providers configured: {', '.join(configured_providers)}")
        
        return len(configured_providers) > 0
    
    def validate_environment_variables(self, config: Dict[str, Any]) -> bool:
        """Validate environment variables."""
        env_vars_found = []
        env_vars_missing = []
        
        # Check LLM provider environment variables
        llm_config = config.get('llm', {})
        env_var_mapping = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'google': 'GOOGLE_API_KEY'
        }
        
        for provider in llm_config:
            env_var = env_var_mapping.get(provider)
            if env_var:
                if os.getenv(env_var):
                    env_vars_found.append(env_var)
                else:
                    env_vars_missing.append(env_var)
        
        # Report results
        for var in env_vars_found:
            print(f"✅ Environment variable {var} is set")
        
        for var in env_vars_missing:
            self.warnings.append(f"⚠️  Environment variable {var} is not set")
        
        return len(env_vars_missing) == 0
    
    def validate_routing_config(self, config: Dict[str, Any]) -> bool:
        """Validate routing configuration."""
        routing = config.get('routing', {})
        if not routing.get('enabled', False):
            print("ℹ️  Routing is disabled")
            return True
        
        # Check routing matrix
        matrix = routing.get('routing_matrix', {})
        if not matrix:
            self.warnings.append("⚠️  Routing enabled but no routing matrix defined")
            return False
        
        # Validate matrix structure
        complexity_levels = ['low', 'medium', 'high', 'critical']
        for provider, complexities in matrix.items():
            if not isinstance(complexities, dict):
                self.errors.append(f"❌ Routing matrix for {provider} must be a dictionary")
                continue
                
            missing_levels = [level for level in complexity_levels if level not in complexities]
            if missing_levels:
                self.warnings.append(f"⚠️  {provider} missing complexity levels: {missing_levels}")
        
        print(f"✅ Routing matrix configured for: {', '.join(matrix.keys())}")
        return True
    
    def validate_paths(self, config: Dict[str, Any]) -> bool:
        """Validate path configuration."""
        paths = config.get('paths', {})
        
        # Check if paths exist or can be created
        path_fields = ['custom_agents', 'functions', 'compiled_graphs', 'csv_repository']
        
        for field in path_fields:
            if field in paths:
                path = Path(paths[field])
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    print(f"✅ Path {field}: {path} (accessible)")
                except Exception as e:
                    self.errors.append(f"❌ Cannot access path {field}: {path} - {e}")
        
        return True
    
    def validate(self, config_file: str = "agentmap_config.yaml") -> bool:
        """Run complete validation."""
        print("🔍 Starting AgentMap Configuration Validation...\n")
        
        # Validate YAML syntax
        if not self.validate_yaml_syntax(config_file):
            return False
        
        # Load configuration
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Run validation checks
        self.validate_required_fields(config)
        self.validate_llm_config(config.get('llm', {}))
        self.validate_environment_variables(config)
        self.validate_routing_config(config)
        self.validate_paths(config)
        
        # Check for storage configuration file
        storage_config = config.get('storage_config_path', 'agentmap_config_storage.yaml')
        if Path(storage_config).exists():
            print(f"✅ Storage configuration file found: {storage_config}")
            self.validate_yaml_syntax(storage_config)
        else:
            self.warnings.append(f"⚠️  Storage configuration file not found: {storage_config}")
        
        # Report results
        print("\n" + "="*60)
        print("📊 VALIDATION RESULTS")
        print("="*60)
        
        if self.errors:
            print("\n❌ ERRORS FOUND:")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.errors and not self.warnings:
            print("\n🎉 Configuration validation passed with no issues!")
        elif not self.errors:
            print(f"\n✅ Configuration validation passed with {len(self.warnings)} warnings")
        else:
            print(f"\n❌ Configuration validation failed with {len(self.errors)} errors")
        
        return len(self.errors) == 0

def main():
    validator = ConfigValidator()
    success = validator.validate()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

### Test Configuration Script

**Quick configuration test**:
```python
#!/usr/bin/env python3
"""
Quick AgentMap Configuration Test
"""

def test_basic_config():
    """Test basic configuration loading."""
    try:
        from agentmap.services.config import AppConfigService
        
        print("🧪 Testing configuration loading...")
        config_service = AppConfigService("agentmap_config.yaml")
        
        print("✅ Configuration loaded successfully")
        
        # Test LLM configuration
        llm_config = config_service.get_llm_config()
        print(f"✅ LLM providers configured: {list(llm_config.keys())}")
        
        # Test routing if enabled
        if config_service.is_routing_enabled():
            print("✅ Routing is enabled")
        else:
            print("ℹ️  Routing is disabled")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_llm_connection():
    """Test LLM provider connections."""
    import os
    
    print("\n🧪 Testing LLM connections...")
    
    # Test OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            import openai
            openai.api_key = os.getenv("OPENAI_API_KEY")
            models = openai.Model.list()
            print("✅ OpenAI connection successful")
        except Exception as e:
            print(f"❌ OpenAI connection failed: {e}")
    
    # Test Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            # Simple test call
            print("✅ Anthropic API key format valid")
        except Exception as e:
            print(f"❌ Anthropic setup failed: {e}")

if __name__ == "__main__":
    if test_basic_config():
        test_llm_connection()
        print("\n🎉 Configuration test completed!")
    else:
        print("\n❌ Configuration test failed!")
```

## 🛡️ Security Troubleshooting

### File Permission Issues

**Problem:** Configuration files cannot be read

**Solutions:**
```bash
# Set proper permissions
chmod 600 agentmap_config.yaml
chmod 600 agentmap_config_storage.yaml
chmod 600 .env

# Check file ownership
ls -la agentmap_config.yaml
chown $USER:$USER agentmap_config.yaml
```

### Credential Security Issues

**Problem:** Credentials exposed in configuration files

**Detection:**
```bash
# Check for hardcoded credentials
grep -n "sk-" agentmap_config.yaml
grep -n "api.*key.*:" agentmap_config.yaml | grep -v "env:"
```

**Solutions:**
```yaml
# ❌ Hardcoded credentials (security risk)
llm:
  openai:
    api_key: "sk-1234567890abcdef"

# ✅ Environment variable reference (secure)
llm:
  openai:
    api_key: "env:OPENAI_API_KEY"
```

## 📊 Performance Troubleshooting

### Slow Configuration Loading

**Problem:** Configuration takes too long to load

**Diagnostic:**
```python
import time
import yaml

start_time = time.time()
with open('agentmap_config.yaml', 'r') as f:
    config = yaml.safe_load(f)
load_time = time.time() - start_time

print(f"Configuration load time: {load_time:.2f} seconds")
```

**Solutions:**
1. **Reduce configuration complexity**
2. **Disable unnecessary features during startup**
3. **Use faster YAML parser** (if available)

### Memory Usage Issues

**Problem:** High memory usage from configuration

**Solutions:**
```yaml
# Reduce memory footprint
memory:
  max_token_limit: 2000  # Reduce from default
  buffer_window_size: 5  # Reduce from larger values

routing:
  performance:
    max_cache_size: 1000  # Reduce cache size
```

## 🔄 Configuration Migration Issues

### Upgrading from Previous Versions

**Problem:** Configuration format changes between versions

**Common migration needs:**
1. **Routing configuration** - New format in recent versions
2. **Storage configuration** - Separate file structure
3. **Environment variable** - New naming conventions

**Migration script template:**
```python
#!/usr/bin/env python3
"""
AgentMap Configuration Migration Helper
"""

import yaml
from pathlib import Path

def migrate_config(old_config_file: str, new_config_file: str):
    """Migrate configuration to new format."""
    
    with open(old_config_file, 'r') as f:
        old_config = yaml.safe_load(f)
    
    # Migration logic here
    new_config = {
        'csv_path': old_config.get('csv_path', 'workflows/main.csv'),
        'autocompile': old_config.get('autocompile', True),
        'llm': old_config.get('llm', {}),
        # Add new fields with defaults
        'routing': {
            'enabled': old_config.get('enable_routing', False),
            # ... other routing config
        }
    }
    
    with open(new_config_file, 'w') as f:
        yaml.dump(new_config, f, default_flow_style=False, indent=2)
    
    print(f"✅ Migrated {old_config_file} to {new_config_file}")

if __name__ == "__main__":
    migrate_config("old_config.yaml", "agentmap_config.yaml")
```

## 📞 Getting Additional Help

### Enable Verbose Logging

```yaml
# Maximum verbosity configuration
logging:
  root:
    level: DEBUG
  loggers:
    agentmap:
      level: DEBUG
    agentmap.config:
      level: DEBUG
    agentmap.routing:
      level: DEBUG
    agentmap.storage:
      level: DEBUG
    agentmap.services:
      level: DEBUG
```

### Collect Diagnostic Information

```bash
#!/bin/bash
# AgentMap diagnostic information collector

echo "=== AgentMap Diagnostic Information ==="
echo "Date: $(date)"
echo "Python version: $(python --version)"
echo "AgentMap version: $(python -c 'import agentmap; print(agentmap.__version__)')"
echo ""

echo "=== Configuration Files ==="
ls -la agentmap_config*.yaml .env* 2>/dev/null
echo ""

echo "=== Environment Variables ==="
env | grep -E "(OPENAI|ANTHROPIC|GOOGLE|AGENTMAP|REDIS|PINECONE)" | sort
echo ""

echo "=== Directory Structure ==="
find . -type d -name "data" -o -name "logs" -o -name "compiled" 2>/dev/null
echo ""

echo "=== YAML Syntax Check ==="
python -c "import yaml; yaml.safe_load(open('agentmap_config.yaml', 'r')); print('✅ Valid YAML')" 2>&1
```

### Common Resolution Patterns

1. **Start with minimal configuration** - Strip down to basics, then add features
2. **Test each component separately** - LLM, storage, routing individually  
3. **Check network connectivity** - Firewall, proxy, DNS issues
4. **Verify credentials** - Regenerate API keys if unsure
5. **Review logs carefully** - Often contain specific error details

## 📖 Next Steps

1. **Use the validation script** - Run comprehensive configuration check
2. **Test with minimal config** - Verify basic functionality first
3. **Add complexity gradually** - Enable features one by one
4. **Monitor logs** - Watch for warnings and errors during operation

Ready to implement your configuration? Return to the [Configuration Overview](./index) or check out the [Getting Started Guide](../getting-started) for next steps.
