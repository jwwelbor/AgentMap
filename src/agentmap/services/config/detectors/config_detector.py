"""
Configuration Change Detector for Availability Cache.

Monitors configuration files for changes (modification time and content)
to trigger automatic cache invalidation when config changes.
"""

import hashlib
import threading
from pathlib import Path
from typing import Dict, Union


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
            except:
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
                    # If we can't check, assume no change to avoid false positives
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
                            content_hash = hashlib.sha256(
                                content.encode("utf-8")
                            ).hexdigest()[:16]
                            self._config_hashes[path_str] = content_hash
                except Exception:
                    raise
