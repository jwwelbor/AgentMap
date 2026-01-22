"""Change detection modules for the availability cache service."""

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
    def __init__(self):
        self._env_lock = threading.Lock()
        self._cached_env_hash: Optional[str] = None
        self._last_check_time: float = 0
        self._check_interval: float = 60.0

    def get_environment_hash(self) -> str:
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
        with self._env_lock:
            self._cached_env_hash = None
            self._last_check_time = 0

    def _compute_environment_hash(self) -> str:
        environment_data = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "python_path": sys.path[:5],
            "installed_packages": self._get_packages_hash(),
        }
        return hashlib.sha256(
            json.dumps(environment_data, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

    def _get_packages_hash(self) -> str:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return hashlib.sha256(
                    "\n".join(sorted(result.stdout.strip().split("\n"))).encode("utf-8")
                ).hexdigest()[:12]
        except:
            pass
        return hashlib.sha256(
            "\n".join(sorted(list(sys.modules.keys())[:100])).encode("utf-8")
        ).hexdigest()[:12]


class ConfigChangeDetector:
    def __init__(self):
        self._config_lock = threading.Lock()
        self._config_mtimes: Dict[str, float] = {}
        self._config_hashes: Dict[str, str] = {}

    def register_config_file(self, config_path: Union[str, Path]):
        config_path = Path(config_path)
        if not config_path.exists():
            return
        with self._config_lock:
            path_str = str(config_path)
            self._config_mtimes[path_str] = config_path.stat().st_mtime
            with open(config_path, "r", encoding="utf-8") as f:
                self._config_hashes[path_str] = hashlib.sha256(
                    f.read().encode("utf-8")
                ).hexdigest()[:16]

    def has_config_changed(self) -> bool:
        with self._config_lock:
            for path_str, stored_mtime in self._config_mtimes.items():
                config_path = Path(path_str)
                if not config_path.exists():
                    return True
                if abs(config_path.stat().st_mtime - stored_mtime) > 1.0:
                    return True
                with open(config_path, "r", encoding="utf-8") as f:
                    if hashlib.sha256(f.read().encode("utf-8")).hexdigest()[
                        :16
                    ] != self._config_hashes.get(path_str, ""):
                        return True
            return False

    def update_config_tracking(self):
        with self._config_lock:
            for path_str in list(self._config_mtimes.keys()):
                config_path = Path(path_str)
                if config_path.exists():
                    self._config_mtimes[path_str] = config_path.stat().st_mtime
                    with open(config_path, "r", encoding="utf-8") as f:
                        self._config_hashes[path_str] = hashlib.sha256(
                            f.read().encode("utf-8")
                        ).hexdigest()[:16]
