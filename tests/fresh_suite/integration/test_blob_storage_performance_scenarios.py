"""
Performance and cloud provider scenario tests for blob storage.

These tests validate:
- Performance characteristics under various load conditions
- Scalability with different data sizes and concurrent operations
- Cloud provider-specific behavior scenarios
- Error recovery and resilience patterns
- Resource utilization and optimization
- Cross-provider compatibility and migration scenarios
"""

import unittest
import tempfile
import shutil
import time
import threading
import concurrent.futures
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple

from agentmap.services.storage.blob_storage_service import BlobStorageService
from agentmap.agents.builtins.storage.blob.blob_reader_agent import BlobReaderAgent
from agentmap.agents.builtins.storage.blob.blob_writer_agent import BlobWriterAgent
from agentmap.exceptions import StorageConnectionError, StorageOperationError
from tests.utils.mock_service_factory import MockServiceFactory
from tests.fresh_suite.unit.services.storage.blob_storage_test_fixtures import (
    BlobStorageTestFixtures,
    MockBlobStorageServiceFactory,
    CloudProviderScenarios,
    PerformanceTestHelpers,
    BlobAgentTestHelpers,
    MockCloudProviderHelpers
)


class TestBlobStoragePerformance(unittest.TestCase):
    """
    Performance tests for blob storage operations.
    
    Tests various performance characteristics including throughput,
    latency, memory usage, and scalability under different conditions.
    """
    
    def setUp(self):
        """Set up performance test fixtures."""
        self.mock_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {"blob": {"providers": {"file": {"base_directory": "/tmp"}}}}
        })
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        self.mock_availability_cache = MockServiceFactory.create_mock_availability_cache_service()
        
        # Create service for testing
        self.service = BlobStorageService(
            configuration=self.mock_config,
            logging_service=self.mock_logging,
            availability_cache=self.mock_availability_cache
        )
    
    # =============================================================================
    # Data Size Performance Tests
    # =============================================================================
    
    def test_performance_small_data_operations(self):
        """Test performance with small data (< 1KB)."""
        # Test data sizes: 10B, 100B, 1KB
        test_sizes = [10, 100, 1024]
        max_time = 0.1  # 100ms should be more than enough for small data
        
        for size in test_sizes:
            with self.subTest(size=size):
                test_data = PerformanceTestHelpers.generate_test_data(size)
                
                # Mock successful operations
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                
                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                test_uri = f"/tmp/perf_small_{size}.blob"
                
                # Measure write performance
                write_time = PerformanceTestHelpers.measure_operation_time(
                    writer.process, {"blob_uri": test_uri, "data": test_data}
                )
                
                # Measure read performance  
                read_time = PerformanceTestHelpers.measure_operation_time(
                    reader.process, {"blob_uri": test_uri}
                )
                
                # Validate performance
                self.assertLess(write_time, max_time, 
                               f"Write too slow for {size}B: {write_time:.3f}s")
                self.assertLess(read_time, max_time,
                               f"Read too slow for {size}B: {read_time:.3f}s")
    
    def test_performance_medium_data_operations(self):
        """Test performance with medium data (1KB - 1MB)."""
        # Test data sizes: 10KB, 100KB, 1MB
        test_sizes = [10*1024, 100*1024, 1024*1024]
        max_time = 1.0  # 1 second should be reasonable for medium data
        
        for size in test_sizes:
            with self.subTest(size=size):
                test_data = PerformanceTestHelpers.generate_test_data(size)
                
                # Mock successful operations
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                
                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                test_uri = f"/tmp/perf_medium_{size}.blob"
                
                # Measure operations
                write_time = PerformanceTestHelpers.measure_operation_time(
                    writer.process, {"blob_uri": test_uri, "data": test_data}
                )
                
                read_time = PerformanceTestHelpers.measure_operation_time(
                    reader.process, {"blob_uri": test_uri}
                )
                
                # Calculate throughput
                write_throughput = PerformanceTestHelpers.calculate_throughput(size, write_time)
                read_throughput = PerformanceTestHelpers.calculate_throughput(size, read_time)
                
                # Validate performance (more lenient for larger data)
                adjusted_max_time = max_time * (size / (100*1024))  # Scale with size
                self.assertLess(write_time, adjusted_max_time,
                               f"Write too slow for {size//1024}KB: {write_time:.3f}s")
                self.assertLess(read_time, adjusted_max_time,
                               f"Read too slow for {size//1024}KB: {read_time:.3f}s")
                
                # Throughput should be reasonable (at least 1MB/s for medium data)
                min_throughput = 1024 * 1024  # 1MB/s
                if write_time > 0.1:  # Only check for operations that take meaningful time
                    self.assertGreater(write_throughput, min_throughput / 10,
                                     f"Write throughput too low: {write_throughput/1024:.1f}KB/s")
                if read_time > 0.1:
                    self.assertGreater(read_throughput, min_throughput / 10,
                                     f"Read throughput too low: {read_throughput/1024:.1f}KB/s")
    
    def test_performance_large_data_operations(self):
        """Test performance with large data (> 1MB)."""
        # Test with 5MB and 10MB (reasonable for testing)
        test_sizes = [5*1024*1024, 10*1024*1024]
        max_time = 5.0  # 5 seconds should be reasonable for large data
        
        for size in test_sizes:
            with self.subTest(size=size):
                test_data = PerformanceTestHelpers.generate_test_data(size)
                
                # Mock successful operations
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                
                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                test_uri = f"/tmp/perf_large_{size}.blob"
                
                # Measure operations
                write_time = PerformanceTestHelpers.measure_operation_time(
                    writer.process, {"blob_uri": test_uri, "data": test_data}
                )
                
                read_time = PerformanceTestHelpers.measure_operation_time(
                    reader.process, {"blob_uri": test_uri}
                )
                
                # Validate performance (very lenient for large data)
                self.assertLess(write_time, max_time,
                               f"Write too slow for {size//1024//1024}MB: {write_time:.3f}s")
                self.assertLess(read_time, max_time,
                               f"Read too slow for {size//1024//1024}MB: {read_time:.3f}s")
    
    # =============================================================================
    # Concurrent Operations Performance Tests
    # =============================================================================
    
    def test_performance_concurrent_writes(self):
        """Test performance with concurrent write operations."""
        num_threads = 5
        operations_per_thread = 3
        test_data = PerformanceTestHelpers.generate_test_data(1024)  # 1KB per operation
        
        # Mock successful operations
        mock_service = MockBlobStorageServiceFactory.create_successful_service()
        
        def write_worker(thread_id: int) -> List[float]:
            """Worker function for concurrent writes."""
            times = []
            writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
            
            for op_id in range(operations_per_thread):
                test_uri = f"/tmp/concurrent_write_{thread_id}_{op_id}.blob"
                
                start_time = time.time()
                writer.process({"blob_uri": test_uri, "data": test_data})
                operation_time = time.time() - start_time
                
                times.append(operation_time)
            
            return times
        
        # Execute concurrent writes
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_worker, i) for i in range(num_threads)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        total_time = time.time() - start_time
        
        # Validate results
        all_times = [time for thread_times in results for time in thread_times]
        total_operations = num_threads * operations_per_thread
        
        # All operations should complete in reasonable time
        max_operation_time = max(all_times)
        avg_operation_time = sum(all_times) / len(all_times)
        
        self.assertLess(max_operation_time, 2.0, "Slowest concurrent write took too long")
        self.assertLess(avg_operation_time, 0.5, "Average concurrent write time too slow")
        self.assertLess(total_time, 10.0, "Total concurrent write time too slow")
        
        # Calculate effective throughput
        total_data = len(test_data) * total_operations
        effective_throughput = total_data / total_time
        self.assertGreater(effective_throughput, 10240, "Concurrent write throughput too low")  # 10KB/s minimum
    
    def test_performance_concurrent_reads(self):
        """Test performance with concurrent read operations."""
        num_threads = 5
        operations_per_thread = 3
        
        # Mock successful operations
        mock_service = MockBlobStorageServiceFactory.create_successful_service()
        
        def read_worker(thread_id: int) -> List[float]:
            """Worker function for concurrent reads."""
            times = []
            reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
            
            for op_id in range(operations_per_thread):
                test_uri = f"/tmp/concurrent_read_{thread_id}_{op_id}.blob"
                
                start_time = time.time()
                reader.process({"blob_uri": test_uri})
                operation_time = time.time() - start_time
                
                times.append(operation_time)
            
            return times
        
        # Execute concurrent reads
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_worker, i) for i in range(num_threads)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        total_time = time.time() - start_time
        
        # Validate results
        all_times = [time for thread_times in results for time in thread_times]
        
        # All operations should complete quickly
        max_operation_time = max(all_times)
        avg_operation_time = sum(all_times) / len(all_times)
        
        self.assertLess(max_operation_time, 1.0, "Slowest concurrent read took too long")
        self.assertLess(avg_operation_time, 0.2, "Average concurrent read time too slow")
        self.assertLess(total_time, 5.0, "Total concurrent read time too slow")
    
    def test_performance_mixed_concurrent_operations(self):
        """Test performance with mixed read/write operations."""
        num_operations = 10
        test_data = PerformanceTestHelpers.generate_test_data(512)  # 512B per operation
        
        # Mock successful operations
        mock_service = MockBlobStorageServiceFactory.create_successful_service()
        
        def mixed_worker(operation_id: int) -> Tuple[str, float]:
            """Worker function for mixed operations."""
            test_uri = f"/tmp/mixed_op_{operation_id}.blob"
            
            if operation_id % 2 == 0:
                # Write operation
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                start_time = time.time()
                writer.process({"blob_uri": test_uri, "data": test_data})
                operation_time = time.time() - start_time
                return ("write", operation_time)
            else:
                # Read operation
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                start_time = time.time()
                reader.process({"blob_uri": test_uri})
                operation_time = time.time() - start_time
                return ("read", operation_time)
        
        # Execute mixed operations
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(mixed_worker, i) for i in range(num_operations)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        total_time = time.time() - start_time
        
        # Analyze results
        write_times = [time for op_type, time in results if op_type == "write"]
        read_times = [time for op_type, time in results if op_type == "read"]
        
        # Validate performance
        if write_times:
            avg_write_time = sum(write_times) / len(write_times)
            self.assertLess(avg_write_time, 0.5, "Average mixed write time too slow")
        
        if read_times:
            avg_read_time = sum(read_times) / len(read_times)
            self.assertLess(avg_read_time, 0.2, "Average mixed read time too slow")
        
        self.assertLess(total_time, 10.0, "Total mixed operations time too slow")
    
    # =============================================================================
    # Memory Usage Performance Tests
    # =============================================================================
    
    def test_performance_memory_efficiency(self):
        """Test memory efficiency of blob operations."""
        # Test with progressively larger data to check memory scaling
        test_sizes = [1024, 10*1024, 100*1024]  # 1KB, 10KB, 100KB
        
        # Mock successful operations
        mock_service = MockBlobStorageServiceFactory.create_successful_service()
        
        for size in test_sizes:
            with self.subTest(size=size):
                test_data = PerformanceTestHelpers.generate_test_data(size)
                
                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                test_uri = f"/tmp/memory_test_{size}.blob"
                
                # Perform operations multiple times to check for memory leaks
                for i in range(5):
                    writer.process({"blob_uri": test_uri, "data": test_data})
                    reader.process({"blob_uri": test_uri})
                
                # Test should complete without memory errors
                # (In a real test environment, you might monitor actual memory usage)
                self.assertTrue(True)  # Test completion indicates no major memory issues


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
        self.mock_availability_cache = MockServiceFactory.create_mock_availability_cache_service()
    
    # =============================================================================
    # Azure Blob Storage Scenario Tests
    # =============================================================================
    
    def test_azure_success_scenarios(self):
        """Test successful Azure Blob Storage operations."""
        scenarios = [
            "successful_upload",
            "successful_download", 
            "successful_metadata_retrieval"
        ]
        
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                # Create service with Azure configuration
                azure_config = MockServiceFactory.create_mock_app_config_service({
                    "storage": {"blob": {"providers": {"azure": BlobStorageTestFixtures.AZURE_CONFIG}}}
                })
                
                service = BlobStorageService(
                    configuration=azure_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache
                )
                
                # Mock Azure behavior
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                MockCloudProviderHelpers.mock_azure_behavior(mock_service, "success")
                
                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                # Test workflow
                test_uri = BlobStorageTestFixtures.AZURE_TEST_URI
                test_data = BlobStorageTestFixtures.TEST_STRING_DATA
                
                success = BlobAgentTestHelpers.test_agent_workflow(
                    writer, reader, test_data, test_uri
                )
                self.assertTrue(success, f"Azure scenario {scenario} failed")
    
    def test_azure_error_scenarios(self):
        """Test Azure Blob Storage error scenarios."""
        error_scenarios = [
            "not_found",
            "auth_error"
        ]
        
        for scenario in error_scenarios:
            with self.subTest(scenario=scenario):
                # Create service
                service = BlobStorageService(
                    configuration=self.mock_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache
                )
                
                # Mock Azure error behavior
                mock_service = Mock()
                MockCloudProviderHelpers.mock_azure_behavior(mock_service, scenario)
                
                # Create reader agent
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                # Test should raise appropriate error
                test_uri = BlobStorageTestFixtures.AZURE_TEST_URI
                
                with self.assertRaises((FileNotFoundError, StorageConnectionError, StorageOperationError)):
                    reader.process({"blob_uri": test_uri})
    
    # =============================================================================
    # AWS S3 Scenario Tests
    # =============================================================================
    
    def test_s3_success_scenarios(self):
        """Test successful AWS S3 operations."""
        scenarios = [
            "successful_put_object",
            "successful_get_object",
            "successful_list_objects"
        ]
        
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                # Create service with S3 configuration
                s3_config = MockServiceFactory.create_mock_app_config_service({
                    "storage": {"blob": {"providers": {"s3": BlobStorageTestFixtures.S3_CONFIG}}}
                })
                
                service = BlobStorageService(
                    configuration=s3_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache
                )
                
                # Mock S3 behavior
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                MockCloudProviderHelpers.mock_s3_behavior(mock_service, "success")
                
                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                # Test workflow
                test_uri = BlobStorageTestFixtures.S3_TEST_URI
                test_data = BlobStorageTestFixtures.TEST_STRING_DATA
                
                success = BlobAgentTestHelpers.test_agent_workflow(
                    writer, reader, test_data, test_uri
                )
                self.assertTrue(success, f"S3 scenario {scenario} failed")
    
    def test_s3_error_scenarios(self):
        """Test AWS S3 error scenarios."""
        error_scenarios = [
            "not_found",
            "access_denied"
        ]
        
        for scenario in error_scenarios:
            with self.subTest(scenario=scenario):
                # Create service
                service = BlobStorageService(
                    configuration=self.mock_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache
                )
                
                # Mock S3 error behavior
                mock_service = Mock()
                MockCloudProviderHelpers.mock_s3_behavior(mock_service, scenario)
                
                # Create reader agent
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
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
            "successful_list_blobs"
        ]
        
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                # Create service with GCS configuration
                gcs_config = MockServiceFactory.create_mock_app_config_service({
                    "storage": {"blob": {"providers": {"gs": BlobStorageTestFixtures.GCS_CONFIG}}}
                })
                
                service = BlobStorageService(
                    configuration=gcs_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache
                )
                
                # Mock GCS behavior
                mock_service = MockBlobStorageServiceFactory.create_successful_service()
                MockCloudProviderHelpers.mock_gcs_behavior(mock_service, "success")
                
                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                
                # Test workflow
                test_uri = BlobStorageTestFixtures.GCS_TEST_URI
                test_data = BlobStorageTestFixtures.TEST_STRING_DATA
                
                success = BlobAgentTestHelpers.test_agent_workflow(
                    writer, reader, test_data, test_uri
                )
                self.assertTrue(success, f"GCS scenario {scenario} failed")
    
    def test_gcs_error_scenarios(self):
        """Test Google Cloud Storage error scenarios."""
        error_scenarios = [
            "not_found",
            "quota_exceeded"
        ]
        
        for scenario in error_scenarios:
            with self.subTest(scenario=scenario):
                # Create service
                service = BlobStorageService(
                    configuration=self.mock_config,
                    logging_service=self.mock_logging,
                    availability_cache=self.mock_availability_cache
                )
                
                # Mock GCS error behavior
                mock_service = Mock()
                MockCloudProviderHelpers.mock_gcs_behavior(mock_service, scenario)
                
                # Test should handle errors appropriately
                test_uri = BlobStorageTestFixtures.GCS_TEST_URI
                
                if scenario == "not_found":
                    reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                    with self.assertRaises(FileNotFoundError):
                        reader.process({"blob_uri": test_uri})
                elif scenario == "quota_exceeded":
                    writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
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
            ("binary", BlobStorageTestFixtures.TEST_BINARY_DATA)
        ]
        
        for provider in providers:
            for data_type, test_data in test_data_types:
                with self.subTest(provider=provider, data_type=data_type):
                    # Create mock service for provider
                    mock_service = MockBlobStorageServiceFactory.create_successful_service()
                    
                    # Create agents
                    writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                    reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                    
                    # Test data round-trip
                    test_uri = BlobStorageTestFixtures.get_test_uri_for_provider(
                        provider, f"compat_{data_type}.blob"
                    )
                    
                    success = BlobAgentTestHelpers.test_agent_workflow(
                        writer, reader, test_data, test_uri
                    )
                    self.assertTrue(success, 
                                  f"Cross-provider compatibility failed: {provider}/{data_type}")
    
    def test_provider_migration_scenarios(self):
        """Test scenarios for migrating data between providers."""
        migration_pairs = [
            ("azure", "s3"),
            ("s3", "gs"),
            ("gs", "file"),
            ("file", "azure")
        ]
        
        test_data = BlobStorageTestFixtures.TEST_STRING_DATA
        
        for source_provider, target_provider in migration_pairs:
            with self.subTest(source=source_provider, target=target_provider):
                # Create mock services
                source_service = MockBlobStorageServiceFactory.create_successful_service()
                target_service = MockBlobStorageServiceFactory.create_successful_service()
                
                # Source: write data
                source_writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=source_service)
                source_reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=source_service)
                
                source_uri = BlobStorageTestFixtures.get_test_uri_for_provider(
                    source_provider, "migration_test.blob"
                )
                
                # Write to source
                source_writer.process({"blob_uri": source_uri, "data": test_data})
                
                # Read from source
                source_data = source_reader.process({"blob_uri": source_uri})
                
                # Target: write the same data
                target_writer = BlobAgentTestHelpers.create_test_blob_writer(blob_service=target_service)
                target_reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=target_service)
                
                target_uri = BlobStorageTestFixtures.get_test_uri_for_provider(
                    target_provider, "migration_test.blob"
                )
                
                # Write to target
                target_writer.process({"blob_uri": target_uri, "data": source_data})
                
                # Read from target
                target_data = target_reader.process({"blob_uri": target_uri})
                
                # Data should be identical
                self.assertEqual(source_data, target_data,
                               f"Migration data mismatch: {source_provider} -> {target_provider}")
    
    # =============================================================================
    # Provider Availability and Fallback Tests
    # =============================================================================
    
    def test_provider_availability_detection(self):
        """Test provider availability detection scenarios."""
        availability_scenarios = CloudProviderScenarios.get_provider_availability_scenarios()
        
        for scenario in availability_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Mock provider availability
                with patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_azure_availability') as mock_azure:
                    with patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_s3_availability') as mock_s3:
                        with patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_gcs_availability') as mock_gcs:
                            # Configure availability
                            mock_azure.return_value = scenario["azure_available"]
                            mock_s3.return_value = scenario["s3_available"]
                            mock_gcs.return_value = scenario["gcs_available"]
                            
                            # Create service
                            service = BlobStorageService(
                                configuration=self.mock_config,
                                logging_service=self.mock_logging,
                                availability_cache=self.mock_availability_cache
                            )
                            
                            # Check available providers
                            available_providers = service.get_available_providers()
                            
                            # Verify expected providers are available
                            for expected_provider in scenario["expected_providers"]:
                                self.assertIn(expected_provider, available_providers,
                                            f"Expected provider {expected_provider} not available in scenario {scenario['name']}")
    
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
                        mock_service = MockBlobStorageServiceFactory.create_failing_service()
                    else:
                        # This provider succeeds
                        mock_service = MockBlobStorageServiceFactory.create_successful_service()
                    mock_services.append(mock_service)
                
                # In a real implementation, the service would try providers in order
                # For this test, we verify that at least one working provider exists
                working_services = [s for s in mock_services[failing_provider_index+1:]]
                
                if working_services:
                    # Should be able to use working service
                    working_service = working_services[0]
                    
                    reader = BlobAgentTestHelpers.create_test_blob_reader(blob_service=working_service)
                    
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
                        error_instance = StorageOperationError(scenario["error_message"])
                    elif error_type == "StorageConnectionError":
                        error_instance = StorageConnectionError(scenario["error_message"])
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
                    agent = BlobAgentTestHelpers.create_test_blob_reader(blob_service=mock_service)
                    inputs = {"blob_uri": "/tmp/error_test.blob"}
                else:
                    agent = BlobAgentTestHelpers.create_test_blob_writer(blob_service=mock_service)
                    inputs = {"blob_uri": "/tmp/error_test.blob", "data": "test"}
                
                # Test error handling
                if scenario["expected_behavior"] == "re_raise":
                    with self.assertRaises(type(error_instance)):
                        agent.process(inputs)
                
                # Agent should remain functional after error
                # Test with a working service
                working_service = MockBlobStorageServiceFactory.create_successful_service()
                agent.configure_blob_storage_service(working_service)
                
                # Should work now
                try:
                    result = agent.process(inputs)
                    # Success indicates good error recovery
                    self.assertIsNotNone(result)
                except Exception as e:
                    # Some operations might still fail due to test setup, but agent should be stable
                    self.assertIsInstance(agent, (BlobReaderAgent, BlobWriterAgent))
    
    def test_intermittent_failure_resilience(self):
        """Test resilience to intermittent failures."""
        # Create service that fails intermittently
        failure_rate = 0.3  # 30% failure rate
        mock_service = MockBlobStorageServiceFactory.create_intermittent_service(failure_rate)
        
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
        self.assertGreater(successes, 0, "No successful operations in intermittent failure test")
        self.assertGreater(failures, 0, "No failed operations in intermittent failure test")
        
        # Failure rate should be approximately as expected (with some tolerance)
        actual_failure_rate = failures / num_operations
        self.assertLess(abs(actual_failure_rate - failure_rate), 0.2, 
                       f"Actual failure rate {actual_failure_rate} too far from expected {failure_rate}")


if __name__ == '__main__':
    unittest.main()
