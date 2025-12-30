"""
Change detection modules for the availability cache service.

Contains detectors for monitoring environment and configuration changes
to trigger automatic cache invalidation.
"""

import hashlib
import json
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Union


class EnvironmentChangeDetector:
    """Detects environment changes for automatic cache invalidation."""

    def __init__(self):
        self._env_lock = threading.Lock()
        self._cached_env_hash: Optional[str] = None
        self._last_check_time: float = 0
        self._check_interval: float = 60.0

    def get_environment_hash(self) -> str:
        """Get current environment hash, with caching to avoid expensive operations."""
        with self._env_lock:
            current_time = time.time()
            if (
                self._cached_env_hash is not None
                and current_time - self._last_check_time < self._check_interval
            ):
                return self._cached_env_hash
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
                "python_path": sys.path[:5],
                "installed_packages": self._get_packages_hash(),
            }
            env_str = json.dumps(environment_data, sort_keys=True)
            return hashlib.sha256(env_str.encode("utf-8")).hexdigest()[:16]
        except Exception:
            raise

    def _get_packages_hash(self) -> str:
        """Get hash of installed packages for change detection."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                packages = sorted(result.stdout.strip().split("\n"))
                packages_str = "\n".join(packages)
                return hashlib.sha256(packages_str.encode("utf-8")).hexdigest()[:12]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        modules = sorted(list(sys.modules.keys())[:100])
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
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
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
                        return True
                    current_mtime = config_path.stat().st_mtime
                    if abs(current_mtime - stored_mtime) > 1.0:
                        return True
                    with open(config_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                        stored_hash = self._config_hashes.get(path_str, "")
                        if current_hash != stored_hash:
                            return True
                except Exception:
                    raise
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
                            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                            self._config_hashes[path_str] = content_hash
                except Exception:
                    raise
