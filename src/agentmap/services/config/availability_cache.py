"""
Reusable availability cache base classes for storage validation caching.

Provides thread-safe, extensible cache management for expensive validation operations
across multiple services. Addresses critical architectural issues including thread safety,
cache corruption, and resource management.
"""

import asyncio
import hashlib
import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union


@dataclass
class CacheValidationResult:
    """Result of cache validation with comprehensive metadata."""

    is_valid: bool
    cache_age_seconds: float
    config_hash_match: bool
    file_mtime_match: bool
    version_compatible: bool
    error_message: Optional[str] = None


class AvailabilityCacheInterface(ABC):
    """Abstract interface for availability caching operations."""

    @abstractmethod
    async def get_availability(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached availability data for a key."""
        pass

    @abstractmethod
    async def set_availability(self, key: str, data: Dict[str, Any]) -> bool:
        """Set availability data for a key. Returns success status."""
        pass

    @abstractmethod
    async def invalidate_cache(self, key: Optional[str] = None) -> None:
        """Invalidate cache for specific key or all keys if None."""
        pass

    @abstractmethod
    def is_cache_valid(self, key: str) -> CacheValidationResult:
        """Check if cached data is still valid."""
        pass


class ValidationStrategy(ABC):
    """Abstract strategy for validation operations."""

    @abstractmethod
    async def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration and return result with metadata."""
        pass

    @abstractmethod
    def get_cache_key(self, config: Dict[str, Any]) -> str:
        """Generate cache key for this validation strategy."""
        pass


class ThreadSafeFileCache:
    """Thread-safe file-based cache implementation with corruption protection."""

    def __init__(
        self, cache_file_path: Union[str, Path], logger: Optional[logging.Logger] = None
    ):
        self._cache_file_path = Path(cache_file_path)
        self._logger = logger or logging.getLogger(__name__)
        self._cache_lock = threading.RLock()
        self._generation_lock = threading.Lock()
        self._memory_cache: Optional[Dict[str, Any]] = None

    def __del__(self):
        """Cleanup resources on destruction."""
        self._cleanup_resources()

    def _cleanup_resources(self):
        """Clean up managed resources."""
        self._memory_cache = None

    @contextmanager
    def _cache_read_lock(self):
        """Context manager for cache read operations."""
        with self._cache_lock:
            yield

    @contextmanager
    def _cache_write_lock(self):
        """Context manager for cache write operations."""
        with self._cache_lock:
            yield

    def _get_full_config_hash(self, config: Dict[str, Any]) -> str:
        """Generate full SHA-256 hash (no truncation) for cache validation."""
        config_str = json.dumps(config, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(config_str.encode("utf-8")).hexdigest()

    def _get_file_mtime(self, file_path: Path) -> float:
        """Get modification time of file with error handling."""
        try:
            return file_path.stat().st_mtime if file_path.exists() else 0.0
        except (OSError, FileNotFoundError):
            return 0.0

    def _is_version_compatible(self, cache_version: str, current_version: str) -> bool:
        """Check version compatibility with semantic versioning support."""
        # For now, exact match required. Future: implement semantic version comparison
        return cache_version == current_version

    def _atomic_write_cache(self, cache_data: Dict[str, Any]) -> bool:
        """Atomically write cache data to prevent corruption."""
        if not self._cache_file_path:
            return False

        temp_file = None
        try:
            # Ensure parent directory exists
            self._cache_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write with proper cleanup
            temp_file = self._cache_file_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, separators=(",", ": "))
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Platform-specific atomic rename
            if os.name == "nt":  # Windows
                if self._cache_file_path.exists():
                    self._cache_file_path.unlink()
            temp_file.replace(self._cache_file_path)

            return True

        except Exception as e:
            self._logger.warning(f"Failed to save cache atomically: {e}")
            # Cleanup temp file on failure
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            return False

    def load_cache(self) -> Optional[Dict[str, Any]]:
        """Load cache from disk with thread safety."""
        with self._cache_read_lock():
            if self._memory_cache is not None:
                return self._memory_cache

            try:
                if self._cache_file_path.exists():
                    with open(self._cache_file_path, "r", encoding="utf-8") as f:
                        cache_data = json.load(f)

                    self._memory_cache = cache_data
                    self._logger.debug(f"Loaded cache from {self._cache_file_path}")
                    return cache_data
            except Exception as e:
                self._logger.warning(f"Failed to load cache: {e}")

            return None

    def save_cache(self, cache_data: Dict[str, Any]) -> bool:
        """Save cache to disk with thread safety."""
        with self._cache_write_lock():
            success = self._atomic_write_cache(cache_data)
            if success:
                self._memory_cache = cache_data
                self._logger.debug(f"Saved cache to {self._cache_file_path}")
            return success

    def validate_cache(
        self, config: Dict[str, Any], config_file_path: Optional[Path] = None
    ) -> CacheValidationResult:
        """Validate cache with comprehensive checks."""
        cache_data = self.load_cache()
        if not cache_data:
            return CacheValidationResult(
                is_valid=False,
                cache_age_seconds=0,
                config_hash_match=False,
                file_mtime_match=False,
                version_compatible=False,
                error_message="No cache data available",
            )

        try:
            # Version compatibility check
            cache_version = cache_data.get("cache_version", "0.0")
            version_compatible = self._is_version_compatible(cache_version, "1.1")

            # Config hash validation (full SHA-256)
            current_hash = self._get_full_config_hash(config)
            cached_hash = cache_data.get("config_hash")
            config_hash_match = current_hash == cached_hash

            # File modification time check (with tolerance for networked filesystems)
            file_mtime_match = True
            if config_file_path:
                current_mtime = self._get_file_mtime(config_file_path)
                cached_mtime = cache_data.get("config_mtime", 0)
                mtime_tolerance = 5.0  # 5 seconds for networked systems
                file_mtime_match = abs(current_mtime - cached_mtime) <= mtime_tolerance

            # Calculate cache age
            generated_at = cache_data.get("generated_at")
            cache_age_seconds = 0.0
            if generated_at:
                try:
                    generated_time = datetime.fromisoformat(
                        generated_at.replace("Z", "+00:00")
                    )
                    cache_age_seconds = (
                        datetime.now(timezone.utc) - generated_time
                    ).total_seconds()
                except ValueError:
                    cache_age_seconds = float("inf")  # Invalid timestamp = very old

            is_valid = version_compatible and config_hash_match and file_mtime_match

            return CacheValidationResult(
                is_valid=is_valid,
                cache_age_seconds=cache_age_seconds,
                config_hash_match=config_hash_match,
                file_mtime_match=file_mtime_match,
                version_compatible=version_compatible,
            )

        except Exception as e:
            return CacheValidationResult(
                is_valid=False,
                cache_age_seconds=0,
                config_hash_match=False,
                file_mtime_match=False,
                version_compatible=False,
                error_message=f"Cache validation error: {e}",
            )


class AvailabilityCacheManager:
    """Main orchestrator for availability caching with pluggable validation strategies."""

    def __init__(
        self, cache_impl: ThreadSafeFileCache, logger: Optional[logging.Logger] = None
    ):
        self._cache = cache_impl
        self._logger = logger or logging.getLogger(__name__)
        self._validators: Dict[str, ValidationStrategy] = {}
        self._generation_lock = None  # Will be initialized lazily

    def register_validator(self, storage_type: str, validator: ValidationStrategy):
        """Register a validation strategy for a storage type."""
        self._validators[storage_type] = validator
        self._logger.debug(f"Registered validator for storage type: {storage_type}")

    def _ensure_lock(self):
        """Lazily initialize the asyncio lock when needed."""
        if self._generation_lock is None:
            self._generation_lock = asyncio.Lock()
        return self._generation_lock

    async def get_or_generate_availability(
        self, storage_type: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get cached availability or generate fresh data with thread safety."""
        validator = self._validators.get(storage_type)
        if not validator:
            return {
                "enabled": False,
                "error": f"No validator registered for storage type: {storage_type}",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        cache_key = validator.get_cache_key(config)

        # Check cache first
        cached_data = self._cache.load_cache()
        if cached_data:
            availability_data = cached_data.get("availability", {}).get(storage_type)
            if availability_data:
                validation_result = self._cache.validate_cache(config)
                if validation_result.is_valid:
                    self._logger.debug(f"Using cached availability for {storage_type}")
                    return availability_data

        # Generate fresh data with double-checked locking
        lock = self._ensure_lock()
        async with lock:
            # Double-check after acquiring lock
            cached_data = self._cache.load_cache()
            if cached_data:
                availability_data = cached_data.get("availability", {}).get(
                    storage_type
                )
                if availability_data:
                    validation_result = self._cache.validate_cache(config)
                    if validation_result.is_valid:
                        return availability_data

            # Generate fresh validation
            self._logger.info(f"Generating fresh availability data for {storage_type}")
            validation_result = await validator.validate(config)

            # Update cache
            if not cached_data:
                cached_data = {
                    "cache_version": "1.1",
                    "config_hash": self._cache._get_full_config_hash(config),
                    "config_mtime": 0.0,  # Will be set by specific implementations
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "availability": {},
                }

            cached_data["availability"][storage_type] = validation_result
            self._cache.save_cache(cached_data)

            return validation_result

    def clear_cache(self, storage_type: Optional[str] = None):
        """Clear cache for specific storage type or all types."""
        cached_data = self._cache.load_cache()
        if not cached_data:
            return

        if storage_type:
            # Clear specific storage type
            availability = cached_data.get("availability", {})
            if storage_type in availability:
                del availability[storage_type]
                self._cache.save_cache(cached_data)
                self._logger.info(f"Cleared cache for storage type: {storage_type}")
        else:
            # Clear all cache
            try:
                if self._cache._cache_file_path.exists():
                    self._cache._cache_file_path.unlink()
                    self._logger.info("Cleared all availability cache")
            except Exception as e:
                self._logger.warning(f"Failed to clear cache file: {e}")

            self._cache._memory_cache = None
