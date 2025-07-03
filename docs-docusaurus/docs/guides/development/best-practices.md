---
title: "Development Best Practices"
description: "Comprehensive guide to building robust, maintainable AgentMap workflows and custom agents. Covers architecture patterns, code quality, testing, performance, and production deployment."
sidebar_position: 7
keywords:
  - development best practices
  - agent development
  - workflow design
  - code quality
  - testing patterns
  - architecture patterns
  - performance optimization
  - production deployment
---

# Development Best Practices

This comprehensive guide outlines essential practices for developing robust, maintainable AgentMap workflows and custom agents. Following these patterns will help you build production-ready solutions that scale and perform well.

:::info Best Practices Overview
- **Architecture Patterns**: Clean design principles for maintainable code
- **Workflow Design**: Effective orchestration and error handling
- **Code Quality**: Standards for readable, testable agent development
- **Testing Strategies**: Comprehensive testing approaches
- **Performance**: Optimization techniques for scalable solutions
- **Security**: Best practices for secure implementations
- **Production**: Deployment and monitoring strategies
:::

---

## 🎯 Workflow Design Best Practices

### ✅ **Clean Architecture Principles**

Follow separation of concerns for maintainable workflows:

```csv title="Clean Workflow Design"
# Good: Clear separation of concerns
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
UserFlow,ValidateInput,,Input validation,validator,ProcessData,ErrorHandler,user_input,validated_data,,Validate user input
UserFlow,ProcessData,,Business logic,processor,FormatOutput,ErrorHandler,validated_data,processed_result,,Core business processing  
UserFlow,FormatOutput,,Output formatting,formatter,End,ErrorHandler,processed_result,final_output,,Format for presentation
UserFlow,ErrorHandler,,Error handling,echo,End,,error,error_message,,Handle any errors
UserFlow,End,,Complete workflow,echo,,,final_output|error_message,result,,Workflow completion
```

```csv title="Avoid: Mixed Concerns"
# Avoid: Mixing validation, processing, and formatting in one agent
UserFlow,DoEverything,,Validate + Process + Format,custom:MegaAgent,End,Error,input,output,,Single agent does everything
```

### ✅ **Error-First Design**

Design workflows with comprehensive error handling:

```csv title="Comprehensive Error Handling"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
RobustFlow,ProcessAPI,,"{'timeout': 30, 'retries': 3}",custom:APIAgent,ValidateResponse,HandleAPIError,api_request,api_response,,API call with timeout
RobustFlow,ValidateResponse,,Validate API response,validator,ProcessData,HandleValidationError,api_response,validated_response,,Response validation
RobustFlow,ProcessData,,Process validated data,processor,End,HandleProcessingError,validated_response,final_result,,Business logic
RobustFlow,HandleAPIError,,Handle API failures,error_handler,RetryAPI|End,FinalError,error,error_details,,API error recovery
RobustFlow,HandleValidationError,,Handle validation errors,error_handler,End,FinalError,error,error_details,,Validation error handling
RobustFlow,HandleProcessingError,,Handle processing errors,error_handler,End,FinalError,error,error_details,,Processing error handling
RobustFlow,RetryAPI,,"{'max_retries': 2}",custom:RetryAgent,ProcessAPI,FinalError,api_request,retry_result,,Retry logic
RobustFlow,FinalError,,Final error handling,echo,End,,error,final_error,,Ultimate fallback
RobustFlow,End,,Complete workflow,echo,,,final_result|final_error,result,,Workflow completion
```

### ✅ **Parallel Processing Patterns**

Use branching for independent operations:

```csv title="Parallel Processing Design"
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
ParallelFlow,SplitWork,,Split into parallel tasks,splitter,TaskA|TaskB|TaskC,Error,input_data,work_packages,,Distribute work
ParallelFlow,TaskA,,Process package A,worker_a,Join,Error,work_packages,result_a,,Independent task A
ParallelFlow,TaskB,,Process package B,worker_b,Join,Error,work_packages,result_b,,Independent task B
ParallelFlow,TaskC,,Process package C,worker_c,Join,Error,work_packages,result_c,,Independent task C
ParallelFlow,Join,,Combine results,aggregator,End,Error,result_a|result_b|result_c,combined_result,,Merge parallel results
ParallelFlow,Error,,Handle errors,echo,End,,error,error_message,,Error handling
ParallelFlow,End,,Complete workflow,echo,,,combined_result|error_message,final_output,,Final output
```

### **Performance Optimization Strategy**

Design workflows for optimal performance:

- **Parallel Execution**: Use branching for independent operations
- **Caching**: Cache expensive operations when possible
- **Resource Management**: Monitor memory usage for large datasets
- **Connection Pooling**: Reuse connections for external services

---

## 🔧 Custom Agent Development

### ✅ **Agent Architecture Best Practices**

Follow these patterns for custom agent development:

```python title="Well-Structured Custom Agent"
from typing import Dict, Any, Optional
import logging
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol

class WeatherAnalysisAgent(BaseAgent, LLMCapableAgent):
    """Agent that analyzes weather data with proper structure."""
    
    def __init__(
        self, 
        name: str, 
        prompt: str, 
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services
        logger: Optional[logging.Logger] = None,
        execution_tracker_service = None,
        state_adapter_service = None
    ):
        """Initialize with infrastructure services."""
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            state_adapter_service=state_adapter_service
        )
        
        # Configuration with defaults
        self.analysis_type = self.context.get("analysis_type", "basic")
        self.temperature = self.context.get("temperature", 0.3)
        self.max_retries = self.context.get("max_retries", 3)
        
        # Validate configuration
        self._validate_config()
    
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        """Configure LLM service."""
        self._llm_service = llm_service
        self.log_debug("LLM service configured")
    
    @property
    def llm_service(self) -> LLMServiceProtocol:
        """Get LLM service with error handling."""
        if self._llm_service is None:
            raise ValueError(f"LLM service not configured for agent '{self.name}'")
        return self._llm_service
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process weather data with comprehensive error handling."""
        weather_data = inputs.get("weather_data")
        
        # Input validation
        if not weather_data:
            return {"error": "No weather data provided"}
        
        try:
            # Process with retries
            for attempt in range(self.max_retries):
                try:
                    analysis = self._analyze_weather(weather_data)
                    return {
                        "analysis": analysis,
                        "analysis_type": self.analysis_type,
                        "attempt": attempt + 1
                    }
                except Exception as e:
                    self.log_warning(f"Analysis attempt {attempt + 1} failed: {e}")
                    if attempt == self.max_retries - 1:
                        raise
            
        except Exception as e:
            self.log_error(f"Weather analysis failed: {e}")
            return {
                "error": f"Analysis failed: {str(e)}",
                "analysis_type": self.analysis_type
            }
    
    def _validate_config(self):
        """Validate agent configuration."""
        valid_types = ["basic", "detailed", "predictive"]
        if self.analysis_type not in valid_types:
            raise ValueError(f"Invalid analysis_type: {self.analysis_type}. Must be one of {valid_types}")
        
        if self.temperature < 0 or self.temperature > 1:
            raise ValueError(f"Invalid temperature: {self.temperature}. Must be between 0 and 1")
    
    def _analyze_weather(self, weather_data: Dict[str, Any]) -> str:
        """Perform weather analysis using LLM."""
        prompt = self._build_analysis_prompt(weather_data)
        
        response = self.llm_service.call_llm(
            provider="openai",
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        
        return response
    
    def _build_analysis_prompt(self, weather_data: Dict[str, Any]) -> str:
        """Build analysis prompt based on type."""
        base_prompt = f"Analyze this weather data: {weather_data}\n\n"
        
        if self.analysis_type == "basic":
            return base_prompt + "Provide a basic weather summary."
        elif self.analysis_type == "detailed":
            return base_prompt + "Provide detailed weather analysis including trends and implications."
        elif self.analysis_type == "predictive":
            return base_prompt + "Analyze patterns and make weather predictions."
        
        return base_prompt
```

### ✅ **Configuration Management**

Handle configuration properly in custom agents:

```python title="Configuration Best Practices"
class ConfigurableAgent(BaseAgent):
    """Agent with proper configuration handling."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # Configuration with defaults and validation
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with defaults."""
        return {
            "timeout": self.context.get("timeout", 30),
            "retries": self.context.get("retries", 3),
            "batch_size": self.context.get("batch_size", 100),
            "api_base_url": self.context.get("api_base_url", "https://api.default.com"),
            "enable_caching": self.context.get("enable_caching", True),
            "debug_mode": self.context.get("debug_mode", False)
        }
    
    def _validate_config(self):
        """Validate configuration values."""
        if self.config["timeout"] <= 0:
            raise ValueError("timeout must be positive")
        
        if self.config["retries"] < 0:
            raise ValueError("retries must be non-negative")
        
        if self.config["batch_size"] <= 0:
            raise ValueError("batch_size must be positive")
        
        # Validate URL format
        if not self.config["api_base_url"].startswith(("http://", "https://")):
            raise ValueError("api_base_url must be a valid URL")
```

### ✅ **Error Handling in Agents**

Implement comprehensive error handling:

```python title="Error Handling Patterns"
class RobustAgent(BaseAgent):
    """Agent with comprehensive error handling."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process with comprehensive error handling."""
        try:
            # Validate inputs
            self._validate_inputs(inputs)
            
            # Process data
            result = self._process_data(inputs)
            
            # Validate outputs
            self._validate_outputs(result)
            
            return result
            
        except ValidationError as e:
            # Handle validation errors
            self.log_warning(f"Validation failed: {e}")
            return {
                "error": f"Validation error: {str(e)}",
                "error_type": "validation",
                "recoverable": True
            }
            
        except ExternalServiceError as e:
            # Handle external service errors
            self.log_error(f"External service failed: {e}")
            return {
                "error": f"Service unavailable: {str(e)}",
                "error_type": "external_service",
                "retry_recommended": True
            }
            
        except Exception as e:
            # Handle unexpected errors
            self.log_error(f"Unexpected error in {self.name}: {e}")
            return {
                "error": f"Processing failed: {str(e)}",
                "error_type": "unexpected",
                "recoverable": False
            }
    
    def _validate_inputs(self, inputs: Dict[str, Any]):
        """Validate input data."""
        required_fields = self.context.get("required_fields", [])
        
        for field in required_fields:
            if field not in inputs:
                raise ValidationError(f"Missing required field: {field}")
            
            if inputs[field] is None:
                raise ValidationError(f"Field cannot be null: {field}")
    
    def _validate_outputs(self, outputs: Any):
        """Validate output data."""
        if outputs is None:
            raise ValidationError("Agent produced no output")
        
        # Additional output validation as needed
        pass
```

---

## 📋 Code Quality Standards

### ✅ **Type Hints and Documentation**

Use type hints and comprehensive documentation:

```python title="Type Hints and Documentation"
from typing import Dict, Any, Optional, List, Union
import time

class DocumentedAgent(BaseAgent):
    """
    Agent that demonstrates proper documentation patterns.
    
    This agent processes user queries and returns structured responses
    with comprehensive error handling and logging.
    
    Attributes:
        query_processor: Service for processing user queries
        response_formatter: Service for formatting responses
        max_retries: Maximum number of retry attempts
    """
    
    def __init__(
        self, 
        name: str, 
        prompt: str, 
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize the documented agent.
        
        Args:
            name: Unique name for the agent
            prompt: Template or instructions for the agent
            context: Configuration dictionary with optional parameters
            **kwargs: Additional arguments passed to BaseAgent
            
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        super().__init__(name, prompt, context, **kwargs)
        self.max_retries = self.context.get("max_retries", 3)
    
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Union[str, int, bool]]:
        """
        Process user query and return structured response.
        
        Args:
            inputs: Dictionary containing 'query' field with user input
            
        Returns:
            Dictionary with either:
            - Success: {'response': str, 'confidence': float, 'processing_time': float}
            - Error: {'error': str, 'error_type': str, 'recoverable': bool}
            
        Raises:
            ValueError: If inputs are invalid
        """
        query = inputs.get("query", "")
        
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        
        start_time = time.time()
        
        try:
            response = self._process_query(query)
            processing_time = time.time() - start_time
            
            return {
                "response": response,
                "confidence": 0.9,  # Example confidence score
                "processing_time": processing_time
            }
            
        except Exception as e:
            self.log_error(f"Query processing failed: {e}")
            return {
                "error": str(e),
                "error_type": "processing_error",
                "recoverable": True
            }
    
    def _process_query(self, query: str) -> str:
        """
        Internal method to process the query.
        
        Args:
            query: User query string
            
        Returns:
            Processed response string
        """
        # Implementation here
        return f"Processed: {query}"
```

---

## 🧪 Testing Strategies

### **Test Pyramid**
1. **Unit Tests**: Individual agent functionality
2. **Integration Tests**: Agent interaction patterns
3. **End-to-End Tests**: Complete workflow validation
4. **Performance Tests**: Load and stress testing

### ✅ **Agent Testing Best Practices**

Write comprehensive tests for custom agents:

```python title="Agent Testing Best Practices"
import unittest
from unittest.mock import Mock, patch
from agentmap.agents.custom.weather_agent import WeatherAnalysisAgent

class TestWeatherAnalysisAgent(unittest.TestCase):
    """Comprehensive tests for WeatherAnalysisAgent."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = Mock()
        self.mock_tracker = Mock()
        self.mock_state_adapter = Mock()
        self.mock_llm_service = Mock()
        
        self.context = {
            "analysis_type": "detailed",
            "temperature": 0.3,
            "max_retries": 2
        }
        
        self.agent = WeatherAnalysisAgent(
            name="TestWeatherAgent",
            prompt="Analyze weather",
            context=self.context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_tracker,
            state_adapter_service=self.mock_state_adapter
        )
        
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
    
    def test_initialization(self):
        """Test agent initializes correctly."""
        self.assertEqual(self.agent.name, "TestWeatherAgent")
        self.assertEqual(self.agent.analysis_type, "detailed")
        self.assertEqual(self.agent.temperature, 0.3)
        self.assertEqual(self.agent.max_retries, 2)
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Test invalid analysis type
        with self.assertRaises(ValueError):
            WeatherAnalysisAgent(
                name="TestAgent",
                prompt="test",
                context={"analysis_type": "invalid"}
            )
        
        # Test invalid temperature
        with self.assertRaises(ValueError):
            WeatherAnalysisAgent(
                name="TestAgent", 
                prompt="test",
                context={"temperature": 2.0}
            )
    
    def test_successful_processing(self):
        """Test successful weather analysis."""
        # Configure mock LLM service
        self.mock_llm_service.call_llm.return_value = "Detailed weather analysis"
        
        # Test data
        weather_data = {
            "temperature": 22,
            "humidity": 65,
            "wind_speed": 10
        }
        
        inputs = {"weather_data": weather_data}
        
        # Execute
        result = self.agent.process(inputs)
        
        # Verify
        self.assertIn("analysis", result)
        self.assertEqual(result["analysis"], "Detailed weather analysis")
        self.assertEqual(result["analysis_type"], "detailed")
        self.assertEqual(result["attempt"], 1)
        
        # Verify LLM service was called correctly
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args
        self.assertEqual(call_args[1]["temperature"], 0.3)
    
    def test_missing_input_handling(self):
        """Test handling of missing weather data."""
        inputs = {}  # No weather_data
        
        result = self.agent.process(inputs)
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No weather data provided")
    
    def test_llm_service_error_handling(self):
        """Test handling of LLM service errors."""
        # Configure mock to raise exception
        self.mock_llm_service.call_llm.side_effect = Exception("LLM service error")
        
        inputs = {"weather_data": {"temp": 20}}
        
        result = self.agent.process(inputs)
        
        self.assertIn("error", result)
        self.assertIn("Analysis failed", result["error"])
        self.assertEqual(result["analysis_type"], "detailed")
    
    def test_retry_logic(self):
        """Test retry logic on failures."""
        # Configure mock to fail once, then succeed
        self.mock_llm_service.call_llm.side_effect = [
            Exception("Temporary error"),
            "Successful analysis"
        ]
        
        inputs = {"weather_data": {"temp": 20}}
        
        result = self.agent.process(inputs)
        
        # Should succeed on second attempt
        self.assertIn("analysis", result)
        self.assertEqual(result["analysis"], "Successful analysis")
        self.assertEqual(result["attempt"], 2)
        
        # Verify retry happened
        self.assertEqual(self.mock_llm_service.call_llm.call_count, 2)

if __name__ == "__main__":
    unittest.main()
```

---

## 🚀 Performance Best Practices

### ✅ **Memory Management**

Optimize memory usage in agents:

```python title="Memory-Efficient Agent"
class MemoryEfficientAgent(BaseAgent):
    """Agent optimized for memory efficiency."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process data with memory optimization."""
        data = inputs.get("data", [])
        
        # Process in chunks to avoid memory issues
        chunk_size = self.context.get("chunk_size", 1000)
        results = []
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            
            # Process chunk
            chunk_result = self._process_chunk(chunk)
            results.append(chunk_result)
            
            # Explicit cleanup
            del chunk
            
            # Optional: Trigger garbage collection for large datasets
            if len(data) > 10000 and i % (chunk_size * 10) == 0:
                import gc
                gc.collect()
        
        return {"results": results, "total_chunks": len(results)}
    
    def _process_chunk(self, chunk: List[Any]) -> Any:
        """Process a single chunk of data."""
        # Implementation here
        return f"Processed {len(chunk)} items"
```

### ✅ **Caching Patterns**

Implement effective caching:

```python title="Caching Agent"
from functools import lru_cache
import hashlib
import json

class CachingAgent(BaseAgent):
    """Agent with intelligent caching."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self.cache_enabled = self.context.get("cache_enabled", True)
        self.cache_ttl = self.context.get("cache_ttl", 3600)  # 1 hour
        self._cache = {}
        self._cache_timestamps = {}
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process with caching."""
        if not self.cache_enabled:
            return self._process_without_cache(inputs)
        
        # Generate cache key
        cache_key = self._generate_cache_key(inputs)
        
        # Check cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            self.log_debug(f"Cache hit for key: {cache_key}")
            return {**cached_result, "_cache_hit": True}
        
        # Process and cache
        result = self._process_without_cache(inputs)
        self._store_in_cache(cache_key, result)
        
        return {**result, "_cache_hit": False}
    
    def _generate_cache_key(self, inputs: Dict[str, Any]) -> str:
        """Generate deterministic cache key."""
        # Create deterministic string representation
        sorted_inputs = json.dumps(inputs, sort_keys=True)
        return hashlib.md5(sorted_inputs.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache with TTL check."""
        if cache_key not in self._cache:
            return None
        
        # Check TTL
        import time
        if time.time() - self._cache_timestamps[cache_key] > self.cache_ttl:
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None
        
        return self._cache[cache_key]
    
    def _store_in_cache(self, cache_key: str, result: Dict[str, Any]):
        """Store result in cache."""
        import time
        self._cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()
        
        # Simple cache size management
        if len(self._cache) > self.context.get("max_cache_size", 1000):
            # Remove oldest entry
            oldest_key = min(self._cache_timestamps.keys(), 
                           key=lambda k: self._cache_timestamps[k])
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]
```

### **Scalability Patterns**

**Horizontal Scaling**:
- **Stateless Design**: Keep workflows stateless for easy scaling
- **Load Distribution**: Distribute workflows across instances
- **Database Optimization**: Optimize data access patterns
- **Caching Strategy**: Implement multi-level caching

**Vertical Scaling**:
- **Resource Optimization**: Tune memory and CPU usage
- **Batch Processing**: Process multiple items efficiently
- **Connection Management**: Optimize external service calls
- **Memory Management**: Implement proper cleanup patterns

---

## 🔒 Security Best Practices

### ✅ **Input Validation**

Always validate and sanitize inputs:

```python title="Secure Input Handling"
import re
from typing import Any, Dict

class SecureAgent(BaseAgent):
    """Agent with comprehensive input validation."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process with security validation."""
        try:
            # Validate and sanitize inputs
            clean_inputs = self._validate_and_sanitize(inputs)
            
            # Process clean inputs
            result = self._process_safely(clean_inputs)
            
            return result
            
        except SecurityError as e:
            self.log_warning(f"Security validation failed: {e}")
            return {"error": "Invalid input", "details": "Input validation failed"}
    
    def _validate_and_sanitize(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize all inputs."""
        clean_inputs = {}
        
        for key, value in inputs.items():
            # Validate key names
            if not self._is_valid_key(key):
                raise SecurityError(f"Invalid key name: {key}")
            
            # Sanitize values
            clean_value = self._sanitize_value(value)
            clean_inputs[key] = clean_value
        
        return clean_inputs
    
    def _is_valid_key(self, key: str) -> bool:
        """Validate input key names."""
        # Only allow alphanumeric and underscore
        return re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key) is not None
    
    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize input values."""
        if isinstance(value, str):
            # Remove potentially dangerous characters
            # This is a basic example - adjust based on your needs
            value = re.sub(r'[<>"\']', '', value)
            
            # Limit string length
            max_length = self.context.get("max_string_length", 10000)
            if len(value) > max_length:
                value = value[:max_length]
        
        elif isinstance(value, dict):
            # Recursively sanitize dictionary values
            return {k: self._sanitize_value(v) for k, v in value.items() 
                   if self._is_valid_key(k)}
        
        elif isinstance(value, list):
            # Limit list size and sanitize elements
            max_list_size = self.context.get("max_list_size", 1000)
            if len(value) > max_list_size:
                value = value[:max_list_size]
            
            return [self._sanitize_value(item) for item in value]
        
        return value

class SecurityError(Exception):
    """Security validation error."""
    pass
```

### ✅ **Secret Management**

Handle secrets securely:

```python title="Secure Secret Management"
import os
from typing import Optional

class SecureServiceAgent(BaseAgent):
    """Agent with secure secret management."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # Load secrets securely
        self.api_key = self._get_secret("API_KEY")
        self.database_password = self._get_secret("DATABASE_PASSWORD")
        
        # Never log secrets
        self.log_debug("Agent initialized with secrets loaded")
    
    def _get_secret(self, secret_name: str) -> str:
        """Get secret from environment with fallback to context."""
        # Try environment first
        secret = os.getenv(secret_name)
        
        if secret:
            return secret
        
        # Fall back to context (for testing)
        secret = self.context.get(secret_name.lower())
        
        if not secret:
            raise ValueError(f"Required secret not found: {secret_name}")
        
        return secret
    
    def _make_secure_api_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make API call with secure headers."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"AgentMap/{self.name}"
        }
        
        # Never log headers containing secrets
        self.log_debug("Making secure API call")
        
        # Implementation here
        return {"status": "success"}
```

### **Compliance Considerations**
- **GDPR**: Implement data processing transparency
- **HIPAA**: Secure health data handling patterns
- **SOC 2**: Security control implementations
- **PCI DSS**: Payment data protection strategies

---

## 📊 Production Deployment

### ✅ **Environment Configuration**

Structure configuration for different environments:

```yaml title="Environment Configuration"
# development.yaml
environment: development
debug: true
log_level: DEBUG

agents:
  weather_agent:
    timeout: 60
    retries: 1
    cache_enabled: false

# production.yaml  
environment: production
debug: false
log_level: INFO

agents:
  weather_agent:
    timeout: 30
    retries: 3
    cache_enabled: true
    cache_ttl: 3600
```

### ✅ **Monitoring Integration**

Build monitoring into agents:

```python title="Monitored Agent"
import time
from typing import Dict, Any

class MonitoredAgent(BaseAgent):
    """Agent with built-in monitoring."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process with monitoring."""
        start_time = time.time()
        
        try:
            # Record start
            self._record_start()
            
            # Process
            result = self._process_with_monitoring(inputs)
            
            # Record success
            execution_time = time.time() - start_time
            self._record_success(execution_time, result)
            
            return result
            
        except Exception as e:
            # Record failure
            execution_time = time.time() - start_time
            self._record_failure(execution_time, e)
            raise
    
    def _record_start(self):
        """Record processing start."""
        self.log_info(f"Agent {self.name} processing started")
        
        # Send to monitoring system
        self._send_metric("agent.processing.started", 1, {
            "agent_name": self.name,
            "agent_type": self.__class__.__name__
        })
    
    def _record_success(self, execution_time: float, result: Any):
        """Record successful processing."""
        self.log_info(f"Agent {self.name} completed successfully in {execution_time:.2f}s")
        
        # Send metrics
        self._send_metric("agent.processing.success", 1, {
            "agent_name": self.name,
            "execution_time": execution_time
        })
        
        self._send_metric("agent.execution_time", execution_time, {
            "agent_name": self.name
        })
    
    def _record_failure(self, execution_time: float, error: Exception):
        """Record processing failure."""
        self.log_error(f"Agent {self.name} failed after {execution_time:.2f}s: {error}")
        
        # Send metrics
        self._send_metric("agent.processing.failure", 1, {
            "agent_name": self.name,
            "error_type": type(error).__name__,
            "execution_time": execution_time
        })
    
    def _send_metric(self, metric_name: str, value: float, tags: Dict[str, str]):
        """Send metric to monitoring system."""
        # Implementation depends on your monitoring system
        # Example: StatsD, CloudWatch, Prometheus, etc.
        pass
```

### **Production Deployment Checklist**
- [ ] All environment variables configured
- [ ] External service connectivity verified
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures tested
- [ ] Performance benchmarks established
- [ ] Security review completed

### **Key Metrics to Track**
- **Execution Time**: Per-node and end-to-end timing
- **Success Rates**: Success/failure ratios by workflow
- **Resource Usage**: Memory and CPU consumption
- **Error Patterns**: Common failure modes and frequencies

---

## 📋 Development Workflow

### **1. Planning Phase**
- Map business requirements to workflow steps
- Identify external dependencies and integration points
- Design error handling and edge case management
- Plan testing strategy and success criteria

### **2. Development Phase**
- Start with simple end-to-end workflow
- Add complexity incrementally
- Test each component thoroughly
- Document configuration and dependencies

### **3. Deployment Phase**
- Use staging environment for validation
- Implement monitoring and alerting
- Plan rollback strategy
- Document operational procedures

---

## Related Documentation

### **Core Development**
- **[Custom Agent Development](/docs/guides/development/agents/custom-agents)** - Building custom agents
- **[Service Injection](/docs/contributing/service-injection)** - Dependency injection patterns
- **[Testing Strategies](./testing)** - Comprehensive testing approaches

### **Advanced Topics**
- **[Integration Patterns](./integrations)** - External system integration
- **[Memory Management](/docs/guides/development/agent-memory/memory-management)** - Conversation and state management
- **[Orchestration Patterns](./orchestration)** - Dynamic workflow routing

### **Production**
- **[Deployment](/docs/guides/deploying/deployment)** - Production deployment strategies
- **[Monitoring](/docs/guides/deploying/monitoring)** - Production monitoring and alerting
- **[Security](/docs/guides/deploying/deployment)** - Security implementation patterns

---

## 🤝 Community Best Practices

Share your best practices and learn from the community:

- **[GitHub Discussions](https://github.com/jwwelbor/AgentMap/discussions)** - Share patterns and get feedback
- **[Example Repository](https://github.com/jwwelbor/AgentMap-Examples)** - Real-world implementation patterns
- **[Community Discord](https://discord.gg/agentmap)** - Real-time discussion with other developers

---

*💡 **Remember**: Good development practices are about building systems that are maintainable, testable, and scalable. Start with these patterns and adapt them to your specific needs!*

**Last updated: June 28, 2025**
