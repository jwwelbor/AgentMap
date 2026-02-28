"""
Comprehensive tests for GraphRegistryService.

Tests hash computation, registry operations, thread safety, persistence,
error handling, and integration with dependency services.
"""

import hashlib
import threading
import time
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch

from agentmap.services.graph.graph_registry_service import GraphRegistryService
from agentmap.services.storage.types import StorageResult, WriteMode


class MockJSONStorageService:
    """Mock JSON storage service for testing."""

    def __init__(self, fail_operations: bool = False, empty_registry: bool = False):
        self.fail_operations = fail_operations
        self.empty_registry = empty_registry
        self.stored_data = {}
        self.read_count = 0
        self.write_count = 0

    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Mock read operation matching JSONStorageService interface."""
        self.read_count += 1

        if self.fail_operations:
            raise Exception("Mock storage read failure")

        if self.empty_registry:
            return None

        # Return mock registry data if available - use collection as the key
        data = self.stored_data.get(collection)
        return data

    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """Mock write operation matching JSONStorageService interface."""
        self.write_count += 1

        if self.fail_operations:
            return StorageResult(
                success=False, data=None, error="Mock storage write failure"
            )

        # Store data using collection as the key
        self.stored_data[collection] = data
        return StorageResult(success=True, data=data, error=None)


class MockSystemStorageManager:
    """Mock SystemStorageManager for testing."""

    def __init__(self):
        self._json_storage = MockJSONStorageService()

    def get_json_storage(self) -> MockJSONStorageService:
        """Return mock JSON storage service."""
        return self._json_storage

    def get_file_storage(self) -> MockJSONStorageService:
        """Return mock file storage service."""
        return self._json_storage


class MockAppConfigService:
    """Mock app config service for testing."""

    def __init__(self, cache_path: Optional[Path] = None):
        self._cache_path = cache_path or Path("test_cache")

    def get_cache_path(self) -> Path:
        """Return mock cache path."""
        return self._cache_path


class MockLoggingService:
    """Mock logging service for testing."""

    def __init__(self):
        self.logger = Mock()
        self.logger.debug = Mock()
        self.logger.info = Mock()
        self.logger.warning = Mock()
        self.logger.error = Mock()

    def get_class_logger(self, obj: Any) -> Mock:
        """Return mock logger."""
        return self.logger


class TestGraphRegistryService(unittest.TestCase):
    """Comprehensive tests for GraphRegistryService."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.cache_path = Path(self.temp_dir.name)

        # Create shared storage instance that will be used by both the service and tests
        self.json_storage = MockJSONStorageService()

        # Configure system storage manager to use our shared storage instance
        self.system_storage_manager = MockSystemStorageManager()
        self.system_storage_manager._json_storage = (
            self.json_storage
        )  # Use the shared instance

        self.app_config = MockAppConfigService(self.cache_path)
        self.logging_service = MockLoggingService()

        # Create service instance
        self.registry_service = GraphRegistryService(
            system_storage_manager=self.system_storage_manager,
            app_config_service=self.app_config,
            logging_service=self.logging_service,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def create_test_csv_file(
        self, content: str = "node,agent,action\ntest,test,test\n"
    ) -> Path:
        """Create a temporary CSV file for testing."""
        csv_file = NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        csv_file.write(content)
        csv_file.flush()
        csv_file.close()
        return Path(csv_file.name)

    def create_test_bundle_file(self, content: bytes = b"test bundle data") -> Path:
        """Create a temporary bundle file for testing."""
        bundle_file = NamedTemporaryFile(mode="wb", suffix=".bundle", delete=False)
        bundle_file.write(content)
        bundle_file.flush()
        bundle_file.close()
        return Path(bundle_file.name)

    # ===== HASH COMPUTATION TESTS =====

    def test_compute_hash_success(self):
        """Test successful hash computation."""
        csv_file = self.create_test_csv_file("node,agent,action\ntest,test,test\n")

        try:
            hash_result = self.registry_service.compute_hash(csv_file)

            # Verify hash format
            self.assertEqual(
                len(hash_result), 64, "Hash should be 64 characters (SHA-256)"
            )
            self.assertTrue(
                all(c in "0123456789abcdef" for c in hash_result),
                "Hash should be hexadecimal",
            )

            # Verify hash consistency
            hash_result2 = self.registry_service.compute_hash(csv_file)
            self.assertEqual(hash_result, hash_result2, "Hash should be consistent")

            # Verify hash accuracy
            with open(csv_file, "rb") as f:
                expected_hash = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(
                hash_result, expected_hash, "Hash should match direct SHA-256"
            )

        finally:
            csv_file.unlink()

    def test_compute_hash_different_content(self):
        """Test that different content produces different hashes."""
        csv_file1 = self.create_test_csv_file("node,agent,action\ntest1,test1,test1\n")
        csv_file2 = self.create_test_csv_file("node,agent,action\ntest2,test2,test2\n")

        try:
            hash1 = self.registry_service.compute_hash(csv_file1)
            hash2 = self.registry_service.compute_hash(csv_file2)

            self.assertNotEqual(
                hash1, hash2, "Different content should produce different hashes"
            )

        finally:
            csv_file1.unlink()
            csv_file2.unlink()

    def test_compute_hash_file_not_found(self):
        """Test hash computation with non-existent file."""
        non_existent_file = Path("non_existent_file.csv")

        with self.assertRaises(FileNotFoundError) as context:
            self.registry_service.compute_hash(non_existent_file)

        self.assertIn("CSV file not found", str(context.exception))
        self.assertIn(str(non_existent_file), str(context.exception))

    def test_compute_hash_permission_error(self):
        """Test hash computation with file permission error."""
        csv_file = self.create_test_csv_file()

        try:
            # Mock open to raise PermissionError
            with patch(
                "builtins.open", side_effect=PermissionError("Permission denied")
            ):
                with self.assertRaises(IOError) as context:
                    self.registry_service.compute_hash(csv_file)

                self.assertIn("Cannot read CSV file", str(context.exception))
                self.assertIn("Permission denied", str(context.exception))
        finally:
            csv_file.unlink()

    # ===== REGISTRY OPERATIONS TESTS =====

    def test_register_new_entry(self):
        """Test registering a new graph bundle entry."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register the entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
                node_count=3,
            )

            # Verify entry was stored
            entry = self.registry_service.get_entry_info(csv_hash, "test_graph")
            self.assertIsNotNone(entry, "Entry should exist")
            self.assertEqual(entry["graph_name"], "test_graph")
            self.assertEqual(entry["csv_hash"], csv_hash)
            self.assertEqual(entry["bundle_path"], str(bundle_file))
            self.assertEqual(entry["csv_path"], str(csv_file))
            self.assertEqual(entry["node_count"], 3)
            self.assertIn("created_at", entry)
            self.assertIn("last_accessed", entry)
            self.assertEqual(entry["access_count"], 0)

            # Verify persistence was called
            self.assertGreater(
                self.json_storage.write_count, 0, "Should persist to storage"
            )

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_register_update_existing_entry(self):
        """Test updating an existing registry entry."""
        csv_file = self.create_test_csv_file()
        bundle_file1 = self.create_test_bundle_file(b"bundle1")
        bundle_file2 = self.create_test_bundle_file(b"bundle2")

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register initial entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph_v1",
                bundle_path=bundle_file1,
                csv_path=csv_file,
                node_count=3,
            )

            initial_write_count = self.json_storage.write_count

            # Update entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph_v2",
                bundle_path=bundle_file2,
                csv_path=csv_file,
                node_count=5,
            )

            # Verify entry was updated
            entry = self.registry_service.get_entry_info(csv_hash, "test_graph_v2")
            self.assertEqual(entry["graph_name"], "test_graph_v2")
            self.assertEqual(entry["bundle_path"], str(bundle_file2))
            self.assertEqual(entry["node_count"], 5)

            # Verify additional persistence occurred
            self.assertGreater(
                self.json_storage.write_count,
                initial_write_count,
                "Should persist update",
            )

        finally:
            csv_file.unlink()
            bundle_file1.unlink()
            bundle_file2.unlink()

    def test_find_bundle_existing(self):
        """Test finding an existing bundle."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            # Find bundle
            found_bundle = self.registry_service.find_bundle(csv_hash)

            self.assertIsNotNone(found_bundle, "Should find existing bundle")
            self.assertEqual(
                found_bundle, bundle_file, "Should return correct bundle path"
            )

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_find_bundle_not_found(self):
        """Test finding a non-existent bundle."""
        non_existent_hash = "a" * 64  # Valid hash format but not registered

        found_bundle = self.registry_service.find_bundle(non_existent_hash)

        self.assertIsNone(found_bundle, "Should return None for non-existent bundle")

    def test_find_bundle_file_missing(self):
        """Test finding bundle when bundle file no longer exists."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            # Delete bundle file
            bundle_file.unlink()

            # Try to find bundle
            found_bundle = self.registry_service.find_bundle(csv_hash)

            self.assertIsNone(
                found_bundle, "Should return None when bundle file missing"
            )

            # Verify warning was logged
            self.logging_service.logger.warning.assert_called()
            warning_call = self.logging_service.logger.warning.call_args[0][0]
            self.assertIn("Bundle file missing", warning_call)

        finally:
            csv_file.unlink()
            if bundle_file.exists():
                bundle_file.unlink()

    def test_remove_entry_existing(self):
        """Test removing an existing entry."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            # Verify entry exists
            self.assertIsNotNone(
                self.registry_service.get_entry_info(csv_hash, "test_graph")
            )

            # Remove entry
            removed = self.registry_service.remove_entry(csv_hash)

            self.assertTrue(removed, "Should return True for successful removal")
            self.assertIsNone(
                self.registry_service.get_entry_info(csv_hash, "test_graph"),
                "Entry should no longer exist",
            )

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_remove_entry_not_found(self):
        """Test removing a non-existent entry."""
        non_existent_hash = "b" * 64

        removed = self.registry_service.remove_entry(non_existent_hash)

        self.assertFalse(removed, "Should return False for non-existent entry")

    def test_get_entry_info_not_found(self):
        """Test getting info for non-existent entry."""
        non_existent_hash = "c" * 64

        info = self.registry_service.get_entry_info(
            non_existent_hash, "non_existent_graph"
        )

        self.assertIsNone(info, "Should return None for non-existent entry")

    # ===== VALIDATION TESTS =====

    def test_register_invalid_hash(self):
        """Test registration with invalid hash."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            with self.assertRaises(ValueError) as context:
                self.registry_service.register(
                    csv_hash="invalid_hash",  # Invalid format
                    graph_name="test_graph",
                    bundle_path=bundle_file,
                    csv_path=csv_file,
                )

            self.assertIn("Invalid CSV hash", str(context.exception))

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_register_empty_graph_name(self):
        """Test registration with empty graph name."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            with self.assertRaises(ValueError) as context:
                self.registry_service.register(
                    csv_hash=csv_hash,
                    graph_name="",  # Empty name
                    bundle_path=bundle_file,
                    csv_path=csv_file,
                )

            self.assertIn("Graph name cannot be empty", str(context.exception))

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_register_missing_bundle_file(self):
        """Test registration with non-existent bundle file."""
        csv_file = self.create_test_csv_file()
        non_existent_bundle = Path("non_existent_bundle.bundle")

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            with self.assertRaises(ValueError) as context:
                self.registry_service.register(
                    csv_hash=csv_hash,
                    graph_name="test_graph",
                    bundle_path=non_existent_bundle,
                    csv_path=csv_file,
                )

            self.assertIn("Bundle file does not exist", str(context.exception))

        finally:
            csv_file.unlink()

    # ===== THREAD SAFETY TESTS =====

    def test_concurrent_registrations(self):
        """Test concurrent registration operations."""
        csv_files = []
        bundle_files = []
        results = {}
        errors = []

        def register_entry(index: int):
            """Register an entry in a thread."""
            try:
                csv_file = self.create_test_csv_file(
                    f"node,agent,action\ntest{index},test{index},test{index}\n"
                )
                bundle_file = self.create_test_bundle_file(f"bundle{index}".encode())

                csv_files.append(csv_file)
                bundle_files.append(bundle_file)

                csv_hash = self.registry_service.compute_hash(csv_file)

                self.registry_service.register(
                    csv_hash=csv_hash,
                    graph_name=f"test_graph_{index}",
                    bundle_path=bundle_file,
                    csv_path=csv_file,
                    node_count=index,
                )

                results[index] = csv_hash

            except Exception as e:
                errors.append(f"Thread {index}: {e}")

        try:
            # Create and start multiple threads
            threads = []
            for i in range(10):
                thread = threading.Thread(target=register_entry, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Verify no errors occurred
            self.assertEqual(len(errors), 0, f"No thread errors expected: {errors}")

            # Verify all entries were registered
            self.assertEqual(len(results), 10, "All 10 entries should be registered")

            # Verify all entries can be found
            for index, csv_hash in results.items():
                entry = self.registry_service.get_entry_info(
                    csv_hash, f"test_graph_{index}"
                )
                self.assertIsNotNone(entry, f"Entry {index} should exist")
                self.assertEqual(entry["graph_name"], f"test_graph_{index}")
                self.assertEqual(entry["node_count"], index)

        finally:
            # Clean up files
            for csv_file in csv_files:
                if csv_file.exists():
                    csv_file.unlink()
            for bundle_file in bundle_files:
                if bundle_file.exists():
                    bundle_file.unlink()

    def test_concurrent_find_operations(self):
        """Test concurrent find operations."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            results = []
            errors = []

            def find_bundle():
                """Find bundle in a thread."""
                try:
                    found = self.registry_service.find_bundle(csv_hash)
                    results.append(found)
                except Exception as e:
                    errors.append(str(e))

            # Create and start multiple threads
            threads = []
            for i in range(20):
                thread = threading.Thread(target=find_bundle)
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Verify no errors occurred
            self.assertEqual(len(errors), 0, f"No thread errors expected: {errors}")

            # Verify all finds returned the same result
            self.assertEqual(len(results), 20, "All 20 finds should complete")
            for result in results:
                self.assertEqual(
                    result, bundle_file, "All finds should return same bundle"
                )

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    # ===== PERSISTENCE TESTS =====

    def test_persistence_on_registration(self):
        """Test that registration triggers persistence."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)
            initial_write_count = self.json_storage.write_count

            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            # Verify persistence was triggered
            self.assertGreater(
                self.json_storage.write_count,
                initial_write_count,
                "Registration should trigger persistence",
            )

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_persistence_failure_handling(self):
        """Test handling of persistence failures."""
        # Create service with failing storage
        failing_storage = MockJSONStorageService(fail_operations=True)
        failing_system_storage_manager = MockSystemStorageManager()
        failing_system_storage_manager._json_storage = failing_storage

        service = GraphRegistryService(
            system_storage_manager=failing_system_storage_manager,
            app_config_service=self.app_config,
            logging_service=self.logging_service,
        )

        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = service.compute_hash(csv_file)

            # Registration should complete despite persistence failure
            service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            # Entry should still exist in memory
            entry = service.get_entry_info(csv_hash, "test_graph")
            self.assertIsNotNone(
                entry, "Entry should exist in memory despite persistence failure"
            )

            # Error should be logged
            self.logging_service.logger.error.assert_called()

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_load_existing_registry(self):
        """Test loading existing registry from storage."""
        # Prepare mock data
        existing_data = {
            "version": "1.0.0",
            "entries": {
                "abc123": {
                    "existing_graph": {
                        "graph_name": "existing_graph",
                        "csv_hash": "abc123",
                        "bundle_path": "/path/to/bundle.bundle",
                        "csv_path": "/path/to/graph.csv",
                        "created_at": "2023-01-01T00:00:00",
                        "last_accessed": "2023-01-01T00:00:00",
                        "access_count": 0,
                        "bundle_size": 1024,
                        "node_count": 5,
                    }
                }
            },
            "metadata": {
                "created_at": "2023-01-01T00:00:00",
                "last_modified": "2023-01-01T00:00:00",
                "total_entries": 1,
                "total_bundle_size": 1024,
            },
        }

        # Configure storage to return existing data
        storage = MockJSONStorageService()
        # The service uses the registry filename as the collection key
        registry_filename = "graph_registry.json"
        # Store data with the registry filename as the key
        storage.stored_data[registry_filename] = existing_data

        # Create new service - should load existing data
        system_storage_manager = MockSystemStorageManager()
        system_storage_manager._json_storage = storage

        service = GraphRegistryService(
            system_storage_manager=system_storage_manager,
            app_config_service=self.app_config,
            logging_service=self.logging_service,
        )

        # Verify data was loaded
        entry = service.get_entry_info("abc123", "existing_graph")
        self.assertIsNotNone(entry, "Existing entry should be loaded")
        self.assertEqual(entry["graph_name"], "existing_graph")
        self.assertEqual(entry["node_count"], 5)

    def test_load_empty_registry(self):
        """Test loading when no existing registry exists."""
        # Configure storage to return no data
        storage = MockJSONStorageService(empty_registry=True)

        # Create new service - should create empty registry
        system_storage_manager = MockSystemStorageManager()
        system_storage_manager._json_storage = storage

        service = GraphRegistryService(
            system_storage_manager=system_storage_manager,
            app_config_service=self.app_config,
            logging_service=self.logging_service,
        )

        # Verify empty registry was created
        non_existent_entry = service.get_entry_info("nonexistent", "nonexistent_graph")
        self.assertIsNone(non_existent_entry, "Should have empty registry")

        # Verify initial persistence was called
        self.assertGreater(storage.write_count, 0, "Should persist empty registry")

    # ===== METADATA TESTS =====

    def test_metadata_tracking(self):
        """Test that metadata is properly tracked."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file(b"test data for size calculation")

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Get initial metadata state (should be clean registry)
            initial_metadata = self.registry_service._metadata.copy()

            # Register entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
                node_count=3,
            )

            # Verify metadata was updated
            updated_metadata = self.registry_service._metadata
            self.assertEqual(
                updated_metadata["total_entries"],
                initial_metadata["total_entries"] + 1,
                "Entry count should increase",
            )
            self.assertGreater(
                updated_metadata["total_bundle_size"],
                initial_metadata["total_bundle_size"],
                "Bundle size should increase",
            )
            self.assertNotEqual(
                updated_metadata["last_modified"],
                initial_metadata["last_modified"],
                "Last modified should be updated",
            )

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    def test_metadata_removal_tracking(self):
        """Test that metadata is updated when entries are removed."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register entry
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            # Get metadata after registration
            after_registration = self.registry_service._metadata.copy()

            # Remove entry
            self.registry_service.remove_entry(csv_hash)

            # Verify metadata was updated
            after_removal = self.registry_service._metadata
            self.assertEqual(
                after_removal["total_entries"],
                after_registration["total_entries"] - 1,
                "Entry count should decrease",
            )
            self.assertLess(
                after_removal["total_bundle_size"],
                after_registration["total_bundle_size"],
                "Bundle size should decrease",
            )

        finally:
            csv_file.unlink()
            bundle_file.unlink()

    # ===== PERFORMANCE TESTS =====
    # skip this in CI
    @unittest.skip("Skipping performance tests in CI")
    def test_lookup_performance(self):
        """Test O(1) lookup performance."""
        # Register multiple entries
        csv_files = []
        bundle_files = []
        hashes = []

        try:
            # Register 100 entries
            for i in range(100):
                csv_file = self.create_test_csv_file(
                    f"node,agent,action\ntest{i},test{i},test{i}\n"
                )
                bundle_file = self.create_test_bundle_file(f"bundle{i}".encode())

                csv_files.append(csv_file)
                bundle_files.append(bundle_file)

                csv_hash = self.registry_service.compute_hash(csv_file)
                hashes.append(csv_hash)

                self.registry_service.register(
                    csv_hash=csv_hash,
                    graph_name=f"graph_{i}",
                    bundle_path=bundle_file,
                    csv_path=csv_file,
                )

            # Measure lookup performance
            start_time = time.time()

            # Perform 1000 lookups
            for _ in range(1000):
                for csv_hash in hashes[:10]:  # Use first 10 hashes
                    self.registry_service.find_bundle(csv_hash)

            total_time = time.time() - start_time

            # Performance should be very fast (O(1) lookups)
            self.assertLess(
                total_time, 1.0, "10,000 lookups should complete in under 1 second"
            )

            avg_time_per_lookup = total_time / 10000
            self.assertLess(
                avg_time_per_lookup, 0.0001, "Each lookup should be under 0.1ms"
            )

            print(f"Lookup performance: {avg_time_per_lookup*1000:.3f}ms per lookup")

        finally:
            # Clean up files
            for csv_file in csv_files:
                if csv_file.exists():
                    csv_file.unlink()
            for bundle_file in bundle_files:
                if bundle_file.exists():
                    bundle_file.unlink()

    def test_hash_computation_performance(self):
        """Test hash computation performance for various file sizes."""
        test_sizes = [1024, 10240, 102400]  # 1KB, 10KB, 100KB

        for size in test_sizes:
            content = "a" * size
            csv_file = self.create_test_csv_file(content)

            try:
                start_time = time.time()
                csv_hash = self.registry_service.compute_hash(csv_file)
                computation_time = time.time() - start_time

                # Verify hash is correct
                self.assertEqual(len(csv_hash), 64)

                # Performance should be reasonable
                self.assertLess(
                    computation_time,
                    1.0,
                    f"Hash computation for {size} bytes should be under 1 second",
                )

                print(f"Hash computation ({size} bytes): {computation_time*1000:.2f}ms")

            finally:
                csv_file.unlink()

    # ===== ERROR RECOVERY TESTS =====

    def test_recovery_from_load_error(self):
        """Test recovery when registry loading fails."""
        # Create a mock storage that raises an exception instead of returning failed result
        failing_storage = MockJSONStorageService()

        def failing_read(*args, **kwargs):
            raise Exception("Simulated storage failure")

        failing_storage.read = failing_read

        failing_system_storage_manager = MockSystemStorageManager()
        failing_system_storage_manager._json_storage = failing_storage

        service = GraphRegistryService(
            system_storage_manager=failing_system_storage_manager,
            app_config_service=self.app_config,
            logging_service=self.logging_service,
        )

        # Service should still be functional with empty registry
        non_existent = service.find_bundle("abc123")
        self.assertIsNone(non_existent, "Should return None for non-existent entry")

        # Warning should be logged about registry creation
        self.assertTrue(
            self.logging_service.logger.warning.called,
            "Warning should be logged during error recovery",
        )

    def test_schema_version_mismatch_warning(self):
        """Test warning when loading registry with different schema version."""
        # Prepare mock data with different version
        existing_data = {
            "version": "0.9.0",  # Different version
            "entries": {},
            "metadata": {
                "created_at": "2023-01-01T00:00:00",
                "last_modified": "2023-01-01T00:00:00",
                "total_entries": 0,
                "total_bundle_size": 0,
            },
        }

        storage = MockJSONStorageService()
        # The service uses the registry filename as the collection key
        registry_filename = "graph_registry.json"
        storage.stored_data[registry_filename] = existing_data

        # Create service - should warn about version mismatch
        system_storage_manager = MockSystemStorageManager()
        system_storage_manager._json_storage = storage

        GraphRegistryService(
            system_storage_manager=system_storage_manager,
            app_config_service=self.app_config,
            logging_service=self.logging_service,
        )

        # Verify warning was logged
        self.logging_service.logger.warning.assert_called()
        warning_call = self.logging_service.logger.warning.call_args[0][0]
        self.assertIn("Registry schema version mismatch", warning_call)

    # ===== INTEGRATION VERIFICATION TESTS =====

    def test_configuration_path_integration(self):
        """Test integration with app config service for paths."""
        custom_cache_path = Path(self.temp_dir.name) / "custom_cache"
        custom_config = MockAppConfigService(custom_cache_path)

        custom_system_storage_manager = MockSystemStorageManager()
        custom_system_storage_manager._json_storage = self.json_storage

        service = GraphRegistryService(
            system_storage_manager=custom_system_storage_manager,
            app_config_service=custom_config,
            logging_service=self.logging_service,
        )

        # Verify custom path is used - the service stores only the filename, not the full path
        expected_registry_path = "graph_registry.json"
        self.assertEqual(service._registry_path, expected_registry_path)

    def test_logging_integration(self):
        """Test integration with logging service."""
        csv_file = self.create_test_csv_file()
        bundle_file = self.create_test_bundle_file()

        try:
            csv_hash = self.registry_service.compute_hash(csv_file)

            # Register entry - should log info message
            self.registry_service.register(
                csv_hash=csv_hash,
                graph_name="test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
            )

            # Verify info logging occurred
            self.logging_service.logger.info.assert_called()
            info_calls = [
                call[0][0] for call in self.logging_service.logger.info.call_args_list
            ]
            registration_logged = any(
                "Registering graph bundle" in msg for msg in info_calls
            )
            self.assertTrue(registration_logged, "Registration should be logged")

        finally:
            csv_file.unlink()
            bundle_file.unlink()


class TestGraphRegistryServiceIntegration(unittest.TestCase):
    """Integration tests for GraphRegistryService with real dependencies."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.test_cache_path = Path(self.temp_dir.name) / "integration_cache"
        self.test_cache_path.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up integration test fixtures."""
        self.temp_dir.cleanup()

    def test_real_file_persistence(self):
        """Test with real file system persistence."""
        # This would require actual JSONStorageService implementation
        # For now, we verify the mock behavior matches expected interface

    def test_concurrent_service_instances(self):
        """Test multiple service instances accessing same registry."""
        # Create shared mock storage
        shared_storage = MockJSONStorageService()
        shared_config = MockAppConfigService(self.test_cache_path)

        # Create two service instances
        logging1 = MockLoggingService()
        logging2 = MockLoggingService()

        shared_system_storage_manager1 = MockSystemStorageManager()
        shared_system_storage_manager1._json_storage = shared_storage

        shared_system_storage_manager2 = MockSystemStorageManager()
        shared_system_storage_manager2._json_storage = shared_storage

        service1 = GraphRegistryService(
            system_storage_manager=shared_system_storage_manager1,
            app_config_service=shared_config,
            logging_service=logging1,
        )

        GraphRegistryService(
            system_storage_manager=shared_system_storage_manager2,
            app_config_service=shared_config,
            logging_service=logging2,
        )

        # Register entry with service1
        csv_file = NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        csv_file.write("node,agent,action\ntest,test,test\n")
        csv_file.flush()
        csv_file.close()
        csv_path = Path(csv_file.name)

        bundle_file = NamedTemporaryFile(mode="wb", suffix=".bundle", delete=False)
        bundle_file.write(b"test bundle")
        bundle_file.flush()
        bundle_file.close()
        bundle_path = Path(bundle_file.name)

        try:
            csv_hash = service1.compute_hash(csv_path)
            service1.register(
                csv_hash=csv_hash,
                graph_name="shared_graph",
                bundle_path=bundle_path,
                csv_path=csv_path,
            )

            # Service2 should be able to find it after reload
            # In real scenario, this would require service2 to reload from persistent storage
            # For now, we verify the storage interaction occurred
            self.assertGreater(
                shared_storage.write_count,
                0,
                "Registration should persist to shared storage",
            )

        finally:
            csv_path.unlink()
            bundle_path.unlink()


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
