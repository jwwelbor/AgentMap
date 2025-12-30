"""
Unit tests for LLMRoutingService.

These tests validate the core LLM routing service using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional
import time

from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import (
    TaskComplexity, RoutingContext, RoutingDecision
)
from agentmap.exceptions.base_exceptions import ConfigurationException
from tests.utils.mock_service_factory import MockServiceFactory


class TestLLMRoutingService(unittest.TestCase):
    """Unit tests for LLMRoutingService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create mock LLMRoutingConfigService
        self.mock_routing_config = Mock()
        self.mock_routing_config.is_routing_cache_enabled.return_value = True
        self.mock_routing_config.performance.get.return_value = 1000
        self.mock_routing_config.get_cache_ttl.return_value = 300
        self.mock_routing_config.get_provider_preference.return_value = ["openai", "anthropic"]
        self.mock_routing_config.is_cost_optimization_enabled.return_value = True
        self.mock_routing_config.get_max_cost_tier.return_value = "high"
        self.mock_routing_config.get_fallback_provider.return_value = "anthropic"
        self.mock_routing_config.get_fallback_model.return_value = "claude-3-7-sonnet-20250219"
        # Mock should return from routing_matrix based on provider and complexity
        def mock_get_model(provider, complexity):
            matrix = {
                "openai": {"low": "gpt-3.5-turbo", "medium": "gpt-4", "high": "gpt-4", "critical": "gpt-4"},
                "anthropic": {"low": "claude-3-5-haiku-20241022", "medium": "claude-3-7-sonnet-20250219", "high": "claude-opus-4-20250514", "critical": "claude-opus-4-20250514"}
            }
            return matrix.get(provider, {}).get(complexity)

        self.mock_routing_config.get_model_for_complexity.side_effect = mock_get_model
        self.mock_routing_config.routing_matrix = {
            "openai": {"low": "gpt-3.5-turbo", "medium": "gpt-4", "high": "gpt-4", "critical": "gpt-4"},
            "anthropic": {"low": "claude-3-5-haiku-20241022", "medium": "claude-3-7-sonnet-20250219", "high": "claude-opus-4-20250514", "critical": "claude-opus-4-20250514"}
        }
        
        # Create mock RoutingCache
        self.mock_cache = Mock()
        self.mock_cache.get.return_value = None
        self.mock_cache.put.return_value = None
        self.mock_cache.get_stats.return_value = {"hits": 10, "misses": 5}
        self.mock_cache.reset_stats.return_value = None
        self.mock_cache.clear.return_value = None
        self.mock_cache.cleanup_expired.return_value = 2
        self.mock_cache.update_cache_parameters.return_value = self.mock_cache
        
        # Create mock PromptComplexityAnalyzer
        self.mock_complexity_analyzer = Mock()
        self.mock_complexity_analyzer.determine_overall_complexity.return_value = TaskComplexity.MEDIUM
        
        # Initialize LLMRoutingService with mocked dependencies
        self.service = LLMRoutingService(
            llm_routing_config_service=self.mock_routing_config,
            logging_service=self.mock_logging_service,
            routing_cache=self.mock_cache,
            prompt_complexity_analyzer=self.mock_complexity_analyzer
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service._logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization_with_cache(self):
        """Test that service initializes correctly with cache enabled."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.routing_config, self.mock_routing_config)
        self.assertEqual(self.service.complexity_analyzer, self.mock_complexity_analyzer)
        self.assertEqual(self.service.cache, self.mock_cache)
        self.assertIsNotNone(self.service._logger)
        
        # Verify cache was configured
        self.mock_cache.update_cache_parameters.assert_called_once_with(max_size=1000, default_ttl=300)
        
        # Verify statistics are initialized
        expected_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "fallback_used": 0,
            "complexity_overrides": 0
        }
        self.assertEqual(self.service._routing_stats, expected_stats)
    
    def test_service_initialization_without_cache(self):
        """Test service initialization with cache disabled."""
        self.mock_routing_config.is_routing_cache_enabled.return_value = False
        
        service_no_cache = LLMRoutingService(
            llm_routing_config_service=self.mock_routing_config,
            logging_service=self.mock_logging_service,
            routing_cache=self.mock_cache,
            prompt_complexity_analyzer=self.mock_complexity_analyzer
        )
        
        # Verify cache is disabled
        self.assertIsNone(service_no_cache.cache)
    
    def test_service_logging_setup(self):
        """Test that service logging is set up correctly."""
        # Verify get_class_logger was called with service instance
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
    
    # =============================================================================
    # 2. Core Routing Logic Tests
    # =============================================================================
    
    def test_route_request_success_without_cache(self):
        """Test successful routing request without cache hit."""
        # Disable cache for this test
        self.service.cache = None
        
        # Setup test data
        prompt = "Analyze this complex data"
        task_type = "analysis"
        available_providers = ["openai", "anthropic"]
        routing_context = RoutingContext(
            task_type=task_type,
            auto_detect_complexity=True,
            cost_optimization=True
        )
        
        # Mock complexity determination
        self.mock_complexity_analyzer.determine_overall_complexity.return_value = TaskComplexity.HIGH
        
        # Execute test
        # Mock select_candidates to return empty so select_optimal_model is called
        with patch.object(self.service, 'select_candidates', return_value=[]), \
             patch.object(self.service, 'select_optimal_model') as mock_select:
            mock_decision = RoutingDecision(
                provider="anthropic",
                model="claude-opus-4-20250514",
                complexity=TaskComplexity.HIGH,
                confidence=0.9,
                reasoning="Selected for high complexity analysis",
                fallback_used=False
            )
            mock_select.return_value = mock_decision

            result = self.service.route_request(
                prompt=prompt,
                task_type=task_type,
                available_providers=available_providers,
                routing_context=routing_context
            )

            # Verify result
            self.assertEqual(result.provider, "anthropic")
            self.assertEqual(result.model, "claude-opus-4-20250514")
            self.assertEqual(result.complexity, TaskComplexity.HIGH)
            self.assertFalse(result.fallback_used)
            
            # Verify method calls
            self.mock_complexity_analyzer.determine_overall_complexity.assert_called_once_with(
                prompt, task_type, routing_context
            )
            mock_select.assert_called_once_with(
                task_type, TaskComplexity.HIGH, available_providers, routing_context
            )
            
            # Verify statistics updated
            self.assertEqual(self.service._routing_stats["total_requests"], 1)
    
    def test_route_request_with_cache_hit(self):
        """Test routing request with cache hit."""
        # Setup cached decision
        cached_decision = RoutingDecision(
            provider="openai",
            model="gpt-4",
            complexity=TaskComplexity.MEDIUM,
            confidence=0.8,
            reasoning="Cached decision",
            fallback_used=False,
            cache_hit=True
        )
        self.mock_cache.get.return_value = cached_decision
        
        # Setup test data
        prompt = "Simple question"
        task_type = "general"
        available_providers = ["openai", "anthropic"]
        routing_context = RoutingContext(task_type=task_type)
        
        # Execute test
        result = self.service.route_request(
            prompt=prompt,
            task_type=task_type,
            available_providers=available_providers,
            routing_context=routing_context
        )
        
        # Verify cache hit result
        self.assertEqual(result, cached_decision)
        self.assertTrue(result.cache_hit)
        
        # Verify cache stats updated
        self.assertEqual(self.service._routing_stats["cache_hits"], 1)
        self.assertEqual(self.service._routing_stats["total_requests"], 1)
    
    def test_route_request_with_caching_new_decision(self):
        """Test routing request that caches a new decision."""
        # Setup cache miss
        self.mock_cache.get.return_value = None
        
        # Setup test data
        prompt = "New complex task"
        task_type = "technical"
        available_providers = ["anthropic"]
        routing_context = RoutingContext(task_type=task_type)
        
        # Mock complexity and selection
        self.mock_complexity_analyzer.determine_overall_complexity.return_value = TaskComplexity.HIGH
        
        decision = RoutingDecision(
            provider="anthropic",
            model="claude-opus-4-20250514",
            complexity=TaskComplexity.HIGH,
            confidence=0.9,
            reasoning="New decision",
            fallback_used=False
        )
        
        # Mock select_candidates to ensure select_optimal_model is called
        with patch.object(self.service, 'select_candidates', return_value=[]), \
             patch.object(self.service, 'select_optimal_model', return_value=decision):
            result = self.service.route_request(
                prompt=prompt,
                task_type=task_type,
                available_providers=available_providers,
                routing_context=routing_context
            )

            # Verify decision was cached
            self.mock_cache.put.assert_called_once()

            # Verify result
            self.assertEqual(result, decision)
    
    def test_route_request_with_fallback(self):
        """Test routing request that triggers fallback decision."""
        # Setup test data
        prompt = "Emergency request"
        task_type = "urgent"
        available_providers = ["openai"]
        routing_context = RoutingContext(
            task_type=task_type,
            fallback_provider="openai",
            fallback_model="gpt-3.5-turbo"
        )
        
        # Mock to trigger fallback - need to mock select_candidates too
        with patch.object(self.service, 'select_candidates', return_value=[]), \
             patch.object(self.service, 'select_optimal_model') as mock_select:
            fallback_decision = RoutingDecision(
                provider="openai",
                model="gpt-3.5-turbo",
                complexity=TaskComplexity.MEDIUM,
                confidence=0.5,
                reasoning="Fallback strategy",
                fallback_used=True
            )
            mock_select.return_value = fallback_decision

            result = self.service.route_request(
                prompt=prompt,
                task_type=task_type,
                available_providers=available_providers,
                routing_context=routing_context
            )

            # Verify fallback was used
            self.assertTrue(result.fallback_used)
            self.assertEqual(self.service._routing_stats["fallback_used"], 1)
    
    def test_route_request_error_handling(self):
        """Test routing request error handling with emergency fallback."""
        # Setup test data
        prompt = "Test prompt"
        task_type = "general"
        available_providers = ["openai", "anthropic"]
        routing_context = RoutingContext(task_type=task_type)
        
        # Mock complexity analyzer to raise exception
        self.mock_complexity_analyzer.determine_overall_complexity.side_effect = Exception("Analysis failed")
        
        # Execute test
        result = self.service.route_request(
            prompt=prompt,
            task_type=task_type,
            available_providers=available_providers,
            routing_context=routing_context
        )
        
        # Verify emergency fallback was created
        self.assertEqual(result.provider, "openai")  # First available
        self.assertTrue(result.fallback_used)
        self.assertLess(result.confidence, 0.5)  # Low confidence
        self.assertIn("Analysis failed", result.reasoning)
    
    # =============================================================================
    # 3. Complexity Determination Tests
    # =============================================================================
    
    def test_determine_complexity_success(self):
        """Test successful complexity determination."""
        prompt = "Complex analysis task"
        task_type = "analysis"
        routing_context = RoutingContext(task_type=task_type)
        
        # Mock complexity analyzer
        self.mock_complexity_analyzer.determine_overall_complexity.return_value = TaskComplexity.HIGH
        
        # Execute test
        result = self.service.determine_complexity(task_type, prompt, routing_context)
        
        # Verify result
        self.assertEqual(result, TaskComplexity.HIGH)
        
        # Verify method call
        self.mock_complexity_analyzer.determine_overall_complexity.assert_called_once_with(
            prompt, task_type, routing_context
        )
    
    def test_determine_complexity_with_override(self):
        """Test complexity determination with override."""
        prompt = "Simple task"
        task_type = "general"
        routing_context = RoutingContext(
            task_type=task_type,
            complexity_override="critical"
        )
        
        # Mock analyzer to return override
        self.mock_complexity_analyzer.determine_overall_complexity.return_value = TaskComplexity.CRITICAL
        
        # Execute test
        result = self.service.determine_complexity(task_type, prompt, routing_context)
        
        # Verify override was used
        self.assertEqual(result, TaskComplexity.CRITICAL)
    
    # =============================================================================
    # 4. Model Selection Tests
    # =============================================================================
    
    def test_select_optimal_model_success(self):
        """Test successful optimal model selection."""
        task_type = "analysis"
        complexity = TaskComplexity.HIGH
        available_providers = ["openai", "anthropic"]
        routing_context = RoutingContext(
            task_type=task_type,
            provider_preference=["anthropic", "openai"]
        )
        
        # Mock provider preference and model lookup
        self.mock_routing_config.get_provider_preference.return_value = ["anthropic"]
        self.mock_routing_config.get_model_for_complexity.return_value = "claude-opus-4-20250514"
        
        # Execute test
        result = self.service.select_optimal_model(
            task_type, complexity, available_providers, routing_context
        )
        
        # Verify successful selection
        self.assertEqual(result.provider, "anthropic")
        self.assertEqual(result.model, "claude-opus-4-20250514")
        self.assertEqual(result.complexity, complexity)
        self.assertFalse(result.fallback_used)
        self.assertGreaterEqual(result.confidence, 0.8)
    
    def test_select_optimal_model_with_model_override(self):
        """Test model selection with explicit model override."""
        task_type = "general"
        complexity = TaskComplexity.MEDIUM
        available_providers = ["openai", "anthropic"]
        routing_context = RoutingContext(
            task_type=task_type,
            model_override="gpt-4"
        )
        
        # Mock routing matrix to find model
        self.mock_routing_config.routing_matrix = {
            "openai": {"medium": "gpt-4"},
            "anthropic": {"medium": "claude-3-7-sonnet-20250219"}
        }
        
        # Execute test
        result = self.service.select_optimal_model(
            task_type, complexity, available_providers, routing_context
        )
        
        # Verify model override was used
        self.assertEqual(result.model, "gpt-4")
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.confidence, 1.0)  # High confidence for override
        self.assertIn("Model override", result.reasoning)
    
    def test_select_optimal_model_cost_optimization(self):
        """Test model selection with cost optimization."""
        task_type = "general"
        complexity = TaskComplexity.LOW
        available_providers = ["openai", "anthropic"]
        routing_context = RoutingContext(
            task_type=task_type,
            cost_optimization=True,
            max_cost_tier="medium"
        )
        
        # Mock cost optimization enabled
        self.mock_routing_config.is_cost_optimization_enabled.return_value = True
        self.mock_routing_config.get_provider_preference.return_value = ["openai"]
        self.mock_routing_config.get_model_for_complexity.return_value = "gpt-3.5-turbo"
        
        # Execute test
        result = self.service.select_optimal_model(
            task_type, complexity, available_providers, routing_context
        )
        
        # Verify cost-optimized selection
        self.assertEqual(result.model, "gpt-3.5-turbo")  # Lower cost model
        self.assertFalse(result.fallback_used)
    
    def test_select_optimal_model_fallback_strategy(self):
        """Test model selection fallback strategy."""
        task_type = "specialized"
        complexity = TaskComplexity.HIGH
        available_providers = ["unknown_provider"]  # No preferred providers available
        routing_context = RoutingContext(
            task_type=task_type,
            fallback_provider="unknown_provider",
            fallback_model="fallback-model"
        )
        
        # Mock no preferred providers available
        self.mock_routing_config.get_provider_preference.return_value = ["openai"]  # Not in available
        self.mock_routing_config.get_fallback_provider.return_value = "unknown_provider"
        self.mock_routing_config.get_fallback_model.return_value = "fallback-model"
        
        # Mock get_model_for_complexity to return None for preferred providers (to trigger fallback)
        def mock_get_model_for_complexity(provider, complexity_str):
            if provider == "openai":  # Preferred provider not available
                return None
            elif provider == "unknown_provider":
                return "fallback-model"
            return None
        
        # Temporarily override the mock
        original_side_effect = self.mock_routing_config.get_model_for_complexity.side_effect
        self.mock_routing_config.get_model_for_complexity.side_effect = mock_get_model_for_complexity
        
        try:
            # Execute test
            result = self.service.select_optimal_model(
                task_type, complexity, available_providers, routing_context
            )
            
            # Verify fallback was used
            self.assertTrue(result.fallback_used)
            self.assertEqual(result.provider, "unknown_provider")
            self.assertEqual(result.model, "fallback-model")
            self.assertLess(result.confidence, 0.8)  # Lower confidence for fallback
        finally:
            # Reset the mock for other tests
            self.mock_routing_config.get_model_for_complexity.side_effect = original_side_effect
            self.mock_routing_config.get_model_for_complexity.return_value = "gpt-4"
    
    def test_select_optimal_model_emergency_fallback(self):
        """Test emergency fallback when all strategies fail."""
        task_type = "impossible"
        complexity = TaskComplexity.CRITICAL
        available_providers = ["test_provider"]
        routing_context = RoutingContext(
            task_type=task_type,
            retry_with_lower_complexity=False  # Disable this to force emergency fallback
        )
        
        # Mock all fallback strategies to fail
        self.mock_routing_config.get_provider_preference.return_value = ["nonexistent"]
        self.mock_routing_config.get_fallback_provider.return_value = "nonexistent"
        self.mock_routing_config.routing_matrix = {
            "test_provider": {"low": "test-model"}
        }
        
        # Execute test
        result = self.service.select_optimal_model(
            task_type, complexity, available_providers, routing_context
        )
        
        # Verify emergency fallback
        self.assertEqual(result.provider, "test_provider")
        self.assertTrue(result.fallback_used)
        self.assertLess(result.confidence, 0.5)  # Should be 0.3 for emergency fallback
        self.assertIn("Emergency fallback", result.reasoning)
    
    # =============================================================================
    # 5. Cache Management Tests
    # =============================================================================
    
    def test_cache_check_hit(self):
        """Test cache check with hit."""
        # Setup cached decision
        cached_decision = RoutingDecision(
            provider="cached_provider",
            model="cached_model",
            complexity=TaskComplexity.MEDIUM,
            confidence=0.8,
            reasoning="From cache"
        )
        self.mock_cache.get.return_value = cached_decision
        
        # Execute test
        result = self.service._check_cache(
            task_type="general",
            complexity=TaskComplexity.MEDIUM,
            prompt="test prompt",
            available_providers=["openai"],
            routing_context=RoutingContext()
        )
        
        # Verify cache hit
        self.assertEqual(result, cached_decision)
        self.mock_cache.get.assert_called_once()
    
    def test_cache_check_miss(self):
        """Test cache check with miss."""
        # Setup cache miss
        self.mock_cache.get.return_value = None
        
        # Execute test
        result = self.service._check_cache(
            task_type="general",
            complexity=TaskComplexity.MEDIUM,
            prompt="test prompt",
            available_providers=["openai"],
            routing_context=RoutingContext()
        )
        
        # Verify cache miss
        self.assertIsNone(result)
        self.mock_cache.get.assert_called_once()
    
    def test_cache_decision_storage(self):
        """Test caching a routing decision."""
        decision = RoutingDecision(
            provider="test_provider",
            model="test_model",
            complexity=TaskComplexity.HIGH,
            confidence=0.9,
            reasoning="Test decision"
        )
        
        # Execute test
        self.service._cache_decision(
            task_type="analysis",
            complexity=TaskComplexity.HIGH,
            prompt="complex analysis",
            available_providers=["test_provider"],
            routing_context=RoutingContext(),
            decision=decision
        )
        
        # Verify decision was cached
        self.mock_cache.put.assert_called_once()
    
    def test_clear_cache(self):
        """Test clearing the routing cache."""
        # Execute test
        self.service.clear_cache()
        
        # Verify cache was cleared
        self.mock_cache.clear.assert_called_once()
    
    def test_cleanup_cache(self):
        """Test cleaning up expired cache entries."""
        # Mock expired entries
        self.mock_cache.cleanup_expired.return_value = 5
        
        # Execute test
        self.service.cleanup_cache()
        
        # Verify cleanup was called
        self.mock_cache.cleanup_expired.assert_called_once()
    
    # =============================================================================
    # 6. Statistics and Monitoring Tests
    # =============================================================================
    
    def test_get_routing_stats_with_cache(self):
        """Test getting routing statistics with cache stats."""
        # Setup mock cache stats
        cache_stats = {"hits": 15, "misses": 5, "hit_rate": 0.75}
        self.mock_cache.get_stats.return_value = cache_stats
        
        # Setup service stats
        self.service._routing_stats = {
            "total_requests": 20,
            "cache_hits": 15,
            "fallback_used": 2,
            "complexity_overrides": 1
        }
        
        # Execute test
        result = self.service.get_routing_stats()
        
        # Verify complete stats
        self.assertEqual(result["total_requests"], 20)
        self.assertEqual(result["cache_hits"], 15)
        self.assertEqual(result["fallback_used"], 2)
        self.assertEqual(result["complexity_overrides"], 1)
        self.assertEqual(result["cache_stats"], cache_stats)
        
        # Verify calculated metrics
        self.assertEqual(result["cache_hit_rate"], 0.75)
        self.assertEqual(result["fallback_rate"], 0.1)
        self.assertEqual(result["override_rate"], 0.05)
    
    def test_get_routing_stats_without_cache(self):
        """Test getting routing statistics without cache."""
        # Disable cache
        self.service.cache = None
        
        # Setup service stats
        self.service._routing_stats = {
            "total_requests": 10,
            "cache_hits": 0,
            "fallback_used": 1,
            "complexity_overrides": 0
        }
        
        # Execute test
        result = self.service.get_routing_stats()
        
        # Verify stats without cache
        self.assertEqual(result["total_requests"], 10)
        self.assertNotIn("cache_stats", result)
        self.assertEqual(result["fallback_rate"], 0.1)
    
    def test_reset_stats(self):
        """Test resetting routing statistics."""
        # Set up some stats
        self.service._routing_stats = {
            "total_requests": 10,
            "cache_hits": 5,
            "fallback_used": 2,
            "complexity_overrides": 1
        }
        
        # Execute test
        self.service.reset_stats()
        
        # Verify stats were reset
        expected_reset = {
            "total_requests": 0,
            "cache_hits": 0,
            "fallback_used": 0,
            "complexity_overrides": 0
        }
        self.assertEqual(self.service._routing_stats, expected_reset)
        
        # Verify cache stats were reset
        self.mock_cache.reset_stats.assert_called_once()
    
    # =============================================================================
    # 7. Helper Method Tests
    # =============================================================================
    
    def test_filter_available_providers(self):
        """Test filtering providers by availability and exclusions."""
        preferred_providers = ["openai", "anthropic", "google"]
        available_providers = ["openai", "anthropic", "cohere"]
        excluded_providers = ["openai"]

        # Execute test - now using model_selector
        result = self.service.model_selector.filter_available_providers(
            preferred_providers, available_providers, excluded_providers
        )

        # Should only include anthropic (available and not excluded)
        self.assertEqual(result, ["anthropic"])
    
    def test_get_lower_complexity(self):
        """Test getting lower complexity levels."""
        # Test all complexity levels - now using fallback_handler
        self.assertEqual(
            self.service.fallback_handler.get_lower_complexity(TaskComplexity.CRITICAL),
            TaskComplexity.HIGH
        )
        self.assertEqual(
            self.service.fallback_handler.get_lower_complexity(TaskComplexity.HIGH),
            TaskComplexity.MEDIUM
        )
        self.assertEqual(
            self.service.fallback_handler.get_lower_complexity(TaskComplexity.MEDIUM),
            TaskComplexity.LOW
        )
        self.assertEqual(
            self.service.fallback_handler.get_lower_complexity(TaskComplexity.LOW),
            TaskComplexity.LOW  # Can't go lower
        )
    
    def test_create_emergency_fallback_success(self):
        """Test creating emergency fallback with available providers."""
        available_providers = ["test_provider"]
        reason = "Test emergency"
        
        # Mock routing matrix
        self.mock_routing_config.routing_matrix = {
            "test_provider": {"low": "emergency-model"}
        }
        
        # Execute test
        result = self.service._create_emergency_fallback(available_providers, reason)
        
        # Verify emergency fallback
        self.assertEqual(result.provider, "test_provider")
        self.assertEqual(result.model, "emergency-model")
        self.assertEqual(result.complexity, TaskComplexity.LOW)
        self.assertTrue(result.fallback_used)
        self.assertLess(result.confidence, 0.5)
        self.assertIn(reason, result.reasoning)
    
    def test_create_emergency_fallback_no_providers(self):
        """Test emergency fallback with no available providers."""
        available_providers = []
        reason = "No providers"
        
        # Execute test and verify error
        with self.assertRaises(ValueError) as context:
            self.service._create_emergency_fallback(available_providers, reason)
        
        self.assertIn("No providers available", str(context.exception))
    
    def test_create_emergency_fallback_last_resort(self):
        """Test emergency fallback last resort with no matrix."""
        available_providers = ["unknown_provider"]
        reason = "Last resort test"

        # Mock empty routing matrix and fallback model
        self.mock_routing_config.routing_matrix = {}
        self.mock_routing_config.get_fallback_model.return_value = "claude-3-7-sonnet-20250219"

        # Execute test
        result = self.service._create_emergency_fallback(available_providers, reason)

        # Verify last resort fallback - now uses config's fallback model
        self.assertEqual(result.provider, "unknown_provider")
        self.assertEqual(result.model, "claude-3-7-sonnet-20250219")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.confidence, 0.1)  # Very low confidence
        self.assertIn("Last resort", result.reasoning)


if __name__ == '__main__':
    unittest.main()
