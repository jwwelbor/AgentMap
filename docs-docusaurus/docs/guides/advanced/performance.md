---
sidebar_position: 3
title: Performance Optimization
description: Comprehensive performance optimization guide for AgentMap deployments including caching strategies, parallel processing, and monitoring techniques.
keywords: [AgentMap performance, optimization, caching, parallel processing, monitoring, scalability, performance tuning]
---

# Performance Optimization Guide

Optimizing AgentMap performance is crucial for production deployments and large-scale agent workflows. This guide covers comprehensive strategies for improving throughput, reducing latency, and scaling agent systems effectively.

## Performance Monitoring and Metrics

### 1. Performance Monitoring Agent

```python
import time
import psutil
import threading
from datetime import datetime
from typing import Dict, Any, List
import statistics
from collections import defaultdict, deque

class PerformanceMonitoringAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.metrics = defaultdict(list)
        self.system_metrics = defaultdict(deque)
        self.max_metric_history = 1000
        self.monitoring_active = False
        self.monitor_thread = None
        self.start_monitoring()
    
    def start_monitoring(self):
        """Start system monitoring in background thread"""
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_system_metrics)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_system_metrics(self):
        """Monitor system metrics continuously"""
        while self.monitoring_active:
            try:
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                self.record_metric('system.cpu_percent', cpu_percent)
                
                # Memory metrics
                memory = psutil.virtual_memory()
                self.record_metric('system.memory_percent', memory.percent)
                self.record_metric('system.memory_available', memory.available)
                
                # Disk I/O metrics
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    self.record_metric('system.disk_read_bytes', disk_io.read_bytes)
                    self.record_metric('system.disk_write_bytes', disk_io.write_bytes)
                
                # Network I/O metrics
                network_io = psutil.net_io_counters()
                if network_io:
                    self.record_metric('system.network_sent_bytes', network_io.bytes_sent)
                    self.record_metric('system.network_recv_bytes', network_io.bytes_recv)
                
                time.sleep(5)  # Monitor every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error monitoring system metrics: {str(e)}")
                time.sleep(10)  # Wait longer on error
    
    def record_metric(self, metric_name: str, value: float, timestamp: datetime = None):
        """Record a performance metric"""
        if timestamp is None:
            timestamp = datetime.now()
        
        metric_entry = {
            'value': value,
            'timestamp': timestamp.isoformat()
        }
        
        # Store in appropriate collection
        if metric_name.startswith('system.'):
            self.system_metrics[metric_name].append(metric_entry)
            # Keep only recent entries
            if len(self.system_metrics[metric_name]) > self.max_metric_history:
                self.system_metrics[metric_name].popleft()
        else:
            self.metrics[metric_name].append(metric_entry)
            # Keep only recent entries
            if len(self.metrics[metric_name]) > self.max_metric_history:
                self.metrics[metric_name].pop(0)
    
    def execute(self, input_data, context=None):
        """Execute performance monitoring operations"""
        
        operation = context.get('operation', 'get_metrics')
        
        if operation == 'get_metrics':
            return self.get_performance_metrics(context)
        elif operation == 'get_summary':
            return self.get_performance_summary(context)
        elif operation == 'reset_metrics':
            return self.reset_metrics()
        elif operation == 'benchmark':
            return self.run_benchmark(input_data, context)
        else:
            return {'error': f'Unknown operation: {operation}'}
    
    def get_performance_metrics(self, context: Dict) -> Dict:
        """Get current performance metrics"""
        
        metric_names = context.get('metrics', list(self.metrics.keys()) + list(self.system_metrics.keys()))
        time_range = context.get('time_range_minutes', 60)
        
        cutoff_time = datetime.now() - timedelta(minutes=time_range)
        result = {}
        
        for metric_name in metric_names:
            if metric_name in self.metrics:
                metric_data = self.metrics[metric_name]
            elif metric_name in self.system_metrics:
                metric_data = list(self.system_metrics[metric_name])
            else:
                continue
            
            # Filter by time range
            filtered_data = [
                entry for entry in metric_data
                if datetime.fromisoformat(entry['timestamp']) >= cutoff_time
            ]
            
            if filtered_data:
                values = [entry['value'] for entry in filtered_data]
                result[metric_name] = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'mean': statistics.mean(values),
                    'median': statistics.median(values),
                    'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                    'recent_value': values[-1],
                    'trend': self.calculate_trend(values)
                }
        
        return {
            'metrics': result,
            'time_range_minutes': time_range,
            'generated_at': datetime.now().isoformat()
        }
    
    def get_performance_summary(self, context: Dict) -> Dict:
        """Get performance summary with recommendations"""
        
        metrics = self.get_performance_metrics(context)['metrics']
        
        # Analyze performance issues
        issues = []
        recommendations = []
        
        # CPU analysis
        if 'system.cpu_percent' in metrics:
            cpu_avg = metrics['system.cpu_percent']['mean']
            if cpu_avg > 80:
                issues.append(f"High CPU usage: {cpu_avg:.1f}%")
                recommendations.append("Consider scaling horizontally or optimizing CPU-intensive operations")
        
        # Memory analysis
        if 'system.memory_percent' in metrics:
            memory_avg = metrics['system.memory_percent']['mean']
            if memory_avg > 85:
                issues.append(f"High memory usage: {memory_avg:.1f}%")
                recommendations.append("Implement memory optimization strategies or increase available memory")
        
        # Agent performance analysis
        agent_latency_metrics = [m for m in metrics if 'latency' in m.lower()]
        high_latency_agents = []
        
        for metric_name in agent_latency_metrics:
            avg_latency = metrics[metric_name]['mean']
            if avg_latency > 5.0:  # 5 seconds threshold
                high_latency_agents.append((metric_name, avg_latency))
        
        if high_latency_agents:
            issues.append(f"High latency agents: {len(high_latency_agents)}")
            recommendations.append("Optimize slow agents or implement caching")
        
        # Calculate overall health score
        health_score = self.calculate_health_score(metrics)
        
        return {
            'health_score': health_score,
            'status': 'healthy' if health_score > 80 else 'needs_attention' if health_score > 60 else 'critical',
            'issues': issues,
            'recommendations': recommendations,
            'metrics_summary': {
                'total_metrics': len(metrics),
                'time_period': context.get('time_range_minutes', 60)
            }
        }
    
    def calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for metric values"""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear trend calculation
        n = len(values)
        x = list(range(n))
        
        # Calculate correlation coefficient
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        x_var = sum((x[i] - x_mean) ** 2 for i in range(n))
        y_var = sum((values[i] - y_mean) ** 2 for i in range(n))
        
        if x_var == 0 or y_var == 0:
            return 'stable'
        
        correlation = numerator / (x_var * y_var) ** 0.5
        
        if correlation > 0.3:
            return 'increasing'
        elif correlation < -0.3:
            return 'decreasing'
        else:
            return 'stable'
    
    def calculate_health_score(self, metrics: Dict) -> float:
        """Calculate overall system health score (0-100)"""
        
        score = 100.0
        
        # CPU health
        if 'system.cpu_percent' in metrics:
            cpu_avg = metrics['system.cpu_percent']['mean']
            if cpu_avg > 90:
                score -= 20
            elif cpu_avg > 80:
                score -= 10
            elif cpu_avg > 70:
                score -= 5
        
        # Memory health
        if 'system.memory_percent' in metrics:
            memory_avg = metrics['system.memory_percent']['mean']
            if memory_avg > 95:
                score -= 20
            elif memory_avg > 85:
                score -= 10
            elif memory_avg > 75:
                score -= 5
        
        # Agent performance health
        agent_metrics = [m for m in metrics if not m.startswith('system.')]
        if agent_metrics:
            high_latency_count = sum(
                1 for metric_name in agent_metrics
                if 'latency' in metric_name.lower() and metrics[metric_name]['mean'] > 5.0
            )
            
            if high_latency_count > 0:
                score -= min(high_latency_count * 5, 15)
        
        return max(score, 0.0)
    
    def run_benchmark(self, input_data: Dict, context: Dict) -> Dict:
        """Run performance benchmark"""
        
        benchmark_type = context.get('benchmark_type', 'simple')
        iterations = context.get('iterations', 100)
        
        if benchmark_type == 'simple':
            return self.run_simple_benchmark(iterations)
        elif benchmark_type == 'agent_execution':
            return self.run_agent_benchmark(input_data, iterations)
        elif benchmark_type == 'memory':
            return self.run_memory_benchmark(iterations)
        else:
            return {'error': f'Unknown benchmark type: {benchmark_type}'}
    
    def run_simple_benchmark(self, iterations: int) -> Dict:
        """Run simple CPU benchmark"""
        
        start_time = time.time()
        
        # Simple computation benchmark
        total = 0
        for i in range(iterations * 1000):
            total += i * i
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'benchmark_type': 'simple_cpu',
            'iterations': iterations * 1000,
            'duration_seconds': duration,
            'operations_per_second': (iterations * 1000) / duration,
            'result': total
        }

def performance_decorator(metric_name: str = None):
    """Decorator to measure agent execution performance"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get metric name
            actual_metric_name = metric_name or f"{self.__class__.__name__}.{func.__name__}"
            
            # Record start metrics
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss
            
            try:
                # Execute function
                result = func(self, *args, **kwargs)
                
                # Record success metrics
                end_time = time.time()
                end_memory = psutil.Process().memory_info().rss
                
                execution_time = end_time - start_time
                memory_delta = end_memory - start_memory
                
                # Record metrics if monitoring agent is available
                if hasattr(self, 'performance_monitor'):
                    self.performance_monitor.record_metric(f"{actual_metric_name}.latency", execution_time)
                    self.performance_monitor.record_metric(f"{actual_metric_name}.memory_delta", memory_delta)
                    self.performance_monitor.record_metric(f"{actual_metric_name}.success", 1)
                
                return result
                
            except Exception as e:
                # Record failure metrics
                end_time = time.time()
                execution_time = end_time - start_time
                
                if hasattr(self, 'performance_monitor'):
                    self.performance_monitor.record_metric(f"{actual_metric_name}.latency", execution_time)
                    self.performance_monitor.record_metric(f"{actual_metric_name}.failure", 1)
                
                raise
        
        return wrapper
    return decorator
```

### 2. Caching Strategies

```python
import hashlib
import pickle
import redis
from functools import wraps
from typing import Any, Optional, Callable
import json

class MultiLevelCacheManager:
    def __init__(self):
        self.memory_cache = {}
        self.memory_cache_size = 1000
        self.memory_access_order = []
        
        # Redis cache (if available)
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=int(os.getenv('REDIS_DB', 0)),
                decode_responses=True
            )
            self.redis_available = True
            # Test connection
            self.redis_client.ping()
        except:
            self.redis_available = False
            self.redis_client = None
    
    def generate_cache_key(self, *args, **kwargs) -> str:
        """Generate deterministic cache key from arguments"""
        
        # Create deterministic representation
        cache_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        
        # Serialize and hash
        cache_str = json.dumps(cache_data, sort_keys=True, default=str)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (try memory first, then Redis)"""
        
        # Try memory cache first
        if key in self.memory_cache:
            # Update access order
            if key in self.memory_access_order:
                self.memory_access_order.remove(key)
            self.memory_access_order.append(key)
            
            return self.memory_cache[key]
        
        # Try Redis cache
        if self.redis_available:
            try:
                redis_value = self.redis_client.get(key)
                if redis_value is not None:
                    # Deserialize and store in memory cache
                    value = pickle.loads(redis_value.encode('latin1'))
                    self.set_memory_cache(key, value)
                    return value
            except Exception as e:
                self.logger.warning(f"Redis cache error: {str(e)}")
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache (both memory and Redis)"""
        
        # Set in memory cache
        self.set_memory_cache(key, value)
        
        # Set in Redis cache
        if self.redis_available:
            try:
                serialized_value = pickle.dumps(value).decode('latin1')
                self.redis_client.setex(key, ttl, serialized_value)
            except Exception as e:
                self.logger.warning(f"Redis cache set error: {str(e)}")
    
    def set_memory_cache(self, key: str, value: Any):
        """Set value in memory cache with LRU eviction"""
        
        # Remove oldest entries if cache is full
        while len(self.memory_cache) >= self.memory_cache_size:
            oldest_key = self.memory_access_order.pop(0)
            del self.memory_cache[oldest_key]
        
        # Add new entry
        self.memory_cache[key] = value
        
        # Update access order
        if key in self.memory_access_order:
            self.memory_access_order.remove(key)
        self.memory_access_order.append(key)
    
    def delete(self, key: str):
        """Delete value from all cache levels"""
        
        # Remove from memory cache
        if key in self.memory_cache:
            del self.memory_cache[key]
            if key in self.memory_access_order:
                self.memory_access_order.remove(key)
        
        # Remove from Redis cache
        if self.redis_available:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                self.logger.warning(f"Redis cache delete error: {str(e)}")
    
    def clear(self):
        """Clear all cache levels"""
        
        self.memory_cache.clear()
        self.memory_access_order.clear()
        
        if self.redis_available:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                self.logger.warning(f"Redis cache clear error: {str(e)}")

class CachingAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.cache_manager = MultiLevelCacheManager()
        self.cache_config = {
            'enabled': True,
            'default_ttl': 3600,  # 1 hour
            'max_cache_size': 1000,
            'cache_strategies': {
                'aggressive': {'ttl': 7200, 'enabled': True},
                'moderate': {'ttl': 3600, 'enabled': True},
                'conservative': {'ttl': 900, 'enabled': True}
            }
        }
    
    def execute(self, input_data, context=None):
        """Execute with intelligent caching"""
        
        if not self.cache_config['enabled']:
            return self.process_without_cache(input_data, context)
        
        # Generate cache key
        cache_strategy = context.get('cache_strategy', 'moderate')
        cache_key = self.generate_execution_cache_key(input_data, context)
        
        # Try to get from cache
        cached_result = self.cache_manager.get(cache_key)
        
        if cached_result is not None:
            # Cache hit
            self.record_cache_hit(cache_key)
            cached_result['_cache_hit'] = True
            cached_result['_cache_key'] = cache_key
            return cached_result
        
        # Cache miss - execute and cache result
        self.record_cache_miss(cache_key)
        result = self.process_without_cache(input_data, context)
        
        # Cache the result
        strategy_config = self.cache_config['cache_strategies'].get(cache_strategy, {})
        ttl = strategy_config.get('ttl', self.cache_config['default_ttl'])
        
        if strategy_config.get('enabled', True):
            # Add cache metadata
            result['_cache_hit'] = False
            result['_cache_key'] = cache_key
            result['_cached_at'] = datetime.now().isoformat()
            
            self.cache_manager.set(cache_key, result, ttl)
        
        return result
    
    def generate_execution_cache_key(self, input_data: Any, context: Dict) -> str:
        """Generate cache key for execution"""
        
        # Include relevant context items (exclude non-deterministic items)
        cache_context = {}
        
        cache_relevant_keys = [
            'agent_type', 'model', 'temperature', 'max_tokens',
            'processing_mode', 'validation_rules'
        ]
        
        for key in cache_relevant_keys:
            if key in context:
                cache_context[key] = context[key]
        
        # Create cache key
        return self.cache_manager.generate_cache_key(
            self.__class__.__name__,
            input_data,
            cache_context
        )
    
    def process_without_cache(self, input_data: Any, context: Dict) -> Dict:
        """Process data without caching - override in subclasses"""
        
        # Default implementation
        return {
            'processed_data': f"Processed: {input_data}",
            'processing_time': 0.1,
            'agent': self.__class__.__name__
        }
    
    def record_cache_hit(self, cache_key: str):
        """Record cache hit for monitoring"""
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.record_metric('cache.hits', 1)
    
    def record_cache_miss(self, cache_key: str):
        """Record cache miss for monitoring"""
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.record_metric('cache.misses', 1)

def cache_result(ttl: int = 3600, cache_key_func: Callable = None, strategy: str = 'moderate'):
    """Decorator for caching method results"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Check if caching is enabled
            if not getattr(self, 'cache_manager', None):
                return func(self, *args, **kwargs)
            
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(self, *args, **kwargs)
            else:
                cache_key = self.cache_manager.generate_cache_key(
                    func.__name__, args, kwargs
                )
            
            # Try to get from cache
            cached_result = self.cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(self, *args, **kwargs)
            self.cache_manager.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator
```

### 3. Parallel Processing Optimization

```python
import concurrent.futures
import asyncio
import multiprocessing
from typing import List, Callable, Any, Dict
import queue
import threading

class ParallelProcessingManager:
    def __init__(self):
        self.cpu_count = multiprocessing.cpu_count()
        self.optimal_thread_count = min(self.cpu_count * 2, 32)
        self.optimal_process_count = self.cpu_count
        
    def execute_parallel_tasks(self, tasks: List[Dict], execution_mode: str = 'auto') -> List[Dict]:
        """Execute tasks in parallel using optimal strategy"""
        
        if execution_mode == 'auto':
            execution_mode = self.determine_optimal_mode(tasks)
        
        if execution_mode == 'threads':
            return self.execute_with_threads(tasks)
        elif execution_mode == 'processes':
            return self.execute_with_processes(tasks)
        elif execution_mode == 'asyncio':
            return asyncio.run(self.execute_with_asyncio(tasks))
        else:
            return self.execute_sequential(tasks)
    
    def determine_optimal_mode(self, tasks: List[Dict]) -> str:
        """Determine optimal execution mode based on task characteristics"""
        
        if len(tasks) == 1:
            return 'sequential'
        
        # Analyze task characteristics
        io_bound_count = 0
        cpu_bound_count = 0
        
        for task in tasks:
            task_type = task.get('type', 'unknown')
            if task_type in ['api_call', 'file_read', 'database_query']:
                io_bound_count += 1
            elif task_type in ['computation', 'data_processing', 'analysis']:
                cpu_bound_count += 1
        
        # Decision logic
        if io_bound_count > cpu_bound_count and len(tasks) <= 100:
            return 'asyncio'
        elif cpu_bound_count > io_bound_count and len(tasks) <= self.optimal_process_count * 2:
            return 'processes'
        elif len(tasks) <= self.optimal_thread_count * 2:
            return 'threads'
        else:
            return 'threads'  # Default for mixed workloads
    
    def execute_with_threads(self, tasks: List[Dict]) -> List[Dict]:
        """Execute tasks using thread pool"""
        
        results = [None] * len(tasks)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.optimal_thread_count) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self.execute_single_task, task): i
                for i, task in enumerate(tasks)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    results[index] = {'error': str(e), 'task_index': index}
        
        return results
    
    def execute_with_processes(self, tasks: List[Dict]) -> List[Dict]:
        """Execute tasks using process pool"""
        
        results = [None] * len(tasks)
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.optimal_process_count) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(execute_task_static, task): i
                for i, task in enumerate(tasks)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    results[index] = {'error': str(e), 'task_index': index}
        
        return results
    
    async def execute_with_asyncio(self, tasks: List[Dict]) -> List[Dict]:
        """Execute tasks using asyncio"""
        
        semaphore = asyncio.Semaphore(self.optimal_thread_count)
        
        async def execute_task_async(task: Dict, index: int) -> Dict:
            async with semaphore:
                try:
                    # Simulate async execution
                    await asyncio.sleep(0.01)  # Small delay to yield control
                    return self.execute_single_task(task)
                except Exception as e:
                    return {'error': str(e), 'task_index': index}
        
        # Execute all tasks concurrently
        coroutines = [execute_task_async(task, i) for i, task in enumerate(tasks)]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({'error': str(result), 'task_index': i})
            else:
                processed_results.append(result)
        
        return processed_results
    
    def execute_sequential(self, tasks: List[Dict]) -> List[Dict]:
        """Execute tasks sequentially"""
        
        results = []
        for i, task in enumerate(tasks):
            try:
                result = self.execute_single_task(task)
                results.append(result)
            except Exception as e:
                results.append({'error': str(e), 'task_index': i})
        
        return results
    
    def execute_single_task(self, task: Dict) -> Dict:
        """Execute a single task - override in subclasses"""
        
        task_type = task.get('type', 'generic')
        data = task.get('data')
        
        # Simulate task execution
        if task_type == 'computation':
            # CPU-bound task simulation
            result = sum(i * i for i in range(1000))
            return {'result': result, 'type': task_type}
        
        elif task_type == 'api_call':
            # I/O-bound task simulation
            time.sleep(0.1)  # Simulate API call delay
            return {'result': f"API response for {data}", 'type': task_type}
        
        else:
            return {'result': f"Processed {data}", 'type': task_type}

class HighPerformanceAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.parallel_manager = ParallelProcessingManager()
        self.performance_monitor = PerformanceMonitoringAgent()
        self.cache_manager = MultiLevelCacheManager()
        
    @performance_decorator('high_performance_agent.execute')
    def execute(self, input_data, context=None):
        """High-performance execution with optimization strategies"""
        
        # Determine processing strategy
        processing_strategy = context.get('processing_strategy', 'auto')
        
        if isinstance(input_data, list) and len(input_data) > 1:
            return self.execute_batch(input_data, context)
        else:
            return self.execute_single(input_data, context)
    
    def execute_batch(self, input_list: List, context: Dict) -> Dict:
        """Execute batch processing with parallel optimization"""
        
        batch_size = context.get('batch_size', 'auto')
        parallel_mode = context.get('parallel_mode', 'auto')
        
        # Determine optimal batch size
        if batch_size == 'auto':
            batch_size = self.calculate_optimal_batch_size(len(input_list), context)
        
        # Create tasks
        tasks = []
        for i, item in enumerate(input_list):
            tasks.append({
                'type': context.get('task_type', 'data_processing'),
                'data': item,
                'index': i,
                'context': context
            })
        
        # Execute in parallel
        start_time = time.time()
        results = self.parallel_manager.execute_parallel_tasks(tasks, parallel_mode)
        execution_time = time.time() - start_time
        
        # Process results
        successful_results = [r for r in results if 'error' not in r]
        failed_results = [r for r in results if 'error' in r]
        
        return {
            'total_items': len(input_list),
            'successful_items': len(successful_results),
            'failed_items': len(failed_results),
            'execution_time': execution_time,
            'throughput': len(input_list) / execution_time,
            'results': successful_results,
            'errors': failed_results,
            'parallel_mode': parallel_mode,
            'batch_size': batch_size
        }
    
    def execute_single(self, input_data: Any, context: Dict) -> Dict:
        """Execute single item with caching optimization"""
        
        # Check cache first
        cache_enabled = context.get('cache_enabled', True)
        
        if cache_enabled:
            cache_key = self.cache_manager.generate_cache_key(
                'single_execution', input_data, context
            )
            
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                cached_result['_cache_hit'] = True
                return cached_result
        
        # Execute
        start_time = time.time()
        result = self.process_single_item(input_data, context)
        execution_time = time.time() - start_time
        
        # Add metadata
        result.update({
            'execution_time': execution_time,
            '_cache_hit': False,
            'processed_at': datetime.now().isoformat()
        })
        
        # Cache result
        if cache_enabled:
            ttl = context.get('cache_ttl', 3600)
            self.cache_manager.set(cache_key, result, ttl)
        
        return result
    
    def calculate_optimal_batch_size(self, total_items: int, context: Dict) -> int:
        """Calculate optimal batch size based on system resources"""
        
        cpu_count = multiprocessing.cpu_count()
        available_memory = psutil.virtual_memory().available
        
        # Base batch size on CPU cores
        base_batch_size = cpu_count * 2
        
        # Adjust for memory constraints
        estimated_memory_per_item = context.get('estimated_memory_per_item', 1024 * 1024)  # 1MB default
        max_batch_size_by_memory = available_memory // (estimated_memory_per_item * 2)  # Use half available memory
        
        # Adjust for total items
        if total_items < base_batch_size:
            return total_items
        
        optimal_batch_size = min(base_batch_size, max_batch_size_by_memory, total_items // cpu_count)
        
        return max(optimal_batch_size, 1)
    
    def process_single_item(self, item: Any, context: Dict) -> Dict:
        """Process single item - override in subclasses"""
        
        # Default implementation
        processing_delay = context.get('processing_delay', 0.01)
        time.sleep(processing_delay)
        
        return {
            'processed_data': f"High-performance processed: {item}",
            'item_size': len(str(item)),
            'processing_mode': 'optimized'
        }

# Static function for process pool
def execute_task_static(task: Dict) -> Dict:
    """Static function for process pool execution"""
    
    try:
        task_type = task.get('type', 'generic')
        data = task.get('data')
        
        if task_type == 'computation':
            # CPU-bound processing
            result = sum(i * i for i in range(1000))
            return {'result': result, 'type': task_type, 'data': data}
        
        elif task_type == 'data_processing':
            # Data processing
            if isinstance(data, str):
                processed = data.upper()
            elif isinstance(data, (int, float)):
                processed = data * 2
            else:
                processed = str(data)
            
            return {'result': processed, 'type': task_type, 'original_data': data}
        
        else:
            return {'result': f"Processed {data}", 'type': task_type}
    
    except Exception as e:
        return {'error': str(e), 'task': task}
```

### 4. Memory Optimization

```python
import gc
import weakref
from memory_profiler import profile
import tracemalloc

class MemoryOptimizedAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.memory_threshold = 1024 * 1024 * 1024  # 1GB
        self.cleanup_interval = 100  # operations
        self.operation_count = 0
        self.weak_references = weakref.WeakSet()
        
    def execute(self, input_data, context=None):
        """Memory-optimized execution"""
        
        # Start memory tracking
        if context and context.get('track_memory', False):
            tracemalloc.start()
        
        try:
            # Process data with memory optimization
            result = self.process_with_memory_optimization(input_data, context)
            
            # Periodic cleanup
            self.operation_count += 1
            if self.operation_count % self.cleanup_interval == 0:
                self.perform_memory_cleanup()
            
            return result
            
        finally:
            # Stop memory tracking and get stats
            if context and context.get('track_memory', False):
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                
                if 'result' in locals():
                    result['memory_stats'] = {
                        'current_memory': current,
                        'peak_memory': peak,
                        'memory_mb': peak / 1024 / 1024
                    }
    
    def process_with_memory_optimization(self, input_data: Any, context: Dict) -> Dict:
        """Process data with memory optimization strategies"""
        
        # Use generators for large datasets
        if isinstance(input_data, list) and len(input_data) > 1000:
            return self.process_large_dataset_streaming(input_data, context)
        
        # Use chunking for medium datasets
        elif isinstance(input_data, list) and len(input_data) > 100:
            return self.process_dataset_chunked(input_data, context)
        
        # Direct processing for small datasets
        else:
            return self.process_dataset_direct(input_data, context)
    
    def process_large_dataset_streaming(self, data_list: List, context: Dict) -> Dict:
        """Process large dataset using streaming/generator approach"""
        
        chunk_size = context.get('chunk_size', 100)
        
        def data_generator():
            for i in range(0, len(data_list), chunk_size):
                yield data_list[i:i + chunk_size]
        
        processed_count = 0
        total_size = 0
        
        for chunk in data_generator():
            # Process chunk
            chunk_result = self.process_chunk_memory_efficient(chunk)
            processed_count += len(chunk)
            total_size += chunk_result.get('size', 0)
            
            # Force garbage collection after each chunk
            gc.collect()
        
        return {
            'processed_count': processed_count,
            'total_size': total_size,
            'processing_mode': 'streaming',
            'chunks_processed': (len(data_list) + chunk_size - 1) // chunk_size
        }
    
    def process_dataset_chunked(self, data_list: List, context: Dict) -> Dict:
        """Process dataset in memory-efficient chunks"""
        
        chunk_size = context.get('chunk_size', 50)
        chunks = [data_list[i:i + chunk_size] for i in range(0, len(data_list), chunk_size)]
        
        results = []
        memory_usage = []
        
        for i, chunk in enumerate(chunks):
            # Monitor memory before processing
            process = psutil.Process()
            memory_before = process.memory_info().rss
            
            # Process chunk
            chunk_result = self.process_chunk_memory_efficient(chunk)
            results.append(chunk_result)
            
            # Monitor memory after processing
            memory_after = process.memory_info().rss
            memory_usage.append({
                'chunk': i,
                'memory_before': memory_before,
                'memory_after': memory_after,
                'memory_delta': memory_after - memory_before
            })
            
            # Cleanup between chunks
            del chunk_result
            gc.collect()
        
        return {
            'total_chunks': len(chunks),
            'results': results,
            'memory_usage': memory_usage,
            'processing_mode': 'chunked'
        }
    
    def process_dataset_direct(self, data: Any, context: Dict) -> Dict:
        """Process small dataset directly"""
        
        if isinstance(data, list):
            processed_items = []
            for item in data:
                processed_item = self.process_single_item_efficient(item)
                processed_items.append(processed_item)
            
            return {
                'processed_items': processed_items,
                'processing_mode': 'direct',
                'item_count': len(data)
            }
        else:
            processed_item = self.process_single_item_efficient(data)
            return {
                'processed_item': processed_item,
                'processing_mode': 'direct'
            }
    
    def process_chunk_memory_efficient(self, chunk: List) -> Dict:
        """Process chunk with memory efficiency"""
        
        # Use list comprehension instead of loops where possible
        processed_data = [self.process_single_item_efficient(item) for item in chunk]
        
        # Calculate chunk statistics
        chunk_size = len(chunk)
        processed_size = sum(len(str(item)) for item in processed_data)
        
        return {
            'size': processed_size,
            'count': chunk_size,
            'data': processed_data
        }
    
    def process_single_item_efficient(self, item: Any) -> str:
        """Process single item with memory efficiency"""
        
        # Efficient string operations
        if isinstance(item, str):
            return item.strip().upper()
        elif isinstance(item, (int, float)):
            return str(item * 2)
        else:
            return str(item)
    
    def perform_memory_cleanup(self):
        """Perform periodic memory cleanup"""
        
        # Force garbage collection
        collected = gc.collect()
        
        # Check memory usage
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # Log memory status
        self.logger.info(f"Memory cleanup: collected {collected} objects, "
                        f"current memory: {memory_info.rss / 1024 / 1024:.1f} MB")
        
        # Aggressive cleanup if memory usage is high
        if memory_info.rss > self.memory_threshold:
            self.aggressive_memory_cleanup()
    
    def aggressive_memory_cleanup(self):
        """Perform aggressive memory cleanup"""
        
        # Clear weak references
        self.weak_references.clear()
        
        # Clear any local caches
        if hasattr(self, '_local_cache'):
            self._local_cache.clear()
        
        # Multiple garbage collection passes
        for _ in range(3):
            gc.collect()
        
        self.logger.warning("Performed aggressive memory cleanup due to high memory usage")

class MemoryProfiledAgent(BaseAgent):
    """Agent with built-in memory profiling"""
    
    def __init__(self, services=None):
        super().__init__(services)
        self.memory_profiles = []
    
    @profile
    def execute(self, input_data, context=None):
        """Execute with memory profiling"""
        
        # Start memory tracking
        tracemalloc.start()
        
        try:
            result = self.process_data(input_data, context)
            
            # Get memory statistics
            current, peak = tracemalloc.get_traced_memory()
            
            memory_profile = {
                'timestamp': datetime.now().isoformat(),
                'current_memory': current,
                'peak_memory': peak,
                'memory_mb': peak / 1024 / 1024,
                'input_size': len(str(input_data))
            }
            
            self.memory_profiles.append(memory_profile)
            
            # Keep only recent profiles
            if len(self.memory_profiles) > 100:
                self.memory_profiles = self.memory_profiles[-50:]
            
            result['memory_profile'] = memory_profile
            
            return result
            
        finally:
            tracemalloc.stop()
    
    def process_data(self, data: Any, context: Dict) -> Dict:
        """Process data - override in subclasses"""
        
        # Example memory-intensive operation
        if isinstance(data, list):
            # Create temporary large data structure
            temp_data = [str(item) * 100 for item in data]  # Expand data
            
            # Process
            result = [item.upper() for item in temp_data]
            
            # Clean up temporary data
            del temp_data
            
            return {'processed_data': result[:10]}  # Return only first 10 items
        else:
            return {'processed_data': str(data).upper()}
    
    def get_memory_analysis(self) -> Dict:
        """Get memory usage analysis"""
        
        if not self.memory_profiles:
            return {'error': 'No memory profiles available'}
        
        peak_memories = [p['peak_memory'] for p in self.memory_profiles]
        
        return {
            'total_executions': len(self.memory_profiles),
            'average_peak_memory_mb': sum(p['memory_mb'] for p in self.memory_profiles) / len(self.memory_profiles),
            'max_peak_memory_mb': max(p['memory_mb'] for p in self.memory_profiles),
            'min_peak_memory_mb': min(p['memory_mb'] for p in self.memory_profiles),
            'memory_trend': 'increasing' if peak_memories[-1] > peak_memories[0] else 'stable',
            'recent_profiles': self.memory_profiles[-5:]
        }
```

This performance optimization guide provides comprehensive strategies for maximizing AgentMap performance in production environments. The techniques can be combined and adapted based on specific requirements and infrastructure constraints.

For security considerations while optimizing performance, see the [Security Guide](/docs/guides/advanced/security).
