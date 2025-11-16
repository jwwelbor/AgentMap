"""
Routing decision caching for LLM routing system.

Provides intelligent caching of routing decisions to improve performance
and reduce repeated complexity analysis for identical requests.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dependency_injector.wiring import inject

from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.types import RoutingDecision, TaskComplexity


@dataclass
class CacheEntry:
    """
    A cached routing decision with metadata.
    """

    decision: RoutingDecision
    timestamp: float
    hit_count: int = 0

    def is_expired(self, ttl: int) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.timestamp > ttl

    def touch(self) -> None:
        """Update hit count and timestamp for cache statistics."""
        self.hit_count += 1
        self.timestamp = time.time()


class RoutingCache:
    """
    Cache for routing decisions to improve performance.

    Caches routing decisions based on a hash of the routing parameters,
    with configurable TTL and maximum cache size.
    """

    def __init__(
        self,
        logging_service: LoggingService,  # injected
        max_size: int = 1000,
        default_ttl: int = 300,
    ):
        """
        Initialize the routing cache.

        Args:
            max_size: Maximum number of entries to cache
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # For LRU eviction
        self._logger = logging_service.get_class_logger(self)

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def update_cache_parameters(self, max_size: int, default_ttl: int) -> None:
        """
        Update the cache parameters.

        Args:
            max_size: Maximum number of entries to cache
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl

    def _generate_cache_key(
        self,
        task_type: str,
        complexity: TaskComplexity,
        prompt_hash: str,
        available_providers: List[str],
        provider_preference: List[str],
        cost_optimization: bool,
    ) -> str:
        """
        Generate a cache key based on routing parameters.

        Args:
            task_type: Task type
            complexity: Determined complexity
            prompt_hash: Hash of the prompt content
            available_providers: List of available providers
            provider_preference: Preferred providers
            cost_optimization: Whether cost optimization is enabled

        Returns:
            Cache key string
        """
        # Create a normalized representation of the routing parameters
        key_data = {
            "task_type": task_type,
            "complexity": str(complexity),
            "prompt_hash": prompt_hash,
            "available_providers": sorted(available_providers),
            "provider_preference": provider_preference,
            "cost_optimization": cost_optimization,
        }

        # Create hash of the key data
        key_string = str(sorted(key_data.items()))
        return hashlib.md5(key_string.encode()).hexdigest()

    def _hash_prompt(self, prompt: str) -> str:
        """
        Generate a hash of the prompt content.

        Args:
            prompt: The prompt text

        Returns:
            MD5 hash of the prompt
        """
        return hashlib.md5(prompt.encode()).hexdigest()

    def get(
        self,
        task_type: str,
        complexity: TaskComplexity,
        prompt: str,
        available_providers: List[str],
        provider_preference: List[str] = None,
        cost_optimization: bool = True,
        ttl: Optional[int] = None,
    ) -> Optional[RoutingDecision]:
        """
        Get a cached routing decision if available and not expired.

        Args:
            task_type: Task type
            complexity: Determined complexity
            prompt: The prompt text
            available_providers: List of available providers
            provider_preference: Preferred providers
            cost_optimization: Whether cost optimization is enabled
            ttl: Custom TTL (uses default if None)

        Returns:
            Cached routing decision or None if not found/expired
        """
        if provider_preference is None:
            provider_preference = []

        prompt_hash = self._hash_prompt(prompt)
        cache_key = self._generate_cache_key(
            task_type,
            complexity,
            prompt_hash,
            available_providers,
            provider_preference,
            cost_optimization,
        )

        entry = self._cache.get(cache_key)
        if entry is None:
            self._misses += 1
            return None

        # Check if expired
        cache_ttl = ttl if ttl is not None else self.default_ttl
        if entry.is_expired(cache_ttl):
            self._remove_entry(cache_key)
            self._misses += 1
            return None

        # Update access order for LRU
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)

        # Update entry statistics
        entry.touch()
        self._hits += 1

        # Mark as cache hit in the decision
        decision = entry.decision
        decision.cache_hit = True

        self._logger.trace(f"Cache hit for key: {cache_key[:8]}...")
        return decision

    def put(
        self,
        task_type: str,
        complexity: TaskComplexity,
        prompt: str,
        available_providers: List[str],
        decision: RoutingDecision,
        provider_preference: List[str] = None,
        cost_optimization: bool = True,
    ) -> None:
        """
        Cache a routing decision.

        Args:
            task_type: Task type
            complexity: Determined complexity
            prompt: The prompt text
            available_providers: List of available providers
            decision: The routing decision to cache
            provider_preference: Preferred providers
            cost_optimization: Whether cost optimization is enabled
        """
        if provider_preference is None:
            provider_preference = []

        prompt_hash = self._hash_prompt(prompt)
        cache_key = self._generate_cache_key(
            task_type,
            complexity,
            prompt_hash,
            available_providers,
            provider_preference,
            cost_optimization,
        )

        # Evict if at max size
        if len(self._cache) >= self.max_size and cache_key not in self._cache:
            self._evict_lru()

        # Create cache entry
        entry = CacheEntry(decision=decision, timestamp=time.time())

        self._cache[cache_key] = entry

        # Update access order
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)

        self._logger.debug(f"Cached decision for key: {cache_key[:8]}...")

    def _evict_lru(self) -> None:
        """Evict the least recently used cache entry."""
        if not self._access_order:
            return

        lru_key = self._access_order.pop(0)
        self._remove_entry(lru_key)
        self._evictions += 1

        self._logger.debug(f"Evicted LRU entry: {lru_key[:8]}...")

    def _remove_entry(self, cache_key: str) -> None:
        """Remove an entry from the cache."""
        if cache_key in self._cache:
            del self._cache[cache_key]
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._access_order.clear()
        self._logger.debug("Cache cleared")

    def cleanup_expired(self, ttl: Optional[int] = None) -> int:
        """
        Remove all expired entries from the cache.

        Args:
            ttl: Custom TTL (uses default if None)

        Returns:
            Number of entries removed
        """
        cache_ttl = ttl if ttl is not None else self.default_ttl
        expired_keys = []

        for key, entry in self._cache.items():
            if entry.is_expired(cache_ttl):
                expired_keys.append(key)

        for key in expired_keys:
            self._remove_entry(key)

        if expired_keys:
            self._logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
            "total_requests": total_requests,
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
