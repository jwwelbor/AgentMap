"""
Unit tests for RoutingCache.

These tests validate the routing decision caching system using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch
import time
import hashlib
from typing import Dict, Any, List

from agentmap.services.routing.cache import RoutingCache, CacheEntry
from agentmap.services.routing.types import RoutingDecision, TaskComplexity
from tests.utils.mock_service_factory import MockServiceFactory


class TestCacheEntry(unittest.TestCase):
    """Unit tests for CacheEntry data class."""
    
    def test_cache_entry_creation(self):
        """Test CacheEntry creation and basic properties."""
        decision = RoutingDecision(
            provider="test_provider",
            model="test_model",
            complexity=TaskComplexity.MEDIUM,
            confidence=0.8,
            reasoning="Test decision"
        )
        
        entry = CacheEntry(decision=decision, timestamp=123456789.0)
        
        self.assertEqual(entry.decision, decision)
        self.assertEqual(entry.timestamp, 123456789.0)
        self.assertEqual(entry.hit_count, 0)
    
    def test_cache_entry_is_expired(self):
        """Test cache entry expiration checking."""
        decision = RoutingDecision(
            provider="test", model="test", complexity=TaskComplexity.LOW
        )
        
        current_time = time.time()
        entry = CacheEntry(decision=decision, timestamp=current_time - 400)  # 400 seconds ago
        
        # Test with TTL of 300 seconds
        self.assertTrue(entry.is_expired(300))
        
        # Test with TTL of 500 seconds
        self.assertFalse(entry.is_expired(500))
    
    def test_cache_entry_touch(self):
        """Test cache entry touch method updates hit count and timestamp."""
        decision = RoutingDecision(
            provider="test", model="test", complexity=TaskComplexity.LOW
        )
        
        original_time = 123456789.0
        entry = CacheEntry(decision=decision, timestamp=original_time)
        
        # Touch the entry
        with patch('time.time', return_value=123456800.0):
            entry.touch()
        
        # Verify hit count increased and timestamp updated
        self.assertEqual(entry.hit_count, 1)
        self.assertEqual(entry.timestamp, 123456800.0)


class TestRoutingCache(unittest.TestCase):
    """Unit tests for RoutingCache with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Initialize RoutingCache with mocked dependencies
        self.cache = RoutingCache(
            logging_service=self.mock_logging_service,
            max_size=100,
            default_ttl=300
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.cache._logger
    
    # =============================================================================
    # 1. Cache Initialization Tests
    # =============================================================================
    
    def test_cache_initialization(self):
        """Test that cache initializes correctly with all parameters."""
        # Verify configuration
        self.assertEqual(self.cache.max_size, 100)
        self.assertEqual(self.cache.default_ttl, 300)
        self.assertIsNotNone(self.cache._logger)
        
        # Verify internal state
        self.assertEqual(self.cache._cache, {})
        self.assertEqual(self.cache._access_order, [])
        
        # Verify statistics
        self.assertEqual(self.cache._hits, 0)
        self.assertEqual(self.cache._misses, 0)
        self.assertEqual(self.cache._evictions, 0)
    
    def test_cache_initialization_with_injection(self):
        """Test cache initialization with dependency injection."""
        # Verify logging service was called
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.cache)
    
    def test_update_cache_parameters(self):
        """Test updating cache parameters."""
        # Execute update
        self.cache.update_cache_parameters(max_size=200, default_ttl=600)
        
        # Verify parameters updated
        self.assertEqual(self.cache.max_size, 200)
        self.assertEqual(self.cache.default_ttl, 600)
    
    # =============================================================================
    # 2. Cache Key Generation Tests
    # =============================================================================
    
    def test_generate_cache_key_consistency(self):
        """Test cache key generation consistency."""
        # Same parameters should generate same key
        key1 = self.cache._generate_cache_key(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt_hash="abc123",
            available_providers=["openai", "anthropic"],
            provider_preference=["anthropic"],
            cost_optimization=True
        )
        
        key2 = self.cache._generate_cache_key(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt_hash="abc123",
            available_providers=["openai", "anthropic"],
            provider_preference=["anthropic"],
            cost_optimization=True
        )
        
        self.assertEqual(key1, key2)
    
    def test_generate_cache_key_differences(self):
        """Test that different parameters generate different keys."""
        base_params = {
            "task_type": "analysis",
            "complexity": TaskComplexity.HIGH,
            "prompt_hash": "abc123",
            "available_providers": ["openai", "anthropic"],
            "provider_preference": ["anthropic"],
            "cost_optimization": True
        }
        
        base_key = self.cache._generate_cache_key(**base_params)
        
        # Different task type
        different_task = base_params.copy()
        different_task["task_type"] = "general"
        task_key = self.cache._generate_cache_key(**different_task)
        self.assertNotEqual(base_key, task_key)
        
        # Different complexity
        different_complexity = base_params.copy()
        different_complexity["complexity"] = TaskComplexity.LOW
        complexity_key = self.cache._generate_cache_key(**different_complexity)
        self.assertNotEqual(base_key, complexity_key)
        
        # Different providers
        different_providers = base_params.copy()
        different_providers["available_providers"] = ["google"]
        providers_key = self.cache._generate_cache_key(**different_providers)
        self.assertNotEqual(base_key, providers_key)
    
    def test_hash_prompt_consistency(self):
        """Test prompt hashing consistency."""
        prompt = "Test prompt for consistency"
        
        hash1 = self.cache._hash_prompt(prompt)
        hash2 = self.cache._hash_prompt(prompt)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 32)  # MD5 hex length
    
    def test_hash_prompt_differences(self):
        """Test that different prompts generate different hashes."""
        prompt1 = "First prompt"
        prompt2 = "Second prompt"
        
        hash1 = self.cache._hash_prompt(prompt1)
        hash2 = self.cache._hash_prompt(prompt2)
        
        self.assertNotEqual(hash1, hash2)
    
    # =============================================================================
    # 3. Cache Get Operations Tests
    # =============================================================================
    
    def test_cache_get_miss(self):
        """Test cache get operation with cache miss."""
        result = self.cache.get(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="Test prompt",
            available_providers=["openai"],
            provider_preference=["openai"],
            cost_optimization=True
        )
        
        # Should return None for cache miss
        self.assertIsNone(result)
        
        # Verify statistics
        self.assertEqual(self.cache._misses, 1)
        self.assertEqual(self.cache._hits, 0)
    
    def test_cache_get_hit_valid_entry(self):
        """Test cache get operation with valid cache hit."""
        # Create and store a cache entry
        decision = RoutingDecision(
            provider="openai",
            model="gpt-4",
            complexity=TaskComplexity.HIGH,
            confidence=0.9,
            reasoning="Cached decision"
        )
        
        # Put entry in cache
        self.cache.put(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="Test prompt",
            available_providers=["openai"],
            decision=decision
        )
        
        # Get from cache
        result = self.cache.get(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="Test prompt",
            available_providers=["openai"]
        )
        
        # Verify cache hit
        self.assertIsNotNone(result)
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.model, "gpt-4")
        self.assertTrue(result.cache_hit)
        
        # Verify statistics
        self.assertEqual(self.cache._hits, 1)
        self.assertEqual(self.cache._misses, 0)
    
    def test_cache_get_expired_entry(self):
        """Test cache get operation with expired entry."""
        # Create a decision
        decision = RoutingDecision(
            provider="openai",
            model="gpt-4",
            complexity=TaskComplexity.HIGH
        )
        
        # Manually create expired entry
        expired_time = time.time() - 400  # 400 seconds ago
        cache_key = self.cache._generate_cache_key(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt_hash=self.cache._hash_prompt("Test prompt"),
            available_providers=["openai"],
            provider_preference=[],
            cost_optimization=True
        )
        
        expired_entry = CacheEntry(decision=decision, timestamp=expired_time)
        self.cache._cache[cache_key] = expired_entry
        self.cache._access_order.append(cache_key)
        
        # Try to get with short TTL
        result = self.cache.get(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="Test prompt",
            available_providers=["openai"],
            ttl=300  # 5 minutes
        )
        
        # Should return None and remove expired entry
        self.assertIsNone(result)
        self.assertEqual(self.cache._misses, 1)
        self.assertNotIn(cache_key, self.cache._cache)
    
    def test_cache_get_updates_access_order(self):
        """Test that cache get updates LRU access order."""
        # Put two entries
        decision1 = RoutingDecision(provider="openai", model="gpt-3.5", complexity=TaskComplexity.LOW)
        decision2 = RoutingDecision(provider="anthropic", model="claude", complexity=TaskComplexity.HIGH)
        
        self.cache.put("general", TaskComplexity.LOW, "prompt1", ["openai"], decision1)
        self.cache.put("analysis", TaskComplexity.HIGH, "prompt2", ["anthropic"], decision2)
        
        # Access first entry
        self.cache.get("general", TaskComplexity.LOW, "prompt1", ["openai"])
        
        # First entry should now be at end of access order (most recent)
        key1 = self.cache._generate_cache_key(
            "general", TaskComplexity.LOW, self.cache._hash_prompt("prompt1"),
            ["openai"], [], True
        )
        self.assertEqual(self.cache._access_order[-1], key1)
    
    # =============================================================================
    # 4. Cache Put Operations Tests
    # =============================================================================
    
    def test_cache_put_new_entry(self):
        """Test putting a new entry in cache."""
        decision = RoutingDecision(
            provider="anthropic",
            model="claude-3-opus",
            complexity=TaskComplexity.HIGH,
            confidence=0.95,
            reasoning="New cache entry"
        )
        
        # Put entry in cache
        self.cache.put(
            task_type="creative",
            complexity=TaskComplexity.HIGH,
            prompt="Write a story",
            available_providers=["anthropic"],
            decision=decision
        )
        
        # Verify entry was stored
        self.assertEqual(len(self.cache._cache), 1)
        self.assertEqual(len(self.cache._access_order), 1)
        
        # Verify we can retrieve it
        result = self.cache.get(
            task_type="creative",
            complexity=TaskComplexity.HIGH,
            prompt="Write a story",
            available_providers=["anthropic"]
        )
        
        self.assertEqual(result.provider, "anthropic")
        self.assertEqual(result.model, "claude-3-opus")
    
    def test_cache_put_update_existing_entry(self):
        """Test updating an existing cache entry."""
        decision1 = RoutingDecision(provider="openai", model="gpt-3.5", complexity=TaskComplexity.LOW)
        decision2 = RoutingDecision(provider="openai", model="gpt-4", complexity=TaskComplexity.LOW)
        
        # Put first entry
        self.cache.put("general", TaskComplexity.LOW, "test", ["openai"], decision1)
        
        # Put same key with different decision
        self.cache.put("general", TaskComplexity.LOW, "test", ["openai"], decision2)
        
        # Should only have one entry (updated)
        self.assertEqual(len(self.cache._cache), 1)
        
        # Should retrieve updated decision
        result = self.cache.get("general", TaskComplexity.LOW, "test", ["openai"])
        self.assertEqual(result.model, "gpt-4")
    
    def test_cache_put_triggers_eviction(self):
        """Test that cache put triggers LRU eviction when at max size."""
        # Set small cache size
        self.cache.max_size = 2
        
        # Add entries to fill cache
        decision1 = RoutingDecision(provider="p1", model="m1", complexity=TaskComplexity.LOW)
        decision2 = RoutingDecision(provider="p2", model="m2", complexity=TaskComplexity.LOW)
        decision3 = RoutingDecision(provider="p3", model="m3", complexity=TaskComplexity.LOW)
        
        self.cache.put("t1", TaskComplexity.LOW, "prompt1", ["p1"], decision1)
        self.cache.put("t2", TaskComplexity.LOW, "prompt2", ["p2"], decision2)
        
        # Cache should be full
        self.assertEqual(len(self.cache._cache), 2)
        
        # Add third entry to trigger eviction
        self.cache.put("t3", TaskComplexity.LOW, "prompt3", ["p3"], decision3)
        
        # Should still have 2 entries, first one evicted
        self.assertEqual(len(self.cache._cache), 2)
        self.assertEqual(self.cache._evictions, 1)
        
        # First entry should be gone
        result1 = self.cache.get("t1", TaskComplexity.LOW, "prompt1", ["p1"])
        self.assertIsNone(result1)
        
        # Third entry should be present
        result3 = self.cache.get("t3", TaskComplexity.LOW, "prompt3", ["p3"])
        self.assertEqual(result3.provider, "p3")
    
    # =============================================================================
    # 5. Cache Management Tests
    # =============================================================================
    
    def test_cache_clear(self):
        """Test clearing all cache entries."""
        # Add some entries
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        self.cache.put("t1", TaskComplexity.LOW, "p1", ["test"], decision)
        self.cache.put("t2", TaskComplexity.LOW, "p2", ["test"], decision)
        
        # Verify entries exist
        self.assertEqual(len(self.cache._cache), 2)
        
        # Clear cache
        self.cache.clear()
        
        # Verify cache is empty
        self.assertEqual(len(self.cache._cache), 0)
        self.assertEqual(len(self.cache._access_order), 0)
    
    def test_cache_cleanup_expired(self):
        """Test cleaning up expired cache entries."""
        # Create entries with different timestamps
        current_time = time.time()
        
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        
        # Create expired entries manually
        key1 = "expired_key_1"
        key2 = "expired_key_2"
        key3 = "valid_key"
        
        expired_entry1 = CacheEntry(decision=decision, timestamp=current_time - 400)
        expired_entry2 = CacheEntry(decision=decision, timestamp=current_time - 500)
        valid_entry = CacheEntry(decision=decision, timestamp=current_time - 100)
        
        self.cache._cache[key1] = expired_entry1
        self.cache._cache[key2] = expired_entry2
        self.cache._cache[key3] = valid_entry
        self.cache._access_order = [key1, key2, key3]
        
        # Cleanup with 300 second TTL
        expired_count = self.cache.cleanup_expired(ttl=300)
        
        # Should have removed 2 expired entries
        self.assertEqual(expired_count, 2)
        self.assertEqual(len(self.cache._cache), 1)
        self.assertIn(key3, self.cache._cache)
        self.assertNotIn(key1, self.cache._cache)
        self.assertNotIn(key2, self.cache._cache)
    
    def test_cache_cleanup_expired_default_ttl(self):
        """Test cleanup with default TTL."""
        current_time = time.time()
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        
        # Create entry older than default TTL
        old_entry = CacheEntry(decision=decision, timestamp=current_time - 400)
        self.cache._cache["old_key"] = old_entry
        self.cache._access_order = ["old_key"]
        
        # Cleanup without specifying TTL (should use default 300)
        expired_count = self.cache.cleanup_expired()
        
        # Should remove the old entry
        self.assertEqual(expired_count, 1)
        self.assertEqual(len(self.cache._cache), 0)
    
    # =============================================================================
    # 6. LRU Eviction Tests
    # =============================================================================
    
    def test_lru_eviction_order(self):
        """Test LRU eviction removes least recently used entry."""
        self.cache.max_size = 3
        
        # Add entries
        decisions = [
            RoutingDecision(provider=f"p{i}", model=f"m{i}", complexity=TaskComplexity.LOW)
            for i in range(4)
        ]
        
        # Add first 3 entries
        for i in range(3):
            self.cache.put(f"t{i}", TaskComplexity.LOW, f"prompt{i}", [f"p{i}"], decisions[i])
        
        # Access first entry to make it recently used
        self.cache.get("t0", TaskComplexity.LOW, "prompt0", ["p0"])
        
        # Add fourth entry to trigger eviction
        self.cache.put("t3", TaskComplexity.LOW, "prompt3", ["p3"], decisions[3])
        
        # Should have evicted entry 1 (oldest unaccessed)
        result1 = self.cache.get("t1", TaskComplexity.LOW, "prompt1", ["p1"])
        self.assertIsNone(result1)
        
        # Entry 0 should still be there (recently accessed)
        result0 = self.cache.get("t0", TaskComplexity.LOW, "prompt0", ["p0"])
        self.assertIsNotNone(result0)
    
    def test_evict_lru_empty_cache(self):
        """Test LRU eviction with empty cache."""
        # Should not crash
        self.cache._evict_lru()
        
        # Cache should still be empty
        self.assertEqual(len(self.cache._cache), 0)
        self.assertEqual(len(self.cache._access_order), 0)
    
    def test_remove_entry_cleanup(self):
        """Test that _remove_entry cleans up both cache and access order."""
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        test_key = "test_key"
        
        # Add entry manually
        self.cache._cache[test_key] = CacheEntry(decision=decision, timestamp=time.time())
        self.cache._access_order.append(test_key)
        
        # Remove entry
        self.cache._remove_entry(test_key)
        
        # Should be removed from both structures
        self.assertNotIn(test_key, self.cache._cache)
        self.assertNotIn(test_key, self.cache._access_order)
    
    # =============================================================================
    # 7. Statistics Tests
    # =============================================================================
    
    def test_get_stats_empty_cache(self):
        """Test getting statistics from empty cache."""
        stats = self.cache.get_stats()
        
        expected = {
            "size": 0,
            "max_size": 100,
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "evictions": 0,
            "total_requests": 0
        }
        
        self.assertEqual(stats, expected)
    
    def test_get_stats_with_activity(self):
        """Test getting statistics after cache activity."""
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        
        # Add entry and access it
        self.cache.put("test", TaskComplexity.LOW, "prompt", ["test"], decision)
        self.cache.get("test", TaskComplexity.LOW, "prompt", ["test"])  # Hit
        self.cache.get("other", TaskComplexity.LOW, "prompt", ["test"])  # Miss
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 0.5)
        self.assertEqual(stats["total_requests"], 2)
    
    def test_reset_stats(self):
        """Test resetting cache statistics."""
        # Generate some activity
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        self.cache.put("test", TaskComplexity.LOW, "prompt", ["test"], decision)
        self.cache.get("test", TaskComplexity.LOW, "prompt", ["test"])
        self.cache.get("miss", TaskComplexity.LOW, "prompt", ["test"])
        
        # Verify stats exist
        self.assertGreater(self.cache._hits, 0)
        self.assertGreater(self.cache._misses, 0)
        
        # Reset stats
        self.cache.reset_stats()
        
        # Verify stats reset
        self.assertEqual(self.cache._hits, 0)
        self.assertEqual(self.cache._misses, 0)
        self.assertEqual(self.cache._evictions, 0)
    
    # =============================================================================
    # 8. Edge Cases and Error Handling Tests
    # =============================================================================
    
    def test_cache_with_none_values(self):
        """Test cache operations with None values."""
        # Test with None provider preference
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        
        self.cache.put(
            task_type="test",
            complexity=TaskComplexity.LOW,
            prompt="test",
            available_providers=["test"],
            decision=decision,
            provider_preference=None  # Should default to []
        )
        
        result = self.cache.get(
            task_type="test",
            complexity=TaskComplexity.LOW,
            prompt="test",
            available_providers=["test"],
            provider_preference=None
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.provider, "test")
    
    def test_cache_hit_count_tracking(self):
        """Test that cache entries track hit counts correctly."""
        decision = RoutingDecision(provider="test", model="test", complexity=TaskComplexity.LOW)
        
        # Put entry
        self.cache.put("test", TaskComplexity.LOW, "prompt", ["test"], decision)
        
        # Access multiple times
        for i in range(3):
            result = self.cache.get("test", TaskComplexity.LOW, "prompt", ["test"])
            self.assertIsNotNone(result)
        
        # Check hit count in cache entry
        cache_key = self.cache._generate_cache_key(
            "test", TaskComplexity.LOW, self.cache._hash_prompt("prompt"),
            ["test"], [], True
        )
        entry = self.cache._cache[cache_key]
        self.assertEqual(entry.hit_count, 3)
    
    def test_cache_with_complex_routing_context(self):
        """Test cache operations with complex routing parameters."""
        decision = RoutingDecision(provider="complex", model="model", complexity=TaskComplexity.HIGH)
        
        # Put with complex parameters
        self.cache.put(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="Complex analytical task with many parameters",
            available_providers=["openai", "anthropic", "google"],
            decision=decision,
            provider_preference=["anthropic", "openai"],
            cost_optimization=False
        )
        
        # Get with same parameters
        result = self.cache.get(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="Complex analytical task with many parameters",
            available_providers=["openai", "anthropic", "google"],
            provider_preference=["anthropic", "openai"],
            cost_optimization=False
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.provider, "complex")
        
        # Get with different parameters should miss
        result_miss = self.cache.get(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="Complex analytical task with many parameters",
            available_providers=["openai", "anthropic", "google"],
            provider_preference=["openai", "anthropic"],  # Different order
            cost_optimization=False
        )
        
        self.assertIsNone(result_miss)


if __name__ == '__main__':
    unittest.main()
