---
sidebar_position: 4
title: Advanced Testing Patterns
description: Specialized testing patterns for performance, security, integration, and complex scenarios in AgentMap
keywords: [advanced testing, performance testing, security testing, integration testing, load testing, specialized patterns]
---

# Advanced Testing Patterns

Specialized testing patterns for complex AgentMap scenarios including performance testing, security validation, integration testing, and advanced mock strategies.

:::tip For Complex Scenarios
Reference these patterns when implementing:
- 🚀 **Performance & Load Testing** - Scalability and timing requirements
- 🔐 **Security Testing** - Authentication and authorization patterns
- 🔄 **Integration Testing** - Multi-service coordination
- 🎛️ **Advanced Mocking** - Complex dependency scenarios
- 📊 **Monitoring & Metrics** - Observability testing
:::

## 🚀 Performance Testing Patterns

### Benchmark Testing with Timing Assertions

```python
import time
import threading
from unittest.mock import patch
from contextlib import contextmanager

class PerformanceTestMixin:
    """Mixin for performance testing capabilities."""
    
    @contextmanager
    def time_operation(self, max_duration=1.0, operation_name="operation"):
        """Context manager for timing operations with automatic assertions."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.assertLess(
                duration, 
                max_duration, 
                f"{operation_name} took {duration:.2f}s, expected < {max_duration}s"
            )
    
    def assert_performance_improvement(self, baseline_func, optimized_func, 
                                     min_improvement=0.5, iterations=3):
        """Assert that optimized function performs better than baseline."""
        
        # Measure baseline performance
        baseline_times = []
        for _ in range(iterations):
            start = time.time()
            baseline_func()
            baseline_times.append(time.time() - start)
        
        # Measure optimized performance
        optimized_times = []
        for _ in range(iterations):
            start = time.time()
            optimized_func()
            optimized_times.append(time.time() - start)
        
        # Calculate averages
        avg_baseline = sum(baseline_times) / len(baseline_times)
        avg_optimized = sum(optimized_times) / len(optimized_times)
        
        improvement = (avg_baseline - avg_optimized) / avg_baseline
        
        self.assertGreater(
            improvement,
            min_improvement,
            f"Expected {min_improvement*100}% improvement, got {improvement*100:.1f}%"
        )

class TestServicePerformance(unittest.TestCase, PerformanceTestMixin):
    """Performance testing for AgentMap services."""
    
    def setUp(self):
        self.mock_config = MockServiceFactory.create_mock_app_config_service()
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        self.mock_llm = MockServiceFactory.create_mock_llm_service()
        
        # Configure fast mock responses
        self.mock_llm.process.return_value = {"result": "fast_response"}
        
        self.service = MyService(
            app_config_service=self.mock_config,
            logging_service=self.mock_logging,
            llm_service=self.mock_llm
        )
    
    def test_single_request_performance(self):
        """Test single request meets performance requirements."""
        with self.time_operation(max_duration=0.1, operation_name="single_request"):
            result = self.service.process_single_request("test_input")
        
        self.assertTrue(result.success)
        self.mock_llm.process.assert_called_once()
    
    def test_batch_processing_efficiency(self):
        """Test batch processing is more efficient than individual requests."""
        
        def process_individually():
            for i in range(10):
                self.service.process_single_request(f"input_{i}")
        
        def process_as_batch():
            inputs = [f"input_{i}" for i in range(10)]
            self.service.process_batch_requests(inputs)
        
        # Reset mock call counts between tests
        self.mock_llm.reset_mock()
        
        self.assert_performance_improvement(
            baseline_func=process_individually,
            optimized_func=process_as_batch,
            min_improvement=0.3  # 30% improvement expected
        )
    
    def test_caching_performance_benefit(self):
        """Test caching provides measurable performance improvement."""
        
        # First call - cache miss (slower)
        self.mock_storage = MockServiceFactory.create_mock_storage_service()
        self.mock_storage.cache_lookup.return_value = None
        self.mock_storage.cache_store.return_value = True
        self.service.storage = self.mock_storage
        
        with self.time_operation(max_duration=0.5, operation_name="cache_miss"):
            result1 = self.service.process_with_cache("test_key")
        
        # Second call - cache hit (faster)
        self.mock_storage.cache_lookup.return_value = {"cached": "fast_result"}
        
        with self.time_operation(max_duration=0.1, operation_name="cache_hit"):
            result2 = self.service.process_with_cache("test_key")
        
        # Verify cache was used
        self.assertEqual(self.mock_storage.cache_lookup.call_count, 2)
        self.assertEqual(result2.result, "fast_result")
```

### Load Testing and Concurrency

```python
import concurrent.futures
import queue
import threading
from unittest.mock import Mock

class LoadTestingMixin:
    """Mixin for load testing capabilities."""
    
    def run_concurrent_requests(self, request_func, num_requests=10, 
                               max_workers=5, timeout=10):
        """Run multiple requests concurrently and collect results."""
        
        results = []
        errors = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all requests
            futures = []
            for i in range(num_requests):
                future = executor.submit(request_func, i)
                futures.append(future)
            
            # Collect results with timeout
            for future in concurrent.futures.as_completed(futures, timeout=timeout):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append(e)
        
        return results, errors
    
    def assert_concurrent_performance(self, request_func, expected_success_rate=0.95,
                                    max_response_time=2.0, num_requests=20):
        """Assert service handles concurrent load appropriately."""
        
        start_time = time.time()
        results, errors = self.run_concurrent_requests(request_func, num_requests)
        total_time = time.time() - start_time
        
        # Calculate success rate
        success_rate = len(results) / num_requests
        avg_response_time = total_time / num_requests
        
        self.assertGreaterEqual(
            success_rate, 
            expected_success_rate,
            f"Success rate {success_rate:.2%} below expected {expected_success_rate:.2%}"
        )
        
        self.assertLess(
            avg_response_time,
            max_response_time,
            f"Average response time {avg_response_time:.2f}s exceeds {max_response_time}s"
        )
        
        if errors:
            print(f"Encountered {len(errors)} errors during load test:")
            for error in errors[:3]:  # Show first 3 errors
                print(f"  - {error}")

class TestServiceLoadHandling(unittest.TestCase, LoadTestingMixin):
    """Load testing for service scalability."""
    
    def setUp(self):
        self.service = self.create_test_service()
        
        # Configure thread-safe mocks
        self.mock_llm = MockServiceFactory.create_mock_llm_service()
        self.mock_llm.process.return_value = {"result": "load_test_response"}
        self.service.llm_service = self.mock_llm
    
    def test_concurrent_request_handling(self):
        """Test service handles concurrent requests without issues."""
        
        def make_request(request_id):
            return self.service.process_request(f"request_{request_id}")
        
        self.assert_concurrent_performance(
            request_func=make_request,
            expected_success_rate=0.95,
            max_response_time=1.0,
            num_requests=20
        )
        
        # Verify all requests were processed
        self.assertEqual(self.mock_llm.process.call_count, 20)
    
    def test_memory_usage_under_load(self):
        """Test memory usage remains stable under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Process large dataset
        large_inputs = [f"large_input_{i}" * 100 for i in range(100)]
        
        results = []
        for input_data in large_inputs:
            result = self.service.process_large_input(input_data)
            results.append(result)
        
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Assert memory growth is reasonable (< 100MB)
        max_growth = 100 * 1024 * 1024  # 100MB in bytes
        self.assertLess(
            memory_growth,
            max_growth,
            f"Memory grew by {memory_growth / (1024*1024):.1f}MB, expected < 100MB"
        )
        
        # Verify all results were processed
        self.assertEqual(len(results), 100)
        self.assertTrue(all(r.success for r in results))
```

### Resource Usage and Profiling

```python
import cProfile
import pstats
import memory_profiler
from functools import wraps

class ProfilingTestMixin:
    """Mixin for performance profiling in tests."""
    
    def profile_operation(self, operation_func, *args, **kwargs):
        """Profile an operation and return performance statistics."""
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            result = operation_func(*args, **kwargs)
        finally:
            profiler.disable()
        
        # Analyze results
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        
        return result, stats
    
    def assert_no_expensive_operations(self, operation_func, forbidden_patterns, *args, **kwargs):
        """Assert operation doesn't perform expensive operations."""
        
        result, stats = self.profile_operation(operation_func, *args, **kwargs)
        
        # Check for forbidden operations
        stats_dict = stats.get_stats()
        for func_info in stats_dict:
            func_name = str(func_info)
            for pattern in forbidden_patterns:
                if pattern in func_name.lower():
                    self.fail(f"Forbidden operation detected: {pattern} in {func_name}")
        
        return result
    
    @memory_profiler.profile
    def memory_profile_operation(self, operation_func, *args, **kwargs):
        """Profile memory usage of an operation."""
        return operation_func(*args, **kwargs)

class TestServiceProfiling(unittest.TestCase, ProfilingTestMixin):
    """Performance profiling tests."""
    
    def test_no_file_operations_in_processing(self):
        """Ensure processing doesn't perform real file operations."""
        
        forbidden_operations = ['open', 'read', 'write', 'stat']
        
        result = self.assert_no_expensive_operations(
            self.service.process_data,
            forbidden_operations,
            "test_input"
        )
        
        self.assertTrue(result.success)
    
    def test_batch_processing_efficiency_profile(self):
        """Profile batch processing to identify bottlenecks."""
        
        large_batch = [f"item_{i}" for i in range(1000)]
        
        result, stats = self.profile_operation(
            self.service.process_batch,
            large_batch
        )
        
        # Analyze top time consumers
        stats.sort_stats('cumulative')
        top_functions = stats.get_stats()
        
        # Print top 5 for analysis
        print("Top time consumers:")
        for i, (func_info, (cc, nc, tt, ct, callers)) in enumerate(list(top_functions.items())[:5]):
            print(f"{i+1}. {func_info}: {ct:.3f}s cumulative")
        
        # Assert reasonable performance
        self.assertTrue(result.success)
        self.assertEqual(len(result.processed_items), 1000)
```

## 🔐 Security Testing Patterns

### Authentication and Authorization Testing

```python
import jwt
from datetime import datetime, timedelta

class SecurityTestMixin:
    """Mixin for security testing capabilities."""
    
    def create_test_jwt_token(self, payload=None, secret="test_secret", 
                             expires_in_minutes=60, algorithm="HS256"):
        """Create test JWT token with configurable payload."""
        
        default_payload = {
            "user_id": "test_user",
            "permissions": ["read", "write"],
            "exp": datetime.utcnow() + timedelta(minutes=expires_in_minutes),
            "iat": datetime.utcnow()
        }
        
        if payload:
            default_payload.update(payload)
        
        return jwt.encode(default_payload, secret, algorithm=algorithm)
    
    def assert_requires_authentication(self, request_func, *args, **kwargs):
        """Assert that endpoint requires authentication."""
        
        # Test without authentication
        response = request_func(*args, **kwargs)
        self.assertEqual(response.status_code, 401, "Expected 401 for unauthenticated request")
        
        # Test with invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        kwargs_with_auth = kwargs.copy()
        kwargs_with_auth['headers'] = headers
        
        response = request_func(*args, **kwargs_with_auth)
        self.assertEqual(response.status_code, 401, "Expected 401 for invalid token")
    
    def assert_requires_permission(self, request_func, required_permission, *args, **kwargs):
        """Assert that endpoint requires specific permission."""
        
        # Test with insufficient permissions
        token = self.create_test_jwt_token({"permissions": ["read"]})
        headers = {"Authorization": f"Bearer {token}"}
        kwargs_with_auth = kwargs.copy()
        kwargs_with_auth['headers'] = headers
        
        response = request_func(*args, **kwargs_with_auth)
        self.assertEqual(response.status_code, 403, "Expected 403 for insufficient permissions")
        
        # Test with correct permissions
        token = self.create_test_jwt_token({"permissions": [required_permission]})
        headers = {"Authorization": f"Bearer {token}"}
        kwargs_with_auth['headers'] = headers
        
        response = request_func(*args, **kwargs_with_auth)
        self.assertNotEqual(response.status_code, 403, "Should allow access with correct permission")

class TestAPISecurityPatterns(unittest.TestCase, SecurityTestMixin):
    """Security testing for API endpoints."""
    
    def setUp(self):
        self.client = self.create_test_client()
        self.setup_auth_service()
    
    def test_authentication_matrix(self):
        """Test authentication requirements across all endpoints."""
        
        protected_endpoints = [
            ("GET", "/api/graphs"),
            ("POST", "/api/graphs"),
            ("PUT", "/api/graphs/test"),
            ("DELETE", "/api/graphs/test")
        ]
        
        for method, endpoint in protected_endpoints:
            with self.subTest(method=method, endpoint=endpoint):
                request_func = getattr(self.client, method.lower())
                self.assert_requires_authentication(request_func, endpoint)
    
    def test_permission_matrix(self):
        """Test permission requirements for different operations."""
        
        permission_tests = [
            ("GET", "/api/graphs", "graphs:read"),
            ("POST", "/api/graphs", "graphs:write"),
            ("PUT", "/api/graphs/test", "graphs:write"),
            ("DELETE", "/api/graphs/test", "graphs:delete")
        ]
        
        for method, endpoint, permission in permission_tests:
            with self.subTest(method=method, endpoint=endpoint, permission=permission):
                request_func = getattr(self.client, method.lower())
                self.assert_requires_permission(request_func, permission, endpoint)
    
    def test_token_expiration_handling(self):
        """Test expired token handling."""
        
        # Create expired token
        expired_token = self.create_test_jwt_token(expires_in_minutes=-60)
        headers = {"Authorization": f"Bearer {expired_token}"}
        
        response = self.client.get("/api/graphs", headers=headers)
        self.assertEqual(response.status_code, 401)
        
        response_data = response.json()
        self.assertIn("expired", response_data.get("error", "").lower())
    
    def test_rate_limiting(self):
        """Test rate limiting protection."""
        
        # Create valid token
        token = self.create_test_jwt_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make requests up to rate limit
        responses = []
        for i in range(20):  # Assuming 10 requests per minute limit
            response = self.client.get("/api/graphs", headers=headers)
            responses.append(response)
            if response.status_code == 429:  # Rate limited
                break
        
        # Should eventually get rate limited
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        self.assertGreater(len(rate_limited_responses), 0, "Rate limiting should activate")
```

### Input Validation and Security

```python
class SecurityValidationTestMixin:
    """Mixin for input validation security testing."""
    
    def assert_rejects_sql_injection(self, request_func, param_name, *args, **kwargs):
        """Test that endpoint rejects SQL injection attempts."""
        
        sql_injection_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM admin_users",
            "'; EXEC xp_cmdshell('dir'); --"
        ]
        
        for payload in sql_injection_payloads:
            with self.subTest(payload=payload):
                kwargs_copy = kwargs.copy()
                kwargs_copy[param_name] = payload
                
                response = request_func(*args, **kwargs_copy)
                self.assertIn(
                    response.status_code, 
                    [400, 422],  # Bad Request or Unprocessable Entity
                    f"Should reject SQL injection payload: {payload}"
                )
    
    def assert_rejects_xss_attempts(self, request_func, param_name, *args, **kwargs):
        """Test that endpoint rejects XSS attempts."""
        
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//"
        ]
        
        for payload in xss_payloads:
            with self.subTest(payload=payload):
                kwargs_copy = kwargs.copy()
                kwargs_copy[param_name] = payload
                
                response = request_func(*args, **kwargs_copy)
                
                # Should either reject (400/422) or sanitize
                if response.status_code == 200:
                    response_text = response.text or ""
                    self.assertNotIn("<script>", response_text.lower())
                    self.assertNotIn("javascript:", response_text.lower())
                else:
                    self.assertIn(response.status_code, [400, 422])
    
    def assert_validates_file_uploads(self, upload_func, allowed_types, *args, **kwargs):
        """Test file upload validation."""
        
        dangerous_files = [
            ("malware.exe", b"MZ\x90\x00", "application/octet-stream"),
            ("script.php", b"<?php echo 'hello'; ?>", "text/php"),
            ("payload.js", b"alert('xss')", "application/javascript")
        ]
        
        for filename, content, content_type in dangerous_files:
            with self.subTest(filename=filename):
                # Should reject files not in allowed types
                if content_type not in allowed_types:
                    response = upload_func(filename, content, content_type, *args, **kwargs)
                    self.assertIn(response.status_code, [400, 422, 415])

class TestInputValidationSecurity(unittest.TestCase, SecurityValidationTestMixin):
    """Input validation security tests."""
    
    def test_graph_name_validation(self):
        """Test graph name input validation."""
        
        token = self.create_test_jwt_token({"permissions": ["graphs:write"]})
        headers = {"Authorization": f"Bearer {token}"}
        
        def create_graph_request(graph_name):
            return self.client.post(
                "/api/graphs",
                json={"name": graph_name, "description": "Test graph"},
                headers=headers
            )
        
        # Test SQL injection protection
        self.assert_rejects_sql_injection(create_graph_request, "graph_name")
        
        # Test XSS protection
        self.assert_rejects_xss_attempts(create_graph_request, "graph_name")
        
        # Test path traversal protection
        path_traversal_payloads = ["../../../etc/passwd", "..\\windows\\system32"]
        for payload in path_traversal_payloads:
            response = create_graph_request(payload)
            self.assertIn(response.status_code, [400, 422])
    
    def test_csv_upload_security(self):
        """Test CSV upload security validation."""
        
        def upload_csv(filename, content, content_type):
            return self.client.post(
                "/api/graphs/upload",
                files={"file": (filename, content, content_type)},
                headers=self.get_auth_headers()
            )
        
        allowed_types = ["text/csv", "application/csv"]
        self.assert_validates_file_uploads(upload_csv, allowed_types)
        
        # Test CSV bomb protection (large files)
        large_csv = "a,b,c\n" * 1000000  # 1M rows
        response = upload_csv("large.csv", large_csv.encode(), "text/csv")
        self.assertIn(response.status_code, [400, 413, 422])  # Should reject large files
```

## 🔄 Integration Testing Patterns

### Multi-Service Integration Testing

```python
class IntegrationTestBase(unittest.TestCase):
    """Base class for integration testing with real service coordination."""
    
    def setUp(self):
        """Set up integration test environment with real services."""
        
        # Use real config service with test configuration
        self.config_service = ConfigService()
        self.config_service.load_config("tests/data/integration_config.yaml")
        
        # Use real dependency injection container
        self.container = DIContainer()
        self.container.register_service("config", self.config_service)
        
        # Register real services
        self.container.register_service(
            "app_config", 
            AppConfigService(config_service=self.config_service)
        )
        
        # Mock only external dependencies (LLM, storage)
        self.mock_llm_service = MockServiceFactory.create_mock_llm_service()
        self.mock_storage_service = MockServiceFactory.create_mock_storage_service()
        
        self.container.register_service("llm", self.mock_llm_service)
        self.container.register_service("storage", self.mock_storage_service)
        
        # Real services that depend on mocked externals
        self.graph_builder = GraphBuilderService(
            app_config_service=self.container.get_service("app_config"),
            logging_service=self.container.get_service("logging")
        )
        
        self.workflow_executor = WorkflowExecutorService(
            llm_service=self.mock_llm_service,
            storage_service=self.mock_storage_service,
            app_config_service=self.container.get_service("app_config")
        )
    
    def tearDown(self):
        """Clean up integration test environment."""
        self.container.clear()

class TestEndToEndWorkflowIntegration(IntegrationTestBase):
    """End-to-end workflow integration testing."""
    
    def test_complete_csv_to_execution_flow(self):
        """Test complete flow from CSV input to workflow execution."""
        
        # Step 1: Create realistic CSV
        csv_content = self.create_realistic_workflow_csv()
        csv_file = self.create_temp_csv_file(csv_content)
        
        # Step 2: Configure LLM responses for workflow
        self.configure_llm_for_workflow()
        
        # Step 3: Build graph from CSV
        graph_result = self.graph_builder.build_graph_from_csv(csv_file)
        self.assertTrue(graph_result.success)
        self.assertIsNotNone(graph_result.graph)
        
        # Step 4: Validate graph structure
        validation_result = self.graph_builder.validate_graph(graph_result.graph)
        self.assertTrue(validation_result.is_valid)
        
        # Step 5: Execute workflow
        initial_state = {"user_request": "process customer data"}
        execution_result = self.workflow_executor.execute_workflow(
            graph_result.graph, 
            initial_state
        )
        
        # Step 6: Verify end-to-end results
        self.assertTrue(execution_result.success)
        self.assertIn("final_result", execution_result.final_state)
        
        # Step 7: Verify service coordination
        self.verify_service_interactions()
    
    def configure_llm_for_workflow(self):
        """Configure LLM mock for realistic workflow responses."""
        
        def llm_response_generator(prompt, **kwargs):
            if "analyze" in prompt.lower():
                return {"analysis": "Customer data analysis completed"}
            elif "process" in prompt.lower():
                return {"processed_data": "Processed customer information"}
            elif "format" in prompt.lower():
                return {"final_result": "Formatted customer report"}
            else:
                return {"result": "default_response"}
        
        self.mock_llm_service.process.side_effect = llm_response_generator
    
    def verify_service_interactions(self):
        """Verify proper coordination between services."""
        
        # Verify LLM was called for each processing step
        llm_calls = self.mock_llm_service.process.call_args_list
        self.assertGreaterEqual(len(llm_calls), 3)  # At least 3 processing steps
        
        # Verify storage interactions
        storage_calls = self.mock_storage_service.method_calls
        self.assertTrue(any("save" in str(call) for call in storage_calls))
        
        # Verify configuration was accessed
        config_service = self.container.get_service("app_config")
        self.assertIsInstance(config_service, AppConfigService)
```

### Cross-Service Communication Testing

```python
class TestServiceCommunication(IntegrationTestBase):
    """Test communication patterns between services."""
    
    def test_service_event_propagation(self):
        """Test event propagation between services."""
        
        # Create event-aware services
        event_manager = EventManager()
        
        publisher_service = ServiceA(event_manager=event_manager)
        subscriber_service = ServiceB(event_manager=event_manager)
        
        # Subscribe to events
        events_received = []
        
        def event_handler(event):
            events_received.append(event)
        
        event_manager.subscribe("workflow.completed", event_handler)
        
        # Trigger workflow that should generate events
        result = publisher_service.execute_workflow("test_workflow")
        
        # Verify event was propagated
        self.assertTrue(result.success)
        self.assertEqual(len(events_received), 1)
        
        event = events_received[0]
        self.assertEqual(event.type, "workflow.completed")
        self.assertIn("workflow_id", event.data)
    
    def test_service_dependency_chain(self):
        """Test complex service dependency chains."""
        
        # Create chain: ServiceA -> ServiceB -> ServiceC -> External
        service_c = ServiceC(external_api=self.mock_external_api)
        service_b = ServiceB(service_c=service_c)
        service_a = ServiceA(service_b=service_b)
        
        # Configure external API mock
        self.mock_external_api.process.return_value = {"external_result": "success"}
        
        # Execute operation that flows through all services
        result = service_a.complex_operation("test_input")
        
        # Verify result propagated through chain
        self.assertTrue(result.success)
        self.assertEqual(result.data["external_result"], "success")
        
        # Verify call chain
        self.mock_external_api.process.assert_called_once()
        self.assertIn("test_input", str(self.mock_external_api.process.call_args))
    
    def test_circular_dependency_detection(self):
        """Test detection of circular service dependencies."""
        
        # This should be caught during container setup
        container = DIContainer()
        
        with self.assertRaises(CircularDependencyError):
            container.register_service("service_a", ServiceA, depends_on=["service_b"])
            container.register_service("service_b", ServiceB, depends_on=["service_c"])
            container.register_service("service_c", ServiceC, depends_on=["service_a"])
            
            # This should trigger detection
            container.resolve_dependencies()
```

## 📊 Monitoring and Observability Testing

### Metrics and Telemetry Testing

```python
class ObservabilityTestMixin:
    """Mixin for testing monitoring and observability features."""
    
    def setUp(self):
        super().setUp()
        self.metrics_collector = MetricsCollector()
        self.trace_recorder = TraceRecorder()
    
    def assert_metric_recorded(self, metric_name, expected_value=None, tags=None):
        """Assert that a specific metric was recorded."""
        
        metrics = self.metrics_collector.get_metrics()
        matching_metrics = [m for m in metrics if m.name == metric_name]
        
        self.assertGreater(
            len(matching_metrics), 
            0, 
            f"Metric '{metric_name}' was not recorded"
        )
        
        if expected_value is not None:
            metric_values = [m.value for m in matching_metrics]
            self.assertIn(expected_value, metric_values)
        
        if tags:
            for metric in matching_metrics:
                for tag_key, tag_value in tags.items():
                    self.assertIn(tag_key, metric.tags)
                    self.assertEqual(metric.tags[tag_key], tag_value)
    
    def assert_trace_recorded(self, operation_name, min_duration=None, max_duration=None):
        """Assert that a trace was recorded for an operation."""
        
        traces = self.trace_recorder.get_traces()
        matching_traces = [t for t in traces if t.operation_name == operation_name]
        
        self.assertGreater(
            len(matching_traces),
            0,
            f"No trace recorded for operation '{operation_name}'"
        )
        
        if min_duration or max_duration:
            for trace in matching_traces:
                if min_duration:
                    self.assertGreaterEqual(trace.duration, min_duration)
                if max_duration:
                    self.assertLessEqual(trace.duration, max_duration)

class TestServiceObservability(unittest.TestCase, ObservabilityTestMixin):
    """Test observability features of services."""
    
    def test_request_metrics_collection(self):
        """Test that request metrics are properly collected."""
        
        # Execute operations that should generate metrics
        self.service.process_request("test_input")
        self.service.process_batch_request(["input1", "input2", "input3"])
        
        # Verify metrics were recorded
        self.assert_metric_recorded("requests.processed", expected_value=1)
        self.assert_metric_recorded("batch_requests.processed", expected_value=1)
        self.assert_metric_recorded("items.processed", expected_value=3)
        
        # Verify metric tags
        self.assert_metric_recorded(
            "requests.processed",
            tags={"service": "MyService", "operation": "process_request"}
        )
    
    def test_error_metrics_collection(self):
        """Test that error metrics are collected appropriately."""
        
        # Configure service to fail
        self.mock_dependency.process.side_effect = Exception("Test error")
        
        # Execute operation that should fail
        with self.assertRaises(Exception):
            self.service.process_request("failing_input")
        
        # Verify error metrics
        self.assert_metric_recorded("requests.failed", expected_value=1)
        self.assert_metric_recorded(
            "errors.by_type",
            tags={"error_type": "Exception", "service": "MyService"}
        )
    
    def test_performance_tracing(self):
        """Test that performance traces are recorded."""
        
        # Execute operation with tracing
        with self.trace_recorder.trace("test_operation"):
            result = self.service.complex_operation("test_input")
        
        # Verify trace was recorded
        self.assert_trace_recorded("test_operation", min_duration=0.001)
        
        # Verify nested traces
        self.assert_trace_recorded("complex_operation.step1")
        self.assert_trace_recorded("complex_operation.step2")
    
    def test_custom_metrics_integration(self):
        """Test integration with custom business metrics."""
        
        # Execute business operations
        self.service.process_customer_data({"customer_id": "123", "action": "purchase"})
        self.service.process_customer_data({"customer_id": "456", "action": "refund"})
        
        # Verify business metrics
        self.assert_metric_recorded("customer.actions", expected_value=2)
        self.assert_metric_recorded(
            "customer.actions.by_type",
            tags={"action_type": "purchase"}
        )
        self.assert_metric_recorded(
            "customer.actions.by_type", 
            tags={"action_type": "refund"}
        )
```

## 🎯 Test Execution and Automation

### Test Suite Organization

```python
# tests/conftest.py - Pytest configuration for advanced patterns

import pytest
from unittest.mock import Mock
from tests.utils.test_categories import TestCategory
from tests.utils.performance_markers import PerformanceTest
from tests.utils.integration_markers import IntegrationTest

def pytest_configure(config):
    """Configure pytest with custom markers."""
    
    config.addinivalue_line("markers", "unit: Unit tests with mocked dependencies")
    config.addinivalue_line("markers", "integration: Integration tests with real services")
    config.addinivalue_line("markers", "performance: Performance and load tests")
    config.addinivalue_line("markers", "security: Security validation tests")
    config.addinivalue_line("markers", "slow: Tests that take longer than 5 seconds")

@pytest.fixture(scope="session")
def test_database():
    """Provide test database for integration tests."""
    
    # Set up test database
    db = create_test_database()
    yield db
    
    # Clean up
    db.drop_all_tables()
    db.close()

@pytest.fixture(scope="function")
def isolated_container():
    """Provide isolated DI container for each test."""
    
    container = DIContainer()
    yield container
    container.clear()

# Example test categorization
@pytest.mark.unit
@pytest.mark.fast
class TestUnitPatterns:
    """Fast unit tests with full mocking."""
    pass

@pytest.mark.integration
@pytest.mark.slow
class TestIntegrationPatterns:
    """Integration tests with real service coordination."""
    pass

@pytest.mark.performance
@pytest.mark.slow
class TestPerformancePatterns:
    """Performance and load testing."""
    pass

@pytest.mark.security
class TestSecurityPatterns:
    """Security validation tests."""
    pass
```

### Continuous Integration Patterns

```yaml
# .github/workflows/testing-advanced.yml
name: Advanced Testing Pipeline

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install poetry
        poetry install --with dev
    
    - name: Run unit tests
      run: |
        poetry run pytest tests/ -m "unit and not slow" \
          --cov=agentmap --cov-report=xml \
          --junit-xml=junit-unit.xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
  
  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: 3.11
    
    - name: Run integration tests
      run: |
        poetry run pytest tests/ -m "integration" \
          --junit-xml=junit-integration.xml
  
  performance-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: 3.11
    
    - name: Run performance tests
      run: |
        poetry run pytest tests/ -m "performance" \
          --junit-xml=junit-performance.xml \
          --benchmark-json=benchmark.json
    
    - name: Store benchmark results
      uses: benchmark-action/github-action-benchmark@v1
      with:
        tool: 'pytest'
        output-file-path: benchmark.json
        github-token: ${{ secrets.GITHUB_TOKEN }}
  
  security-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: 3.11
    
    - name: Run security tests
      run: |
        poetry run pytest tests/ -m "security" \
          --junit-xml=junit-security.xml
    
    - name: Run security scan
      run: |
        poetry run bandit -r src/ -f json -o bandit-report.json
    
    - name: Upload security results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: bandit-report.json
```

## 📚 Related Documentation

- **[Quick Reference](/docs/testing/quick-reference)** - Essential patterns and standards
- **[Comprehensive Guide](/docs/testing/comprehensive-guide)** - Detailed examples and workflows
- **[Troubleshooting](/docs/testing/troubleshooting)** - Debugging test issues

---

**For Complex Testing Scenarios:** These advanced patterns provide robust testing strategies for performance, security, integration, and specialized requirements in AgentMap applications.
