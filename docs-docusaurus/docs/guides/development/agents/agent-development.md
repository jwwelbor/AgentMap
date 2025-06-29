---
sidebar_position: 2
title: Agent Development Guide
description: Comprehensive guide to developing custom agents in AgentMap with advanced patterns, best practices, and integration strategies.
keywords: [agent development, custom agents, AgentMap development, agent patterns, agent architecture, advanced agents]
---

# Advanced Agent Development Guide

This comprehensive guide covers advanced agent development patterns in AgentMap, including sophisticated architectures, performance optimization, and integration strategies for building production-ready agent systems.

## AgentMap Agent Architecture

### Core Agent Pattern

All AgentMap agents inherit from `BaseAgent` and implement the `process` method:

```python
from agentmap.agents.base_agent import BaseAgent
from typing import Any, Dict, Optional
import logging

class CustomAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
        execution_tracking_service=None,
        state_adapter_service=None,
    ):
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
        )
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs and return output.
        
        Args:
            inputs: Dictionary of input values from input_fields
            
        Returns:
            Output value for the output_field
        """
        # Your agent logic here
        result = f"Processed: {inputs}"
        return result
```

## Agent Architecture Patterns

### 1. Pipeline Agents

Pipeline agents process data through a series of stages, each handling a specific transformation:

```python
from agentmap.agents.base_agent import BaseAgent
from typing import List, Dict, Any, Callable
import time
from datetime import datetime

class PipelineAgent(BaseAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self.pipeline_stages = []
        self.stage_configs = {}
    
    def add_stage(self, stage_name: str, processor: Callable, config: Dict = None):
        """Add a processing stage to the pipeline"""
        self.pipeline_stages.append(stage_name)
        self.stage_configs[stage_name] = {
            'processor': processor,
            'config': config or {}
        }
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process all pipeline stages in sequence"""
        current_data = inputs
        execution_trace = []
        
        for stage_name in self.pipeline_stages:
            stage_config = self.stage_configs[stage_name]
            processor = stage_config['processor']
            config = stage_config['config']
            
            try:
                # Process stage
                stage_start = time.time()
                current_data = processor(current_data, config)
                stage_duration = time.time() - stage_start
                
                execution_trace.append({
                    'stage': stage_name,
                    'duration': stage_duration,
                    'input_size': len(str(current_data)),
                    'status': 'success'
                })
                
            except Exception as e:
                execution_trace.append({
                    'stage': stage_name,
                    'error': str(e),
                    'status': 'failed'
                })
                
                # Handle pipeline failure
                if self.context.get('stop_on_failure', True):
                    break
                else:
                    # Continue with error placeholder
                    current_data = {'error': str(e), 'stage': stage_name}
        
        return {
            'result': current_data,
            'execution_trace': execution_trace,
            'total_stages': len(self.pipeline_stages),
            'successful_stages': len([t for t in execution_trace if t['status'] == 'success'])
        }

# Example usage
class DataProcessingPipeline(PipelineAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # Add processing stages
        self.add_stage('validate', self.validate_data, {'required_fields': ['id', 'name']})
        self.add_stage('clean', self.clean_data, {'remove_nulls': True})
        self.add_stage('transform', self.transform_data, {'format': 'normalized'})
        self.add_stage('enrich', self.enrich_data, {'add_metadata': True})
    
    def validate_data(self, data: Dict, config: Dict) -> Dict:
        """Validate input data structure"""
        required_fields = config.get('required_fields', [])
        
        if isinstance(data, list):
            # Validate list of records
            for record in data:
                missing_fields = [field for field in required_fields if field not in record]
                if missing_fields:
                    raise ValueError(f"Missing required fields: {missing_fields}")
        else:
            # Validate single record
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
        
        return data
    
    def clean_data(self, data: Dict, config: Dict) -> Dict:
        """Clean and normalize data"""
        remove_nulls = config.get('remove_nulls', False)
        
        if isinstance(data, list):
            cleaned_data = []
            for record in data:
                cleaned_record = self.clean_record(record, remove_nulls)
                if cleaned_record:  # Only include non-empty records
                    cleaned_data.append(cleaned_record)
            return cleaned_data
        else:
            return self.clean_record(data, remove_nulls)
    
    def clean_record(self, record: Dict, remove_nulls: bool) -> Dict:
        """Clean individual record"""
        cleaned = {}
        
        for key, value in record.items():
            # Remove null values if configured
            if remove_nulls and value in [None, '', 'null', 'NULL']:
                continue
            
            # Clean string values
            if isinstance(value, str):
                value = value.strip()
                if value.lower() in ['n/a', 'na', 'none']:
                    value = None if not remove_nulls else continue
            
            cleaned[key] = value
        
        return cleaned
    
    def transform_data(self, data: Dict, config: Dict) -> Dict:
        """Transform data to required format"""
        format_type = config.get('format', 'default')
        
        if format_type == 'normalized':
            return self.normalize_data(data)
        elif format_type == 'standardized':
            return self.standardize_data(data)
        else:
            return data
    
    def normalize_data(self, data: Dict) -> Dict:
        """Normalize data values"""
        if isinstance(data, list):
            return [self.normalize_record(record) for record in data]
        else:
            return self.normalize_record(data)
    
    def normalize_record(self, record: Dict) -> Dict:
        """Normalize individual record"""
        normalized = {}
        
        for key, value in record.items():
            # Normalize field names
            normalized_key = key.lower().replace(' ', '_').replace('-', '_')
            
            # Normalize values
            if isinstance(value, str):
                # Convert to lowercase for standardization
                if key.lower() in ['status', 'type', 'category']:
                    value = value.lower()
                # Handle boolean strings
                elif value.lower() in ['true', 'yes', '1']:
                    value = True
                elif value.lower() in ['false', 'no', '0']:
                    value = False
            
            normalized[normalized_key] = value
        
        return normalized
    
    def enrich_data(self, data: Dict, config: Dict) -> Dict:
        """Enrich data with additional metadata"""
        add_metadata = config.get('add_metadata', False)
        
        if not add_metadata:
            return data
        
        metadata = {
            'processed_at': datetime.now().isoformat(),
            'processor': 'DataProcessingPipeline',
            'version': '1.0'
        }
        
        if isinstance(data, list):
            for record in data:
                record['_metadata'] = metadata.copy()
            return data
        else:
            data['_metadata'] = metadata
            return data
```

### 2. State Machine Agents

State machine agents manage complex workflows with multiple states and transitions:

```python
from enum import Enum
from typing import Dict, Any, Optional, Set

class AgentState(Enum):
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    WAITING_INPUT = "waiting_input"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ERROR = "error"
    SUSPENDED = "suspended"

class StateMachineAgent(BaseAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self.current_state = AgentState.INITIALIZED
        self.state_history = [AgentState.INITIALIZED]
        self.state_data = {}
        self.transitions = {}
        self.state_handlers = {}
        self.setup_state_machine()
    
    def setup_state_machine(self):
        """Define state transitions and handlers"""
        # Define valid transitions
        self.transitions = {
            AgentState.INITIALIZED: {AgentState.PROCESSING, AgentState.ERROR},
            AgentState.PROCESSING: {AgentState.WAITING_INPUT, AgentState.VALIDATING, AgentState.COMPLETED, AgentState.ERROR},
            AgentState.WAITING_INPUT: {AgentState.PROCESSING, AgentState.SUSPENDED, AgentState.ERROR},
            AgentState.VALIDATING: {AgentState.PROCESSING, AgentState.COMPLETED, AgentState.ERROR},
            AgentState.COMPLETED: {AgentState.INITIALIZED},  # Can restart
            AgentState.ERROR: {AgentState.INITIALIZED, AgentState.PROCESSING},  # Can recover
            AgentState.SUSPENDED: {AgentState.PROCESSING, AgentState.ERROR}
        }
        
        # Define state handlers
        self.state_handlers = {
            AgentState.INITIALIZED: self.handle_initialized,
            AgentState.PROCESSING: self.handle_processing,
            AgentState.WAITING_INPUT: self.handle_waiting_input,
            AgentState.VALIDATING: self.handle_validating,
            AgentState.COMPLETED: self.handle_completed,
            AgentState.ERROR: self.handle_error,
            AgentState.SUSPENDED: self.handle_suspended
        }
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process state machine logic"""
        self.state_data['input'] = inputs
        
        max_iterations = inputs.get('max_iterations', 10)
        iterations = 0
        
        while iterations < max_iterations and self.current_state != AgentState.COMPLETED:
            try:
                # Process current state handler
                result = self.process_current_state()
                
                # Check for state transition
                if 'next_state' in result:
                    self.transition_to(result['next_state'])
                
                # Update state data
                if 'state_data' in result:
                    self.state_data.update(result['state_data'])
                
                iterations += 1
                
            except Exception as e:
                self.transition_to(AgentState.ERROR)
                self.state_data['error'] = str(e)
                break
        
        return {
            'final_state': self.current_state.value,
            'state_history': [state.value for state in self.state_history],
            'iterations': iterations,
            'state_data': self.state_data,
            'completed': self.current_state == AgentState.COMPLETED
        }
    
    def process_current_state(self) -> Dict[str, Any]:
        """Process handler for current state"""
        handler = self.state_handlers.get(self.current_state)
        if handler:
            return handler()
        else:
            raise Exception(f"No handler defined for state: {self.current_state}")
    
    def transition_to(self, new_state: AgentState):
        """Transition to new state if valid"""
        valid_transitions = self.transitions.get(self.current_state, set())
        
        if new_state in valid_transitions:
            self.state_history.append(new_state)
            self.current_state = new_state
            self.log_info(f"Transitioned to state: {new_state.value}")
        else:
            raise Exception(f"Invalid transition from {self.current_state.value} to {new_state.value}")
    
    def handle_initialized(self) -> Dict[str, Any]:
        """Handle initialized state"""
        return {
            'next_state': AgentState.PROCESSING,
            'state_data': {'initialized_at': datetime.now().isoformat()}
        }
    
    def handle_processing(self) -> Dict[str, Any]:
        """Handle processing state - override in subclasses"""
        # Default processing logic
        input_data = self.state_data.get('input')
        
        if not input_data:
            return {'next_state': AgentState.ERROR, 'state_data': {'error': 'No input data'}}
        
        # Simulate processing
        processed_data = f"Processed: {input_data}"
        
        return {
            'next_state': AgentState.VALIDATING,
            'state_data': {'processed_data': processed_data}
        }
    
    def handle_waiting_input(self) -> Dict[str, Any]:
        """Handle waiting for input state"""
        # Check if additional input is available
        additional_input = self.state_data.get('additional_input')
        
        if additional_input:
            return {
                'next_state': AgentState.PROCESSING,
                'state_data': {'additional_input': additional_input}
            }
        else:
            return {'next_state': AgentState.SUSPENDED}
    
    def handle_validating(self) -> Dict[str, Any]:
        """Handle validation state"""
        processed_data = self.state_data.get('processed_data')
        
        if processed_data and len(str(processed_data)) > 0:
            return {
                'next_state': AgentState.COMPLETED,
                'state_data': {'validation_passed': True}
            }
        else:
            return {
                'next_state': AgentState.ERROR,
                'state_data': {'validation_error': 'Invalid processed data'}
            }
    
    def handle_completed(self) -> Dict[str, Any]:
        """Handle completed state"""
        return {
            'state_data': {
                'completed_at': datetime.now().isoformat(),
                'final_result': self.state_data.get('processed_data')
            }
        }
    
    def handle_error(self) -> Dict[str, Any]:
        """Handle error state"""
        error = self.state_data.get('error', 'Unknown error')
        
        return {
            'state_data': {
                'error_handled_at': datetime.now().isoformat(),
                'error_message': error,
                'recovery_available': True
            }
        }
    
    def handle_suspended(self) -> Dict[str, Any]:
        """Handle suspended state"""
        return {
            'state_data': {
                'suspended_at': datetime.now().isoformat(),
                'reason': 'Waiting for external input'
            }
        }
```

### 3. Conditional Processing Agents

Agents that implement conditional logic and branching:

```python
class ConditionalAgent(BaseAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self.conditions = self.context.get('conditions', [])
        self.default_action = self.context.get('default_action', 'continue')
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process inputs based on defined conditions"""
        
        for condition in self.conditions:
            if self.evaluate_condition(condition, inputs):
                result = self.process_condition_action(condition, inputs)
                return {
                    'condition_met': condition.get('name', 'unnamed'),
                    'result': result,
                    'matched': True
                }
        
        # No conditions met - use default action
        default_result = self.process_default_action(inputs)
        return {
            'condition_met': 'default',
            'result': default_result,
            'matched': False
        }
    
    def evaluate_condition(self, condition: Dict, inputs: Dict[str, Any]) -> bool:
        """Evaluate if a condition is met"""
        condition_type = condition.get('type', 'equals')
        field = condition.get('field')
        expected_value = condition.get('value')
        
        if field not in inputs:
            return False
        
        actual_value = inputs[field]
        
        if condition_type == 'equals':
            return actual_value == expected_value
        elif condition_type == 'not_equals':
            return actual_value != expected_value
        elif condition_type == 'greater_than':
            return float(actual_value) > float(expected_value)
        elif condition_type == 'less_than':
            return float(actual_value) < float(expected_value)
        elif condition_type == 'contains':
            return expected_value in str(actual_value)
        elif condition_type == 'regex':
            import re
            return bool(re.search(expected_value, str(actual_value)))
        elif condition_type == 'exists':
            return actual_value is not None
        elif condition_type == 'custom':
            # Allow custom evaluation function
            eval_func = condition.get('eval_function')
            if eval_func and callable(eval_func):
                return eval_func(actual_value, expected_value)
        
        return False
    
    def process_condition_action(self, condition: Dict, inputs: Dict[str, Any]) -> Any:
        """Process action when condition is met"""
        action = condition.get('action', 'continue')
        
        if action == 'transform':
            transform_func = condition.get('transform_function')
            if transform_func and callable(transform_func):
                return transform_func(inputs)
            else:
                return inputs
        elif action == 'filter':
            filter_fields = condition.get('filter_fields', [])
            return {field: inputs[field] for field in filter_fields if field in inputs}
        elif action == 'enrich':
            enrichment_data = condition.get('enrichment', {})
            result = inputs.copy()
            result.update(enrichment_data)
            return result
        elif action == 'stop':
            return {'status': 'stopped', 'reason': condition.get('stop_reason', 'Condition met')}
        else:
            return inputs
    
    def process_default_action(self, inputs: Dict[str, Any]) -> Any:
        """Process default action when no conditions are met"""
        if self.default_action == 'continue':
            return inputs
        elif self.default_action == 'error':
            raise ValueError("No matching conditions found")
        elif self.default_action == 'empty':
            return {}
        else:
            return {'status': 'no_match', 'input': inputs}

# Example usage for data routing
class DataRouterAgent(ConditionalAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        # Define routing conditions
        routing_conditions = [
            {
                'name': 'high_priority',
                'type': 'greater_than',
                'field': 'priority',
                'value': 8,
                'action': 'enrich',
                'enrichment': {'route': 'priority_queue', 'urgent': True}
            },
            {
                'name': 'error_status',
                'type': 'equals',
                'field': 'status',
                'value': 'error',
                'action': 'enrich',
                'enrichment': {'route': 'error_handler', 'needs_attention': True}
            },
            {
                'name': 'large_data',
                'type': 'custom',
                'field': 'data_size',
                'eval_function': lambda value, _: int(value) > 1000000,
                'action': 'enrich',
                'enrichment': {'route': 'batch_processor', 'processing_mode': 'parallel'}
            }
        ]
        
        if context is None:
            context = {}
        context.update({
            'conditions': routing_conditions,
            'default_action': 'continue'
        })
        
        super().__init__(name, prompt, context, **kwargs)
```

## Service Integration Patterns

### 1. LLM-Capable Agents

For agents that need LLM capabilities:

```python
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol

class LLMAgent(BaseAgent, LLMCapableAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self._llm_service: Optional[LLMServiceProtocol] = None
    
    def configure_llm_service(self, llm_service: LLMServiceProtocol):
        """Configure LLM service using protocol-based injection"""
        self._llm_service = llm_service
    
    @property
    def llm_service(self) -> LLMServiceProtocol:
        """Get LLM service, raising clear error if not configured"""
        if self._llm_service is None:
            raise ValueError(f"LLM service not configured for agent '{self.name}'")
        return self._llm_service
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process inputs using LLM service"""
        # Format prompt with inputs
        formatted_prompt = self.prompt.format(**inputs)
        
        # Call LLM service
        response = self.llm_service.generate_response(
            prompt=formatted_prompt,
            context=inputs
        )
        
        return response.get('content', 'No response')
    
    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """Provide LLM agent service information"""
        return {
            "services": {
                "llm_service_configured": self._llm_service is not None,
                "supports_llm_generation": True,
            },
            "capabilities": {
                "prompt_formatting": True,
                "context_injection": True,
                "response_processing": True,
            }
        }
```

### 2. Storage-Capable Agents

For agents that need storage capabilities:

```python
from agentmap.services.protocols import StorageCapableAgent, StorageServiceProtocol

class StorageAgent(BaseAgent, StorageCapableAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self._storage_service: Optional[StorageServiceProtocol] = None
    
    def configure_storage_service(self, storage_service: StorageServiceProtocol):
        """Configure storage service using protocol-based injection"""
        self._storage_service = storage_service
    
    @property
    def storage_service(self) -> StorageServiceProtocol:
        """Get storage service, raising clear error if not configured"""
        if self._storage_service is None:
            raise ValueError(f"Storage service not configured for agent '{self.name}'")
        return self._storage_service
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process inputs with storage operations"""
        
        # Store input data
        storage_key = f"{self.name}_{inputs.get('id', 'unknown')}"
        self.storage_service.store(storage_key, inputs)
        
        # Process data
        result = self.process_data(inputs)
        
        # Store result
        result_key = f"{storage_key}_result"
        self.storage_service.store(result_key, result)
        
        return {
            'result': result,
            'storage_keys': {
                'input': storage_key,
                'output': result_key
            }
        }
    
    def process_data(self, inputs: Dict[str, Any]) -> Any:
        """Override for specific data processing logic"""
        return f"Processed: {inputs}"
    
    def retrieve_previous_results(self, identifier: str) -> Any:
        """Retrieve previously stored results"""
        storage_key = f"{self.name}_{identifier}_result"
        return self.storage_service.retrieve(storage_key)
```

## Performance Optimization

### 1. Caching Strategies

```python
from functools import wraps
import hashlib
import json

class CachingAgent(BaseAgent):
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self.cache_config = {
            'default_ttl': 3600,  # 1 hour
            'max_cache_size': 1000,
            'cache_enabled': True
        }
        self._memory_cache = {}
    
    def cache_key(self, inputs: Dict[str, Any]) -> str:
        """Generate cache key from inputs"""
        # Create deterministic hash from input
        if isinstance(inputs, dict):
            data_str = json.dumps(inputs, sort_keys=True)
        else:
            data_str = str(inputs)
        
        combined = f"{data_str}:{self.__class__.__name__}:{self.prompt}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get_from_cache(self, cache_key: str) -> Any:
        """Get result from cache"""
        if not self.cache_config['cache_enabled']:
            return None
        
        return self._memory_cache.get(cache_key)
    
    def store_in_cache(self, cache_key: str, result: Any):
        """Store result in cache"""
        if not self.cache_config['cache_enabled']:
            return
        
        self._memory_cache[cache_key] = result
        
        # Simple cache size management
        if len(self._memory_cache) > self.cache_config['max_cache_size']:
            # Remove oldest entries (simplified LRU)
            keys_to_remove = list(self._memory_cache.keys())[:10]
            for key in keys_to_remove:
                del self._memory_cache[key]
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process with caching"""
        
        # Generate cache key
        cache_key = self.cache_key(inputs)
        
        # Try to get from cache
        cached_result = self.get_from_cache(cache_key)
        
        if cached_result is not None:
            self.log_info(f"Cache hit for key: {cache_key}")
            return {**cached_result, '_cache_hit': True}
        
        # Cache miss - process normally
        self.log_info(f"Cache miss for key: {cache_key}")
        result = self.process_data(inputs)
        
        # Store in cache
        result_with_meta = {**result, '_cache_hit': False} if isinstance(result, dict) else result
        self.store_in_cache(cache_key, result_with_meta)
        
        return result_with_meta
    
    def process_data(self, inputs: Dict[str, Any]) -> Any:
        """Override in subclasses for specific processing logic"""
        return {'processed_data': f"Processed: {inputs}"}
```

## Testing and Quality Assurance

### 1. Agent Testing Framework

```python
import unittest
from unittest.mock import Mock, patch, MagicMock

class AgentTestCase(unittest.TestCase):
    """Base test case for agent testing"""
    
    def setUp(self):
        """Setup test environment"""
        self.mock_logger = Mock()
        self.mock_execution_tracker = Mock()
        self.mock_state_adapter = Mock()
        self.agent = self.create_agent_instance()
        
    def create_agent_instance(self):
        """Create agent instance for testing - override in subclasses"""
        return BaseAgent(
            name="test_agent",
            prompt="Test prompt",
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
    
    def assert_agent_processing_successful(self, result: Any):
        """Assert that agent processing was successful"""
        self.assertIsNotNone(result)
    
    def assert_agent_processing_failed(self, inputs: Dict[str, Any], expected_error: str = None):
        """Assert that agent processing failed"""
        with self.assertRaises(Exception) as context:
            self.agent.process(inputs)
        
        if expected_error:
            self.assertIn(expected_error, str(context.exception))

class TestDataProcessingAgent(AgentTestCase):
    """Test case for DataProcessingAgent"""
    
    def create_agent_instance(self):
        return DataProcessingPipeline(
            name="test_pipeline",
            prompt="Test processing pipeline",
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
    
    def test_valid_data_processing(self):
        """Test processing with valid data"""
        valid_inputs = {
            'data': {
                'id': '123',
                'name': 'Test Item',
                'value': 100
            }
        }
        
        result = self.agent.process(valid_inputs)
        
        self.assert_agent_processing_successful(result)
        self.assertIn('result', result)
        self.assertEqual(result['successful_stages'], result['total_stages'])
    
    def test_invalid_data_processing(self):
        """Test processing with invalid data"""
        invalid_inputs = {
            'data': {
                'name': 'Test Item'
                # Missing required 'id' field
            }
        }
        
        result = self.agent.process(invalid_inputs)
        
        # Should fail at validation stage
        self.assertIn('execution_trace', result)
        validation_stage = next(
            (stage for stage in result['execution_trace'] if stage['stage'] == 'validate'), 
            None
        )
        self.assertIsNotNone(validation_stage)
        self.assertEqual(validation_stage['status'], 'failed')
```

## Best Practices

### 1. Error Handling

```python
class RobustAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process with comprehensive error handling"""
        try:
            # Validate inputs
            self.validate_inputs(inputs)
            
            # Process data
            result = self.process_data(inputs)
            
            # Validate output
            self.validate_output(result)
            
            return result
            
        except ValueError as e:
            self.log_error(f"Validation error: {str(e)}")
            return {'error': 'validation_failed', 'message': str(e)}
        except Exception as e:
            self.log_error(f"Processing error: {str(e)}")
            return {'error': 'processing_failed', 'message': str(e)}
    
    def validate_inputs(self, inputs: Dict[str, Any]):
        """Validate input data"""
        required_fields = self.context.get('required_fields', [])
        
        for field in required_fields:
            if field not in inputs:
                raise ValueError(f"Required field missing: {field}")
    
    def validate_output(self, output: Any):
        """Validate output data"""
        if output is None:
            raise ValueError("Output cannot be None")
        
        if isinstance(output, dict) and 'error' in output:
            raise ValueError(f"Processing resulted in error: {output['error']}")
```

### 2. Logging and Monitoring

```python
class MonitoredAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process with comprehensive monitoring"""
        start_time = time.time()
        
        # Log processing start
        self.log_info(f"Starting processing with inputs: {inputs}")
        
        try:
            result = self.process_data(inputs)
            
            # Log success
            duration = time.time() - start_time
            self.log_info(f"Processing completed successfully in {duration:.3f}s")
            
            # Add monitoring metadata
            if isinstance(result, dict):
                result['_monitoring'] = {
                    'duration': duration,
                    'timestamp': datetime.now().isoformat(),
                    'agent': self.name
                }
            
            return result
            
        except Exception as e:
            # Log error with context
            duration = time.time() - start_time
            self.log_error(f"Processing failed after {duration:.3f}s: {str(e)}")
            
            return {
                'error': str(e),
                '_monitoring': {
                    'duration': duration,
                    'timestamp': datetime.now().isoformat(),
                    'agent': self.name,
                    'failed': True
                }
            }
```

