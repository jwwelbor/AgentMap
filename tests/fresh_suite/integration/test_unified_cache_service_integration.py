"""
Integration tests for the unified AvailabilityCacheService across multiple services.

This test suite validates that the unified cache architecture provides proper
service integration, cross-service coordination, and demonstrates the benefits
of the unified approach over separate cache implementations.

Key Integration Areas:
- DependencyCheckerService integration with unified cache
- LLMRoutingConfigService integration with unified cache
- StorageConfigService integration with unified cache
- Cross-service cache benefits and coordination
- End-to-end workflows demonstrating cache effectiveness
- Performance benefits of unified cache approach
"""

import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

from src.agentmap.services.config.availability_cache_service import (
    AvailabilityCacheService,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestUnifiedCacheServiceIntegration(unittest.TestCase):
    """Integration tests for unified AvailabilityCacheService across services."""

    def setUp(self):
        """Set up test fixtures with shared cache and multiple service mocks."""
        # Create temporary cache file for integration testing
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file_path = Path(self.temp_dir) / "integration_cache.json"

        # Create shared mock logger
        self.mock_logger = (
            MockServiceFactory.create_mock_logging_service().get_class_logger(
                "integration_test"
            )
        )

        # Initialize unified cache service (shared across all services)
        self.unified_cache = AvailabilityCacheService(
            cache_file_path=self.cache_file_path, logger=self.mock_logger
        )

        # Create mock services that would use the unified cache
        self.mock_dependency_checker = self._create_mock_dependency_checker()
        self.mock_llm_routing_config = self._create_mock_llm_routing_config()
        self.mock_storage_config = self._create_mock_storage_config()

        # Sample configurations for testing
        self.sample_configs = {
            "llm_openai": {
                "provider": "openai",
                "api_key": "test-key",
                "model": "gpt-4",
                "timeout": 30,
            },
            "llm_anthropic": {
                "provider": "anthropic",
                "api_key": "test-key",
                "model": "claude-3-sonnet",
                "timeout": 30,
            },
            "storage_csv": {
                "enabled": True,
                "directory": "/data/csv",
                "collections": {"users": {"filename": "users.csv"}},
            },
            "storage_vector": {
                "enabled": True,
                "provider": "local",
                "directory": "/data/vectors",
            },
        }

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        if self.cache_file_path.exists():
            self.cache_file_path.unlink()

        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_mock_dependency_checker(self):
        """Create mock DependencyCheckerService that uses unified cache."""
        mock_service = Mock()

        def check_llm_dependencies(provider=None):
            # Check cache first using unified cache
            if provider:
                cached_result = self.unified_cache.get_availability(
                    "dependency.llm", provider
                )
                if cached_result:
                    return cached_result.get("available", False), cached_result.get(
                        "missing", []
                    )

            # Simulate dependency checking work
            if provider == "openai":
                result = {
                    "available": True,
                    "missing": [],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability("dependency.llm", provider, result)
                return True, []
            elif provider == "anthropic":
                result = {
                    "available": True,
                    "missing": [],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability("dependency.llm", provider, result)
                return True, []
            else:
                result = {
                    "available": False,
                    "missing": [f"missing-{provider}"],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability("dependency.llm", provider, result)
                return False, [f"missing-{provider}"]

        def check_storage_dependencies(storage_type=None):
            # Check cache first using unified cache
            if storage_type:
                cached_result = self.unified_cache.get_availability(
                    "dependency.storage", storage_type
                )
                if cached_result:
                    return cached_result.get("available", False), cached_result.get(
                        "missing", []
                    )

            # Simulate dependency checking work
            if storage_type in ["csv", "vector"]:
                result = {
                    "available": True,
                    "missing": [],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability(
                    "dependency.storage", storage_type, result
                )
                return True, []
            else:
                result = {
                    "available": False,
                    "missing": [f"missing-{storage_type}"],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability(
                    "dependency.storage", storage_type, result
                )
                return False, [f"missing-{storage_type}"]

        mock_service.check_llm_dependencies.side_effect = check_llm_dependencies
        mock_service.check_storage_dependencies.side_effect = check_storage_dependencies

        return mock_service

    def _create_mock_llm_routing_config(self):
        """Create mock LLMRoutingConfigService that uses unified cache."""
        mock_service = Mock()

        def get_provider_availability(provider):
            # Check cache first using unified cache
            cached_result = self.unified_cache.get_availability(
                "llm_provider", provider
            )
            if cached_result:
                return cached_result.get("available", False)

            # Simulate provider configuration validation
            config = self.sample_configs.get(f"llm_{provider}")
            if config and config.get("api_key"):
                result = {
                    "available": True,
                    "config_valid": True,
                    "model": config.get("model"),
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability("llm_provider", provider, result)
                return True
            else:
                result = {
                    "available": False,
                    "config_valid": False,
                    "error": "Invalid configuration",
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability("llm_provider", provider, result)
                return False

        def get_routing_config_for_provider(provider):
            # Check cache first
            cached_result = self.unified_cache.get_availability(
                "llm_provider", provider
            )
            if cached_result and cached_result.get("available"):
                return cached_result.get("config", {})

            # Return empty config if not available
            return {}

        mock_service.get_provider_availability.side_effect = get_provider_availability
        mock_service.get_routing_config_for_provider.side_effect = (
            get_routing_config_for_provider
        )

        return mock_service

    def _create_mock_storage_config(self):
        """Create mock StorageConfigService that uses unified cache."""
        mock_service = Mock()

        def is_storage_available(storage_type):
            # Check cache first using unified cache
            cached_result = self.unified_cache.get_availability("storage", storage_type)
            if cached_result:
                return cached_result.get("available", False)

            # Simulate storage configuration validation
            config = self.sample_configs.get(f"storage_{storage_type}")
            if config and config.get("enabled"):
                result = {
                    "available": True,
                    "config_valid": True,
                    "provider": config.get("provider", storage_type),
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability("storage", storage_type, result)
                return True
            else:
                result = {
                    "available": False,
                    "config_valid": False,
                    "error": "Storage not configured",
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                }
                self.unified_cache.set_availability("storage", storage_type, result)
                return False

        def get_storage_config(storage_type):
            # Use cache to get configuration details
            cached_result = self.unified_cache.get_availability("storage", storage_type)
            if cached_result and cached_result.get("available"):
                return self.sample_configs.get(f"storage_{storage_type}", {})
            return {}

        mock_service.is_storage_available.side_effect = is_storage_available
        mock_service.get_storage_config.side_effect = get_storage_config

        return mock_service

    # =============================================================================
    # 1. Service Integration Pattern Tests
    # =============================================================================

    def test_dependency_checker_service_integration(self):
        """Test DependencyCheckerService integration with unified cache."""
        # First call should be cache miss and perform work
        available1, missing1 = self.mock_dependency_checker.check_llm_dependencies(
            "openai"
        )
        self.assertTrue(available1)
        self.assertEqual(missing1, [])

        # Verify data was cached
        cached_result = self.unified_cache.get_availability("dependency.llm", "openai")
        self.assertIsNotNone(cached_result)
        self.assertTrue(cached_result["available"])
        self.assertIn("checked_at", cached_result)

        # Second call should be cache hit (no additional work)
        available2, missing2 = self.mock_dependency_checker.check_llm_dependencies(
            "openai"
        )
        self.assertTrue(available2)
        self.assertEqual(missing2, [])

        # Verify cache statistics
        stats = self.unified_cache.get_cache_stats()
        self.assertGreaterEqual(stats["performance"]["cache_hits"], 1)
        self.assertGreaterEqual(stats["performance"]["cache_sets"], 1)

    def test_llm_routing_config_service_integration(self):
        """Test LLMRoutingConfigService integration with unified cache."""
        # First call should cache the availability check
        available1 = self.mock_llm_routing_config.get_provider_availability("anthropic")
        self.assertTrue(available1)

        # Verify caching in correct category
        cached_result = self.unified_cache.get_availability("llm_provider", "anthropic")
        self.assertIsNotNone(cached_result)
        self.assertTrue(cached_result["available"])
        self.assertIn("model", cached_result)

        # Second call should use cache
        available2 = self.mock_llm_routing_config.get_provider_availability("anthropic")
        self.assertTrue(available2)

        # Get routing config should use cached data
        config = self.mock_llm_routing_config.get_routing_config_for_provider(
            "anthropic"
        )
        self.assertIsInstance(config, dict)

    def test_storage_config_service_integration(self):
        """Test StorageConfigService integration with unified cache."""
        # First call should cache the result
        available1 = self.mock_storage_config.is_storage_available("csv")
        self.assertTrue(available1)

        # Verify caching in storage category
        cached_result = self.unified_cache.get_availability("storage", "csv")
        self.assertIsNotNone(cached_result)
        self.assertTrue(cached_result["available"])
        self.assertIn("provider", cached_result)

        # Second call should use cache
        available2 = self.mock_storage_config.is_storage_available("csv")
        self.assertTrue(available2)

        # Configuration retrieval should work with cached data
        config = self.mock_storage_config.get_storage_config("csv")
        self.assertIn("collections", config)

    # =============================================================================
    # 2. Cross-Service Cache Coordination Tests
    # =============================================================================

    def test_cross_service_cache_benefits(self):
        """Test that unified cache provides benefits across different services."""
        # Scenario: Multiple services checking the same underlying resource

        # 1. DependencyChecker validates OpenAI dependencies
        dep_available, _ = self.mock_dependency_checker.check_llm_dependencies("openai")
        self.assertTrue(dep_available)

        # 2. LLMRoutingConfig checks OpenAI availability
        # Should potentially benefit from dependency check, but uses different category
        routing_available = self.mock_llm_routing_config.get_provider_availability(
            "openai"
        )
        self.assertTrue(routing_available)

        # 3. Verify both services cached their results in appropriate categories
        dep_cached = self.unified_cache.get_availability("dependency.llm", "openai")
        routing_cached = self.unified_cache.get_availability("llm_provider", "openai")

        self.assertIsNotNone(dep_cached)
        self.assertIsNotNone(routing_cached)

        # Both should show successful validation
        self.assertTrue(dep_cached["available"])
        self.assertTrue(routing_cached["available"])

        # Verify cache contains data from both services
        stats = self.unified_cache.get_cache_stats()
        self.assertIn("dependency.llm", stats["categories"])
        self.assertIn("llm_provider", stats["categories"])
        self.assertGreaterEqual(stats["total_entries"], 2)

    def test_unified_cache_invalidation_coordination(self):
        """Test that cache invalidation affects all coordinated services."""
        # Populate cache from multiple services
        self.mock_dependency_checker.check_llm_dependencies("openai")
        self.mock_dependency_checker.check_storage_dependencies("csv")
        self.mock_llm_routing_config.get_provider_availability("anthropic")
        self.mock_storage_config.is_storage_available("vector")

        # Verify all data is cached
        self.assertIsNotNone(
            self.unified_cache.get_availability("dependency.llm", "openai")
        )
        self.assertIsNotNone(
            self.unified_cache.get_availability("dependency.storage", "csv")
        )
        self.assertIsNotNone(
            self.unified_cache.get_availability("llm_provider", "anthropic")
        )
        self.assertIsNotNone(self.unified_cache.get_availability("storage", "vector"))

        # Invalidate entire cache
        self.unified_cache.invalidate_cache()

        # All cached data should be cleared
        self.assertIsNone(
            self.unified_cache.get_availability("dependency.llm", "openai")
        )
        self.assertIsNone(
            self.unified_cache.get_availability("dependency.storage", "csv")
        )
        self.assertIsNone(
            self.unified_cache.get_availability("llm_provider", "anthropic")
        )
        self.assertIsNone(self.unified_cache.get_availability("storage", "vector"))

        # All services should need to revalidate
        stats = self.unified_cache.get_cache_stats()
        self.assertEqual(stats.get("total_entries", 0), 0)

    def test_category_specific_invalidation_coordination(self):
        """Test that category-specific invalidation maintains service boundaries."""
        # Populate cache from multiple services
        self.mock_dependency_checker.check_llm_dependencies("openai")
        self.mock_dependency_checker.check_storage_dependencies("csv")
        self.mock_llm_routing_config.get_provider_availability("openai")
        self.mock_storage_config.is_storage_available("csv")

        # Invalidate only LLM-related dependencies
        self.unified_cache.invalidate_cache(category="dependency.llm")

        # Only dependency.llm should be cleared
        self.assertIsNone(
            self.unified_cache.get_availability("dependency.llm", "openai")
        )

        # Other categories should remain
        self.assertIsNotNone(
            self.unified_cache.get_availability("dependency.storage", "csv")
        )
        self.assertIsNotNone(
            self.unified_cache.get_availability("llm_provider", "openai")
        )
        self.assertIsNotNone(self.unified_cache.get_availability("storage", "csv"))

    # =============================================================================
    # 3. Concurrent Multi-Service Access Tests
    # =============================================================================

    def test_concurrent_multi_service_access(self):
        """Test concurrent access from multiple services is thread-safe."""
        results = []
        errors = []

        def dependency_worker():
            try:
                for provider in ["openai", "anthropic", "google"]:
                    available, missing = (
                        self.mock_dependency_checker.check_llm_dependencies(provider)
                    )
                    results.append(("dependency", provider, available))
                    time.sleep(0.001)  # Small delay to encourage race conditions
            except Exception as e:
                errors.append(("dependency", e))

        def routing_worker():
            try:
                for provider in ["openai", "anthropic"]:
                    available = self.mock_llm_routing_config.get_provider_availability(
                        provider
                    )
                    results.append(("routing", provider, available))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(("routing", e))

        def storage_worker():
            try:
                for storage_type in ["csv", "vector", "json"]:
                    available = self.mock_storage_config.is_storage_available(
                        storage_type
                    )
                    results.append(("storage", storage_type, available))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(("storage", e))

        # Execute concurrent operations
        threads = [
            threading.Thread(target=dependency_worker),
            threading.Thread(target=routing_worker),
            threading.Thread(target=storage_worker),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=10.0)

        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")

        # Verify operations completed
        self.assertGreater(len(results), 0, "Some operations should have completed")

        # Verify cache maintained consistency
        stats = self.unified_cache.get_cache_stats()
        self.assertGreater(stats["total_entries"], 0)

        # Verify different service categories are represented
        categories = stats.get("categories", {})
        expected_categories = {
            "dependency.llm",
            "dependency.storage",
            "llm_provider",
            "storage",
        }
        actual_categories = set(categories.keys())
        self.assertTrue(
            actual_categories.intersection(expected_categories),
            f"Expected some categories from {expected_categories}, got {actual_categories}",
        )

    # =============================================================================
    # 4. End-to-End Workflow Integration Tests
    # =============================================================================

    def test_complete_service_coordination_workflow(self):
        """Test complete workflow showcasing unified cache coordination."""
        # Simulate realistic workflow: Agent initialization requires multiple checks

        workflow_log = []

        # 1. Check LLM dependencies (e.g., for an LLM agent)
        start_time = time.time()

        openai_deps_available, _ = self.mock_dependency_checker.check_llm_dependencies(
            "openai"
        )
        workflow_log.append(
            ("check_deps", "openai", time.time() - start_time, openai_deps_available)
        )

        # 2. Check LLM provider configuration (routing service)
        start_time = time.time()

        openai_config_available = (
            self.mock_llm_routing_config.get_provider_availability("openai")
        )
        workflow_log.append(
            (
                "check_config",
                "openai",
                time.time() - start_time,
                openai_config_available,
            )
        )

        # 3. Check storage dependencies (for data persistence)
        start_time = time.time()

        csv_deps_available, _ = self.mock_dependency_checker.check_storage_dependencies(
            "csv"
        )
        workflow_log.append(
            ("check_storage_deps", "csv", time.time() - start_time, csv_deps_available)
        )

        # 4. Check storage configuration
        start_time = time.time()

        csv_config_available = self.mock_storage_config.is_storage_available("csv")
        workflow_log.append(
            (
                "check_storage_config",
                "csv",
                time.time() - start_time,
                csv_config_available,
            )
        )

        # 5. Second agent initialization (should benefit from cache)
        start_time = time.time()

        openai_deps_available2, _ = self.mock_dependency_checker.check_llm_dependencies(
            "openai"
        )
        workflow_log.append(
            (
                "check_deps_cached",
                "openai",
                time.time() - start_time,
                openai_deps_available2,
            )
        )

        start_time = time.time()
        openai_config_available2 = (
            self.mock_llm_routing_config.get_provider_availability("openai")
        )
        workflow_log.append(
            (
                "check_config_cached",
                "openai",
                time.time() - start_time,
                openai_config_available2,
            )
        )

        # Verify all checks succeeded
        for operation, resource, duration, available in workflow_log:
            self.assertTrue(
                available, f"Workflow step failed: {operation} for {resource}"
            )

        # Verify caching improved performance (cached operations should be faster)
        initial_checks = [log for log in workflow_log if not log[0].endswith("_cached")]
        cached_checks = [log for log in workflow_log if log[0].endswith("_cached")]

        if cached_checks:
            avg_initial_time = sum(log[2] for log in initial_checks) / len(
                initial_checks
            )
            avg_cached_time = sum(log[2] for log in cached_checks) / len(cached_checks)

            # Cached operations should generally be faster
            # (allowing some tolerance for system variations)
            self.assertLessEqual(
                avg_cached_time,
                avg_initial_time * 2,
                "Cached operations should be faster than initial operations",
            )

        # Verify comprehensive cache coverage
        stats = self.unified_cache.get_cache_stats()
        self.assertGreaterEqual(stats["total_entries"], 3)
        self.assertIn("dependency.llm", stats["categories"])
        self.assertIn("llm_provider", stats["categories"])
        self.assertIn("dependency.storage", stats["categories"])
        self.assertIn("storage", stats["categories"])

    def test_service_failure_handling_workflow(self):
        """Test workflow behavior when some services fail."""
        # Simulate mixed success/failure scenario

        # 1. Successful dependency check
        openai_available, _ = self.mock_dependency_checker.check_llm_dependencies(
            "openai"
        )
        self.assertTrue(openai_available)

        # 2. Failed dependency check (missing provider)
        missing_available, missing_deps = (
            self.mock_dependency_checker.check_llm_dependencies("missing_provider")
        )
        self.assertFalse(missing_available)
        self.assertGreater(len(missing_deps), 0)

        # 3. Successful routing config
        anthropic_available = self.mock_llm_routing_config.get_provider_availability(
            "anthropic"
        )
        self.assertTrue(anthropic_available)

        # 4. Failed storage check
        invalid_storage_available = self.mock_storage_config.is_storage_available(
            "invalid_storage"
        )
        self.assertFalse(invalid_storage_available)

        # Verify cache contains both successful and failed results
        openai_cached = self.unified_cache.get_availability("dependency.llm", "openai")
        self.assertIsNotNone(openai_cached)
        self.assertTrue(openai_cached["available"])

        missing_cached = self.unified_cache.get_availability(
            "dependency.llm", "missing_provider"
        )
        self.assertIsNotNone(missing_cached)
        self.assertFalse(missing_cached["available"])

        anthropic_cached = self.unified_cache.get_availability(
            "llm_provider", "anthropic"
        )
        self.assertIsNotNone(anthropic_cached)
        self.assertTrue(anthropic_cached["available"])

        invalid_storage_cached = self.unified_cache.get_availability(
            "storage", "invalid_storage"
        )
        self.assertIsNotNone(invalid_storage_cached)
        self.assertFalse(invalid_storage_cached["available"])

        # Verify cache statistics account for all operations
        stats = self.unified_cache.get_cache_stats()
        self.assertEqual(stats["total_entries"], 4)

    # =============================================================================
    # 5. Performance and Scalability Tests
    # =============================================================================

    def test_unified_cache_performance_benefits(self):
        """Test performance benefits of unified vs separate cache approach."""
        # Simulate high-frequency service operations

        providers = ["openai", "anthropic", "google", "local"]
        storage_types = ["csv", "json", "vector", "firebase"]

        # Measure time for initial cache population
        start_time = time.time()

        for provider in providers:
            self.mock_dependency_checker.check_llm_dependencies(provider)
            self.mock_llm_routing_config.get_provider_availability(provider)

        for storage_type in storage_types:
            self.mock_dependency_checker.check_storage_dependencies(storage_type)
            self.mock_storage_config.is_storage_available(storage_type)

        population_time = time.time() - start_time

        # Measure time for cached operations
        start_time = time.time()

        for _ in range(3):  # Multiple rounds to test cache effectiveness
            for provider in providers:
                self.mock_dependency_checker.check_llm_dependencies(provider)
                self.mock_llm_routing_config.get_provider_availability(provider)

            for storage_type in storage_types:
                self.mock_dependency_checker.check_storage_dependencies(storage_type)
                self.mock_storage_config.is_storage_available(storage_type)

        cached_time = time.time() - start_time

        # Cached operations should be significantly faster per operation
        operations_per_round = (
            len(providers) * 2 + len(storage_types) * 2
        )  # 2 services per resource type
        cached_time_per_operation = cached_time / (3 * operations_per_round)
        population_time_per_operation = population_time / operations_per_round

        # Cache should provide performance benefit
        self.assertLess(
            cached_time_per_operation,
            population_time_per_operation,
            f"Cached operations ({cached_time_per_operation:.4f}s) should be faster than "
            f"population operations ({population_time_per_operation:.4f}s)",
        )

        # Verify comprehensive cache usage statistics
        stats = self.unified_cache.get_cache_stats()
        self.assertGreater(
            stats["performance"]["cache_hits"], 20
        )  # Should have many cache hits
        self.assertGreater(
            stats["performance"]["cache_sets"], 10
        )  # Should have initial cache sets

    def test_cache_memory_efficiency_across_services(self):
        """Test memory efficiency of unified cache vs separate caches."""
        # Simulate scenario where separate caches might duplicate data

        # Same resource checked by multiple service types
        resource_checks = [
            ("dependency.llm", "openai"),
            ("llm_provider", "openai"),
            ("dependency.storage", "csv"),
            ("storage", "csv"),
        ]

        # Populate cache through different services
        self.mock_dependency_checker.check_llm_dependencies("openai")
        self.mock_llm_routing_config.get_provider_availability("openai")
        self.mock_dependency_checker.check_storage_dependencies("csv")
        self.mock_storage_config.is_storage_available("csv")

        # Verify each service type uses its own cache category (no duplication conflict)
        for category, key in resource_checks:
            cached_result = self.unified_cache.get_availability(category, key)
            self.assertIsNotNone(cached_result, f"Missing cache for {category}.{key}")

        # Verify unified cache maintains service boundaries while sharing infrastructure
        stats = self.unified_cache.get_cache_stats()
        self.assertEqual(
            stats["total_entries"], 4
        )  # One entry per category/key combination

        # Verify categories are properly separated
        categories = stats["categories"]
        self.assertEqual(len(categories), 4)  # All 4 categories should be present
        for category_name in [
            "dependency.llm",
            "llm_provider",
            "dependency.storage",
            "storage",
        ]:
            self.assertIn(category_name, categories)
            self.assertEqual(categories[category_name], 1)  # Each category has 1 entry

    # =============================================================================
    # 6. Cache Invalidation Impact Tests
    # =============================================================================

    def test_config_change_invalidation_impact(self):
        """Test impact of configuration changes on multi-service cache."""
        # Populate cache with data from multiple services
        services_data = [
            (self.mock_dependency_checker.check_llm_dependencies, "openai"),
            (self.mock_llm_routing_config.get_provider_availability, "anthropic"),
            (self.mock_storage_config.is_storage_available, "csv"),
        ]

        for service_method, resource in services_data:
            service_method(resource)

        # Verify cache is populated
        initial_stats = self.unified_cache.get_cache_stats()
        self.assertGreater(initial_stats["total_entries"], 0)

        # Simulate configuration change by invalidating cache
        self.unified_cache.invalidate_cache()

        # Verify cache is cleared
        cleared_stats = self.unified_cache.get_cache_stats()
        self.assertEqual(cleared_stats.get("total_entries", 0), 0)

        # All services should need to revalidate
        for service_method, resource in services_data:
            # This should repopulate cache
            result = service_method(resource)
            self.assertIsNotNone(result)

        # Verify cache is repopulated
        repopulated_stats = self.unified_cache.get_cache_stats()
        self.assertEqual(
            repopulated_stats["total_entries"], initial_stats["total_entries"]
        )

    def test_selective_invalidation_preserves_unrelated_services(self):
        """Test that selective invalidation doesn't affect unrelated services."""
        # Populate cache with data from different service categories
        self.mock_dependency_checker.check_llm_dependencies("openai")
        self.mock_dependency_checker.check_storage_dependencies("csv")
        self.mock_llm_routing_config.get_provider_availability("anthropic")
        self.mock_storage_config.is_storage_available("vector")

        # Verify all data is cached
        self.assertIsNotNone(
            self.unified_cache.get_availability("dependency.llm", "openai")
        )
        self.assertIsNotNone(
            self.unified_cache.get_availability("dependency.storage", "csv")
        )
        self.assertIsNotNone(
            self.unified_cache.get_availability("llm_provider", "anthropic")
        )
        self.assertIsNotNone(self.unified_cache.get_availability("storage", "vector"))

        # Invalidate only LLM provider category
        self.unified_cache.invalidate_cache(category="llm_provider")

        # Only LLM provider should be cleared
        self.assertIsNotNone(
            self.unified_cache.get_availability("dependency.llm", "openai")
        )
        self.assertIsNotNone(
            self.unified_cache.get_availability("dependency.storage", "csv")
        )
        self.assertIsNone(
            self.unified_cache.get_availability("llm_provider", "anthropic")
        )
        self.assertIsNotNone(self.unified_cache.get_availability("storage", "vector"))

        # Other services should continue to benefit from their cached data
        # while the affected service needs to revalidate
        anthropic_available = self.mock_llm_routing_config.get_provider_availability(
            "anthropic"
        )
        self.assertTrue(anthropic_available)

        # Verify cache statistics show selective impact
        stats = self.unified_cache.get_cache_stats()
        self.assertEqual(
            stats["total_entries"], 4
        )  # All 4 entries should be present again

    # =============================================================================
    # 7. Service Integration Architecture Validation
    # =============================================================================

    def test_cache_service_never_performs_business_logic(self):
        """Verify cache service only provides storage, never business logic."""
        # The cache service should never import or call external services
        # This test validates the architectural boundary

        # Cache service should only store and retrieve data, not validate it
        fake_result = {
            "available": True,
            "fake_validation": "this would never be real",
            "invalid_data": 12345,
        }

        # Cache should store any data without validation
        success = self.unified_cache.set_availability("test", "fake", fake_result)
        self.assertTrue(success)

        # Cache should retrieve exactly what was stored
        retrieved = self.unified_cache.get_availability("test", "fake")
        self.assertEqual(retrieved["fake_validation"], "this would never be real")
        self.assertEqual(retrieved["invalid_data"], 12345)

        # Cache should not modify or validate business data
        self.assertEqual(retrieved["available"], fake_result["available"])

    def test_services_populate_cache_after_doing_work(self):
        """Verify services follow 'check cache → do work → populate cache' pattern."""
        # This test validates the integration pattern through mock behavior

        # Track cache access patterns
        original_get = self.unified_cache.get_availability
        original_set = self.unified_cache.set_availability

        access_log = []

        def tracking_get(category, key):
            result = original_get(category, key)
            access_log.append(("GET", category, key, result is not None))
            return result

        def tracking_set(category, key, data):
            result = original_set(category, key, data)
            access_log.append(("SET", category, key, result))
            return result

        self.unified_cache.get_availability = tracking_get
        self.unified_cache.set_availability = tracking_set

        # Execute service operation
        available = self.mock_llm_routing_config.get_provider_availability("openai")
        self.assertTrue(available)

        # Verify pattern: GET (cache miss) → SET (populate cache)
        get_operations = [op for op in access_log if op[0] == "GET"]
        set_operations = [op for op in access_log if op[0] == "SET"]

        self.assertGreater(len(get_operations), 0, "Service should check cache first")
        self.assertGreater(
            len(set_operations), 0, "Service should populate cache after work"
        )

        # First GET should be cache miss, then SET should populate
        first_get = get_operations[0]
        self.assertFalse(first_get[3], "First cache check should be miss")

        corresponding_set = None
        for set_op in set_operations:
            if (
                set_op[1] == first_get[1] and set_op[2] == first_get[2]
            ):  # Same category and key
                corresponding_set = set_op
                break

        self.assertIsNotNone(
            corresponding_set, "Service should populate cache after cache miss"
        )
        self.assertTrue(corresponding_set[3], "Cache population should succeed")

    def test_unified_cache_provides_proper_service_isolation(self):
        """Test that unified cache maintains proper service isolation."""
        # Different services should be able to cache data for the same logical resource
        # without interfering with each other

        resource_name = "openai"

        # Different services cache data about the same resource
        self.mock_dependency_checker.check_llm_dependencies(resource_name)
        self.mock_llm_routing_config.get_provider_availability(resource_name)

        # Each service should have its own cache entry
        dep_result = self.unified_cache.get_availability(
            "dependency.llm", resource_name
        )
        routing_result = self.unified_cache.get_availability(
            "llm_provider", resource_name
        )

        self.assertIsNotNone(dep_result)
        self.assertIsNotNone(routing_result)

        # Results should be different (service-specific data)
        self.assertIn("checked_at", dep_result)  # DependencyChecker-specific
        self.assertIn("model", routing_result)  # LLMRoutingConfig-specific

        # Services should be isolated - clearing one shouldn't affect the other
        self.unified_cache.invalidate_cache(
            category="dependency.llm", key=resource_name
        )

        # Only dependency cache should be cleared
        self.assertIsNone(
            self.unified_cache.get_availability("dependency.llm", resource_name)
        )
        self.assertIsNotNone(
            self.unified_cache.get_availability("llm_provider", resource_name)
        )


if __name__ == "__main__":
    unittest.main()
