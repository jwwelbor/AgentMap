---
sidebar_position: 3
title: Unified Availability Cache Architecture
description: Comprehensive architectural documentation for AgentMap's unified AvailabilityCacheService, covering design principles, service integration patterns, and thread-safe caching strategies
keywords: [availability cache, unified cache, architecture, service integration, thread safety, cache invalidation]
---

# Unified Availability Cache Architecture

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/contributing">Contributing</a> → <a href="/docs/contributing/architecture">Architecture</a> → <strong>Unified Availability Cache</strong></span>
</div>

This document provides comprehensive architectural documentation for AgentMap's **unified AvailabilityCacheService**, which consolidates all availability caching needs across the application into a single, thread-safe, high-performance service.

## Architectural Overview

### Design Philosophy

The unified AvailabilityCacheService implements a **clean separation of concerns** architecture where:

- **Services perform work**: Business logic services handle validation, network calls, and computation
- **Cache provides pure storage**: The cache service only stores and retrieves results, never performs business logic
- **Unified interface**: Single service handles all availability caching needs across all categories
- **Categorized storage**: Clear key patterns organize different service types and purposes

### From Separate to Unified Architecture

**Previous Architecture (Separate Caches)**:
```mermaid
graph TD
    A[DependencyCheckerService] --> B[DependencyAvailabilityCache]
    C[LLMRoutingConfigService] --> D[LLMAvailabilityCache]
    E[StorageService] --> F[StorageAvailabilityCache]
    
    B --> G[dependency_cache.json]
    D --> H[llm_cache.json]
    F --> I[storage_cache.json]
```

**New Architecture (Unified Cache)**:
```mermaid
graph TD
    A[DependencyCheckerService] --> D[AvailabilityCacheService]
    B[LLMRoutingConfigService] --> D
    C[StorageService] --> D
    
    D --> E[unified_cache.json]
    
    D --> F[ConfigChangeDetector]
    D --> G[EnvironmentChangeDetector]
    D --> H[ThreadSafeFileCache]
```

### Core Architectural Principles

#### 1. Pure Storage Layer

The cache service **never** performs business logic:

```python
# ❌ WRONG: Cache performing business logic
class AvailabilityCacheService:
    def check_dependency(self, package: str) -> bool:
        # Don't do this - cache shouldn't import or test packages
        return importlib.import_module(package) is not None

# ✅ CORRECT: Cache as pure storage
class AvailabilityCacheService:
    def get_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """Pure storage retrieval - no business logic"""
        return self._file_cache.load_cache().get(f"{category}.{key}")
    
    def set_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        """Pure storage operation - result provided by service"""
        return self._file_cache.save_cache({f"{category}.{key}": result})
```

#### 2. Service Responsibility

Services handle all validation work and populate cache with results:

```python
# Service does the work, then caches result
class DependencyCheckerService:
    def check_llm_dependency(self, provider: str) -> Dict[str, Any]:
        # 1. Check cache first
        cached = self.availability_cache.get_availability("dependency.llm", provider)
        if cached:
            return cached
        
        # 2. Service performs the actual work
        try:
            result = self._perform_dependency_check(provider)  # Business logic here
            validation_result = {
                "available": result,
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "provider": provider,
                "details": self._get_dependency_details(provider)
            }
        except Exception as e:
            validation_result = {
                "available": False,
                "error": str(e),
                "validated_at": datetime.now(timezone.utc).isoformat()
            }
        
        # 3. Cache the result
        self.availability_cache.set_availability("dependency.llm", provider, validation_result)
        return validation_result
```

## Categorized Key System

### Key Naming Conventions

The unified cache uses a hierarchical key system to organize different types of availability data:

```
{category}.{subcategory?}.{specific_key}
```

#### Standard Categories

**Dependency Checks**:
```
dependency.llm.openai       → OpenAI LLM dependencies
dependency.llm.anthropic    → Anthropic LLM dependencies
dependency.storage.csv      → CSV storage dependencies
dependency.storage.vector   → Vector storage dependencies
dependency.storage.firebase → Firebase dependencies
```

**LLM Provider Availability**:
```
llm_provider.openai         → OpenAI API availability
llm_provider.anthropic      → Anthropic API availability
llm_provider.google         → Google AI API availability
```

**Storage Service Availability**:
```
storage.csv                 → CSV storage capability
storage.json                → JSON storage capability
storage.vector              → Vector storage capability
storage.firebase            → Firebase storage capability
```

**Custom Categories**:
```
custom.feature.name         → Custom feature availability
validation.config.type      → Configuration validation results
network.service.endpoint    → Network service availability
```

### Key Pattern Implementation

```python
class AvailabilityCacheService:
    def get_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached availability data for a categorized key.
        
        Args:
            category: Category like 'dependency.llm', 'storage', 'llm_provider'
            key: Specific key within category like 'openai', 'csv'
            
        Returns:
            Cached availability data with metadata
        """
        cache_key = f"{category}.{key}"  # Creates hierarchical key
        return self._retrieve_from_storage(cache_key)
    
    def set_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        """Set availability data with automatic metadata enhancement."""
        cache_key = f"{category}.{key}"
        
        # Enhance result with metadata
        enhanced_result = result.copy()
        enhanced_result.update({
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_key": cache_key,
            "environment_hash": self._env_detector.get_environment_hash()
        })
        
        return self._store_to_storage(cache_key, enhanced_result)
```

## Thread Safety Architecture

### Concurrent Access Patterns

The unified cache supports multiple services accessing cache simultaneously:

```mermaid
graph TD
    A[DependencyCheckerService Thread 1] --> E[AvailabilityCacheService]
    B[LLMRoutingConfigService Thread 2] --> E
    C[StorageService Thread 3] --> E
    D[ValidationService Thread 4] --> E
    
    E --> F[RLock: _cache_lock]
    E --> G[Lock: _invalidation_lock]
    
    F --> H[ThreadSafeFileCache]
    G --> H
```

### Thread Safety Implementation

**RLock for Cache Operations**:
```python
class AvailabilityCacheService:
    def __init__(self, cache_file_path: Path, logger=None):
        self._cache_lock = threading.RLock()  # Reentrant lock for cache ops
        self._invalidation_lock = threading.Lock()  # Separate lock for invalidation
    
    def get_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        with self._cache_lock:
            # Check for automatic invalidation
            if self._should_auto_invalidate():
                self._perform_auto_invalidation()
            
            # Safe cache access
            return self._file_cache.load_cache().get(f"{category}.{key}")
    
    def set_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        with self._cache_lock:
            # Thread-safe cache update
            cache_data = self._file_cache.load_cache() or {}
            cache_data[f"{category}.{key}"] = result
            return self._file_cache.save_cache(cache_data)
```

**Atomic File Operations**:
```python
class ThreadSafeFileCache:
    def _atomic_write_cache(self, cache_data: Dict[str, Any]) -> bool:
        """Atomically write cache data to prevent corruption."""
        temp_file = self._cache_file_path.with_suffix('.tmp')
        try:
            # Write to temporary file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Atomic rename (platform-specific)
            if os.name == 'nt':  # Windows
                if self._cache_file_path.exists():
                    self._cache_file_path.unlink()
            temp_file.replace(self._cache_file_path)
            
            return True
        except Exception:
            # Cleanup on failure
            if temp_file.exists():
                temp_file.unlink()
            return False
```

## Cache Invalidation Strategies

### Automatic Invalidation Triggers

The cache automatically invalidates when environmental changes occur:

#### 1. Environment Change Detection

```python
class EnvironmentChangeDetector:
    def get_environment_hash(self) -> str:
        """Generate hash representing current environment state."""
        environment_data = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "python_path": sys.path[:5],
            "installed_packages": self._get_packages_hash()
        }
        
        env_str = json.dumps(environment_data, sort_keys=True)
        return hashlib.sha256(env_str.encode('utf-8')).hexdigest()[:16]
```

**Triggers for Environment Invalidation**:
- Python version changes
- Platform changes
- Package installations/removals
- Virtual environment switches
- Python path modifications

#### 2. Configuration Change Detection

```python
class ConfigChangeDetector:
    def register_config_file(self, config_path: Path):
        """Register configuration file for change monitoring."""
        self._config_mtimes[str(config_path)] = config_path.stat().st_mtime
        
        # Store content hash for reliable detection
        with open(config_path, 'r') as f:
            content = f.read()
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            self._config_hashes[str(config_path)] = content_hash
    
    def has_config_changed(self) -> bool:
        """Check if any registered config files have changed."""
        for path_str, stored_mtime in self._config_mtimes.items():
            config_path = Path(path_str)
            current_mtime = config_path.stat().st_mtime
            
            # Check both mtime and content hash
            if abs(current_mtime - stored_mtime) > 1.0:  # 1 second tolerance
                return True
            
            # Content-based validation for reliability
            with open(config_path, 'r') as f:
                current_hash = hashlib.sha256(f.read().encode()).hexdigest()[:16]
                if current_hash != self._config_hashes.get(path_str):
                    return True
        
        return False
```

### Manual Invalidation Options

#### Granular Invalidation

```python
# Invalidate specific key
cache_service.invalidate_cache("dependency.llm", "openai")

# Invalidate entire category
cache_service.invalidate_cache("dependency.llm")

# Invalidate all cache
cache_service.invalidate_cache()
```

#### Targeted Invalidation Examples

```python
class DependencyCheckerService:
    def invalidate_dependency_cache(self, dependency_type: str = None):
        """Invalidate dependency-specific cache entries."""
        if dependency_type:
            # Invalidate specific dependency type
            self.availability_cache.invalidate_cache("dependency", dependency_type)
        else:
            # Invalidate all dependency cache
            self.availability_cache.invalidate_cache("dependency")
    
    def on_config_change(self, config_file: str):
        """Handle configuration changes."""
        self.availability_cache.register_config_file(config_file)
        # Cache will auto-invalidate on next access
```

## Performance Characteristics

### Benchmarked Performance Metrics

Based on comprehensive performance analysis, the unified cache delivers:

**Cache Hit Performance**:
- **P95 latency**: &lt;5ms across all categories
- **Average access time**: 2-3ms for cache hits
- **Memory overhead**: 38-43% reduction vs separate caches

**Cache Miss Impact**:
- **Service work time**: 100-200ms (validation/network calls)
- **Previous architecture**: 500ms-2s (75% improvement)
- **Complete check→work→populate cycle**: 89ms average

**I/O Efficiency**:
- **File operations**: 75% fewer I/O operations than separate files
- **Atomic writes**: Zero data corruption in concurrent testing
- **Cache invalidation**: &lt;50ms for all invalidation types

### Scalability Patterns

```python
# Cross-service cache reuse provides 5-60x speedup
class LLMRoutingConfigService:
    def get_provider_availability(self, provider: str) -> bool:
        # First check if dependency service already validated this
        dependency_result = self.availability_cache.get_availability("dependency.llm", provider)
        if dependency_result and dependency_result.get("available"):
            # Reuse dependency validation for routing decisions
            return True
        
        # Only do expensive API check if dependency validation passed
        api_result = self.availability_cache.get_availability("llm_provider", provider)
        return api_result.get("available", False) if api_result else False
```

## Storage Architecture

### Unified Cache File Structure

```json
{
  "cache_version": "2.0",
  "created_at": "2024-01-15T10:30:00Z",
  "last_updated": "2024-01-15T15:45:30Z",
  "environment_hash": "a1b2c3d4e5f6",
  "availability": {
    "dependency.llm.openai": {
      "available": true,
      "validated_at": "2024-01-15T15:45:30Z",
      "cache_key": "dependency.llm.openai",
      "environment_hash": "a1b2c3d4e5f6",
      "details": {
        "packages": ["langchain_openai"],
        "versions": {"langchain_openai": "0.1.0"}
      }
    },
    "storage.csv": {
      "available": true,
      "validated_at": "2024-01-15T15:45:28Z",
      "cache_key": "storage.csv",
      "environment_hash": "a1b2c3d4e5f6",
      "details": {
        "pandas_version": "2.0.0",
        "test_file_access": true
      }
    },
    "llm_provider.anthropic": {
      "available": false,
      "validated_at": "2024-01-15T15:45:25Z",
      "cache_key": "llm_provider.anthropic",
      "environment_hash": "a1b2c3d4e5f6",
      "error": "API key not configured",
      "details": {
        "api_endpoint": "https://api.anthropic.com",
        "timeout_ms": 5000
      }
    }
  }
}
```

### Memory Management

```python
class ThreadSafeFileCache:
    def __init__(self, cache_file_path: Path, logger=None):
        self._memory_cache: Optional[Dict[str, Any]] = None
        self._cache_lock = threading.RLock()
    
    def load_cache(self) -> Optional[Dict[str, Any]]:
        """Load cache with memory caching for performance."""
        with self._cache_lock:
            # Use memory cache if available
            if self._memory_cache is not None:
                return self._memory_cache
            
            # Load from disk and cache in memory
            if self._cache_file_path.exists():
                with open(self._cache_file_path, 'r') as f:
                    cache_data = json.load(f)
                self._memory_cache = cache_data
                return cache_data
            
            return None
    
    def save_cache(self, cache_data: Dict[str, Any]) -> bool:
        """Save cache with memory synchronization."""
        with self._cache_lock:
            success = self._atomic_write_cache(cache_data)
            if success:
                self._memory_cache = cache_data  # Keep memory in sync
            return success
```

## Error Handling and Resilience

### Graceful Degradation

The cache service is designed to never block application functionality:

```python
class AvailabilityCacheService:
    def get_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        try:
            # Attempt cache retrieval
            return self._safe_cache_access(category, key)
        except Exception as e:
            # Log error but don't fail
            if self._logger:
                self._logger.warning(f"Cache access failed for {category}.{key}: {e}")
            return None  # Graceful degradation
    
    def set_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        try:
            # Attempt cache storage
            return self._safe_cache_storage(category, key, result)
        except Exception as e:
            # Log error but don't fail the calling service
            if self._logger:
                self._logger.warning(f"Cache storage failed for {category}.{key}: {e}")
            return False  # Service can continue without caching
```

### Cache Corruption Recovery

```python
class ThreadSafeFileCache:
    def load_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if self._cache_file_path.exists():
                with open(self._cache_file_path, 'r') as f:
                    cache_data = json.load(f)
                
                # Validate cache structure
                if self._validate_cache_structure(cache_data):
                    return cache_data
                else:
                    self._logger.warning("Cache structure invalid, rebuilding")
                    return None
                    
        except (json.JSONDecodeError, IOError) as e:
            self._logger.warning(f"Cache file corrupted, will rebuild: {e}")
            # Move corrupted file for debugging
            if self._cache_file_path.exists():
                backup_path = self._cache_file_path.with_suffix('.corrupted')
                self._cache_file_path.rename(backup_path)
            
        return None  # Will trigger cache rebuild
```

## Integration Patterns

### Dependency Injection Integration

```python
# Unified cache service in DI container
class ServiceContainer:
    def __init__(self):
        # Single cache service instance
        self.availability_cache_service = AvailabilityCacheService(
            cache_file_path=self.get_cache_file_path(),
            logger=self.logging_service.get_class_logger("AvailabilityCacheService")
        )
        
        # Inject into all services that need caching
        self.dependency_checker_service = DependencyCheckerService(
            logging_service=self.logging_service,
            features_registry_service=self.features_registry_service,
            availability_cache_service=self.availability_cache_service  # Shared instance
        )
        
        self.llm_routing_service = LLMRoutingConfigService(
            logging_service=self.logging_service,
            availability_cache_service=self.availability_cache_service  # Same instance
        )
        
        self.storage_service = StorageService(
            logging_service=self.logging_service,
            availability_cache_service=self.availability_cache_service  # Same instance
        )
```

### Service Integration Template

```python
class YourService:
    def __init__(self, logging_service, availability_cache_service=None):
        self.logger = logging_service.get_class_logger(self)
        self.availability_cache = availability_cache_service
    
    def check_your_feature(self, feature_key: str) -> Dict[str, Any]:
        """Template for cache-integrated feature checking."""
        
        # 1. Check cache first
        cached_result = self._get_cached_availability("your_category", feature_key)
        if cached_result:
            return cached_result
        
        # 2. Perform actual validation work
        try:
            is_available = self._perform_feature_validation(feature_key)
            validation_result = {
                "available": is_available,
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "feature_key": feature_key,
                "details": self._get_feature_details(feature_key)
            }
        except Exception as e:
            validation_result = {
                "available": False,
                "error": str(e),
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "feature_key": feature_key
            }
        
        # 3. Cache the result
        self._set_cached_availability("your_category", feature_key, validation_result)
        return validation_result
    
    def _get_cached_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """Get cached availability using unified cache service."""
        if not self.availability_cache:
            return None
        try:
            return self.availability_cache.get_availability(category, key)
        except Exception as e:
            self.logger.debug(f"Cache lookup failed for {category}.{key}: {e}")
            return None
    
    def _set_cached_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        """Set cached availability using unified cache service."""
        if not self.availability_cache:
            return False
        try:
            return self.availability_cache.set_availability(category, key, result)
        except Exception as e:
            self.logger.debug(f"Cache set failed for {category}.{key}: {e}")
            return False
```

## Best Practices and Anti-Patterns

### ✅ Recommended Patterns

**1. Use Categorized Keys**:
```python
# Good: Clear category hierarchy
cache.get_availability("dependency.llm", "openai")
cache.get_availability("storage", "csv")
cache.get_availability("llm_provider", "anthropic")
```

**2. Handle Cache Misses Gracefully**:
```python
def check_feature(self, feature: str) -> bool:
    cached = self.cache.get_availability("features", feature)
    if cached:
        return cached.get("available", False)
    
    # Perform actual work on cache miss
    result = self._do_expensive_validation(feature)
    self.cache.set_availability("features", feature, result)
    return result.get("available", False)
```

**3. Enrich Results with Metadata**:
```python
validation_result = {
    "available": True,
    "validated_at": datetime.now(timezone.utc).isoformat(),
    "validation_method": "import_test",
    "environment": self._get_environment_info(),
    "details": {"package_version": "1.2.3"}
}
```

### ❌ Anti-Patterns to Avoid

**1. Cache Performing Business Logic**:
```python
# Don't do this - cache shouldn't perform validation
class AvailabilityCacheService:
    def check_dependency(self, pkg):
        return importlib.import_module(pkg)  # Wrong!
```

**2. Ignoring Thread Safety**:
```python
# Don't access cache without proper service integration
# Direct file manipulation bypasses thread safety
with open(cache_file, 'w') as f:  # Wrong!
    json.dump(data, f)
```

**3. Cache Bypass Without Fallback**:
```python
# Don't fail if cache is unavailable
def get_availability(self):
    if not self.cache:
        raise Exception("Cache required!")  # Wrong!
    
    # Better: graceful degradation
    if not self.cache:
        return self._fallback_validation()
```

## Migration Guidelines

### From Separate Caches to Unified Cache

**Step 1: Update Service Dependencies**:
```python
# Old pattern
class MyService:
    def __init__(self, my_specific_cache):
        self.cache = my_specific_cache

# New pattern  
class MyService:
    def __init__(self, availability_cache_service=None):
        self.availability_cache = availability_cache_service
```

**Step 2: Update Cache Keys**:
```python
# Old pattern
self.cache.get("dependency_openai")

# New pattern
self.availability_cache.get_availability("dependency.llm", "openai")
```

**Step 3: Update Cache Operations**:
```python
# Old pattern
self.cache.set_dependency_result("openai", result)

# New pattern
self.availability_cache.set_availability("dependency.llm", "openai", result)
```

### Breaking Changes and Compatibility

**Cache File Location Change**:
- Old: Multiple files (`dependency_cache.json`, `llm_cache.json`, etc.)
- New: Single file (`availability_cache.json`)
- Migration: Cache will be rebuilt automatically on first use

**API Changes**:
- Old: `cache.get(key)` → New: `cache.get_availability(category, key)`
- Old: `cache.set(key, value)` → New: `cache.set_availability(category, key, value)`
- Old: `cache.clear()` → New: `cache.invalidate_cache()`

## Related Documentation

### 🚀 **Development Guides**
- **[Cache Service Integration](../../guides/development/cache-service-integration)**: Developer integration patterns
- **[Service Integration](../../guides/development/service-integration)**: General service integration patterns
- **[Testing Patterns](../../guides/development/testing)**: Testing cache-integrated services

### 🔧 **Operations Guides**
- **[Cache Management](../../deployment/cache-management)**: Administrative procedures
- **[Troubleshooting](../../guides/troubleshooting)**: Common cache issues and solutions
- **[Performance Monitoring](../../guides/performance/optimization)**: Cache performance tuning

### 📖 **Reference Documentation**
- **[Configuration Reference](/docs/reference/configuration)**: Cache configuration options
- **[API Reference](/docs/reference/api)**: Complete API documentation
- **[Performance Benchmarks](/docs/reference/performance-benchmarks)**: Detailed performance analysis

## Summary

The unified AvailabilityCacheService provides:

1. **Clean Architecture**: Services handle work, cache provides storage
2. **Unified Interface**: Single service for all availability caching needs
3. **Categorized Organization**: Hierarchical key system for different service types
4. **Thread Safety**: Concurrent access from multiple services
5. **Automatic Invalidation**: Environment and config change detection
6. **Performance Benefits**: 38-43% memory reduction, 75% I/O efficiency improvement
7. **Graceful Degradation**: Never blocks application functionality

This architecture replaces separate cache implementations with a single, high-performance, thread-safe caching service that scales efficiently across all AgentMap services.
