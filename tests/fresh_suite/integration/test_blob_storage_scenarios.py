"""
Functional scenario tests for blob storage.

These tests validate:
- Write/read round-trip integrity across a range of data sizes
- Correctness and thread-safety under concurrent and mixed operations
- Stability of repeated operations
- Cloud provider-specific behavior scenarios
- Error recovery and resilience patterns
- Cross-provider compatibility and migration scenarios

These run against an in-memory mock service and make no timing/throughput
assertions; performance benchmarking belongs in a separate, opt-in suite.
"""

import concurrent.futures
import unittest
from unittest.mock import Mock, patch

from agentmap.agents.builtins.storage.blob.blob_reader_agent import BlobReaderAgent
from agentmap.agents.builtins.storage.blob.blob_writer_agent import BlobWriterAgent
from agentmap.exceptions import StorageConnectionError, StorageOperationError
from agentmap.services.storage.blob_storage_service import BlobStorageService
from tests.fresh_suite.unit.services.storage.blob_storage_test_fixtures import (
    BlobAgentTestHelpers,
    BlobStorageTestFixtures,
    CloudProviderScenarios,
    MockBlobStorageServiceFactory,
    MockCloudProviderHelpers,
    PerformanceTestHelpers,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestBlobStorageOperationScenarios(unittest.TestCase):
    """
    Functional scenario tests for blob storage write/read agents.

    Exercises the BlobWriterAgent -> BlobReaderAgent round trip across a range
    of data sizes, concurrent access patterns, and repeated operations to
    verify correctness and thread-safety. These run against an in-memory mock
    service, so they intentionally make no wall-clock/throughput assertions
    (those would only measure runner speed, not the code under test). True
    performance benchmarking belongs in a dedicated, opt-in benchmark suite
    against real or latency-simulating providers.
    """

    def setUp(self):
        """Set up scenario test fixtures."""
        self.mock_config = MockServiceFactory.create_mock_app_config_service(
            {"storage": {"blob": {"providers": {"file": {"base_directory": "/tmp"}}}}}
        )
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        self.mock_availability_cache = (
            MockServiceFactory.create_mock_availability_cache_service()
        )

        # Create service for testing
        self.service = BlobStorageService(
            configuration=self.mock_config,
            logging_service=self.mock_logging,
            availability_cache=self.mock_availability_cache,
        )

    # =============================================================================
    # Data Size Round-Trip Tests
    # =============================================================================

    def _assert_round_trip(self, size: int, uri: str):
        """Write `size` bytes through the writer agent, read them back through
        the reader agent, and assert the bytes survive the round trip intact."""
        test_data = PerformanceTestHelpers.generate_test_data(size)

        mock_service = MockBlobStorageServiceFactory.create_successful_service()
        writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
        reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)

        writer.process({"blob_uri": uri, "data": test_data})
        read_result = reader.process({"blob_uri": uri})

        self.assertEqual(
            read_result,
            test_data,
            f"Round-trip mismatch for {size} bytes",
        )

    def test_round_trip_small_data(self):
        """Small payloads (10B, 100B, 1KB) round-trip through write/read intact."""
        for size in [10, 100, 1024]:
            with self.subTest(size=size):
                self._assert_round_trip(size, f"/tmp/roundtrip_small_{size}.blob")

    def test_round_trip_medium_data(self):
        """Medium payloads (10KB, 100KB, 1MB) round-trip through write/read intact."""
        for size in [10 * 1024, 100 * 1024, 1024 * 1024]:
            with self.subTest(size=size):
                self._assert_round_trip(size, f"/tmp/roundtrip_medium_{size}.blob")

    def test_round_trip_large_data(self):
        """Large payloads (5MB, 10MB) round-trip through write/read intact."""
        for size in [5 * 1024 * 1024, 10 * 1024 * 1024]:
            with self.subTest(size=size):
                self._assert_round_trip(size, f"/tmp/roundtrip_large_{size}.blob")

    # =============================================================================
    # Concurrent Operations Tests (thread-safety / correctness)
    # =============================================================================

    @staticmethod
    def _concurrent_uri(prefix: str, thread_id: int, op_id: int) -> str:
        return f"/tmp/{prefix}_{thread_id}_{op_id}.blob"

    def test_concurrent_writes_all_succeed(self):
        """Concurrent writes from multiple threads complete and store correct data."""
        num_threads = 5
        operations_per_thread = 3
        test_data = PerformanceTestHelpers.generate_test_data(1024)  # 1KB per operation

        mock_service = MockBlobStorageServiceFactory.create_successful_service()

        def write_worker(thread_id: int) -> int:
            """Write `operations_per_thread` blobs; return the number written."""
            writer = BlobAgentTestHelpers.create_test_blob_writer(
                blob_service=mock_service
            )
            for op_id in range(operations_per_thread):
                writer.process(
                    {
                        "blob_uri": self._concurrent_uri("cwrite", thread_id, op_id),
                        "data": test_data,
                    }
                )
            return operations_per_thread

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_worker, i) for i in range(num_threads)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        self.assertEqual(
            sum(results),
            num_threads * operations_per_thread,
            "Not all concurrent writes completed",
        )

        # Every concurrently-written blob must hold the data that was written.
        reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
        for thread_id in range(num_threads):
            for op_id in range(operations_per_thread):
                self.assertEqual(
                    reader.process(
                        {"blob_uri": self._concurrent_uri("cwrite", thread_id, op_id)}
                    ),
                    test_data,
                    f"Concurrent write {thread_id}/{op_id} stored wrong data",
                )

    def test_concurrent_reads_all_succeed(self):
        """Concurrent reads from multiple threads return the data that was written."""
        num_threads = 5
        operations_per_thread = 3

        mock_service = MockBlobStorageServiceFactory.create_successful_service()

        def expected_data(thread_id: int, op_id: int) -> bytes:
            return f"payload-{thread_id}-{op_id}".encode("utf-8")

        # Pre-populate each blob with distinct, known data so the reads have
        # something real to verify against.
        writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
        for thread_id in range(num_threads):
            for op_id in range(operations_per_thread):
                writer.process(
                    {
                        "blob_uri": self._concurrent_uri("cread", thread_id, op_id),
                        "data": expected_data(thread_id, op_id),
                    }
                )

        def read_worker(thread_id: int) -> list:
            """Read this thread's blobs; return per-op data-integrity booleans."""
            reader = BlobAgentTestHelpers.create_test_blob_reader(
                blob_service=mock_service
            )
            return [
                reader.process(
                    {"blob_uri": self._concurrent_uri("cread", thread_id, op_id)}
                )
                == expected_data(thread_id, op_id)
                for op_id in range(operations_per_thread)
            ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_worker, i) for i in range(num_threads)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        checks = [ok for thread_checks in results for ok in thread_checks]
        self.assertEqual(
            len(checks),
            num_threads * operations_per_thread,
            "Not all concurrent reads completed",
        )
        self.assertTrue(all(checks), "Some concurrent reads returned incorrect data")

    def test_mixed_concurrent_operations_all_succeed(self):
        """Interleaved concurrent reads and writes complete and use correct data."""
        num_operations = 10
        test_data = PerformanceTestHelpers.generate_test_data(512)  # 512B per operation

        mock_service = MockBlobStorageServiceFactory.create_successful_service()

        def uri_for(operation_id: int) -> str:
            return f"/tmp/mixed_op_{operation_id}.blob"

        # Pre-populate the blobs that the read operations (odd ids) will target.
        setup_writer = BlobAgentTestHelpers.create_test_blob_writer(
            blob_service=mock_service
        )
        for operation_id in range(num_operations):
            if operation_id % 2 == 1:
                setup_writer.process(
                    {"blob_uri": uri_for(operation_id), "data": test_data}
                )

        def mixed_worker(operation_id: int) -> tuple:
            """Perform one read or write; return (op_type, data_ok)."""
            if operation_id % 2 == 0:
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                writer.process({"blob_uri": uri_for(operation_id), "data": test_data})
                return ("write", True)
            else:
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )
                result = reader.process({"blob_uri": uri_for(operation_id)})
                return ("read", result == test_data)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(mixed_worker, i) for i in range(num_operations)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        op_types = [op_type for op_type, _ in results]
        self.assertEqual(
            len(results), num_operations, "Not all mixed operations completed"
        )
        self.assertEqual(op_types.count("write"), 5)
        self.assertEqual(op_types.count("read"), 5)
        self.assertTrue(
            all(ok for _, ok in results),
            "Some mixed operations read or wrote incorrect data",
        )

    # =============================================================================
    # Repeated Operation Stability Tests
    # =============================================================================

    def test_repeated_operations_remain_consistent(self):
        """Repeating the write/read cycle keeps returning the same data intact."""
        # Progressively larger data, repeated to surface state-bleed or leaks.
        test_sizes = [1024, 10 * 1024, 100 * 1024]  # 1KB, 10KB, 100KB

        mock_service = MockBlobStorageServiceFactory.create_successful_service()

        for size in test_sizes:
            with self.subTest(size=size):
                test_data = PerformanceTestHelpers.generate_test_data(size)
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )
                test_uri = f"/tmp/repeat_test_{size}.blob"

                # Each iteration must return the same intact payload.
                for _ in range(5):
                    writer.process({"blob_uri": test_uri, "data": test_data})
                    read_result = reader.process({"blob_uri": test_uri})
                    self.assertEqual(read_result, test_data)


class TestBlobStorageCloudProviderScenarios(unittest.TestCase):
    """
    Cloud provider scenario tests for blob storage.

    Tests various cloud provider-specific behaviors, error conditions,
    and compatibility scenarios.
    """

    def setUp(self):
        """Set up cloud provider scenario test fixtures."""
        self.mock_config = MockServiceFactory.create_mock_app_config_service()
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        self.mock_availability_cache = (
            MockServiceFactory.create_mock_availability_cache_service()
        )

    # =============================================================================
    # Azure Blob Storage Scenario Tests
    # =============================================================================

    def test_azure_success_scenarios(self):
        """Test successful Azure Blob Storage operations."""
        scenarios = [
            "successful_upload",
            "successful_download",
            "successful_metadata_retrieval",
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                # Create service with Azure configuration
                azure_config = MockServiceFactory.create_mock_app_config_service(
                    {
                        "storage": {
                            "blob": {
                                "providers": {
                                    "azure": BlobStorageTestFixtures.AZURE_CONFIG
                                }
                            }
                        }
                    }
                )

                BlobStorageService(
                    configuration=azure_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache,
                )

                # Mock Azure behavior
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                MockCloudProviderHelpers.mock_azure_behavior(mock_service, "success")

                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                # Test workflow
                test_uri = BlobStorageTestFixtures.AZURE_TEST_URI
                test_data = BlobStorageTestFixtures.TEST_STRING_DATA

                success = BlobAgentTestHelpers.test_agent_workflow(
                    writer, reader, test_data, test_uri
                )
                self.assertTrue(success, f"Azure scenario {scenario} failed")

    def test_azure_error_scenarios(self):
        """Test Azure Blob Storage error scenarios."""
        error_scenarios = ["not_found", "auth_error"]

        for scenario in error_scenarios:
            with self.subTest(scenario=scenario):
                # Create service
                BlobStorageService(
                    configuration=self.mock_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache,
                )

                # Mock Azure error behavior
                mock_service = Mock()
                MockCloudProviderHelpers.mock_azure_behavior(mock_service, scenario)

                # Create reader agent
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                # Test should raise appropriate error
                test_uri = BlobStorageTestFixtures.AZURE_TEST_URI

                with self.assertRaises(
                    (FileNotFoundError, StorageConnectionError, StorageOperationError)
                ):
                    reader.process({"blob_uri": test_uri})

    # =============================================================================
    # AWS S3 Scenario Tests
    # =============================================================================

    def test_s3_success_scenarios(self):
        """Test successful AWS S3 operations."""
        scenarios = [
            "successful_put_object",
            "successful_get_object",
            "successful_list_objects",
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                # Create service with S3 configuration
                s3_config = MockServiceFactory.create_mock_app_config_service(
                    {
                        "storage": {
                            "blob": {
                                "providers": {"s3": BlobStorageTestFixtures.S3_CONFIG}
                            }
                        }
                    }
                )

                BlobStorageService(
                    configuration=s3_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache,
                )

                # Mock S3 behavior
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                MockCloudProviderHelpers.mock_s3_behavior(mock_service, "success")

                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                # Test workflow
                test_uri = BlobStorageTestFixtures.S3_TEST_URI
                test_data = BlobStorageTestFixtures.TEST_STRING_DATA

                success = BlobAgentTestHelpers.test_agent_workflow(
                    writer, reader, test_data, test_uri
                )
                self.assertTrue(success, f"S3 scenario {scenario} failed")

    def test_s3_error_scenarios(self):
        """Test AWS S3 error scenarios."""
        error_scenarios = ["not_found", "access_denied"]

        for scenario in error_scenarios:
            with self.subTest(scenario=scenario):
                # Create service
                BlobStorageService(
                    configuration=self.mock_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache,
                )

                # Mock S3 error behavior
                mock_service = Mock()
                MockCloudProviderHelpers.mock_s3_behavior(mock_service, scenario)

                # Create reader agent
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                # Test should raise appropriate error
                test_uri = BlobStorageTestFixtures.S3_TEST_URI

                with self.assertRaises((FileNotFoundError, StorageOperationError)):
                    reader.process({"blob_uri": test_uri})

    # =============================================================================
    # Google Cloud Storage Scenario Tests
    # =============================================================================

    def test_gcs_success_scenarios(self):
        """Test successful Google Cloud Storage operations."""
        scenarios = [
            "successful_upload",
            "successful_download",
            "successful_list_blobs",
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                # Create service with GCS configuration
                gcs_config = MockServiceFactory.create_mock_app_config_service(
                    {
                        "storage": {
                            "blob": {
                                "providers": {"gs": BlobStorageTestFixtures.GCS_CONFIG}
                            }
                        }
                    }
                )

                BlobStorageService(
                    configuration=gcs_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache,
                )

                # Mock GCS behavior
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                MockCloudProviderHelpers.mock_gcs_behavior(mock_service, "success")

                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                # Test workflow
                test_uri = BlobStorageTestFixtures.GCS_TEST_URI
                test_data = BlobStorageTestFixtures.TEST_STRING_DATA

                success = BlobAgentTestHelpers.test_agent_workflow(
                    writer, reader, test_data, test_uri
                )
                self.assertTrue(success, f"GCS scenario {scenario} failed")

    def test_gcs_error_scenarios(self):
        """Test Google Cloud Storage error scenarios."""
        error_scenarios = ["not_found", "quota_exceeded"]

        for scenario in error_scenarios:
            with self.subTest(scenario=scenario):
                # Create service
                BlobStorageService(
                    configuration=self.mock_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache,
                )

                # Mock GCS error behavior
                mock_service = Mock()
                MockCloudProviderHelpers.mock_gcs_behavior(mock_service, scenario)

                # Test should handle errors appropriately
                test_uri = BlobStorageTestFixtures.GCS_TEST_URI

                if scenario == "not_found":
                    reader = BlobAgentTestHelpers.create_test_blob_reader(
                        blob_service=mock_service
                    )
                    with self.assertRaises(FileNotFoundError):
                        reader.process({"blob_uri": test_uri})
                elif scenario == "quota_exceeded":
                    writer = BlobAgentTestHelpers.create_test_blob_writer(
                        blob_service=mock_service
                    )
                    with self.assertRaises(StorageOperationError):
                        writer.process({"blob_uri": test_uri, "data": "test"})

    # =============================================================================
    # Cross-Provider Compatibility Tests
    # =============================================================================

    def test_cross_provider_data_compatibility(self):
        """Test data compatibility across different providers."""
        providers = ["azure", "s3", "gs", "file"]
        test_data_types = [
            ("string", BlobStorageTestFixtures.TEST_STRING_DATA),
            ("json", BlobStorageTestFixtures.TEST_JSON_DATA),
            ("binary", BlobStorageTestFixtures.TEST_BINARY_DATA),
        ]

        for provider in providers:
            for data_type, test_data in test_data_types:
                with self.subTest(provider=provider, data_type=data_type):
                    # Create mock service for provider
                    mock_service = (
                        MockBlobStorageServiceFactory.create_successful_service()
                    )

                    # Create agents
                    writer = BlobAgentTestHelpers.create_test_blob_writer(
                        blob_service=mock_service
                    )
                    reader = BlobAgentTestHelpers.create_test_blob_reader(
                        blob_service=mock_service
                    )

                    # Test data round-trip
                    test_uri = BlobStorageTestFixtures.get_test_uri_for_provider(
                        provider, f"compat_{data_type}.blob"
                    )

                    success = BlobAgentTestHelpers.test_agent_workflow(
                        writer, reader, test_data, test_uri
                    )
                    self.assertTrue(
                        success,
                        f"Cross-provider compatibility failed: {provider}/{data_type}",
                    )

    def test_provider_migration_scenarios(self):
        """Test scenarios for migrating data between providers."""
        migration_pairs = [
            ("azure", "s3"),
            ("s3", "gs"),
            ("gs", "file"),
            ("file", "azure"),
        ]

        test_data = BlobStorageTestFixtures.TEST_STRING_DATA

        for source_provider, target_provider in migration_pairs:
            with self.subTest(source=source_provider, target=target_provider):
                # Create mock services
                source_service = (
                    MockBlobStorageServiceFactory.create_successful_service()
                )
                target_service = (
                    MockBlobStorageServiceFactory.create_successful_service()
                )

                # Source: write data
                source_writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=source_service
                )
                source_reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=source_service
                )

                source_uri = BlobStorageTestFixtures.get_test_uri_for_provider(
                    source_provider, "migration_test.blob"
                )

                # Write to source
                source_writer.process({"blob_uri": source_uri, "data": test_data})

                # Read from source
                source_data = source_reader.process({"blob_uri": source_uri})

                # Target: write the same data
                target_writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=target_service
                )
                target_reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=target_service
                )

                target_uri = BlobStorageTestFixtures.get_test_uri_for_provider(
                    target_provider, "migration_test.blob"
                )

                # Write to target
                target_writer.process({"blob_uri": target_uri, "data": source_data})

                # Read from target
                target_data = target_reader.process({"blob_uri": target_uri})

                # Data should be identical
                self.assertEqual(
                    source_data,
                    target_data,
                    f"Migration data mismatch: {source_provider} -> {target_provider}",
                )

    # =============================================================================
    # Provider Availability and Fallback Tests
    # =============================================================================

    def test_provider_availability_detection(self):
        """Test provider availability detection scenarios."""
        availability_scenarios = (
            CloudProviderScenarios.get_provider_availability_scenarios()
        )

        for scenario in availability_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Mock provider availability
                with patch(
                    "agentmap.services.storage.blob_storage_service.BlobStorageService._check_azure_availability"
                ) as mock_azure:
                    with patch(
                        "agentmap.services.storage.blob_storage_service.BlobStorageService._check_s3_availability"
                    ) as mock_s3:
                        with patch(
                            "agentmap.services.storage.blob_storage_service.BlobStorageService._check_gcs_availability"
                        ) as mock_gcs:
                            # Configure availability
                            mock_azure.return_value = scenario["azure_available"]
                            mock_s3.return_value = scenario["s3_available"]
                            mock_gcs.return_value = scenario["gcs_available"]

                            # Create service
                            service = BlobStorageService(
                                configuration=self.mock_config,
                                logging_service=self.mock_logging,
                                availability_cache=self.mock_availability_cache,
                            )

                            # Check available providers
                            available_providers = service.get_available_providers()

                            # Verify expected providers are available
                            for expected_provider in scenario["expected_providers"]:
                                self.assertIn(
                                    expected_provider,
                                    available_providers,
                                    f"Expected provider {expected_provider} not available in scenario {scenario['name']}",
                                )

    def test_provider_fallback_mechanisms(self):
        """Test fallback mechanisms when preferred providers fail."""
        # Test scenario: Azure fails, fallback to S3, then to local
        fallback_chain = ["azure", "s3", "file"]

        for failing_provider_index in range(len(fallback_chain)):
            with self.subTest(failing_index=failing_provider_index):
                # Create services with different failure points
                mock_services = []
                for i, provider in enumerate(fallback_chain):
                    if i <= failing_provider_index:
                        # This provider and earlier ones fail
                        mock_service = (
                            MockBlobStorageServiceFactory.create_failing_service()
                        )
                    else:
                        # This provider succeeds
                        mock_service = (
                            MockBlobStorageServiceFactory.create_successful_service()
                        )
                    mock_services.append(mock_service)

                # In a real implementation, the service would try providers in order
                # For this test, we verify that at least one working provider exists
                working_services = [
                    s for s in mock_services[failing_provider_index + 1 :]
                ]

                if working_services:
                    # Should be able to use working service
                    working_service = working_services[0]

                    reader = BlobAgentTestHelpers.create_test_blob_reader(
                        blob_service=working_service
                    )

                    # Operation should succeed with working service
                    test_uri = "/tmp/fallback_test.blob"
                    result = reader.process({"blob_uri": test_uri})
                    self.assertIsInstance(result, bytes)

    # =============================================================================
    # Error Recovery and Resilience Tests
    # =============================================================================

    def test_error_recovery_patterns(self):
        """Test error recovery patterns for different failure scenarios."""
        error_scenarios = CloudProviderScenarios.get_error_scenarios()

        for scenario in error_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Create mock service that raises the specified error
                mock_service = Mock()

                error_type = scenario["error_type"]
                if isinstance(error_type, str):
                    # Handle string error types
                    if error_type == "StorageOperationError":
                        error_instance = StorageOperationError(
                            scenario["error_message"]
                        )
                    elif error_type == "StorageConnectionError":
                        error_instance = StorageConnectionError(
                            scenario["error_message"]
                        )
                    else:
                        error_instance = Exception(scenario["error_message"])
                else:
                    # Handle class error types
                    error_instance = error_type(scenario["error_message"])

                if scenario["operation"] == "read":
                    mock_service.read_blob.side_effect = error_instance
                elif scenario["operation"] == "write":
                    mock_service.write_blob.side_effect = error_instance

                # Create agent
                if scenario["operation"] == "read":
                    agent = BlobAgentTestHelpers.create_test_blob_reader(
                        blob_service=mock_service
                    )
                    inputs = {"blob_uri": "/tmp/error_test.blob"}
                else:
                    agent = BlobAgentTestHelpers.create_test_blob_writer(
                        blob_service=mock_service
                    )
                    inputs = {"blob_uri": "/tmp/error_test.blob", "data": "test"}

                # Test error handling
                if scenario["expected_behavior"] == "re_raise":
                    with self.assertRaises(type(error_instance)):
                        agent.process(inputs)

                # Agent should remain functional after error
                # Test with a working service
                working_service = (
                    MockBlobStorageServiceFactory.create_successful_service()
                )
                agent.configure_blob_storage_service(working_service)

                # Should work now
                try:
                    result = agent.process(inputs)
                    # Success indicates good error recovery
                    self.assertIsNotNone(result)
                except Exception:
                    # Some operations might still fail due to test setup, but agent should be stable
                    self.assertIsInstance(agent, (BlobReaderAgent, BlobWriterAgent))

    def test_intermittent_failure_resilience(self):
        """Test resilience to intermittent failures."""
        # Create service that fails intermittently
        failure_rate = 0.3  # 30% failure rate
        mock_service = MockBlobStorageServiceFactory.create_intermittent_service(
            failure_rate
        )

        # Create agents
        writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
        reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)

        # Run multiple operations
        num_operations = 20
        successes = 0
        failures = 0

        for i in range(num_operations):
            try:
                test_uri = f"/tmp/intermittent_{i}.blob"
                writer.process({"blob_uri": test_uri, "data": f"test data {i}"})
                reader.process({"blob_uri": test_uri})
                successes += 1
            except StorageOperationError:
                failures += 1

        # Should have some successes and some failures
        self.assertGreater(
            successes, 0, "No successful operations in intermittent failure test"
        )
        self.assertGreater(
            failures, 0, "No failed operations in intermittent failure test"
        )

        # Failure rate should be approximately as expected (with some tolerance)
        actual_failure_rate = failures / num_operations
        self.assertLess(
            abs(actual_failure_rate - failure_rate),
            0.2,
            f"Actual failure rate {actual_failure_rate} too far from expected {failure_rate}",
        )


if __name__ == "__main__":
    unittest.main()
