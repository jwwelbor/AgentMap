"""
Environment Change Detector for Availability Cache.

Detects changes in the Python environment (packages, version, platform)
to trigger automatic cache invalidation when dependencies change.
"""

import hashlib
import json
import platform
import subprocess
import sys
import threading
import time
from typing import Optional


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
