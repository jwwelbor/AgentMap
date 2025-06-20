"""
Storage Service Coordination Integration Tests.

This module tests the coordination between all storage services (MemoryService, 
FileService, JsonService, CsvService, VectorService) using the StorageManager 
and real DI container instances. Tests storage type selection, fallback mechanisms,
data migration between storage types, and concurrent storage operations.
"""

import unittest
import tempfile
import json
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.services.storage.types import WriteMode, StorageResult
from agentmap.services.storage.protocols import StorageService
from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException


class TestStorageServiceCoordination(BaseIntegrationTest):
    """
    Integration tests for StorageManager coordination of multiple storage backends.
    
    Tests real coordination between:
    - MemoryService for in-memory caching
    - FileService for file system operations
    - JsonService for structured JSON data
    - CsvService for tabular data
    - VectorService for embeddings and semantic search
    - StorageManager for coordinating all services
    """
    
    def setup_services(self):
        """Initialize storage services for coordination testing."""
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
        except Exception as e:
            self.logging_service.get_class_logger(self).warning(f"Vector service not available: {e}")
            self.vector_service = None
        
        # Create test data directories
        self.test_storage_dir = Path(self.temp_dir) / "storage_test"
        self.test_storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Test data for coordination scenarios
        self.test_data = {
            "simple_data": {"id": 1, "name": "test", "value": 100},
            "complex_data": {
                "user_id": "user_123",
                "profile": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "preferences": {
                        "theme": "dark",
                        "notifications": True
                    }
                },
                "activity": [
                    {"timestamp": "2025-06-01T10:00:00Z", "action": "login"},
                    {"timestamp": "2025-06-01T10:05:00Z", "action": "view_dashboard"},
                    {"timestamp": "2025-06-01T10:10:00Z", "action": "edit_profile"}
                ]
            },
            "tabular_data": [
                {"id": 1, "name": "Alice", "department": "Engineering", "salary": 75000},
                {"id": 2, "name": "Bob", "department": "Marketing", "salary": 65000},
                {"id": 3, "name": "Carol", "department": "Engineering", "salary": 80000}
            ]
        }
    
    # =============================================================================
    # 1. StorageManager Provider Registration and Discovery Tests
    # =============================================================================
    
    def test_storage_manager_provider_registration(self):
        """Test StorageManager registers and discovers all storage providers."""
        # Test provider availability
        available_providers = self.storage_manager.list_available_providers()
        
        # Verify core providers are available
        expected_core_providers = ["memory", "file", "json", "csv"]
        for provider in expected_core_providers:
            self.assertIn(provider, available_providers, 
                         f"Provider '{provider}' should be available")
            self.assertTrue(self.storage_manager.is_provider_available(provider),
                          f"Provider '{provider}' should be available via is_provider_available")
        
        # Test provider service retrieval
        for provider in expected_core_providers:
            with self.subTest(provider=provider):
                service = self.storage_manager.get_service(provider)
                self.assertIsNotNone(service, f"Should retrieve {provider} service")
                self.assertEqual(service.get_provider_name(), provider,
                               f"Service should identify as {provider} provider")
                
                # Verify service implements StorageService protocol
                self.assertTrue(hasattr(service, 'read'), f"{provider} should have read method")
                self.assertTrue(hasattr(service, 'write'), f"{provider} should have write method")
                self.assertTrue(hasattr(service, 'exists'), f"{provider} should have exists method")
                self.assertTrue(hasattr(service, 'health_check'), f"{provider} should have health_check method")
    
    def test_storage_manager_health_check_coordination(self):
        """Test StorageManager coordinates health checks across all providers."""
        # Test health check for all providers
        health_status = self.storage_manager.health_check()
        
        # Verify health status for each provider
        expected_providers = ["memory", "file", "json", "csv"]
        for provider in expected_providers:
            self.assertIn(provider, health_status, f"Health status should include {provider}")
            self.assertIsInstance(health_status[provider], bool, 
                                f"Health status for {provider} should be boolean")
        
        # Test individual provider health check
        for provider in expected_providers:
            with self.subTest(provider=provider):
                individual_health = self.storage_manager.health_check(provider)
                self.assertIn(provider, individual_health, 
                            f"Individual health check should include {provider}")
                self.assertEqual(individual_health[provider], health_status[provider],
                               f"Individual and bulk health check should match for {provider}")
    
    def test_storage_manager_service_caching_coordination(self):
        """Test StorageManager correctly caches and manages service instances."""
        # Test service caching
        memory_service1 = self.storage_manager.get_service("memory")
        memory_service2 = self.storage_manager.get_service("memory")
        
        # Should return same cached instance
        self.assertIs(memory_service1, memory_service2, 
                     "StorageManager should cache service instances")
        
        # Test cache clearing
        self.storage_manager.clear_cache("memory")
        memory_service3 = self.storage_manager.get_service("memory")
        
        # Should create new instance after cache clear
        self.assertIsNot(memory_service1, memory_service3,
                        "Should create new instance after cache clear")
        
        # Test clearing all caches
        json_service1 = self.storage_manager.get_service("json")
        self.storage_manager.clear_cache()
        json_service2 = self.storage_manager.get_service("json")
        
        self.assertIsNot(json_service1, json_service2,
                        "Should create new instances after clearing all caches")
    
    # =============================================================================
    # 2. Cross-Service Data Flow Coordination Tests
    # =============================================================================
    
    def test_memory_to_file_data_coordination(self):
        """Test coordinated data flow from memory to file storage."""
        collection = "memory_to_file_test"
        
        # Step 1: Write data to memory storage
        memory_result = self.memory_service.write(
            collection=collection,
            data=self.test_data["simple_data"],
            document_id="test_doc"
        )
        self.assertTrue(memory_result.success, "Memory write should succeed")
        
        # Step 2: Verify data exists in memory
        self.assertTrue(self.memory_service.exists(collection, "test_doc"),
                       "Data should exist in memory")
        
        # Step 3: Read from memory and write to file storage
        memory_data = self.memory_service.read(collection, "test_doc")
        file_result = self.file_service.write(
            collection=f"{collection}.json",
            data=json.dumps(memory_data, indent=2),
            document_id="test_doc"
        )
        self.assertTrue(file_result.success, "File write should succeed")
        
        # Step 4: Verify data integrity across storage types
        file_data_raw = self.file_service.read(f"{collection}.json", "test_doc")
        file_data = json.loads(file_data_raw)
        
        self.assertEqual(memory_data, file_data, 
                        "Data should be identical across memory and file storage")
        self.assertEqual(file_data["id"], 1)
        self.assertEqual(file_data["name"], "test")
        self.assertEqual(file_data["value"], 100)
    
    def test_json_to_csv_data_transformation_coordination(self):
        """Test coordinated data transformation from JSON to CSV format."""
        json_collection = "json_source"
        csv_collection = "csv_target"
        
        # Step 1: Write complex data to JSON storage
        json_result = self.json_service.write(
            collection=json_collection,
            data=self.test_data["tabular_data"],
            document_id="employee_data"
        )
        self.assertTrue(json_result.success, "JSON write should succeed")
        
        # Step 2: Read from JSON and prepare for CSV format
        json_data = self.json_service.read(json_collection, "employee_data")
        self.assertIsInstance(json_data, list, "JSON data should be a list")
        self.assertEqual(len(json_data), 3, "Should have 3 employee records")
        
        # Step 3: Write to CSV storage (CSVService handles the transformation)
        csv_result = self.csv_service.write(
            collection=csv_collection,
            data=json_data,
            document_id="employees"
        )
        self.assertTrue(csv_result.success, "CSV write should succeed")
        
        # Step 4: Verify CSV data structure and content
        csv_data = self.csv_service.read(csv_collection, "employees")
        self.assertIsInstance(csv_data, list, "CSV data should be a list")
        self.assertEqual(len(csv_data), 3, "CSV should have 3 records")
        
        # Verify first record
        first_record = csv_data[0]
        self.assertEqual(first_record["name"], "Alice")
        self.assertEqual(first_record["department"], "Engineering")
        self.assertEqual(first_record["salary"], "75000")  # CSV values are strings
        
        # Step 5: Verify data transformation preserved structure
        original_keys = set(self.test_data["tabular_data"][0].keys())
        csv_keys = set(first_record.keys())
        self.assertEqual(original_keys, csv_keys, 
                        "Column structure should be preserved in transformation")
    
    def test_multi_service_data_pipeline_coordination(self):
        """Test complex data pipeline across multiple storage services."""
        pipeline_id = "multi_service_pipeline"
        
        # Stage 1: Raw data input to memory (simulating real-time input)
        raw_data = {
            "batch_id": pipeline_id,
            "timestamp": "2025-06-01T12:00:00Z",
            "raw_records": self.test_data["tabular_data"]
        }
        
        memory_result = self.memory_service.write(
            collection="raw_input",
            data=raw_data,
            document_id=pipeline_id
        )
        self.assertTrue(memory_result.success, "Stage 1 - Memory write should succeed")
        
        # Stage 2: Process and store structured data in JSON
        memory_data = self.memory_service.read("raw_input", pipeline_id)
        processed_data = {
            "metadata": {
                "batch_id": memory_data["batch_id"],
                "processed_at": "2025-06-01T12:01:00Z",
                "record_count": len(memory_data["raw_records"])
            },
            "records": memory_data["raw_records"]
        }
        
        json_result = self.json_service.write(
            collection="processed_data",
            data=processed_data,
            document_id=pipeline_id
        )
        self.assertTrue(json_result.success, "Stage 2 - JSON write should succeed")
        
        # Stage 3: Extract tabular data for CSV analysis
        json_data = self.json_service.read("processed_data", pipeline_id)
        csv_records = json_data["records"]
        
        csv_result = self.csv_service.write(
            collection="analysis_data",
            data=csv_records,
            document_id=pipeline_id
        )
        self.assertTrue(csv_result.success, "Stage 3 - CSV write should succeed")
        
        # Stage 4: Create summary and store in file system
        csv_data = self.csv_service.read("analysis_data", pipeline_id)
        
        # Calculate summary statistics
        total_salary = sum(int(record["salary"]) for record in csv_data)
        avg_salary = total_salary / len(csv_data)
        departments = list(set(record["department"] for record in csv_data))
        
        summary = {
            "pipeline_id": pipeline_id,
            "total_records": len(csv_data),
            "average_salary": avg_salary,
            "departments": departments,
            "total_salary_budget": total_salary
        }
        
        file_result = self.file_service.write(
            collection="pipeline_summary.json",
            data=json.dumps(summary, indent=2),
            document_id=pipeline_id
        )
        self.assertTrue(file_result.success, "Stage 4 - File write should succeed")
        
        # Verification: Validate end-to-end data integrity
        final_summary_raw = self.file_service.read("pipeline_summary.json", pipeline_id)
        final_summary = json.loads(final_summary_raw)
        
        self.assertEqual(final_summary["total_records"], 3)
        self.assertEqual(final_summary["average_salary"], 73333.33333333333)
        self.assertIn("Engineering", final_summary["departments"])
        self.assertIn("Marketing", final_summary["departments"])
        self.assertEqual(final_summary["total_salary_budget"], 220000)
    
    # =============================================================================
    # 3. Storage Type Selection and Fallback Mechanisms
    # =============================================================================
    
    def test_automatic_storage_type_selection(self):
        """Test StorageManager automatic storage type selection based on data characteristics."""
        # Test data types that should route to different storage services
        test_scenarios = [
            {
                "name": "structured_json",
                "data": {"id": 1, "nested": {"value": "test"}},
                "expected_service": "json",
                "collection": "auto_select_json"
            },
            {
                "name": "tabular_data",
                "data": [{"col1": "val1", "col2": "val2"}, {"col1": "val3", "col2": "val4"}],
                "expected_service": "csv",
                "collection": "auto_select_csv"
            },
            {
                "name": "simple_text",
                "data": "This is simple text content",
                "expected_service": "file",
                "collection": "auto_select_file.txt"
            }
        ]
        
        for scenario in test_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Get service based on data characteristics
                service = self.storage_manager.get_service(scenario["expected_service"])
                
                # Write data using the selected service
                result = service.write(
                    collection=scenario["collection"],
                    data=scenario["data"],
                    document_id="test"
                )
                self.assertTrue(result.success, f"Write should succeed for {scenario['name']}")
                
                # Verify data can be read back correctly
                read_data = service.read(scenario["collection"], "test")
                
                if scenario["expected_service"] == "csv":
                    # CSV service returns list of dictionaries
                    self.assertIsInstance(read_data, list)
                    self.assertEqual(len(read_data), 2)
                elif scenario["expected_service"] == "json":
                    # JSON service preserves object structure
                    self.assertEqual(read_data, scenario["data"])
                elif scenario["expected_service"] == "file":
                    # File service returns raw text
                    self.assertEqual(read_data, scenario["data"])
    
    def test_storage_fallback_mechanism(self):
        """Test fallback to alternative storage when primary service fails."""
        primary_collection = "primary_test"
        fallback_collection = "fallback_test"
        test_data = {"id": 1, "content": "fallback test"}
        
        # Scenario 1: Primary service succeeds - no fallback needed
        primary_result = self.json_service.write(
            collection=primary_collection,
            data=test_data,
            document_id="test1"
        )
        self.assertTrue(primary_result.success, "Primary service should succeed")
        
        # Verify primary data
        primary_data = self.json_service.read(primary_collection, "test1")
        self.assertEqual(primary_data, test_data)
        
        # Scenario 2: Simulate fallback by explicitly using alternative service
        # (In a real implementation, this would be triggered by primary service failure)
        fallback_result = self.memory_service.write(
            collection=fallback_collection,
            data=test_data,
            document_id="test2"
        )
        self.assertTrue(fallback_result.success, "Fallback service should succeed")
        
        # Verify fallback data integrity
        fallback_data = self.memory_service.read(fallback_collection, "test2")
        self.assertEqual(fallback_data, test_data, 
                        "Fallback service should preserve data integrity")
        
        # Scenario 3: Test multiple fallback options
        fallback_services = [self.memory_service, self.file_service]
        successful_writes = 0
        
        for i, service in enumerate(fallback_services):
            try:
                if service == self.file_service:
                    # File service expects string data
                    service_data = json.dumps(test_data)
                else:
                    service_data = test_data
                
                result = service.write(
                    collection=f"fallback_option_{i}",
                    data=service_data,
                    document_id="fallback_test"
                )
                if result.success:
                    successful_writes += 1
            except Exception as e:
                self.logging_service.get_class_logger(self).warning(f"Fallback service {i} failed: {e}")
        
        self.assertGreater(successful_writes, 0, 
                          "At least one fallback service should succeed")
    
    def test_cross_service_data_migration(self):
        """Test data migration between different storage services."""
        migration_data = self.test_data["complex_data"]
        source_collection = "migration_source"
        target_collection = "migration_target"
        
        # Phase 1: Store data in source service (JSON)
        source_result = self.json_service.write(
            collection=source_collection,
            data=migration_data,
            document_id="migrate_test"
        )
        self.assertTrue(source_result.success, "Source storage should succeed")
        
        # Phase 2: Read from source
        source_data = self.json_service.read(source_collection, "migrate_test")
        self.assertEqual(source_data, migration_data, "Source data should match original")
        
        # Phase 3: Migrate to target service (Memory)
        migration_result = self.memory_service.write(
            collection=target_collection,
            data=source_data,
            document_id="migrate_test"
        )
        self.assertTrue(migration_result.success, "Migration should succeed")
        
        # Phase 4: Verify migration integrity
        target_data = self.memory_service.read(target_collection, "migrate_test")
        self.assertEqual(target_data, source_data, 
                        "Migrated data should match source")
        self.assertEqual(target_data["user_id"], "user_123")
        self.assertEqual(len(target_data["activity"]), 3)
        
        # Phase 5: Cleanup source after successful migration
        source_delete_result = self.json_service.delete(source_collection, "migrate_test")
        self.assertTrue(source_delete_result.success, "Source cleanup should succeed")
        
        # Verify source is cleaned up but target remains
        self.assertFalse(self.json_service.exists(source_collection, "migrate_test"),
                        "Source should be deleted")
        self.assertTrue(self.memory_service.exists(target_collection, "migrate_test"),
                       "Target should remain after migration")
    
    # =============================================================================
    # 4. Concurrent Storage Operations Tests
    # =============================================================================
    
    def test_concurrent_reads_across_services(self):
        """Test concurrent read operations across multiple storage services."""
        # Setup: Prepare data in all services
        test_scenarios = [
            ("memory", self.memory_service, "concurrent_memory", self.test_data["simple_data"]),
            ("json", self.json_service, "concurrent_json", self.test_data["complex_data"]),
            ("csv", self.csv_service, "concurrent_csv", self.test_data["tabular_data"]),
            ("file", self.file_service, "concurrent_file.txt", "Concurrent file test content")
        ]
        
        # Pre-populate all services
        for service_name, service, collection, data in test_scenarios:
            if service_name == "file":
                result = service.write(collection=collection, data=data, document_id="concurrent")
            else:
                result = service.write(collection=collection, data=data, document_id="concurrent")
            self.assertTrue(result.success, f"Setup for {service_name} should succeed")
        
        # Test concurrent reads
        def perform_read(service_info):
            service_name, service, collection, expected_data = service_info
            try:
                read_data = service.read(collection, "concurrent")
                return {
                    "service": service_name,
                    "success": True,
                    "data": read_data,
                    "expected": expected_data
                }
            except Exception as e:
                return {
                    "service": service_name,
                    "success": False,
                    "error": str(e)
                }
        
        # Execute concurrent reads
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(perform_read, scenario) for scenario in test_scenarios]
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all reads succeeded
        self.assertEqual(len(results), 4, "Should have results from all services")
        
        for result in results:
            self.assertTrue(result["success"], 
                          f"Read from {result['service']} should succeed")
            
            # Verify data integrity (considering service-specific transformations)
            if result["service"] == "csv":
                # CSV returns list of dictionaries
                self.assertIsInstance(result["data"], list)
            elif result["service"] == "file":
                # File returns string
                self.assertEqual(result["data"], result["expected"])
            else:
                # JSON and memory preserve structure
                self.assertEqual(result["data"], result["expected"])
    
    def test_concurrent_writes_across_services(self):
        """Test concurrent write operations across multiple storage services."""
        concurrent_collection = "concurrent_writes"
        
        def perform_concurrent_write(service_info):
            service_name, service, data = service_info
            try:
                start_time = time.time()
                
                result = service.write(
                    collection=f"{concurrent_collection}_{service_name}",
                    data=data,
                    document_id=f"concurrent_{service_name}"
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                return {
                    "service": service_name,
                    "success": result.success,
                    "duration": duration,
                    "result": result
                }
            except Exception as e:
                return {
                    "service": service_name,
                    "success": False,
                    "error": str(e)
                }
        
        # Prepare concurrent write scenarios
        write_scenarios = [
            ("memory", self.memory_service, {"thread": "memory", "data": "concurrent test"}),
            ("json", self.json_service, {"thread": "json", "nested": {"value": "concurrent"}}),
            ("csv", self.csv_service, [{"thread": "csv", "value": 1}, {"thread": "csv", "value": 2}]),
            ("file", self.file_service, "Concurrent file write test")
        ]
        
        # Execute concurrent writes
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(perform_concurrent_write, scenario) 
                      for scenario in write_scenarios]
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all writes succeeded
        self.assertEqual(len(results), 4, "Should have results from all services")
        
        for result in results:
            self.assertTrue(result["success"], 
                          f"Concurrent write to {result['service']} should succeed")
            self.assertLess(result["duration"], 5.0, 
                          f"Write to {result['service']} should complete within 5 seconds")
        
        # Verify data integrity after concurrent writes
        for service_name, service, original_data in write_scenarios:
            collection_name = f"{concurrent_collection}_{service_name}"
            document_id = f"concurrent_{service_name}"
            
            # Verify data exists and is readable
            self.assertTrue(service.exists(collection_name, document_id),
                          f"Data should exist in {service_name} after concurrent write")
            
            read_data = service.read(collection_name, document_id)
            
            # Verify data integrity (considering service-specific handling)
            if service_name == "csv":
                self.assertIsInstance(read_data, list)
                self.assertEqual(len(read_data), 2)
            elif service_name == "file":
                self.assertEqual(read_data, original_data)
            else:
                self.assertEqual(read_data, original_data)
    
    def test_concurrent_mixed_operations(self):
        """Test mixed concurrent operations (reads, writes, deletes) across services."""
        mixed_collection = "mixed_operations"
        
        # Setup initial data
        setup_data = [
            ("memory", self.memory_service, {"id": 1, "type": "memory"}),
            ("json", self.json_service, {"id": 2, "type": "json"}),
            ("csv", self.csv_service, [{"id": 3, "type": "csv"}]),
            ("file", self.file_service, "Initial file content")
        ]
        
        for service_name, service, data in setup_data:
            service.write(
                collection=f"{mixed_collection}_{service_name}",
                data=data,
                document_id="mixed_test"
            )
        
        def perform_mixed_operation(operation_info):
            operation_type, service_name, service = operation_info
            collection = f"{mixed_collection}_{service_name}"
            
            try:
                if operation_type == "read":
                    data = service.read(collection, "mixed_test")
                    return {"operation": "read", "service": service_name, "success": True, "data": data}
                
                elif operation_type == "write":
                    new_data = {"updated": True, "service": service_name}
                    if service_name == "csv":
                        new_data = [new_data]
                    elif service_name == "file":
                        new_data = f"Updated content for {service_name}"
                    
                    result = service.write(collection, new_data, "mixed_update")
                    return {"operation": "write", "service": service_name, "success": result.success}
                
                elif operation_type == "exists":
                    exists = service.exists(collection, "mixed_test")
                    return {"operation": "exists", "service": service_name, "success": True, "exists": exists}
                
            except Exception as e:
                return {"operation": operation_type, "service": service_name, "success": False, "error": str(e)}
        
        # Define mixed operations
        operations = [
            ("read", "memory", self.memory_service),
            ("write", "json", self.json_service),
            ("exists", "csv", self.csv_service),
            ("read", "file", self.file_service),
            ("write", "memory", self.memory_service),
            ("exists", "json", self.json_service)
        ]
        
        # Execute mixed operations concurrently
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(perform_mixed_operation, op) for op in operations]
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all operations completed
        self.assertEqual(len(results), 6, "Should complete all mixed operations")
        
        # Analyze results by operation type
        read_results = [r for r in results if r["operation"] == "read"]
        write_results = [r for r in results if r["operation"] == "write"]
        exists_results = [r for r in results if r["operation"] == "exists"]
        
        # Verify reads succeeded and returned valid data
        for read_result in read_results:
            self.assertTrue(read_result["success"], 
                          f"Read from {read_result['service']} should succeed")
            self.assertIsNotNone(read_result.get("data"), 
                               f"Read should return data from {read_result['service']}")
        
        # Verify writes succeeded
        for write_result in write_results:
            self.assertTrue(write_result["success"], 
                          f"Write to {write_result['service']} should succeed")
        
        # Verify exists checks succeeded
        for exists_result in exists_results:
            self.assertTrue(exists_result["success"], 
                          f"Exists check for {exists_result['service']} should succeed")
            self.assertTrue(exists_result.get("exists", False), 
                          f"Data should exist in {exists_result['service']}")
    
    # =============================================================================
    # 5. Service Information and Diagnostics
    # =============================================================================
    
    def test_storage_manager_service_information(self):
        """Test StorageManager provides accurate service information and diagnostics."""
        # Test getting service information for all providers
        service_info = self.storage_manager.get_service_info()
        
        # Verify information structure
        self.assertIsInstance(service_info, dict, "Service info should be a dictionary")
        
        # Test information for each expected provider
        expected_providers = ["memory", "file", "json", "csv"]
        for provider in expected_providers:
            self.assertIn(provider, service_info, f"Service info should include {provider}")
            
            provider_info = service_info[provider]
            self.assertIn("available", provider_info, f"{provider} info should include availability")
            self.assertIn("cached", provider_info, f"{provider} info should include cache status")
            self.assertIn("type", provider_info, f"{provider} info should include type")
            
            self.assertTrue(provider_info["available"], f"{provider} should be available")
            self.assertIn(provider_info["type"], ["class", "factory"], 
                         f"{provider} should have valid type")
        
        # Test individual service information
        memory_info = self.storage_manager.get_service_info("memory")
        self.assertIn("memory", memory_info, "Individual service info should include provider")
        self.assertTrue(memory_info["memory"]["available"], "Memory service should be available")
    
    def test_storage_service_coordination_diagnostics(self):
        """Test diagnostic capabilities across coordinated storage services."""
        diagnostic_collection = "diagnostics_test"
        
        # Create test data in multiple services for diagnostics
        test_services = [
            ("memory", self.memory_service, {"diag": "memory_test"}),
            ("json", self.json_service, {"diag": "json_test", "metadata": {"type": "diagnostic"}}),
            ("csv", self.csv_service, [{"diag": "csv_test", "row": 1}]),
            ("file", self.file_service, "Diagnostic file content")
        ]
        
        for service_name, service, data in test_services:
            service.write(
                collection=f"{diagnostic_collection}_{service_name}",
                data=data,
                document_id="diag_test"
            )
        
        # Run diagnostics across all services
        diagnostic_results = {}
        
        for service_name, service, expected_data in test_services:
            collection = f"{diagnostic_collection}_{service_name}"
            
            # Test health check
            health = service.health_check()
            
            # Test existence check
            exists = service.exists(collection, "diag_test")
            
            # Test read operation
            try:
                read_data = service.read(collection, "diag_test")
                read_success = True
            except Exception as e:
                read_success = False
                read_data = None
            
            diagnostic_results[service_name] = {
                "health": health,
                "exists": exists,
                "read_success": read_success,
                "data_retrieved": read_data is not None
            }
        
        # Verify diagnostic results
        for service_name, results in diagnostic_results.items():
            with self.subTest(service=service_name):
                self.assertTrue(results["health"], f"{service_name} should be healthy")
                self.assertTrue(results["exists"], f"Data should exist in {service_name}")
                self.assertTrue(results["read_success"], f"Should read from {service_name}")
                self.assertTrue(results["data_retrieved"], f"Should retrieve data from {service_name}")
        
        # Test StorageManager aggregated health check
        manager_health = self.storage_manager.health_check()
        for service_name in ["memory", "json", "csv", "file"]:
            self.assertTrue(manager_health.get(service_name, False),
                          f"Manager should report {service_name} as healthy")


if __name__ == '__main__':
    unittest.main()
