"""
Storage Performance Integration Tests.

This module tests storage performance under load, storage scaling and optimization,
concurrent access patterns, and large dataset processing across all storage services.
"""

import unittest
import tempfile
import json
import time
import threading
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.services.storage.types import WriteMode, StorageResult
from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException


@dataclass
class PerformanceMetrics:
    """Data class for tracking performance metrics."""
    operation: str
    service_name: str
    start_time: float
    end_time: float
    success: bool
    data_size: int
    error_message: Optional[str] = None
    
    @property
    def duration(self) -> float:
        """Calculate operation duration in seconds."""
        return self.end_time - self.start_time
    
    @property
    def throughput(self) -> float:
        """Calculate throughput in bytes per second."""
        if self.duration > 0:
            return self.data_size / self.duration
        # For extremely fast operations (duration ~ 0), return a reasonable estimate
        # This prevents division by zero and acknowledges the operation completed
        elif self.success and self.data_size > 0:
            # Assume minimum measurable time of 1 microsecond for very fast operations
            return self.data_size / 0.000001  # 1 microsecond minimum
        return 0.0


class TestStoragePerformanceIntegration(BaseIntegrationTest):
    """
    Integration tests for storage performance under load and concurrent access.
    
    Tests performance characteristics across:
    - Memory, File, JSON, CSV, and Vector storage services
    - Various data sizes and access patterns
    - Concurrent read/write operations
    - Large dataset processing and scaling
    - Performance optimization and bottleneck identification
    """
    
    def setup_services(self):
        """Initialize storage services for performance testing."""
        super().setup_services()
        
        # Initialize all storage services through StorageManager
        self.storage_manager = self.container.storage_service_manager()
        self.memory_service = self.storage_manager.get_service("memory")
        self.file_service = self.storage_manager.get_service("file")
        self.json_service = self.storage_manager.get_service("json")
        self.csv_service = self.storage_manager.get_service("csv")
        
        # Initialize vector service if available
        try:
            self.vector_service = self.storage_manager.get_service("vector")
            self.vector_available = True
        except Exception as e:
            self.logging_service.get_class_logger(self).warning(f"Vector service not available: {e}")
            self.vector_service = None
            self.vector_available = False
        
        # Create performance test directories
        self.perf_dir = Path(self.temp_dir) / "performance"
        self.perf_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance test configuration
        self.test_config = {
            "small_data_size": 100,      # Small dataset size
            "medium_data_size": 1000,    # Medium dataset size
            "large_data_size": 10000,    # Large dataset size
            "concurrent_threads": 10,    # Number of concurrent threads
            "stress_iterations": 50,     # Iterations for stress testing
            "timeout_seconds": 30        # Operation timeout
        }
        
        # Initialize performance metrics collection
        self.performance_metrics: List[PerformanceMetrics] = []
    
    def _generate_test_data(self, size: int, data_type: str = "mixed") -> Any:
        """Generate test data of specified size and type."""
        if data_type == "json_object":
            return {
                "test_id": f"perf_test_{size}",
                "timestamp": "2025-06-01T12:00:00Z",
                "data_size": size,
                "records": [
                    {
                        "id": i,
                        "value": f"test_value_{i}",
                        "nested": {
                            "field1": f"nested_value_{i}",
                            "field2": random.randint(1, 1000),
                            "field3": [f"item_{j}" for j in range(3)]
                        }
                    }
                    for i in range(size)
                ]
            }
        
        elif data_type == "csv_rows":
            return [
                {
                    "id": i,
                    "name": f"Record_{i}",
                    "value": random.randint(1, 1000),
                    "category": random.choice(["A", "B", "C", "D"]),
                    "timestamp": f"2025-06-{(i % 30) + 1:02d}T12:00:00Z",
                    "active": random.choice([True, False])
                }
                for i in range(size)
            ]
        
        elif data_type == "file_content":
            lines = [
                f"Line {i}: Performance test content with random data {random.randint(1, 10000)}"
                for i in range(size)
            ]
            return "\\n".join(lines)
        
        elif data_type == "memory_data":
            return {
                "cache_id": f"perf_cache_{size}",
                "created_at": "2025-06-01T12:00:00Z",
                "cache_size": size,
                "entries": {
                    f"key_{i}": {
                        "value": f"cached_value_{i}",
                        "score": random.random(),
                        "metadata": {"index": i, "processed": True}
                    }
                    for i in range(size)
                }
            }
        
        else:  # mixed
            return {
                "test_type": "mixed_performance_test",
                "size": size,
                "data": [f"item_{i}" for i in range(size)]
            }
    
    def _measure_operation(
        self, 
        operation_name: str, 
        service_name: str, 
        operation_func, 
        data_size: int = 0
    ) -> PerformanceMetrics:
        """Measure the performance of a storage operation."""
        start_time = time.perf_counter()  # Use high-precision timer
        success = False
        error_message = None
        
        try:
            result = operation_func()
            success = True
        except Exception as e:
            error_message = str(e)
        
        end_time = time.perf_counter()  # Use high-precision timer
        
        metrics = PerformanceMetrics(
            operation=operation_name,
            service_name=service_name,
            start_time=start_time,
            end_time=end_time,
            success=success,
            data_size=data_size,
            error_message=error_message
        )
        
        self.performance_metrics.append(metrics)
        return metrics
    
    # =============================================================================
    # 1. Single Service Performance Tests
    # =============================================================================
    
    def test_memory_service_performance_scaling(self):
        """Test Memory service performance across different data sizes."""
        test_id = "memory_performance_scaling"
        data_sizes = [
            self.test_config["small_data_size"],
            self.test_config["medium_data_size"],
            self.test_config["large_data_size"]
        ]
        
        scaling_results = {}
        
        for size in data_sizes:
            # Generate test data
            test_data = self._generate_test_data(size, "memory_data")
            data_size_bytes = len(str(test_data))
            
            # Test write performance
            write_metrics = self._measure_operation(
                operation_name="write",
                service_name="memory",
                operation_func=lambda: self.memory_service.write(
                    collection=f"perf_memory_{size}",
                    data=test_data,
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            # Test read performance
            read_metrics = self._measure_operation(
                operation_name="read",
                service_name="memory",
                operation_func=lambda: self.memory_service.read(
                    collection=f"perf_memory_{size}",
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            # Test exists performance
            exists_metrics = self._measure_operation(
                operation_name="exists",
                service_name="memory",
                operation_func=lambda: self.memory_service.exists(
                    collection=f"perf_memory_{size}",
                    document_id=test_id
                ),
                data_size=0
            )
            
            scaling_results[size] = {
                "write": write_metrics,
                "read": read_metrics,
                "exists": exists_metrics,
                "data_size_bytes": data_size_bytes
            }
            
            # Verify operations succeeded
            self.assertTrue(write_metrics.success, f"Write should succeed for size {size}")
            self.assertTrue(read_metrics.success, f"Read should succeed for size {size}")
            self.assertTrue(exists_metrics.success, f"Exists should succeed for size {size}")
        
        # Analyze scaling characteristics
        write_times = [scaling_results[size]["write"].duration for size in data_sizes]
        read_times = [scaling_results[size]["read"].duration for size in data_sizes]
        
        # Memory operations should be fast and scale reasonably
        for i, size in enumerate(data_sizes):
            self.assertLess(write_times[i], 1.0, f"Memory write for size {size} should be under 1 second")
            self.assertLess(read_times[i], 1.0, f"Memory read for size {size} should be under 1 second")
        
        # Log performance characteristics
        logger = self.logging_service.get_class_logger(self)
        for size in data_sizes:
            results = scaling_results[size]
            logger.info(f"Memory service size {size}: "
                       f"write={results['write'].duration:.4f}s, "
                       f"read={results['read'].duration:.4f}s")
    
    def test_json_service_performance_scaling(self):
        """Test JSON service performance across different data sizes."""
        test_id = "json_performance_scaling"
        data_sizes = [
            self.test_config["small_data_size"],
            self.test_config["medium_data_size"],
            self.test_config["large_data_size"]
        ]
        
        scaling_results = {}
        
        for size in data_sizes:
            # Generate structured JSON test data
            test_data = self._generate_test_data(size, "json_object")
            data_size_bytes = len(json.dumps(test_data))
            
            # Test write performance
            write_metrics = self._measure_operation(
                operation_name="write",
                service_name="json",
                operation_func=lambda: self.json_service.write(
                    collection=f"perf_json_{size}",
                    data=test_data,
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            # Test read performance
            read_metrics = self._measure_operation(
                operation_name="read",
                service_name="json",
                operation_func=lambda: self.json_service.read(
                    collection=f"perf_json_{size}",
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            scaling_results[size] = {
                "write": write_metrics,
                "read": read_metrics,
                "data_size_bytes": data_size_bytes
            }
            
            # Verify operations and data integrity
            self.assertTrue(write_metrics.success, f"JSON write should succeed for size {size}")
            self.assertTrue(read_metrics.success, f"JSON read should succeed for size {size}")
            
            # Verify data integrity
            read_data = self.json_service.read(f"perf_json_{size}", test_id)
            self.assertEqual(len(read_data["records"]), size, 
                           f"Should read back all {size} records")
        
        # Analyze JSON service scaling
        for size in data_sizes:
            results = scaling_results[size]
            # JSON operations should complete within reasonable time
            self.assertLess(results["write"].duration, 5.0, 
                          f"JSON write for size {size} should complete within 5 seconds")
            self.assertLess(results["read"].duration, 5.0, 
                          f"JSON read for size {size} should complete within 5 seconds")
    
    def test_csv_service_performance_scaling(self):
        """Test CSV service performance across different data sizes."""
        test_id = "csv_performance_scaling"
        data_sizes = [
            self.test_config["small_data_size"],
            self.test_config["medium_data_size"],
            self.test_config["large_data_size"]
        ]
        
        scaling_results = {}
        
        for size in data_sizes:
            # Generate CSV test data
            test_data = self._generate_test_data(size, "csv_rows")
            data_size_bytes = len(str(test_data))
            
            # Test write performance
            write_metrics = self._measure_operation(
                operation_name="write",
                service_name="csv",
                operation_func=lambda: self.csv_service.write(
                    collection=f"perf_csv_{size}",
                    data=test_data,
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            # Test read performance
            read_metrics = self._measure_operation(
                operation_name="read",
                service_name="csv",
                operation_func=lambda: self.csv_service.read(
                    collection=f"perf_csv_{size}",
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            scaling_results[size] = {
                "write": write_metrics,
                "read": read_metrics,
                "data_size_bytes": data_size_bytes
            }
            
            # Verify operations
            self.assertTrue(write_metrics.success, f"CSV write should succeed for size {size}")
            self.assertTrue(read_metrics.success, f"CSV read should succeed for size {size}")
            
            # Verify data integrity
            read_data = self.csv_service.read(f"perf_csv_{size}", test_id)
            self.assertEqual(len(read_data), size, f"Should read back all {size} CSV records")
        
        # Analyze CSV service performance characteristics
        for size in data_sizes:
            results = scaling_results[size]
            # CSV operations should scale reasonably with data size
            self.assertLess(results["write"].duration, 10.0, 
                          f"CSV write for size {size} should complete within 10 seconds")
            self.assertLess(results["read"].duration, 10.0, 
                          f"CSV read for size {size} should complete within 10 seconds")
    
    def test_file_service_performance_scaling(self):
        """Test File service performance across different data sizes."""
        test_id = "file_performance_scaling"
        data_sizes = [
            self.test_config["small_data_size"],
            self.test_config["medium_data_size"],
            self.test_config["large_data_size"]
        ]
        
        scaling_results = {}
        
        for size in data_sizes:
            # Generate file content
            test_content = self._generate_test_data(size, "file_content")
            data_size_bytes = len(test_content.encode('utf-8'))
            
            # Test write performance
            write_metrics = self._measure_operation(
                operation_name="write",
                service_name="file",
                operation_func=lambda: self.file_service.write(
                    collection=f"perf_file_{size}.txt",
                    data=test_content,
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            # Test read performance
            read_metrics = self._measure_operation(
                operation_name="read",
                service_name="file",
                operation_func=lambda: self.file_service.read(
                    collection=f"perf_file_{size}.txt",
                    document_id=test_id
                ),
                data_size=data_size_bytes
            )
            
            scaling_results[size] = {
                "write": write_metrics,
                "read": read_metrics,
                "data_size_bytes": data_size_bytes
            }
            
            # Verify operations
            self.assertTrue(write_metrics.success, f"File write should succeed for size {size}")
            self.assertTrue(read_metrics.success, f"File read should succeed for size {size}")
            
            # Verify content integrity
            read_content = self.file_service.read(f"perf_file_{size}.txt", test_id)
            self.assertEqual(len(read_content.split('\\n')), size, 
                           f"Should read back all {size} lines")
        
        # Analyze file service performance
        for size in data_sizes:
            results = scaling_results[size]
            # File operations should be efficient
            self.assertLess(results["write"].duration, 5.0, 
                          f"File write for size {size} should complete within 5 seconds")
            self.assertLess(results["read"].duration, 5.0, 
                          f"File read for size {size} should complete within 5 seconds")
    
    # =============================================================================
    # 2. Concurrent Access Performance Tests
    # =============================================================================
    
    def test_concurrent_read_performance(self):
        """Test concurrent read performance across all storage services."""
        test_id = "concurrent_read_performance"
        concurrent_threads = self.test_config["concurrent_threads"]
        
        # Setup: Create test data in all services
        test_data_specs = [
            ("memory", self.memory_service, "concurrent_memory", 
             self._generate_test_data(100, "memory_data")),
            ("json", self.json_service, "concurrent_json", 
             self._generate_test_data(100, "json_object")),
            ("csv", self.csv_service, "concurrent_csv", 
             self._generate_test_data(100, "csv_rows")),
            ("file", self.file_service, "concurrent_file.txt", 
             self._generate_test_data(100, "file_content"))
        ]
        
        # Pre-populate all services
        for service_name, service, collection, data in test_data_specs:
            result = service.write(collection, data, test_id)
            self.assertTrue(result.success, f"Setup for {service_name} should succeed")
        
        def perform_concurrent_read(service_info: Tuple[str, Any, str]) -> PerformanceMetrics:
            """Perform a single concurrent read operation."""
            service_name, service, collection = service_info
            
            return self._measure_operation(
                operation_name="concurrent_read",
                service_name=service_name,
                operation_func=lambda: service.read(collection, test_id),
                data_size=0  # We're measuring read performance, not data size
            )
        
        # Execute concurrent reads for each service
        concurrent_results = {}
        
        for service_name, service, collection, _ in test_data_specs:
            service_info = (service_name, service, collection)
            
            # Launch concurrent read operations
            with ThreadPoolExecutor(max_workers=concurrent_threads) as executor:
                futures = [
                    executor.submit(perform_concurrent_read, service_info)
                    for _ in range(concurrent_threads)
                ]
                
                # Collect results
                thread_results = []
                for future in as_completed(futures):
                    metrics = future.result()
                    thread_results.append(metrics)
                
                concurrent_results[service_name] = thread_results
        
        # Analyze concurrent read performance
        for service_name, thread_results in concurrent_results.items():
            # All reads should succeed
            successful_reads = [r for r in thread_results if r.success]
            self.assertEqual(len(successful_reads), concurrent_threads, 
                           f"All concurrent reads should succeed for {service_name}")
            
            # Calculate performance statistics
            read_times = [r.duration for r in successful_reads]
            avg_read_time = sum(read_times) / len(read_times)
            max_read_time = max(read_times)
            min_read_time = min(read_times)
            
            # Performance should be reasonable under concurrent load
            self.assertLess(avg_read_time, 2.0, 
                          f"Average concurrent read time for {service_name} should be under 2 seconds")
            self.assertLess(max_read_time, 5.0, 
                          f"Max concurrent read time for {service_name} should be under 5 seconds")
            
            # Log concurrent performance results
            logger = self.logging_service.get_class_logger(self)
            logger.info(f"Concurrent reads for {service_name}: "
                       f"avg={avg_read_time:.4f}s, min={min_read_time:.4f}s, max={max_read_time:.4f}s")
    
    def test_concurrent_write_performance(self):
        """Test concurrent write performance across storage services."""
        test_id = "concurrent_write_performance"
        concurrent_threads = self.test_config["concurrent_threads"]
        
        def perform_concurrent_write(write_info: Tuple[str, Any, str, Any, int]) -> PerformanceMetrics:
            """Perform a single concurrent write operation."""
            service_name, service, collection_prefix, data_generator, thread_id = write_info
            
            # Generate unique data for each thread
            test_data = data_generator(thread_id)
            collection_name = f"{collection_prefix}_{thread_id}"
            document_id = f"{test_id}_{thread_id}"
            
            return self._measure_operation(
                operation_name="concurrent_write",
                service_name=service_name,
                operation_func=lambda: service.write(collection_name, test_data, document_id),
                data_size=len(str(test_data))
            )
        
        # Define concurrent write test scenarios
        write_scenarios = [
            ("memory", self.memory_service, "concurrent_write_memory", 
             lambda tid: self._generate_test_data(50, "memory_data")),
            ("json", self.json_service, "concurrent_write_json", 
             lambda tid: self._generate_test_data(50, "json_object")),
            ("csv", self.csv_service, "concurrent_write_csv", 
             lambda tid: self._generate_test_data(50, "csv_rows")),
            ("file", self.file_service, "concurrent_write_file", 
             lambda tid: self._generate_test_data(50, "file_content"))
        ]
        
        # Execute concurrent writes for each service
        concurrent_results = {}
        
        for service_name, service, collection_prefix, data_generator in write_scenarios:
            # Create write info for each thread
            write_infos = [
                (service_name, service, collection_prefix, data_generator, thread_id)
                for thread_id in range(concurrent_threads)
            ]
            
            # Launch concurrent write operations
            with ThreadPoolExecutor(max_workers=concurrent_threads) as executor:
                futures = [
                    executor.submit(perform_concurrent_write, write_info)
                    for write_info in write_infos
                ]
                
                # Collect results
                thread_results = []
                for future in as_completed(futures):
                    metrics = future.result()
                    thread_results.append(metrics)
                
                concurrent_results[service_name] = thread_results
        
        # Analyze concurrent write performance
        for service_name, thread_results in concurrent_results.items():
            # All writes should succeed
            successful_writes = [r for r in thread_results if r.success]
            self.assertEqual(len(successful_writes), concurrent_threads, 
                           f"All concurrent writes should succeed for {service_name}")
            
            # Calculate performance statistics
            write_times = [r.duration for r in successful_writes]
            avg_write_time = sum(write_times) / len(write_times)
            max_write_time = max(write_times)
            total_throughput = sum(r.throughput for r in successful_writes)
            
            # Performance should be reasonable under concurrent load
            self.assertLess(avg_write_time, 5.0, 
                          f"Average concurrent write time for {service_name} should be under 5 seconds")
            self.assertLess(max_write_time, 10.0, 
                          f"Max concurrent write time for {service_name} should be under 10 seconds")
            self.assertGreater(total_throughput, 0, 
                             f"Total throughput for {service_name} should be positive")
            
            # Log concurrent write performance
            logger = self.logging_service.get_class_logger(self)
            logger.info(f"Concurrent writes for {service_name}: "
                       f"avg={avg_write_time:.4f}s, max={max_write_time:.4f}s, "
                       f"throughput={total_throughput:.0f} bytes/sec")
    
    def test_mixed_concurrent_operations(self):
        """Test mixed concurrent operations (reads and writes) performance."""
        test_id = "mixed_concurrent_operations"
        total_operations = self.test_config["concurrent_threads"] * 2  # Mix of reads and writes
        
        # Setup: Pre-populate services with initial data
        initial_data_specs = [
            ("memory", self.memory_service, "mixed_memory", 
             self._generate_test_data(100, "memory_data")),
            ("json", self.json_service, "mixed_json", 
             self._generate_test_data(100, "json_object")),
            ("csv", self.csv_service, "mixed_csv", 
             self._generate_test_data(100, "csv_rows")),
            ("file", self.file_service, "mixed_file.txt", 
             self._generate_test_data(100, "file_content"))
        ]
        
        for service_name, service, collection, data in initial_data_specs:
            service.write(collection, data, test_id)
        
        def perform_mixed_operation(operation_info: Tuple[str, str, Any, str, Any, int]) -> PerformanceMetrics:
            """Perform a mixed read or write operation."""
            operation_type, service_name, service, collection, data_gen, operation_id = operation_info
            
            if operation_type == "read":
                return self._measure_operation(
                    operation_name="mixed_read",
                    service_name=service_name,
                    operation_func=lambda: service.read(collection, test_id),
                    data_size=0
                )
            else:  # write
                write_data = data_gen(operation_id)
                write_collection = f"{collection}_write_{operation_id}"
                write_doc_id = f"{test_id}_write_{operation_id}"
                
                return self._measure_operation(
                    operation_name="mixed_write",
                    service_name=service_name,
                    operation_func=lambda: service.write(write_collection, write_data, write_doc_id),
                    data_size=len(str(write_data))
                )
        
        # Create mixed operation scenarios
        mixed_operations = []
        operation_id = 0
        
        for service_name, service, collection, initial_data in initial_data_specs:
            # Determine data generator based on service type
            if service_name == "memory":
                data_gen = lambda oid: self._generate_test_data(25, "memory_data")
            elif service_name == "json":
                data_gen = lambda oid: self._generate_test_data(25, "json_object")
            elif service_name == "csv":
                data_gen = lambda oid: self._generate_test_data(25, "csv_rows")
            else:  # file
                data_gen = lambda oid: self._generate_test_data(25, "file_content")
                collection = "mixed_file_write.txt"  # Adjust for file writes
            
            # Add mixed read and write operations for this service
            for _ in range(self.test_config["concurrent_threads"] // 2):
                # Add read operation
                mixed_operations.append((
                    "read", service_name, service, collection, data_gen, operation_id
                ))
                operation_id += 1
                
                # Add write operation
                mixed_operations.append((
                    "write", service_name, service, collection, data_gen, operation_id
                ))
                operation_id += 1
        
        # Execute mixed operations concurrently
        with ThreadPoolExecutor(max_workers=self.test_config["concurrent_threads"]) as executor:
            futures = [
                executor.submit(perform_mixed_operation, op_info)
                for op_info in mixed_operations
            ]
            
            # Collect all results
            mixed_results = []
            for future in as_completed(futures):
                metrics = future.result()
                mixed_results.append(metrics)
        
        # Analyze mixed operation performance
        successful_operations = [r for r in mixed_results if r.success]
        failed_operations = [r for r in mixed_results if not r.success]
        
        # Most operations should succeed under mixed load
        success_rate = len(successful_operations) / len(mixed_results)
        self.assertGreater(success_rate, 0.8, 
                         "At least 80% of mixed operations should succeed")
        
        # Analyze by operation type
        read_operations = [r for r in successful_operations if r.operation == "mixed_read"]
        write_operations = [r for r in successful_operations if r.operation == "mixed_write"]
        
        if read_operations:
            avg_read_time = sum(r.duration for r in read_operations) / len(read_operations)
            self.assertLess(avg_read_time, 3.0, 
                          "Average read time under mixed load should be under 3 seconds")
        
        if write_operations:
            avg_write_time = sum(r.duration for r in write_operations) / len(write_operations)
            self.assertLess(avg_write_time, 5.0, 
                          "Average write time under mixed load should be under 5 seconds")
        
        # Log mixed operation results
        logger = self.logging_service.get_class_logger(self)
        logger.info(f"Mixed operations: {len(successful_operations)}/{len(mixed_results)} succeeded, "
                   f"success rate: {success_rate:.2%}")
        
        if failed_operations:
            logger.warning(f"Failed operations: {len(failed_operations)}")
            for failed_op in failed_operations[:3]:  # Log first 3 failures
                logger.warning(f"Failed {failed_op.operation} on {failed_op.service_name}: {failed_op.error_message}")
    
    # =============================================================================
    # 3. Large Dataset Processing Performance Tests
    # =============================================================================
    
    def test_large_dataset_processing_performance(self):
        """Test performance with large datasets across storage services."""
        test_id = "large_dataset_processing"
        large_size = self.test_config["large_data_size"]
        
        # Test large dataset processing for each service
        large_dataset_results = {}
        
        # Memory service large dataset test
        large_memory_data = self._generate_test_data(large_size, "memory_data")
        memory_write_metrics = self._measure_operation(
            operation_name="large_write",
            service_name="memory",
            operation_func=lambda: self.memory_service.write(
                "large_memory_dataset", large_memory_data, test_id
            ),
            data_size=len(str(large_memory_data))
        )
        
        memory_read_metrics = self._measure_operation(
            operation_name="large_read",
            service_name="memory",
            operation_func=lambda: self.memory_service.read(
                "large_memory_dataset", test_id
            ),
            data_size=len(str(large_memory_data))
        )
        
        large_dataset_results["memory"] = {
            "write": memory_write_metrics,
            "read": memory_read_metrics,
            "data_size": len(str(large_memory_data))
        }
        
        # JSON service large dataset test
        large_json_data = self._generate_test_data(large_size, "json_object")
        json_write_metrics = self._measure_operation(
            operation_name="large_write",
            service_name="json",
            operation_func=lambda: self.json_service.write(
                "large_json_dataset", large_json_data, test_id
            ),
            data_size=len(json.dumps(large_json_data))
        )
        
        json_read_metrics = self._measure_operation(
            operation_name="large_read",
            service_name="json",
            operation_func=lambda: self.json_service.read(
                "large_json_dataset", test_id
            ),
            data_size=len(json.dumps(large_json_data))
        )
        
        large_dataset_results["json"] = {
            "write": json_write_metrics,
            "read": json_read_metrics,
            "data_size": len(json.dumps(large_json_data))
        }
        
        # CSV service large dataset test
        large_csv_data = self._generate_test_data(large_size, "csv_rows")
        csv_write_metrics = self._measure_operation(
            operation_name="large_write",
            service_name="csv",
            operation_func=lambda: self.csv_service.write(
                "large_csv_dataset", large_csv_data, test_id
            ),
            data_size=len(str(large_csv_data))
        )
        
        csv_read_metrics = self._measure_operation(
            operation_name="large_read",
            service_name="csv",
            operation_func=lambda: self.csv_service.read(
                "large_csv_dataset", test_id
            ),
            data_size=len(str(large_csv_data))
        )
        
        large_dataset_results["csv"] = {
            "write": csv_write_metrics,
            "read": csv_read_metrics,
            "data_size": len(str(large_csv_data))
        }
        
        # File service large dataset test
        large_file_content = self._generate_test_data(large_size, "file_content")
        file_write_metrics = self._measure_operation(
            operation_name="large_write",
            service_name="file",
            operation_func=lambda: self.file_service.write(
                "large_file_dataset.txt", large_file_content, test_id
            ),
            data_size=len(large_file_content.encode('utf-8'))
        )
        
        file_read_metrics = self._measure_operation(
            operation_name="large_read",
            service_name="file",
            operation_func=lambda: self.file_service.read(
                "large_file_dataset.txt", test_id
            ),
            data_size=len(large_file_content.encode('utf-8'))
        )
        
        large_dataset_results["file"] = {
            "write": file_write_metrics,
            "read": file_read_metrics,
            "data_size": len(large_file_content.encode('utf-8'))
        }
        
        # Analyze large dataset performance
        for service_name, results in large_dataset_results.items():
            write_metrics = results["write"]
            read_metrics = results["read"]
            data_size = results["data_size"]
            
            # Verify operations succeeded
            self.assertTrue(write_metrics.success, 
                          f"Large dataset write should succeed for {service_name}")
            self.assertTrue(read_metrics.success, 
                          f"Large dataset read should succeed for {service_name}")
            
            # Performance should be reasonable for large datasets
            self.assertLess(write_metrics.duration, 30.0, 
                          f"Large dataset write for {service_name} should complete within 30 seconds")
            self.assertLess(read_metrics.duration, 30.0, 
                          f"Large dataset read for {service_name} should complete within 30 seconds")
            
            # Calculate throughput
            write_throughput = write_metrics.throughput
            read_throughput = read_metrics.throughput
            
            self.assertGreater(write_throughput, 0, 
                             f"Write throughput should be positive for {service_name}")
            self.assertGreater(read_throughput, 0, 
                             f"Read throughput should be positive for {service_name}")
            
            # Log large dataset performance
            logger = self.logging_service.get_class_logger(self)
            logger.info(f"Large dataset {service_name}: "
                       f"write={write_metrics.duration:.2f}s ({write_throughput:.0f} B/s), "
                       f"read={read_metrics.duration:.2f}s ({read_throughput:.0f} B/s), "
                       f"size={data_size} bytes")
    
    def test_batch_operation_performance(self):
        """Test batch operation performance across storage services."""
        test_id = "batch_operation_performance"
        batch_size = 100
        
        # Generate batch test data
        batch_items = []
        for i in range(batch_size):
            batch_items.append({
                "id": f"batch_item_{i}",
                "data": f"batch_data_{i}",
                "value": random.randint(1, 1000),
                "timestamp": f"2025-06-01T{(i % 24):02d}:00:00Z"
            })
        
        batch_results = {}
        
        # Test CSV batch operations (CSV naturally supports batch operations)
        csv_batch_metrics = self._measure_operation(
            operation_name="batch_write",
            service_name="csv",
            operation_func=lambda: self.csv_service.write(
                "batch_csv_test", batch_items, test_id
            ),
            data_size=len(str(batch_items))
        )
        
        csv_batch_read_metrics = self._measure_operation(
            operation_name="batch_read",
            service_name="csv",
            operation_func=lambda: self.csv_service.read(
                "batch_csv_test", test_id
            ),
            data_size=len(str(batch_items))
        )
        
        batch_results["csv"] = {
            "write": csv_batch_metrics,
            "read": csv_batch_read_metrics
        }
        
        # Test JSON batch operations (store as array)
        json_batch_data = {"batch_items": batch_items, "batch_size": batch_size}
        json_batch_metrics = self._measure_operation(
            operation_name="batch_write",
            service_name="json",
            operation_func=lambda: self.json_service.write(
                "batch_json_test", json_batch_data, test_id
            ),
            data_size=len(json.dumps(json_batch_data))
        )
        
        json_batch_read_metrics = self._measure_operation(
            operation_name="batch_read",
            service_name="json",
            operation_func=lambda: self.json_service.read(
                "batch_json_test", test_id
            ),
            data_size=len(json.dumps(json_batch_data))
        )
        
        batch_results["json"] = {
            "write": json_batch_metrics,
            "read": json_batch_read_metrics
        }
        
        # Test Memory batch operations
        memory_batch_data = {"batch_items": batch_items, "batch_metadata": {"size": batch_size}}
        memory_batch_metrics = self._measure_operation(
            operation_name="batch_write",
            service_name="memory",
            operation_func=lambda: self.memory_service.write(
                "batch_memory_test", memory_batch_data, test_id
            ),
            data_size=len(str(memory_batch_data))
        )
        
        memory_batch_read_metrics = self._measure_operation(
            operation_name="batch_read",
            service_name="memory",
            operation_func=lambda: self.memory_service.read(
                "batch_memory_test", test_id
            ),
            data_size=len(str(memory_batch_data))
        )
        
        batch_results["memory"] = {
            "write": memory_batch_metrics,
            "read": memory_batch_read_metrics
        }
        
        # Analyze batch operation performance
        for service_name, results in batch_results.items():
            write_metrics = results["write"]
            read_metrics = results["read"]
            
            # Verify batch operations succeeded
            self.assertTrue(write_metrics.success, 
                          f"Batch write should succeed for {service_name}")
            self.assertTrue(read_metrics.success, 
                          f"Batch read should succeed for {service_name}")
            
            # Batch operations should be efficient
            self.assertLess(write_metrics.duration, 5.0, 
                          f"Batch write for {service_name} should complete within 5 seconds")
            self.assertLess(read_metrics.duration, 5.0, 
                          f"Batch read for {service_name} should complete within 5 seconds")
            
            # Verify data integrity
            if service_name == "csv":
                read_data = self.csv_service.read("batch_csv_test", test_id)
                self.assertEqual(len(read_data), batch_size, 
                               "Should read back all batch items from CSV")
            elif service_name == "json":
                read_data = self.json_service.read("batch_json_test", test_id)
                self.assertEqual(len(read_data["batch_items"]), batch_size, 
                               "Should read back all batch items from JSON")
            elif service_name == "memory":
                read_data = self.memory_service.read("batch_memory_test", test_id)
                self.assertEqual(len(read_data["batch_items"]), batch_size, 
                               "Should read back all batch items from Memory")
    
    # =============================================================================
    # 4. Performance Analysis and Reporting
    # =============================================================================
    
    def test_performance_analysis_and_reporting(self):
        """Generate comprehensive performance analysis and reporting."""
        test_id = "performance_analysis"
        
        # Collect all performance metrics from previous tests
        all_metrics = self.performance_metrics
        
        if not all_metrics:
            # If no metrics collected yet, run a quick performance test
            self._run_quick_performance_test(test_id)
            all_metrics = self.performance_metrics
        
        # Analyze metrics by service
        service_analysis = {}
        for service_name in ["memory", "json", "csv", "file"]:
            service_metrics = [m for m in all_metrics if m.service_name == service_name]
            
            if service_metrics:
                successful_ops = [m for m in service_metrics if m.success]
                failed_ops = [m for m in service_metrics if not m.success]
                
                if successful_ops:
                    durations = [m.duration for m in successful_ops]
                    throughputs = [m.throughput for m in successful_ops if m.throughput > 0]
                    
                    analysis = {
                        "total_operations": len(service_metrics),
                        "successful_operations": len(successful_ops),
                        "failed_operations": len(failed_ops),
                        "success_rate": len(successful_ops) / len(service_metrics),
                        "avg_duration": sum(durations) / len(durations),
                        "min_duration": min(durations),
                        "max_duration": max(durations),
                        "avg_throughput": sum(throughputs) / len(throughputs) if throughputs else 0,
                        "operations_by_type": {}
                    }
                    
                    # Analyze by operation type
                    for op_type in set(m.operation for m in successful_ops):
                        op_metrics = [m for m in successful_ops if m.operation == op_type]
                        op_durations = [m.duration for m in op_metrics]
                        
                        analysis["operations_by_type"][op_type] = {
                            "count": len(op_metrics),
                            "avg_duration": sum(op_durations) / len(op_durations),
                            "min_duration": min(op_durations),
                            "max_duration": max(op_durations)
                        }
                    
                    service_analysis[service_name] = analysis
        
        # Generate performance report
        report_sections = []
        
        # Executive Summary
        total_ops = len(all_metrics)
        successful_ops = len([m for m in all_metrics if m.success])
        overall_success_rate = successful_ops / total_ops if total_ops > 0 else 0
        
        report_sections.append(f"""PERFORMANCE ANALYSIS REPORT
Generated: 2025-06-01T12:00:00Z
Test ID: {test_id}

EXECUTIVE SUMMARY:
- Total Operations: {total_ops}
- Successful Operations: {successful_ops}
- Overall Success Rate: {overall_success_rate:.1%}
- Services Tested: {len(service_analysis)}
""")
        
        # Service-by-Service Analysis
        report_sections.append("SERVICE PERFORMANCE ANALYSIS:")
        
        for service_name, analysis in service_analysis.items():
            report_sections.append(f"""
{service_name.upper()} SERVICE:
- Total Operations: {analysis["total_operations"]}
- Success Rate: {analysis["success_rate"]:.1%}
- Average Duration: {analysis["avg_duration"]:.4f}s
- Duration Range: {analysis["min_duration"]:.4f}s - {analysis["max_duration"]:.4f}s
- Average Throughput: {analysis["avg_throughput"]:.0f} bytes/sec
""")
            
            # Operation type breakdown
            if analysis["operations_by_type"]:
                report_sections.append(f"  Operation Types:")
                for op_type, op_analysis in analysis["operations_by_type"].items():
                    report_sections.append(f"    - {op_type}: {op_analysis['count']} ops, "
                                         f"avg {op_analysis['avg_duration']:.4f}s")
        
        # Performance Recommendations
        report_sections.append("""
PERFORMANCE RECOMMENDATIONS:
- Memory service shows fastest performance for cached data access
- JSON service provides good balance of structure and performance
- CSV service excels at batch tabular data operations
- File service is efficient for large text content storage
- Consider service selection based on data type and access patterns
""")
        
        # Compile final report
        performance_report = "\\n".join(report_sections)
        
        # Store performance report
        report_result = self.file_service.write(
            collection=f"performance_report_{test_id}.txt",
            data=performance_report,
            document_id=test_id
        )
        self.assertTrue(report_result.success, "Performance report should be created")
        
        # Verify report content
        final_report = self.file_service.read(f"performance_report_{test_id}.txt", test_id)
        self.assertIn("PERFORMANCE ANALYSIS REPORT", final_report)
        self.assertIn("EXECUTIVE SUMMARY", final_report)
        self.assertIn("SERVICE PERFORMANCE ANALYSIS", final_report)
        
        # Performance assertions
        self.assertGreater(overall_success_rate, 0.8, 
                         "Overall success rate should be above 80%")
        self.assertGreater(len(service_analysis), 0, 
                         "Should have analysis for at least one service")
        
        # Log summary
        logger = self.logging_service.get_class_logger(self)
        logger.info(f"Performance analysis complete: {successful_ops}/{total_ops} operations succeeded "
                   f"({overall_success_rate:.1%} success rate)")
    
    def _run_quick_performance_test(self, test_id: str):
        """Run a quick performance test to generate metrics for analysis."""
        # Quick test data
        test_data = self._generate_test_data(50, "mixed")
        
        # Test each service with basic operations
        services = [
            ("memory", self.memory_service),
            ("json", self.json_service),
            ("csv", self.csv_service),
            ("file", self.file_service)
        ]
        
        for service_name, service in services:
            if service_name == "csv":
                test_data_for_service = [{"id": i, "value": f"test_{i}"} for i in range(10)]
            elif service_name == "file":
                test_data_for_service = "Quick performance test content"
                collection = f"quick_test_{service_name}.txt"
            else:
                test_data_for_service = test_data
                collection = f"quick_test_{service_name}"
            
            if service_name != "file":
                collection = f"quick_test_{service_name}"
            
            # Write test
            self._measure_operation(
                operation_name="quick_write",
                service_name=service_name,
                operation_func=lambda s=service, c=collection, d=test_data_for_service: s.write(c, d, test_id),
                data_size=len(str(test_data_for_service))
            )
            
            # Read test
            self._measure_operation(
                operation_name="quick_read",
                service_name=service_name,
                operation_func=lambda s=service, c=collection: s.read(c, test_id),
                data_size=0
            )


if __name__ == '__main__':
    unittest.main()
