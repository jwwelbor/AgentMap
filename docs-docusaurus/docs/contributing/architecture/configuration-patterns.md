# Configuration Architecture Patterns

## Overview

This document establishes consistent patterns for configuration services in AgentMap, analyzing the established practices in `AppConfigService` and identifying areas for improvement in `StorageConfigService`.

## Core Architecture

### Service Responsibilities

1. **ConfigService** (Infrastructure)
   - Pure YAML file loading and parsing
   - Generic value access via dot notation
   - No business logic or defaults
   - Singleton pattern for efficiency

2. **AppConfigService** (Domain Logic)
   - Application configuration with business logic
   - Named domain-specific methods
   - Default value merging
   - Validation and error handling
   - Bootstrap logging with logger replacement

3. **StorageConfigService** (Domain Logic)
   - Storage configuration with fail-fast behavior
   - Exception-based failure handling
   - Storage-specific business logic
   - Bootstrap logging with logger replacement

## Established Patterns from AppConfigService

### 1. Named Domain Methods Pattern

**✅ Preferred Approach:**
```python
def get_logging_config(self) -> Dict[str, Any]:
    """Get the logging configuration."""
    return self.get_section("logging", {})

def get_routing_config(self) -> Dict[str, Any]:
    """Get the routing configuration with default values."""
    routing_config = self.get_section("routing", {})
    # Business logic: merge with defaults
    defaults = { ... }
    return self._merge_with_defaults(routing_config, defaults)

def get_auth_config(self) -> Dict[str, Any]:
    """Get authentication configuration with default values."""
    # Complex business logic with validation and logging
```

**❌ Avoid Generic Access:**
```python
# Don't rely only on generic methods
def get_config_section(self, section_name: str) -> Dict[str, Any]:
    return self.get_section(section_name, {})
```

### 2. Path Accessor Pattern

**✅ Domain-Specific Path Methods:**
```python
def get_custom_agents_path(self) -> Path:
    """Get the path for custom agents."""
    return Path(self.get_value("paths.custom_agents", "agentmap/custom_agents"))

def get_csv_repository_path(self) -> Path:
    """Get the path for the CSV repository directory where workflows are stored."""
    csv_repo_path = Path(self.get_value("paths.csv_repository", "workflows"))
    
    # Business logic: ensure directory exists
    try:
        csv_repo_path.mkdir(parents=True, exist_ok=True)
        self._logger.debug(f"CSV repository path ensured: {csv_repo_path}")
    except Exception as e:
        self._logger.warning(f"Could not create CSV repository directory {csv_repo_path}: {e}")
    
    return csv_repo_path
```

### 3. Boolean Accessor Pattern

**✅ Clear Boolean Methods:**
```python
def is_authentication_enabled(self) -> bool:
    """Check if authentication is enabled."""
    return self.get_value("authentication.enabled", True)

def is_host_application_enabled(self) -> bool:
    """Check if host application support is enabled."""
    return self.get_value("host_application.enabled", True)
```

### 4. Validation Pattern

**✅ Comprehensive Domain Validation:**
```python
def validate_auth_config(self) -> Dict[str, Any]:
    """
    Validate authentication configuration and return validation results.
    
    Returns:
        Dictionary with validation status:
        - 'valid': Boolean indicating if config is valid
        - 'warnings': List of non-critical issues
        - 'errors': List of critical issues
        - 'summary': Summary of validation results
    """
    warnings = []
    errors = []
    # Comprehensive validation logic with domain knowledge
    # Returns structured validation results
```

### 5. Provider-Specific Access Pattern

**✅ Named Provider Methods:**
```python
def get_llm_config(self, provider: str) -> Dict[str, Any]:
    """Get configuration for a specific LLM provider."""
    return self.get_value(f"llm.{provider}", {})

def get_host_service_config(self, service_name: str) -> Dict[str, Any]:
    """Get configuration for a specific host service."""
    # Includes validation and default merging
```

## Current StorageConfigService Analysis

### Strengths
- ✅ Fail-fast behavior with exceptions
- ✅ Bootstrap logging pattern
- ✅ Some business logic methods (`get_collection_config`, `list_collections`)
- ✅ Clear separation from AppConfigService

### Areas for Improvement

1. **Limited Named Methods**
   - Current: `get_csv_config()`, `get_vector_config()`, `get_kv_config()`
   - Missing: Provider-specific methods like `get_firebase_config()`, `get_mongodb_config()`

2. **Lack of Rich Domain Methods**
   - Missing: Boolean accessors like `is_csv_enabled()`
   - Missing: Path accessors like `get_csv_data_path()`
   - Missing: Validation methods like `validate_csv_config()`

3. **Inconsistent Pattern Usage**
   - Mixes generic `get_value()` with some named methods
   - Could benefit from more domain-specific named methods

## Recommended StorageConfigService Improvements

### 1. Add Provider-Specific Named Methods

```python
def get_firebase_config(self) -> Dict[str, Any]:
    """Get Firebase storage configuration."""
    return self.get_provider_config("firebase")

def get_mongodb_config(self) -> Dict[str, Any]:
    """Get MongoDB storage configuration."""
    return self.get_provider_config("mongodb")

def get_supabase_config(self) -> Dict[str, Any]:
    """Get Supabase storage configuration."""
    return self.get_provider_config("supabase")
```

### 2. Add Boolean Accessors

```python
def is_csv_storage_enabled(self) -> bool:
    """Check if CSV storage is configured and enabled."""
    csv_config = self.get_csv_config()
    return csv_config.get("enabled", True) and bool(csv_config.get("collections"))

def has_vector_storage(self) -> bool:
    """Check if vector storage is available."""
    return bool(self.get_vector_config())

def is_provider_configured(self, provider: str) -> bool:
    """Check if a specific storage provider is configured."""
    return bool(self.get_provider_config(provider))
```

### 3. Add Path Accessors

```python
def get_csv_data_path(self) -> Path:
    """Get the CSV data directory path."""
    csv_config = self.get_csv_config()
    data_path = Path(csv_config.get("default_directory", "data/csv"))
    
    # Business logic: ensure directory exists if enabled
    if self.is_csv_storage_enabled():
        try:
            data_path.mkdir(parents=True, exist_ok=True)
            self._logger.debug(f"CSV data path ensured: {data_path}")
        except Exception as e:
            self._logger.warning(f"Could not create CSV data directory {data_path}: {e}")
    
    return data_path

def get_collection_file_path(self, collection_name: str) -> Path:
    """Get the full file path for a CSV collection."""
    csv_path = self.get_csv_data_path()
    collection_config = self.get_collection_config("csv", collection_name)
    filename = collection_config.get("filename", f"{collection_name}.csv")
    return csv_path / filename
```

### 4. Add Validation Methods

```python
def validate_csv_config(self) -> Dict[str, Any]:
    """
    Validate CSV storage configuration.
    
    Returns:
        Dictionary with validation status similar to AppConfigService pattern
    """
    warnings = []
    errors = []
    
    csv_config = self.get_csv_config()
    
    # Validate directory exists if CSV is enabled
    if self.is_csv_storage_enabled():
        data_path = self.get_csv_data_path()
        if not data_path.exists():
            warnings.append(f"CSV data directory does not exist: {data_path}")
    
    # Validate collections configuration
    collections = csv_config.get("collections", {})
    for collection_name, collection_config in collections.items():
        if not isinstance(collection_config, dict):
            errors.append(f"CSV collection '{collection_name}' configuration must be a dictionary")
    
    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "summary": {
            "collections_count": len(collections),
            "csv_enabled": self.is_csv_storage_enabled(),
        }
    }

def validate_all_storage_config(self) -> Dict[str, Any]:
    """Validate all storage configuration sections."""
    all_warnings = []
    all_errors = []
    
    # Validate each storage type
    for storage_type in ["csv", "vector", "kv"]:
        validation_method = getattr(self, f"validate_{storage_type}_config", None)
        if validation_method:
            result = validation_method()
            all_warnings.extend(result.get("warnings", []))
            all_errors.extend(result.get("errors", []))
    
    return {
        "valid": len(all_errors) == 0,
        "warnings": all_warnings,
        "errors": all_errors,
        "summary": self.get_storage_summary()
    }
```

## Configuration Service Guidelines

### Method Naming Conventions

1. **Domain Methods**: `get_{domain}_config()` (e.g., `get_logging_config`, `get_csv_config`)
2. **Provider Methods**: `get_{provider}_config()` (e.g., `get_openai_config`, `get_firebase_config`)
3. **Boolean Methods**: `is_{feature}_enabled()` or `has_{feature}()` 
4. **Path Methods**: `get_{domain}_path()` or `get_{resource}_path()`
5. **Validation Methods**: `validate_{domain}_config()`
6. **Collection Methods**: `list_{resource}()`, `has_{resource}()`

### Business Logic Integration

1. **Default Merging**: Use `_merge_with_defaults()` for complex default scenarios
2. **Path Creation**: Ensure directories exist when returning paths for enabled features
3. **Logging**: Log configuration status and warnings for visibility
4. **Validation**: Return structured validation results with warnings/errors/summary

### Error Handling Patterns

1. **AppConfigService**: Graceful degradation with defaults and warnings
2. **StorageConfigService**: Fail-fast with specific exceptions
3. **Both**: Structured validation results for debugging

### Bootstrap Logging Pattern

Both services should:
1. Set up bootstrap logging during initialization
2. Provide `replace_logger()` method for DI replacement
3. Use consistent log prefixes for identification

## Anti-Patterns to Avoid

1. **❌ Generic-Only Access**: Don't rely solely on `get_value()` or `get_section()`
2. **❌ Business Logic in ConfigService**: Keep infrastructure service pure
3. **❌ Inconsistent Naming**: Follow established naming conventions
4. **❌ Missing Validation**: Always provide validation methods for complex domains
5. **❌ Path Without Creation**: Don't return paths without ensuring they exist when needed
6. **❌ Silent Failures**: Use appropriate logging and error handling

## Usage Examples

### Correct Configuration Service Usage

```python
# AppConfigService - Rich domain interface
app_config = container.get(AppConfigService)
logging_config = app_config.get_logging_config()  # Named method
is_auth_enabled = app_config.is_authentication_enabled()  # Boolean accessor
csv_path = app_config.get_csv_repository_path()  # Path with business logic
auth_validation = app_config.validate_auth_config()  # Structured validation

# StorageConfigService - Storage-specific interface  
storage_config = container.get(StorageConfigService)
csv_config = storage_config.get_csv_config()  # Named method
has_collections = storage_config.has_collection("csv", "users")  # Boolean check
data_path = storage_config.get_csv_data_path()  # Path accessor
validation = storage_config.validate_csv_config()  # Validation
```

### Integration Between Services

```python
# AppConfigService provides path to storage config
app_config = container.get(AppConfigService)
storage_config_path = app_config.get_storage_config_path()

# StorageConfigService loads from that path
config_service = container.get(ConfigService)
storage_config = StorageConfigService(config_service, storage_config_path)
```

This pattern ensures clean separation while maintaining consistency in method design and behavior.
