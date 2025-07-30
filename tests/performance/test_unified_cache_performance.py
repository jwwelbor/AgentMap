"""
Comprehensive performance tests for the unified AvailabilityCacheService.

This test suite validates the performance characteristics of the unified cache implementation
and measures the benefits of the clean architecture separation where services perform work
and cache provides pure storage.

Key Performance Metrics Validated:
- Cache hit performance across all categories (dependency.*, llm_provider.*, storage.*)
- Cache miss impact when services must do actual work
- Unified cache overhead vs separate cache instances
- Service integration performance (check cache → do work → populate cache pattern)
- Cross-service cache benefits (LLM routing using dependency checker cache results)
- Startup time with unified cache pre-loading vs cold start
- Memory usage patterns with single cache file vs multiple cache files
- Thread safety overhead in concurrent multi-service scenarios
- Cache invalidation performance (config changes, environment changes)
- File system I/O patterns with categorized single-file storage
"""

import asyncio
import concurrent.futures
import json
import os
import statistics
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import Mock, patch

# Add the source directory to the Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agentmap.services.config.availability_cache_service import AvailabilityCacheService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.models.features_registry import FeaturesRegistry
from agentmap.services.logging_service import LoggingService


class CachePerformanceBenchmark:
    """Benchmark harness for cache performance testing."""
    
    def __init__(self, name: str):
        self.name = name
        self.times: List[float] = []
        self.start_time: float = 0
    
    def start(self) -> None:
        """Start timing."""
        self.start_time = time.perf_counter()
    
    def stop(self) -> None:
        """Stop timing and record result."""
        elapsed = time.perf_counter() - self.start_time
        self.times.append(elapsed)
        return elapsed
    
    def get_stats(self) -> Dict[str, float]:
        """Get performance statistics."""
        if not self.times:
            return {"count": 0}
        
        return {
            "count": len(self.times),
            "min_ms": min(self.times) * 1000,
            "max_ms": max(self.times) * 1000,
            "mean_ms": statistics.mean(self.times) * 1000,
            "median_ms": statistics.median(self.times) * 1000,
            "stdev_ms": statistics.stdev(self.times) * 1000 if len(self.times) > 1 else 0,
            "p95_ms": statistics.quantiles(self.times, n=20)[18] * 1000 if len(self.times) >= 20 else max(self.times) * 1000,
            "p99_ms": statistics.quantiles(self.times, n=100)[98] * 1000 if len(self.times) >= 100 else max(self.times) * 1000
        }


class MockLoggingService:
    """Mock logging service for performance testing."""
    
    def __init__(self):
        self._logger = Mock()
        self._logger.debug = Mock()
        self._logger.info = Mock()
        self._logger.warning = Mock()
        self._logger.error = Mock()
    
    def get_logger(self, name: str):
        return self._logger
    
    def get_class_logger(self, obj):
        return self._logger
    
    def initialize(self):
        pass


class UnifiedCachePerformanceTests(unittest.TestCase):
    """Comprehensive performance tests for unified AvailabilityCacheService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = Path(self.temp_dir) / "test_unified_cache.json"
        self.logger = MockLoggingService().get_logger("test")
        
        # Create services for integration testing
        self.logging_service = MockLoggingService()
        self.features_registry_model = FeaturesRegistry()
        self.features_registry_service = FeaturesRegistryService(
            self.features_registry_model, 
            self.logging_service
        )
        
        # Performance tracking
        self.benchmarks: Dict[str, CachePerformanceBenchmark] = {}
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def get_benchmark(self, name: str) -> CachePerformanceBenchmark:
        """Get or create a performance benchmark."""
        if name not in self.benchmarks:
            self.benchmarks[name] = CachePerformanceBenchmark(name)
        return self.benchmarks[name]
    
    def create_cache_service(self) -> AvailabilityCacheService:
        """Create a fresh cache service instance."""
        return AvailabilityCacheService(self.cache_file, self.logger)
    
    def test_cache_hit_performance_all_categories(self):
        """Test cache hit performance across all service categories."""
        cache_service = self.create_cache_service()
        
        # Test data for different categories
        test_categories = [
            ("dependency.llm", "openai"),
            ("dependency.llm", "anthropic"), 
            ("dependency.storage", "csv"),
            ("dependency.storage", "vector"),
            ("llm_provider", "openai"),
            ("llm_provider", "anthropic"),
            ("storage", "csv"),
            ("storage", "vector"),
            ("custom_category", "test_provider")
        ]
        
        # Pre-populate cache with test data
        for category, key in test_categories:
            test_result = {
                "validation_passed": True,
                "enabled": True,
                "last_error": None,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "test_data": f"performance_test_{category}_{key}"
            }
            cache_service.set_availability(category, key, test_result)
        
        # Benchmark cache hits
        iterations = 1000
        hit_benchmark = self.get_benchmark("cache_hit_all_categories")
        
        for _ in range(iterations):
            for category, key in test_categories:
                hit_benchmark.start()
                result = cache_service.get_availability(category, key)
                hit_benchmark.stop()
                
                self.assertIsNotNone(result)
                self.assertTrue(result.get("validation_passed"))
        
        stats = hit_benchmark.get_stats()
        print(f"\n=== Cache Hit Performance (All Categories) ===")
        print(f"Operations: {stats['count']}")
        print(f"Mean: {stats['mean_ms']:.2f}ms")
        print(f"Median: {stats['median_ms']:.2f}ms") 
        print(f"P95: {stats['p95_ms']:.2f}ms")
        print(f"P99: {stats['p99_ms']:.2f}ms")
        
        # Validate performance targets: cache hits should be under 50ms
        self.assertLess(stats['p95_ms'], 50.0, 
                       f"Cache hit P95 ({stats['p95_ms']:.2f}ms) should be under 50ms")
    
    def test_cache_miss_impact_measurement(self):
        """Test cache miss impact when services must do actual work."""
        cache_service = self.create_cache_service()
        
        # Simulate expensive operations for cache misses
        def expensive_dependency_check(category: str, key: str) -> Dict[str, Any]:
            """Simulate expensive dependency validation work."""
            time.sleep(0.1)  # Simulate 100ms dependency check
            return {
                "validation_passed": True,
                "enabled": True,
                "last_error": None,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "dependencies_checked": [f"mock_dependency_{key}"],
                "expensive_work_performed": True
            }
        
        test_cases = [
            ("dependency.llm", "openai"),
            ("dependency.storage", "csv"),
            ("llm_provider", "anthropic"),
            ("storage", "vector")
        ]
        
        miss_benchmark = self.get_benchmark("cache_miss_with_work")
        
        for category, key in test_cases:
            # Measure cache miss + work time
            miss_benchmark.start()
            
            # Check cache (should miss)
            cached_result = cache_service.get_availability(category, key)
            if cached_result is None:
                # Perform expensive work
                work_result = expensive_dependency_check(category, key)
                # Cache the result
                cache_service.set_availability(category, key, work_result)
            
            miss_benchmark.stop()
        
        stats = miss_benchmark.get_stats()
        print(f"\n=== Cache Miss + Work Performance ===")
        print(f"Operations: {stats['count']}")
        print(f"Mean: {stats['mean_ms']:.2f}ms")
        print(f"Median: {stats['median_ms']:.2f}ms")
        print(f"Max: {stats['max_ms']:.2f}ms")
        
        # Validate that cache misses are slower but reasonable
        self.assertGreater(stats['mean_ms'], 50.0, 
                          "Cache miss with work should be significantly slower than hits")
        self.assertLess(stats['mean_ms'], 200.0,
                       "Cache miss with work should complete within 200ms")
    
    def test_unified_vs_separate_cache_overhead(self):
        """Test unified cache overhead vs hypothetical separate cache instances."""
        # Test unified cache performance
        unified_cache = self.create_cache_service()
        unified_benchmark = self.get_benchmark("unified_cache_ops")
        
        # Simulate operations across different categories
        categories = ["dependency.llm", "dependency.storage", "llm_provider", "storage"]
        keys = ["openai", "anthropic", "csv", "vector"]
        
        # Populate unified cache
        for category in categories:
            for key in keys:
                test_data = {
                    "validation_passed": True,
                    "category": category,
                    "key": key,
                    "cached_at": datetime.now(timezone.utc).isoformat()
                }
                unified_cache.set_availability(category, key, test_data)
        
        # Benchmark unified cache operations
        iterations = 500
        for _ in range(iterations):
            for category in categories:
                for key in keys:
                    unified_benchmark.start()
                    result = unified_cache.get_availability(category, key)
                    unified_benchmark.stop()
                    self.assertIsNotNone(result)
        
        # Simulate separate cache instances (memory overhead simulation)
        separate_caches = {}
        separate_benchmark = self.get_benchmark("separate_cache_ops")
        
        for category in categories:
            cache_file = Path(self.temp_dir) / f"cache_{category.replace('.', '_')}.json"
            separate_caches[category] = AvailabilityCacheService(cache_file, self.logger)
            
            # Populate separate cache
            for key in keys:
                test_data = {
                    "validation_passed": True,
                    "category": category,
                    "key": key,
                    "cached_at": datetime.now(timezone.utc).isoformat()
                }
                separate_caches[category].set_availability(category, key, test_data)
        
        # Benchmark separate cache operations
        for _ in range(iterations):
            for category in categories:
                for key in keys:
                    separate_benchmark.start()
                    result = separate_caches[category].get_availability(category, key)
                    separate_benchmark.stop()
                    self.assertIsNotNone(result)
        
        unified_stats = unified_benchmark.get_stats()
        separate_stats = separate_benchmark.get_stats()
        
        print(f"\n=== Unified vs Separate Cache Comparison ===")
        print(f"Unified Cache - Mean: {unified_stats['mean_ms']:.2f}ms, P95: {unified_stats['p95_ms']:.2f}ms")
        print(f"Separate Caches - Mean: {separate_stats['mean_ms']:.2f}ms, P95: {separate_stats['p95_ms']:.2f}ms")
        
        # Calculate memory usage (file sizes)
        unified_size = self.cache_file.stat().st_size if self.cache_file.exists() else 0
        separate_total_size = sum(
            cache_file.stat().st_size if cache_file.exists() else 0
            for cache_file in [Path(self.temp_dir) / f"cache_{cat.replace('.', '_')}.json" 
                              for cat in categories]
        )
        
        print(f"Unified cache file size: {unified_size} bytes")
        print(f"Separate cache files total: {separate_total_size} bytes")
        print(f"Storage efficiency: {((separate_total_size - unified_size) / separate_total_size * 100):.1f}% reduction")
        
        # Unified cache should be more memory efficient
        self.assertLess(unified_size, separate_total_size,
                       "Unified cache should use less storage than separate caches")
    
    def test_service_integration_performance(self):
        """Test service integration performance (check cache → do work → populate cache pattern)."""
        cache_service = self.create_cache_service()
        
        # Create dependency checker service for integration testing
        dependency_checker = DependencyCheckerService(
            self.logging_service,
            self.features_registry_service,
            cache_service
        )
        
        integration_benchmark = self.get_benchmark("service_integration")
        
        # Test the full integration pattern
        providers = ["openai", "anthropic", "google"]
        storage_types = ["csv", "vector", "firebase"]
        
        for provider in providers:
            integration_benchmark.start()
            # This will: check cache → perform validation → populate cache
            result, missing = dependency_checker._validate_llm_provider(provider)
            integration_benchmark.stop()
            
            # Result should be cached now
            cached_result = cache_service.get_availability("dependency.llm", provider)
            self.assertIsNotNone(cached_result)
        
        for storage_type in storage_types:
            integration_benchmark.start()
            # This will: check cache → perform validation → populate cache  
            result, missing = dependency_checker._validate_storage_type(storage_type)
            integration_benchmark.stop()
            
            # Result should be cached now
            cached_result = cache_service.get_availability("dependency.storage", storage_type)
            self.assertIsNotNone(cached_result)
        
        stats = integration_benchmark.get_stats()
        print(f"\n=== Service Integration Performance ===")
        print(f"Operations: {stats['count']}")
        print(f"Mean: {stats['mean_ms']:.2f}ms")
        print(f"Median: {stats['median_ms']:.2f}ms")
        print(f"P95: {stats['p95_ms']:.2f}ms")
        
        # Integration should be reasonable but slower than pure cache hits
        self.assertLess(stats['p95_ms'], 500.0,
                       "Service integration should complete within 500ms")
    
    def test_concurrent_access_performance(self):
        """Test performance with multiple services accessing cache concurrently."""
        cache_service = self.create_cache_service()
        
        # Pre-populate cache
        categories = ["dependency.llm", "dependency.storage", "llm_provider", "storage"]
        keys = ["openai", "anthropic", "csv", "vector", "firebase", "google"]
        
        for category in categories:
            for key in keys:
                test_data = {
                    "validation_passed": True,
                    "enabled": True,
                    "category": category,
                    "key": key,
                    "thread_test": True
                }
                cache_service.set_availability(category, key, test_data)
        
        # Concurrent access test
        concurrent_benchmark = self.get_benchmark("concurrent_access")
        results = []
        errors = []
        
        def worker_thread(thread_id: int, operations: int):
            """Worker thread for concurrent testing."""
            thread_times = []
            thread_errors = []
            
            for i in range(operations):
                category = categories[i % len(categories)]
                key = keys[i % len(keys)]
                
                try:
                    start_time = time.perf_counter()
                    result = cache_service.get_availability(category, key)
                    end_time = time.perf_counter()
                    
                    thread_times.append(end_time - start_time)
                    
                    if result is None:
                        thread_errors.append(f"Thread {thread_id}: Unexpected None result")
                    
                except Exception as e:
                    thread_errors.append(f"Thread {thread_id}: {str(e)}")
            
            return thread_times, thread_errors
        
        # Run concurrent test
        num_threads = 10
        operations_per_thread = 100
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(worker_thread, i, operations_per_thread)
                for i in range(num_threads)
            ]
            
            for future in concurrent.futures.as_completed(futures):
                thread_times, thread_errors = future.result()
                results.extend(thread_times)
                errors.extend(thread_errors)
        
        # Analyze concurrent performance
        if results:
            concurrent_stats = {
                "count": len(results),
                "min_ms": min(results) * 1000,
                "max_ms": max(results) * 1000,
                "mean_ms": statistics.mean(results) * 1000,
                "median_ms": statistics.median(results) * 1000,
                "stdev_ms": statistics.stdev(results) * 1000 if len(results) > 1 else 0
            }
            
            print(f"\n=== Concurrent Access Performance ===")
            print(f"Threads: {num_threads}")
            print(f"Operations per thread: {operations_per_thread}")
            print(f"Total operations: {concurrent_stats['count']}")
            print(f"Mean: {concurrent_stats['mean_ms']:.2f}ms")
            print(f"Median: {concurrent_stats['median_ms']:.2f}ms")
            print(f"Max: {concurrent_stats['max_ms']:.2f}ms")
            print(f"StdDev: {concurrent_stats['stdev_ms']:.2f}ms")
            print(f"Errors: {len(errors)}")
            
            # Validate thread safety and performance
            self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors[:5]}")
            self.assertLess(concurrent_stats['mean_ms'], 100.0,
                           "Concurrent access should maintain good performance")
            self.assertLess(concurrent_stats['max_ms'], 1000.0,
                           "No operation should take longer than 1 second")
    
    def test_cache_invalidation_performance(self):
        """Test cache invalidation performance for different scenarios."""
        cache_service = self.create_cache_service()
        
        # Populate cache with substantial data
        categories = ["dependency.llm", "dependency.storage", "llm_provider", "storage", "custom"]
        keys = [f"provider_{i}" for i in range(20)]  # 20 providers per category
        
        for category in categories:
            for key in keys:
                test_data = {
                    "validation_passed": True,
                    "enabled": True,
                    "large_data": "x" * 1000,  # 1KB of data per entry
                    "category": category,
                    "key": key
                }
                cache_service.set_availability(category, key, test_data)
        
        # Test specific key invalidation
        key_invalidation_benchmark = self.get_benchmark("key_invalidation")
        for i in range(10):
            key_invalidation_benchmark.start()
            cache_service.invalidate_cache("dependency.llm", f"provider_{i}")
            key_invalidation_benchmark.stop()
        
        # Test category invalidation
        category_invalidation_benchmark = self.get_benchmark("category_invalidation")
        category_invalidation_benchmark.start()
        cache_service.invalidate_cache("dependency.storage")
        category_invalidation_benchmark.stop()
        
        # Test full cache invalidation
        full_invalidation_benchmark = self.get_benchmark("full_invalidation")
        full_invalidation_benchmark.start()
        cache_service.invalidate_cache()
        full_invalidation_benchmark.stop()
        
        # Report invalidation performance
        key_stats = key_invalidation_benchmark.get_stats()
        category_stats = category_invalidation_benchmark.get_stats()
        full_stats = full_invalidation_benchmark.get_stats()
        
        print(f"\n=== Cache Invalidation Performance ===")
        print(f"Key invalidation - Mean: {key_stats['mean_ms']:.2f}ms")
        print(f"Category invalidation - Time: {category_stats['mean_ms']:.2f}ms")
        print(f"Full invalidation - Time: {full_stats['mean_ms']:.2f}ms")
        
        # Validate invalidation performance
        self.assertLess(key_stats['mean_ms'], 50.0,
                       "Key invalidation should be fast")
        self.assertLess(category_stats['mean_ms'], 100.0,
                       "Category invalidation should complete quickly")
        self.assertLess(full_stats['mean_ms'], 200.0,
                       "Full cache invalidation should complete reasonably fast")
    
    def test_startup_performance_comparison(self):
        """Test startup time with unified cache pre-loading vs cold start."""
        # Cold start test
        cold_start_benchmark = self.get_benchmark("cold_start")
        
        cold_start_benchmark.start()
        cold_cache = self.create_cache_service()
        
        # Simulate initial service setup without cache
        dependency_checker_cold = DependencyCheckerService(
            self.logging_service,
            self.features_registry_service,
            cold_cache
        )
        
        # Perform initial validations (cache misses)
        providers = ["openai", "anthropic", "google"]
        for provider in providers:
            dependency_checker_cold._validate_llm_provider(provider)
        
        cold_start_benchmark.stop()
        
        # Warm start test (pre-populated cache)
        warm_cache = self.create_cache_service()
        
        # Pre-populate cache
        for provider in providers:
            cached_result = {
                "validation_passed": True,
                "enabled": True,
                "last_error": None,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "dependencies_checked": [f"langchain_{provider}"],
                "pre_populated": True
            }
            warm_cache.set_availability("dependency.llm", provider, cached_result)
        
        warm_start_benchmark = self.get_benchmark("warm_start")
        
        warm_start_benchmark.start()
        dependency_checker_warm = DependencyCheckerService(
            self.logging_service,
            self.features_registry_service,
            warm_cache
        )
        
        # Perform validations (cache hits)
        for provider in providers:
            dependency_checker_warm._validate_llm_provider(provider)
        
        warm_start_benchmark.stop()
        
        # Compare startup performance
        cold_stats = cold_start_benchmark.get_stats()
        warm_stats = warm_start_benchmark.get_stats()
        
        print(f"\n=== Startup Performance Comparison ===")
        print(f"Cold start: {cold_stats['mean_ms']:.2f}ms")
        print(f"Warm start: {warm_stats['mean_ms']:.2f}ms")
        print(f"Speedup: {(cold_stats['mean_ms'] / warm_stats['mean_ms']):.1f}x")
        
        # Warm start should be significantly faster
        self.assertLess(warm_stats['mean_ms'], cold_stats['mean_ms'],
                       "Warm start should be faster than cold start")
        
        speedup_ratio = cold_stats['mean_ms'] / warm_stats['mean_ms']
        self.assertGreater(speedup_ratio, 2.0,
                          "Warm start should be at least 2x faster")
    
    def test_memory_usage_patterns(self):
        """Test memory usage patterns with single cache file vs multiple files."""
        import psutil
        import gc
        
        process = psutil.Process()
        
        # Baseline memory usage
        gc.collect()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test unified cache memory usage
        unified_cache = self.create_cache_service()
        
        # Populate with substantial data
        categories = [f"category_{i}" for i in range(10)]
        keys = [f"key_{j}" for j in range(50)]
        
        for category in categories:
            for key in keys:
                large_data = {
                    "validation_passed": True,
                    "large_field": "x" * 2000,  # 2KB per entry
                    "metadata": {
                        "category": category,
                        "key": key,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "extra_data": list(range(100))
                    }
                }
                unified_cache.set_availability(category, key, large_data)
        
        gc.collect()
        unified_memory = process.memory_info().rss / 1024 / 1024  # MB
        unified_usage = unified_memory - baseline_memory
        
        # Test separate caches memory usage
        separate_caches = []
        for i, category in enumerate(categories):
            cache_file = Path(self.temp_dir) / f"separate_cache_{i}.json"
            cache = AvailabilityCacheService(cache_file, self.logger)
            separate_caches.append(cache)
            
            # Populate each separate cache
            for key in keys:
                large_data = {
                    "validation_passed": True,
                    "large_field": "x" * 2000,  # 2KB per entry
                    "metadata": {
                        "category": category,
                        "key": key,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "extra_data": list(range(100))
                    }
                }
                cache.set_availability(category, key, large_data)
        
        gc.collect()
        separate_memory = process.memory_info().rss / 1024 / 1024  # MB
        separate_usage = separate_memory - unified_memory
        
        print(f"\n=== Memory Usage Patterns ===")
        print(f"Baseline memory: {baseline_memory:.1f} MB")
        print(f"Unified cache memory usage: {unified_usage:.1f} MB")
        print(f"Separate caches additional usage: {separate_usage:.1f} MB")
        print(f"Total separate caches usage: {unified_usage + separate_usage:.1f} MB")
        
        # File size comparison
        unified_file_size = self.cache_file.stat().st_size / 1024  # KB
        separate_file_sizes = [
            (Path(self.temp_dir) / f"separate_cache_{i}.json").stat().st_size / 1024
            for i in range(len(categories))
        ]
        total_separate_size = sum(separate_file_sizes)
        
        print(f"Unified cache file: {unified_file_size:.1f} KB")
        print(f"Separate cache files total: {total_separate_size:.1f} KB")
        print(f"File size efficiency: {((total_separate_size - unified_file_size) / total_separate_size * 100):.1f}% reduction")
        
        # Unified should be more efficient
        self.assertLess(unified_file_size, total_separate_size,
                       "Unified cache should use less disk space")
    
    def test_cross_service_cache_benefits(self):
        """Test cross-service cache benefits (LLM routing using dependency cache results)."""
        cache_service = self.create_cache_service()
        
        # Create multiple services using the same cache
        dependency_checker = DependencyCheckerService(
            self.logging_service,
            self.features_registry_service,
            cache_service
        )
        
        cross_service_benchmark = self.get_benchmark("cross_service_benefits")
        
        # First service populates cache
        providers = ["openai", "anthropic", "google"]
        for provider in providers:
            cross_service_benchmark.start()
            # DependencyChecker validates and caches result
            result, missing = dependency_checker._validate_llm_provider(provider)
            cross_service_benchmark.stop()
        
        # Simulate another service using the same cache results
        llm_routing_benchmark = self.get_benchmark("llm_routing_cache_reuse")
        
        for provider in providers:
            llm_routing_benchmark.start()
            # LLM routing service checks cache (should hit)
            cached_result = cache_service.get_availability("dependency.llm", provider)
            
            # Check if cache was hit (result found, regardless of validation status)
            cache_hit = cached_result is not None
            
            if cache_hit and cached_result.get("validation_passed"):
                # Use provider for routing (available and validated)
                routing_decision = {
                    "selected_provider": provider,
                    "available": True,
                    "cache_hit": True
                }
            elif cache_hit and not cached_result.get("validation_passed"):
                # Provider cached but not available - still a cache hit for performance
                routing_decision = {
                    "selected_provider": "default",
                    "available": False,
                    "cache_hit": True,  # Cache hit even if provider unavailable
                    "reason": "provider_unavailable"
                }
            else:
                # No cached result - true cache miss
                routing_decision = {
                    "selected_provider": "default",
                    "available": False,
                    "cache_hit": False
                }
            
            llm_routing_benchmark.stop()
            
            # Assert cache hit occurred (fast lookup even for unavailable providers)
            if not routing_decision["cache_hit"]:
                self.fail(f"Unexpected cache miss for provider {provider}. Cached result: {cached_result}")
            
            self.assertTrue(routing_decision["cache_hit"])
        
        cross_stats = cross_service_benchmark.get_stats()
        routing_stats = llm_routing_benchmark.get_stats()
        
        print(f"\n=== Cross-Service Cache Benefits ===")
        print(f"Dependency validation + cache: {cross_stats['mean_ms']:.2f}ms")
        print(f"LLM routing cache reuse: {routing_stats['mean_ms']:.2f}ms")
        print(f"Cache reuse speedup: {(cross_stats['mean_ms'] / routing_stats['mean_ms']):.1f}x")
        
        # Cache reuse should be much faster
        speedup = cross_stats['mean_ms'] / routing_stats['mean_ms']
        self.assertGreater(speedup, 5.0,
                          "Cross-service cache reuse should provide significant speedup")
    
    def test_file_io_patterns(self):
        """Test file I/O patterns with categorized single-file storage."""
        cache_service = self.create_cache_service()
        
        io_benchmark = self.get_benchmark("file_io_patterns")
        
        # Test mixed read/write patterns
        categories = ["dependency.llm", "dependency.storage", "llm_provider", "storage"]
        keys = [f"provider_{i}" for i in range(20)]
        
        # Write operations
        write_times = []
        for category in categories:
            for key in keys:
                start_time = time.perf_counter()
                
                test_data = {
                    "validation_passed": True,
                    "enabled": True,
                    "category": category,
                    "key": key,
                    "io_test_data": "x" * 500  # 500 bytes per entry
                }
                success = cache_service.set_availability(category, key, test_data)
                
                end_time = time.perf_counter()
                write_times.append(end_time - start_time)
                self.assertTrue(success)
        
        # Read operations
        read_times = []
        for category in categories:
            for key in keys:
                start_time = time.perf_counter()
                
                result = cache_service.get_availability(category, key)
                
                end_time = time.perf_counter()
                read_times.append(end_time - start_time)
                self.assertIsNotNone(result)
        
        # Analyze I/O patterns
        write_stats = {
            "count": len(write_times),
            "mean_ms": statistics.mean(write_times) * 1000,
            "median_ms": statistics.median(write_times) * 1000,
            "max_ms": max(write_times) * 1000
        }
        
        read_stats = {
            "count": len(read_times),
            "mean_ms": statistics.mean(read_times) * 1000,
            "median_ms": statistics.median(read_times) * 1000,
            "max_ms": max(read_times) * 1000
        }
        
        print(f"\n=== File I/O Patterns ===")
        print(f"Write operations: {write_stats['count']}")
        print(f"Write mean: {write_stats['mean_ms']:.2f}ms")
        print(f"Write max: {write_stats['max_ms']:.2f}ms")
        print(f"Read operations: {read_stats['count']}")
        print(f"Read mean: {read_stats['mean_ms']:.2f}ms")
        print(f"Read max: {read_stats['max_ms']:.2f}ms")
        
        # File size analysis
        file_size = self.cache_file.stat().st_size if self.cache_file.exists() else 0
        entries_count = len(categories) * len(keys)
        size_per_entry = file_size / entries_count if entries_count > 0 else 0
        
        print(f"Final cache file size: {file_size} bytes")
        print(f"Entries: {entries_count}")
        print(f"Average size per entry: {size_per_entry:.1f} bytes")
        
        # Validate I/O performance
        self.assertLess(write_stats['mean_ms'], 50.0,
                       "Write operations should be reasonably fast")
        self.assertLess(read_stats['mean_ms'], 10.0,
                       "Read operations should be very fast")
    
    def test_performance_regression_benchmarks(self):
        """Create baseline performance benchmarks for regression testing."""
        cache_service = self.create_cache_service()
        
        # Standard benchmark scenarios
        scenarios = {
            "cache_hit_standard": {
                "category": "dependency.llm",
                "key": "openai",
                "iterations": 1000
            },
            "cache_set_standard": {
                "category": "storage", 
                "key": "csv",
                "iterations": 100
            },
            "cache_invalidation_standard": {
                "category": "dependency.storage",
                "key": "vector", 
                "iterations": 50
            }
        }
        
        baseline_results = {}
        
        for scenario_name, config in scenarios.items():
            benchmark = self.get_benchmark(scenario_name)
            
            if "hit" in scenario_name:
                # Pre-populate for hit tests
                test_data = {
                    "validation_passed": True,
                    "baseline_test": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                cache_service.set_availability(config["category"], config["key"], test_data)
                
                # Benchmark hits
                for _ in range(config["iterations"]):
                    benchmark.start()
                    result = cache_service.get_availability(config["category"], config["key"])
                    benchmark.stop()
                    self.assertIsNotNone(result)
            
            elif "set" in scenario_name:
                # Benchmark sets
                for i in range(config["iterations"]):
                    test_data = {
                        "validation_passed": True,
                        "iteration": i,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    benchmark.start()
                    success = cache_service.set_availability(config["category"], f"{config['key']}_{i}", test_data)
                    benchmark.stop()
                    self.assertTrue(success)
            
            elif "invalidation" in scenario_name:
                # Pre-populate for invalidation tests
                for i in range(config["iterations"]):
                    test_data = {
                        "validation_passed": True,
                        "invalidation_test": True,
                        "iteration": i
                    }
                    cache_service.set_availability(config["category"], f"{config['key']}_{i}", test_data)
                
                # Benchmark invalidations
                for i in range(config["iterations"]):
                    benchmark.start()
                    cache_service.invalidate_cache(config["category"], f"{config['key']}_{i}")
                    benchmark.stop()
            
            baseline_results[scenario_name] = benchmark.get_stats()
        
        # Report baseline results
        print(f"\n=== Performance Regression Baselines ===")
        for scenario_name, stats in baseline_results.items():
            print(f"{scenario_name}:")
            print(f"  Mean: {stats['mean_ms']:.2f}ms")
            print(f"  P95: {stats['p95_ms']:.2f}ms")
            print(f"  P99: {stats['p99_ms']:.2f}ms")
            print(f"  Operations: {stats['count']}")
        
        # Store baselines for future comparison
        baseline_file = Path(self.temp_dir) / "performance_baselines.json"
        with open(baseline_file, 'w') as f:
            json.dump(baseline_results, f, indent=2)
        
        print(f"\nBaseline results saved to: {baseline_file}")
        
        # Validate baseline performance meets expectations
        hit_baseline = baseline_results["cache_hit_standard"]
        self.assertLess(hit_baseline['p95_ms'], 10.0,
                       "Cache hit P95 baseline should be under 10ms")
        
        set_baseline = baseline_results["cache_set_standard"]
        self.assertLess(set_baseline['p95_ms'], 100.0,
                       "Cache set P95 baseline should be under 100ms")


if __name__ == '__main__':
    # Run performance tests with detailed output
    unittest.main(verbosity=2, buffer=False)
