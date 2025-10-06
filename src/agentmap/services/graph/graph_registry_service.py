"""
GraphRegistryService implementation for AgentMap.

Provides O(1) lookups for graph bundles by mapping CSV file hashes
to their corresponding preprocessed bundle locations.
"""

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.json_service import JSONStorageService
from agentmap.services.storage.system_manager import SystemStorageManager
from agentmap.services.storage.types import StorageResult, WriteMode


class GraphRegistryService:
    """
    High-performance graph registry for O(1) bundle lookups.

    Thread-safe implementation with in-memory caching and persistent storage.
    Eliminates redundant CSV parsing by maintaining a registry of known graphs.
    """

    REGISTRY_SCHEMA_VERSION = "1.0.0"
    DEFAULT_REGISTRY_FILE = "graph_registry.json"

    def __init__(
        self,
        system_storage_manager: SystemStorageManager,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
    ):
        """Initialize GraphRegistryService with required dependencies.

        Args:
            system_storage_manager: System storage manager for cache_folder registry storage (optional)
            app_config_service: Application configuration service
            logging_service: Logging service for proper dependency injection
        """
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.system_storage_manager = system_storage_manager

        # Thread-safe cache
        self._registry_cache: Dict[str, Dict] = {}
        self._cache_lock = threading.RLock()
        self._dirty = False

        # Initialize metadata
        self._metadata = self._create_metadata()
        self._registry_path = self._get_registry_path()

        # Load existing registry
        self._load_registry()

        self.logger.info(
            f"GraphRegistryService initialized with {len(self._registry_cache)} entries"
        )

    @staticmethod
    def compute_hash(
        csv_path: Path, logging_service: Optional[LoggingService] = None
    ) -> str:
        """
        Compute SHA-256 hash of CSV file content.

        Args:
            :param csv_path: Path to CSV file
            :param logging_service: Logging service

        Returns:
            Hexadecimal string representation of SHA-256 hash

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            IOError: If file cannot be read
        """
        import hashlib

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        try:
            with open(csv_path, "rb") as f:
                content = f.read()

            hash_obj = hashlib.sha256(content)
            csv_hash = hash_obj.hexdigest()

            if logging_service:
                logging_service.get_logger("GraphRegistryService").debug(
                    f"Computed hash: {csv_hash[:8]}... for {csv_path.name}"
                )

            # TODO return CSV content to avoid multiple reads.
            return csv_hash

        except Exception as e:
            if logging_service:
                logging_service.get_logger("GraphRegistryService").error(
                    f"Failed to compute hash for {csv_path}: {e}"
                )

            raise IOError(f"Cannot read CSV file {csv_path}: {e}")

    def find_bundle(
        self, csv_hash: str, graph_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Find bundle path for given CSV hash and optional graph name.

        Uses composite key (csv_hash, graph_name) for lookups. Maintains backward
        compatibility when graph_name is None by returning first available bundle.

        Args:
            csv_hash: SHA-256 hash of CSV content
            graph_name: Optional graph name for composite key lookup

        Returns:
            Path to bundle file if found, None otherwise
        """
        with self._cache_lock:
            # Get hash entry - should be nested structure {graph_name: entry}
            hash_entry = self._registry_cache.get(csv_hash)

            if not hash_entry:
                self.logger.debug(f"No bundle found for hash {csv_hash[:8]}...")
                return None

            # Use composite key lookup with nested structure
            if graph_name is None:
                # Return first available bundle for backward compatibility
                if hash_entry:
                    first_graph_name = next(iter(hash_entry.keys()))
                    entry = hash_entry[first_graph_name]
                    self.logger.debug(
                        f"Using default graph '{first_graph_name}' for hash {csv_hash[:8]}..."
                    )
                else:
                    self.logger.debug(f"No bundles found for hash {csv_hash[:8]}...")
                    return None
            else:
                # Specific graph lookup using composite key
                entry = hash_entry.get(graph_name)
                if not entry:
                    self.logger.debug(
                        f"No bundle found for hash {csv_hash[:8]}... and graph {graph_name}"
                    )
                    return None

            # Validate bundle exists
            bundle_path = Path(entry["bundle_path"])
            if bundle_path.exists():
                if graph_name:
                    self.logger.debug(
                        f"Found bundle for hash {csv_hash[:8]}... and graph {graph_name}"
                    )
                else:
                    self.logger.debug(f"Found bundle for hash {csv_hash[:8]}...")
                return bundle_path
            else:
                graph_info = f" and graph {graph_name}" if graph_name else ""
                self.logger.warning(
                    f"Bundle file missing for hash {csv_hash[:8]}...{graph_info}: {bundle_path}"
                )
                return None

    def register(
        self,
        csv_hash: str,
        graph_name: str,
        bundle_path: Path,
        csv_path: Path,
        node_count: int = 0,
    ) -> None:
        """
        Register a new graph bundle mapping.

        Args:
            csv_hash: SHA-256 hash of CSV content
            graph_name: Human-readable graph identifier
            bundle_path: Path to saved bundle file
            csv_path: Original CSV file path for reference
            node_count: Number of nodes in the graph (optional)

        Raises:
            ValueError: If required parameters are invalid
        """
        self._validate_registration_params(csv_hash, graph_name, bundle_path)

        entry = self._create_registry_entry(
            csv_hash, graph_name, bundle_path, csv_path, node_count
        )

        with self._cache_lock:
            # Initialize nested structure if csv_hash doesn't exist
            hash_entry = self._registry_cache.get(csv_hash)
            is_new_hash = False

            if csv_hash not in self._registry_cache:
                self._registry_cache[csv_hash] = {}
                hash_entry = self._registry_cache[csv_hash]
                is_new_hash = True

            is_update = graph_name in hash_entry

            # Store entry using composite key (csv_hash, graph_name)
            hash_entry[graph_name] = entry

            self._update_metadata(bundle_path.stat().st_size, is_update, is_new_hash)
            self._dirty = True

            # Persist immediately
            self._persist_registry()

            action = "Updating" if is_update else "Registering"
            self.logger.info(
                f"{action} graph bundle: {graph_name} (hash: {csv_hash[:8]}...)"
            )

    def remove_entry(self, csv_hash: str, graph_name: Optional[str] = None) -> bool:
        """
        Remove entry from registry.

        Args:
            csv_hash: SHA-256 hash of CSV content
            graph_name: Optional graph name to remove specific graph entry

        Returns:
            True if entry was removed, False if not found
        """
        with self._cache_lock:
            if csv_hash not in self._registry_cache:
                return False

            hash_entry = self._registry_cache[csv_hash]

            # Handle new nested structure
            if graph_name is None:
                # Remove all graphs for this csv_hash
                total_size = sum(
                    entry.get("bundle_size", 0) for entry in hash_entry.values()
                )
                entry_count = len(hash_entry)

                # Update metadata
                self._metadata["total_entries"] -= entry_count
                self._metadata["total_bundle_size"] -= total_size
                self._metadata["last_modified"] = datetime.utcnow().isoformat()

                # Remove from cache
                del self._registry_cache[csv_hash]
                self._dirty = True

                # Persist changes
                self._persist_registry()

                self.logger.info(
                    f"Removed {entry_count} registry entries for hash {csv_hash[:8]}..."
                )
                return True
            else:
                # Remove specific graph
                if graph_name not in hash_entry:
                    return False

                entry = hash_entry[graph_name]
                bundle_size = entry.get("bundle_size", 0)

                # Update metadata
                self._metadata["total_entries"] -= 1
                self._metadata["total_bundle_size"] -= bundle_size
                self._metadata["last_modified"] = datetime.utcnow().isoformat()

                # Remove graph entry
                del hash_entry[graph_name]

                # If no graphs remain, remove the csv_hash entry entirely
                if not hash_entry:
                    del self._registry_cache[csv_hash]

                self._dirty = True

                # Persist changes
                self._persist_registry()

                self.logger.info(
                    f"Removed registry entry: {graph_name} "
                    f"(hash: {csv_hash[:8]}...)"
                )
                return True

    def get_entry_info(
        self, csv_hash: str, graph_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete information about a specific registry entry.

        Args:
            csv_hash: SHA-256 hash of CSV content
            graph_name: Graph name for composite key lookup

        Returns:
            Dictionary with entry information or None if not found
        """
        with self._cache_lock:
            hash_entry = self._registry_cache.get(csv_hash)
            if not hash_entry:
                return None

            # Get specific graph entry using composite key
            entry = hash_entry.get(graph_name)
            return entry.copy() if entry else None

    def _validate_registration_params(
        self, csv_hash: str, graph_name: str, bundle_path: Path
    ) -> None:
        """Validate registration parameters."""
        if not csv_hash or len(csv_hash) != 64:
            raise ValueError(f"Invalid CSV hash: {csv_hash}")

        if not graph_name:
            raise ValueError("Graph name cannot be empty")

        if bundle_path and not bundle_path.exists():
            raise ValueError(f"Bundle file does not exist: {bundle_path}")

    def _create_registry_entry(
        self,
        csv_hash: str,
        graph_name: str,
        bundle_path: Path,
        csv_path: Path,
        node_count: int,
    ) -> Dict[str, Any]:
        """Create a new registry entry."""
        bundle_size = bundle_path.stat().st_size

        return {
            "graph_name": graph_name,
            "csv_hash": csv_hash,
            "bundle_path": str(bundle_path),
            "csv_path": str(csv_path),
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "access_count": 0,
            "bundle_size": bundle_size,
            "node_count": node_count,
        }

    def _update_metadata(
        self, bundle_size: int, is_update: bool, is_new_hash: bool = False
    ) -> None:
        """Update registry metadata."""
        if is_new_hash:
            self._metadata["total_entries"] += 1

        # Only add to total bundle size if this is a new entry (not an update)
        if not is_update:
            self._metadata["total_bundle_size"] += bundle_size

        self._metadata["last_modified"] = datetime.utcnow().isoformat()

    def _create_metadata(self) -> Dict[str, Any]:
        """Create initial metadata."""
        return {
            "created_at": datetime.utcnow().isoformat(),
            "last_modified": datetime.utcnow().isoformat(),
            "total_entries": 0,
            "total_bundle_size": 0,
        }

    def _get_registry_path(self) -> str:
        """Get registry filename for storage."""
        return self.DEFAULT_REGISTRY_FILE

    def _load_registry(self) -> None:
        """Load registry from persistent storage."""
        try:
            # Use system storage for cache_folder storage
            self.logger.debug(
                f"Using SystemStorageManager to load registry: {self._registry_path}"
            )
            storage_service = self.system_storage_manager.get_json_storage()
            registry_data = storage_service.read(collection=self._registry_path)

            if registry_data:
                self._load_registry_data(registry_data)
            else:
                self.logger.info("No existing registry found, starting fresh")
                self._create_empty_registry()

        except Exception as e:
            self.logger.error(f"Failed to load registry: {e}")
            self._handle_load_error(e)

    def _load_registry_data(self, registry_data: Dict[str, Any]) -> None:
        """Load registry data from storage."""
        version = registry_data.get("version", "0.0.0")
        if version != self.REGISTRY_SCHEMA_VERSION:
            self.logger.warning(
                f"Registry schema version mismatch: {version} != {self.REGISTRY_SCHEMA_VERSION}"
            )

        self._registry_cache = registry_data.get("entries", {})
        self._metadata = registry_data.get("metadata", self._metadata)

        self.logger.info(f"Loaded {len(self._registry_cache)} entries from registry")

    def _persist_registry(self) -> None:
        """Persist registry to storage."""
        if not self._dirty:
            return

        try:
            registry_data = {
                "version": self.REGISTRY_SCHEMA_VERSION,
                "entries": self._registry_cache,
                "metadata": self._metadata,
            }

            # Use system storage for cache_folder storage
            self.logger.debug(
                f"Using SystemStorageManager to persist registry: {self._registry_path}"
            )
            storage_service = self.system_storage_manager.get_json_storage()
            result = storage_service.write(
                collection=self._registry_path, data=registry_data, mode=WriteMode.WRITE
            )

            if result.success:
                self._dirty = False
                self.logger.debug("Registry persisted successfully")
            else:
                self.logger.error(f"Failed to persist registry: {result.error}")

        except Exception as e:
            self.logger.error(f"Error persisting registry: {e}")

    def _create_empty_registry(self) -> None:
        """Create a new empty registry."""
        self._registry_cache = {}
        self._metadata = self._create_metadata()
        self._dirty = True
        self._persist_registry()

    def _handle_load_error(self, error: Exception) -> None:
        """Handle registry load errors with recovery."""
        self.logger.warning(f"Creating fresh registry due to load error: {error}")
        self._create_empty_registry()
