"""Unified Availability Cache Service for AgentMap."""
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union
from agentmap.services.config.availability_cache import ThreadSafeFileCache
from agentmap.services.config.cache_invalidation_mixin import CacheInvalidationMixin
from agentmap.services.config.cache_statistics_mixin import CacheStatisticsMixin
from agentmap.services.config.change_detectors import ConfigChangeDetector, EnvironmentChangeDetector

__all__ = ["AvailabilityCacheService", "EnvironmentChangeDetector", "ConfigChangeDetector"]


class EnvironmentChangeDetector:
    """Detects environment changes for automatic cache invalidation."""

    def __init__(self):
        self._env_lock = threading.Lock()
        self._cached_env_hash: Optional[str] = None
        self._last_check_time: float = 0
        self._check_interval: float = 60.0  # Check environment every 60 seconds

    def get_environment_hash(self) -> str:
        """Get current environment hash, with caching to avoid expensive operations."""
        with self._env_lock:
            current_time = time.time()

            # Use cached hash if within check interval
            if (
                self._cached_env_hash is not None
                and current_time - self._last_check_time < self._check_interval
            ):
                return self._cached_env_hash

            # Compute fresh environment hash
            self._cached_env_hash = self._compute_environment_hash()
            self._last_check_time = current_time
            return self._cached_env_hash

    def invalidate_environment_cache(self):
        """Force recomputation of environment hash on next access."""
        with self._env_lock:
            self._cached_env_hash = None
            self._last_check_time = 0

    def _compute_environment_hash(self) -> str:
        """Compute hash representing current environment state."""
        try:
            environment_data = {
                "python_version": sys.version,
                "platform": platform.platform(),
                "python_path": sys.path[:5],  # First 5 paths to avoid excessive data
                "installed_packages": self._get_packages_hash(),
            }

            env_str = json.dumps(environment_data, sort_keys=True)
            return hashlib.sha256(env_str.encode("utf-8")).hexdigest()[:16]

        except Exception:
            # If we can't compute environment hash, re-raise as this is critical
            raise

    def _get_packages_hash(self) -> str:
        """Get hash of installed packages for change detection."""
        try:
            # Try pip freeze with timeout
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=5,  # Reduced timeout for faster response
            )
            if result.returncode == 0:
                packages = sorted(result.stdout.strip().split("\n"))
                packages_str = "\n".join(packages)
                return hashlib.sha256(packages_str.encode("utf-8")).hexdigest()[:12]
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        # Fallback to sys.modules hash
        modules = sorted(
            list(sys.modules.keys())[:100]
        )  # Limit to first 100 for performance
        modules_str = "\n".join(modules)
        return hashlib.sha256(modules_str.encode("utf-8")).hexdigest()[:12]


class ConfigChangeDetector:
    """Detects configuration file changes for automatic cache invalidation."""

    def __init__(self):
        self._config_lock = threading.Lock()
        self._config_mtimes: Dict[str, float] = {}
        self._config_hashes: Dict[str, str] = {}

    def register_config_file(self, config_path: Union[str, Path]):
        """Register a configuration file for change monitoring."""
        config_path = Path(config_path)
        if not config_path.exists():
            return

        with self._config_lock:
            path_str = str(config_path)
            try:
                mtime = config_path.stat().st_mtime
                self._config_mtimes[path_str] = mtime

                # Store hash for content-based comparison
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[
                        :16
                    ]
                    self._config_hashes[path_str] = content_hash
            except Exception:
                raise

    def has_config_changed(self) -> bool:
        """Check if any registered config files have changed."""
        with self._config_lock:
            for path_str, stored_mtime in self._config_mtimes.items():
                try:
                    config_path = Path(path_str)
                    if not config_path.exists():
                        # File was deleted - consider it changed
                        return True

                    current_mtime = config_path.stat().st_mtime
                    if abs(current_mtime - stored_mtime) > 1.0:  # 1 second tolerance
                        return True

                    # Also check content hash for more reliable detection
                    with open(config_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        current_hash = hashlib.sha256(
                            content.encode("utf-8")
                        ).hexdigest()[:16]
                        stored_hash = self._config_hashes.get(path_str, "")
                        if current_hash != stored_hash:
                            return True

                except Exception:
                    # If we can't check, assume change to safely invalidate cache
                    # This prevents using stale data when file access fails
                    return True

            return False

    def update_config_tracking(self):
        """Update tracking data for all registered config files."""
        with self._config_lock:
            for path_str in list(self._config_mtimes.keys()):
                try:
                    config_path = Path(path_str)
                    if config_path.exists():
                        mtime = config_path.stat().st_mtime
                        self._config_mtimes[path_str] = mtime

                        with open(config_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            content_hash = hashlib.sha256(
                                content.encode("utf-8")
                            ).hexdigest()[:16]
                            self._config_hashes[path_str] = content_hash
                except Exception:
                    # Skip files that can't be read, keep tracking existing ones
                    pass


class AvailabilityCacheService:
    """
    Unified availability cache service for storing and retrieving boolean availability results.

    This service provides a clean interface for caching availability checks across all
    categories (dependencies, LLM providers, storage, etc.) using categorized keys.
    It's a pure storage layer that never performs actual validation work.

    Key Categories and Examples:
    - dependency.llm.openai
    - dependency.storage.csv
    - llm_provider.anthropic
    - llm_provider.openai
    - storage.csv
    - storage.vector
    """

    def __init__(self, cache_file_path: Union[str, Path], logger=None):
        self._cache_file_path = Path(cache_file_path)
        self._logger = logger
        self._file_cache = ThreadSafeFileCache(self._cache_file_path, logger)
        self._env_detector = EnvironmentChangeDetector()
        self._config_detector = ConfigChangeDetector()
        self._cache_lock = threading.RLock()
        self._invalidation_lock = threading.Lock()
        self._last_env_hash: Optional[str] = None
        self._auto_invalidation_enabled = False
        self._stats = self._initialize_stats()

    def get_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        cache_key = f"{category}.{key}"
        try:
            with self._cache_lock:
                if not self._cache_file_path.exists():
                    from agentmap.exceptions.service_exceptions import CacheNotFoundError
                    raise CacheNotFoundError(f"Availability cache not found at {self._cache_file_path}.")
                cache_data = self._file_cache.load_cache()
                if not cache_data:
                    self._stats["cache_misses"] += 1
                    return None
                result = cache_data.get("availability", {}).get(cache_key)
                self._stats["cache_hits" if result else "cache_misses"] += 1
                return result
        except Exception:
            self._stats["cache_misses"] += 1
            return None

    def set_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        cache_key = f"{category}.{key}"
        try:
            with self._cache_lock:
                cache_data = self._file_cache.load_cache() or self._create_new_cache_structure()
                if "availability" not in cache_data:
                    cache_data["availability"] = {}
                enhanced_result = result.copy()
                enhanced_result.update({"cached_at": datetime.now(timezone.utc).isoformat(), "cache_key": cache_key, "environment_hash": self._env_detector.get_environment_hash()})
                cache_data["availability"][cache_key] = enhanced_result
                cache_data["last_updated"] = datetime.now(timezone.utc).isoformat()
                if self._file_cache.save_cache(cache_data):
                    self._stats["cache_sets"] += 1
                    return True
                return False
        except Exception:
            return False

    def register_config_file(self, config_file_path: Union[str, Path]) -> None:
        self._config_detector.register_config_file(config_file_path)

    def is_initialized(self) -> bool:
        return self._cache_file_path.exists()

    def refresh_cache(self, container) -> None:
        dependency_checker = container.dependency_checker_service()
        self.invalidate_cache()
        dependency_checker.discover_and_validate_providers("llm", force=True)
        dependency_checker.discover_and_validate_providers("storage", force=True)

    def enable_auto_invalidation(self, enabled: bool = True) -> None:
        self._auto_invalidation_enabled = enabled

    @property
    def _should_auto_invalidate(self) -> bool:
        if not self._auto_invalidation_enabled:
            return False

        try:
            # Check environment changes
            current_env_hash = self._env_detector.get_environment_hash()
            if (
                self._last_env_hash is not None
                and current_env_hash != self._last_env_hash
            ):
                return True

            # Check config file changes
            if self._config_detector.has_config_changed():
                return True

            return False

        except Exception:
            # If we can't check for invalidation, re-raise to prevent silent failures
            raise

    def _perform_auto_invalidation(self) -> None:
        """Perform automatic cache invalidation."""
        try:
            self._clear_entire_cache()

            # Update tracking
            self._last_env_hash = self._env_detector.get_environment_hash()
            self._config_detector.update_config_tracking()

            self._stats["auto_invalidations"] += 1
            if self._logger:
                self._logger.info(
                    "Performed automatic cache invalidation due to environment/config changes"
                )

        except Exception as e:
            if self._logger:
                self._logger.error(f"Error during automatic invalidation: {e}")

    def _create_new_cache_structure(self) -> Dict[str, Any]:
        return {"cache_version": "2.0", "created_at": datetime.now(timezone.utc).isoformat(), "last_updated": datetime.now(timezone.utc).isoformat(), "environment_hash": self._env_detector.get_environment_hash(), "availability": {}}
