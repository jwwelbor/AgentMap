---
sidebar_position: 2
title: Agent Development Guide
description: Comprehensive guide to developing custom agents in AgentMap with advanced patterns, best practices, and integration strategies.
keywords: [agent development, custom agents, AgentMap development, agent patterns, agent architecture, advanced agents]
---

# Advanced Agent Development Guide

This comprehensive guide covers advanced agent development patterns in AgentMap, including sophisticated architectures, performance optimization, and integration strategies for building production-ready agent systems.

## Agent Architecture Patterns

### 1. Pipeline Agents

Pipeline agents process data through a series of stages, each handling a specific transformation:

```python
from agentmap.agents import BaseAgent
from typing import List, Dict, Any, Callable

class PipelineAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.pipeline_stages = []
        self.stage_configs = {}
    
    def add_stage(self, stage_name: str, processor: Callable, config: Dict = None):
        """Add a processing stage to the pipeline"""
        self.pipeline_stages.append(stage_name)
        self.stage_configs[stage_name] = {
            'processor': processor,
            'config': config or {}
        }
    
    def execute(self, input_data, context=None):
        """Execute all pipeline stages in sequence"""
        current_data = input_data
        execution_trace = []
        
        for stage_name in self.pipeline_stages:
            stage_config = self.stage_configs[stage_name]
            processor = stage_config['processor']
            config = stage_config['config']
            
            try:
                # Execute stage
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
                if context and context.get('stop_on_failure', True):
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
    def __init__(self, services=None):
        super().__init__(services)
        
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
    def __init__(self, services=None):
        super().__init__(services)
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
    
    def execute(self, input_data, context=None):
        """Execute state machine logic"""
        self.state_data['input'] = input_data
        self.state_data['context'] = context or {}
        
        max_iterations = context.get('max_iterations', 10) if context else 10
        iterations = 0
        
        while iterations < max_iterations and self.current_state != AgentState.COMPLETED:
            try:
                # Execute current state handler
                result = self.execute_current_state()
                
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
    
    def execute_current_state(self) -> Dict[str, Any]:
        """Execute handler for current state"""
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
            self.logger.info(f"Transitioned to state: {new_state.value}")
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
        context = self.state_data.get('context', {})
        additional_input = context.get('additional_input')
        
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

### 3. Actor Model Agents

Actor model agents enable concurrent processing with message passing:

```python
import asyncio
import uuid
from asyncio import Queue
from typing import Dict, Any, Callable

class ActorMessage:
    def __init__(self, sender: str, receiver: str, message_type: str, data: Any, reply_to: str = None):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.receiver = receiver
        self.message_type = message_type
        self.data = data
        self.reply_to = reply_to
        self.timestamp = datetime.now().isoformat()

class ActorAgent(BaseAgent):
    def __init__(self, actor_id: str, services=None):
        super().__init__(services)
        self.actor_id = actor_id
        self.message_queue = Queue()
        self.message_handlers = {}
        self.actor_registry = {}
        self.running = False
        self.setup_message_handlers()
    
    def setup_message_handlers(self):
        """Setup message type handlers"""
        self.message_handlers = {
            'process_data': self.handle_process_data,
            'get_status': self.handle_get_status,
            'shutdown': self.handle_shutdown,
            'ping': self.handle_ping
        }
    
    async def start(self):
        """Start the actor message processing loop"""
        self.running = True
        await self.message_processing_loop()
    
    async def stop(self):
        """Stop the actor"""
        self.running = False
    
    async def message_processing_loop(self):
        """Main message processing loop"""
        while self.running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self.process_message(message)
            except asyncio.TimeoutError:
                # No message received, continue loop
                continue
            except Exception as e:
                self.logger.error(f"Error processing message: {str(e)}")
    
    async def process_message(self, message: ActorMessage):
        """Process received message"""
        handler = self.message_handlers.get(message.message_type)
        
        if handler:
            try:
                response = await handler(message)
                
                # Send response if reply_to is specified
                if message.reply_to and response:
                    reply_message = ActorMessage(
                        sender=self.actor_id,
                        receiver=message.reply_to,
                        message_type=f"{message.message_type}_response",
                        data=response
                    )
                    await self.send_message(reply_message)
                    
            except Exception as e:
                self.logger.error(f"Error handling message {message.message_type}: {str(e)}")
                
                # Send error response
                if message.reply_to:
                    error_message = ActorMessage(
                        sender=self.actor_id,
                        receiver=message.reply_to,
                        message_type="error",
                        data={'error': str(e), 'original_message_id': message.id}
                    )
                    await self.send_message(error_message)
        else:
            self.logger.warning(f"No handler for message type: {message.message_type}")
    
    async def send_message(self, message: ActorMessage):
        """Send message to another actor"""
        target_actor = self.actor_registry.get(message.receiver)
        
        if target_actor:
            await target_actor.receive_message(message)
        else:
            self.logger.error(f"Actor not found: {message.receiver}")
    
    async def receive_message(self, message: ActorMessage):
        """Receive message from another actor"""
        await self.message_queue.put(message)
    
    def register_actor(self, actor_id: str, actor: 'ActorAgent'):
        """Register another actor for communication"""
        self.actor_registry[actor_id] = actor
    
    # Message Handlers
    async def handle_process_data(self, message: ActorMessage) -> Dict[str, Any]:
        """Handle data processing message"""
        data = message.data
        
        # Simulate processing
        await asyncio.sleep(0.1)  # Simulate async work
        
        processed_data = f"Processed by {self.actor_id}: {data}"
        
        return {
            'processed_data': processed_data,
            'processor': self.actor_id,
            'processing_time': 0.1
        }
    
    async def handle_get_status(self, message: ActorMessage) -> Dict[str, Any]:
        """Handle status request message"""
        return {
            'actor_id': self.actor_id,
            'status': 'running' if self.running else 'stopped',
            'queue_size': self.message_queue.qsize(),
            'registered_actors': list(self.actor_registry.keys())
        }
    
    async def handle_shutdown(self, message: ActorMessage) -> Dict[str, Any]:
        """Handle shutdown message"""
        await self.stop()
        return {'status': 'shutting_down'}
    
    async def handle_ping(self, message: ActorMessage) -> Dict[str, Any]:
        """Handle ping message"""
        return {'pong': True, 'timestamp': datetime.now().isoformat()}
    
    def execute(self, input_data, context=None):
        """Synchronous interface for AgentMap integration"""
        return asyncio.run(self.async_execute(input_data, context))
    
    async def async_execute(self, input_data, context=None):
        """Asynchronous execution method"""
        # Start actor if not running
        if not self.running:
            asyncio.create_task(self.start())
        
        # Create and send processing message to self
        message = ActorMessage(
            sender="external",
            receiver=self.actor_id,
            message_type="process_data",
            data=input_data,
            reply_to="external"
        )
        
        # Send message and wait for response
        await self.receive_message(message)
        
        # Wait for response (simplified - in production use proper response handling)
        await asyncio.sleep(0.2)
        
        return {
            'actor_id': self.actor_id,
            'processed': True,
            'input_data': input_data
        }

# Actor System Manager
class ActorSystem:
    def __init__(self):
        self.actors = {}
        self.running = False
    
    async def create_actor(self, actor_id: str, actor_class: type = ActorAgent, **kwargs) -> ActorAgent:
        """Create and register new actor"""
        actor = actor_class(actor_id, **kwargs)
        self.actors[actor_id] = actor
        
        # Register all existing actors with the new actor
        for existing_id, existing_actor in self.actors.items():
            if existing_id != actor_id:
                actor.register_actor(existing_id, existing_actor)
                existing_actor.register_actor(actor_id, actor)
        
        return actor
    
    async def start_all_actors(self):
        """Start all actors in the system"""
        self.running = True
        tasks = []
        
        for actor in self.actors.values():
            task = asyncio.create_task(actor.start())
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all_actors(self):
        """Stop all actors in the system"""
        self.running = False
        
        for actor in self.actors.values():
            await actor.stop()
    
    async def broadcast_message(self, message_type: str, data: Any, sender: str = "system"):
        """Broadcast message to all actors"""
        for actor_id, actor in self.actors.items():
            message = ActorMessage(
                sender=sender,
                receiver=actor_id,
                message_type=message_type,
                data=data
            )
            await actor.receive_message(message)
    
    def get_actor(self, actor_id: str) -> Optional[ActorAgent]:
        """Get actor by ID"""
        return self.actors.get(actor_id)
```

## Advanced Integration Patterns

### 1. Service Mesh Integration

```python
class ServiceMeshAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.service_registry = self.get_service('service_registry')
        self.circuit_breaker = self.get_service('circuit_breaker')
        self.load_balancer = self.get_service('load_balancer')
        self.service_discovery = self.get_service('service_discovery')
    
    def execute(self, input_data, context=None):
        """Execute with service mesh integration"""
        service_name = context.get('target_service')
        
        if not service_name:
            return {'error': 'No target service specified'}
        
        try:
            # Service discovery
            service_instances = self.service_discovery.discover(service_name)
            
            if not service_instances:
                return {'error': f'No instances found for service: {service_name}'}
            
            # Load balancing
            selected_instance = self.load_balancer.select_instance(service_instances)
            
            # Circuit breaker check
            if not self.circuit_breaker.can_execute(service_name):
                return {'error': f'Circuit breaker open for service: {service_name}'}
            
            # Execute service call
            result = self.call_service(selected_instance, input_data, context)
            
            # Record success
            self.circuit_breaker.record_success(service_name)
            
            return result
            
        except Exception as e:
            # Record failure
            self.circuit_breaker.record_failure(service_name)
            return {'error': f'Service call failed: {str(e)}'}
    
    def call_service(self, service_instance: Dict, data: Any, context: Dict) -> Dict:
        """Call external service"""
        # Implementation depends on service type (HTTP, gRPC, etc.)
        # This is a simplified example
        
        import requests
        
        url = f"http://{service_instance['host']}:{service_instance['port']}{service_instance['path']}"
        
        response = requests.post(url, json={
            'data': data,
            'context': context
        }, timeout=context.get('timeout', 30))
        
        response.raise_for_status()
        return response.json()
```

### 2. Event-Driven Architecture

```python
import asyncio
from typing import List, Callable

class EventDrivenAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.event_bus = self.get_service('event_bus')
        self.event_handlers = {}
        self.subscriptions = []
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Setup event type handlers"""
        self.event_handlers = {
            'data_received': self.handle_data_received,
            'processing_complete': self.handle_processing_complete,
            'error_occurred': self.handle_error_occurred
        }
    
    def subscribe_to_events(self, event_types: List[str]):
        """Subscribe to specific event types"""
        for event_type in event_types:
            self.event_bus.subscribe(event_type, self.handle_event)
            self.subscriptions.append(event_type)
    
    def publish_event(self, event_type: str, data: Any, metadata: Dict = None):
        """Publish event to event bus"""
        event = {
            'type': event_type,
            'data': data,
            'metadata': metadata or {},
            'publisher': self.__class__.__name__,
            'timestamp': datetime.now().isoformat()
        }
        
        self.event_bus.publish(event_type, event)
    
    def handle_event(self, event: Dict):
        """Handle incoming event"""
        event_type = event.get('type')
        handler = self.event_handlers.get(event_type)
        
        if handler:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"Error handling event {event_type}: {str(e)}")
                
                # Publish error event
                self.publish_event('error_occurred', {
                    'original_event': event,
                    'error': str(e),
                    'handler': self.__class__.__name__
                })
    
    def execute(self, input_data, context=None):
        """Execute with event-driven processing"""
        # Publish start event
        self.publish_event('processing_started', {
            'input_data': input_data,
            'agent': self.__class__.__name__
        })
        
        try:
            # Process data
            result = self.process_data(input_data, context)
            
            # Publish completion event
            self.publish_event('processing_complete', {
                'result': result,
                'agent': self.__class__.__name__
            })
            
            return result
            
        except Exception as e:
            # Publish error event
            self.publish_event('error_occurred', {
                'error': str(e),
                'input_data': input_data,
                'agent': self.__class__.__name__
            })
            raise
    
    def process_data(self, data: Any, context: Dict) -> Any:
        """Override in subclasses for specific processing logic"""
        return f"Processed: {data}"
    
    # Event Handlers
    def handle_data_received(self, event: Dict):
        """Handle data received event"""
        data = event.get('data')
        self.logger.info(f"Received data: {data}")
    
    def handle_processing_complete(self, event: Dict):
        """Handle processing complete event"""
        result = event.get('data', {}).get('result')
        self.logger.info(f"Processing completed with result: {result}")
    
    def handle_error_occurred(self, event: Dict):
        """Handle error event"""
        error = event.get('data', {}).get('error')
        self.logger.error(f"Error event received: {error}")
```

### 3. Microservices Integration

```python
class MicroserviceAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.api_gateway = self.get_service('api_gateway')
        self.service_registry = self.get_service('service_registry')
        self.auth_service = self.get_service('auth_service')
        self.monitoring = self.get_service('monitoring')
    
    def execute(self, input_data, context=None):
        """Execute with microservices integration"""
        
        # Start monitoring
        trace_id = self.monitoring.start_trace(self.__class__.__name__)
        
        try:
            # Authentication
            auth_token = self.authenticate(context)
            
            # Process through microservices
            result = self.process_through_services(input_data, auth_token, context)
            
            # End monitoring
            self.monitoring.end_trace(trace_id, 'success')
            
            return result
            
        except Exception as e:
            self.monitoring.end_trace(trace_id, 'error', str(e))
            raise
    
    def authenticate(self, context: Dict) -> str:
        """Authenticate with auth service"""
        credentials = context.get('credentials')
        
        if not credentials:
            raise Exception("No credentials provided")
        
        auth_response = self.auth_service.authenticate(credentials)
        
        if not auth_response.get('success'):
            raise Exception("Authentication failed")
        
        return auth_response.get('token')
    
    def process_through_services(self, data: Any, auth_token: str, context: Dict) -> Dict:
        """Process data through multiple microservices"""
        
        # Service call chain
        services_chain = context.get('services_chain', [
            'validation-service',
            'processing-service',
            'enrichment-service'
        ])
        
        current_data = data
        results = []
        
        for service_name in services_chain:
            service_result = self.call_microservice(
                service_name, 
                current_data, 
                auth_token,
                context
            )
            
            results.append({
                'service': service_name,
                'result': service_result
            })
            
            # Use output as input for next service
            current_data = service_result.get('output', current_data)
        
        return {
            'final_result': current_data,
            'service_results': results,
            'services_called': len(services_chain)
        }
    
    def call_microservice(self, service_name: str, data: Any, auth_token: str, context: Dict) -> Dict:
        """Call individual microservice"""
        
        # Get service endpoint from registry
        service_info = self.service_registry.get_service(service_name)
        
        if not service_info:
            raise Exception(f"Service not found: {service_name}")
        
        # Prepare request
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid.uuid4())
        }
        
        payload = {
            'data': data,
            'context': context,
            'metadata': {
                'caller': self.__class__.__name__,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # Make API call through gateway
        response = self.api_gateway.call(
            service_name=service_name,
            endpoint=service_info['endpoint'],
            method='POST',
            headers=headers,
            data=payload,
            timeout=context.get('service_timeout', 30)
        )
        
        if response.status_code != 200:
            raise Exception(f"Service call failed: {response.status_code}")
        
        return response.json()
```

## Performance Optimization

### 1. Caching Strategies

```python
from functools import wraps
import hashlib
import pickle

class CachingAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.cache_service = self.get_service('cache')
        self.cache_config = {
            'default_ttl': 3600,  # 1 hour
            'max_cache_size': 1000,
            'cache_enabled': True
        }
    
    def cache_key(self, input_data: Any, context: Dict = None) -> str:
        """Generate cache key from input data and context"""
        
        # Create deterministic hash from input
        if isinstance(input_data, (dict, list)):
            data_str = json.dumps(input_data, sort_keys=True)
        else:
            data_str = str(input_data)
        
        context_str = json.dumps(context or {}, sort_keys=True)
        combined = f"{data_str}:{context_str}:{self.__class__.__name__}"
        
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get_from_cache(self, cache_key: str) -> Any:
        """Get result from cache"""
        if not self.cache_config['cache_enabled']:
            return None
        
        if self.cache_service:
            return self.cache_service.get(cache_key)
        else:
            # Use in-memory cache fallback
            return getattr(self, '_memory_cache', {}).get(cache_key)
    
    def store_in_cache(self, cache_key: str, result: Any, ttl: int = None):
        """Store result in cache"""
        if not self.cache_config['cache_enabled']:
            return
        
        ttl = ttl or self.cache_config['default_ttl']
        
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl)
        else:
            # Use in-memory cache fallback
            if not hasattr(self, '_memory_cache'):
                self._memory_cache = {}
            
            self._memory_cache[cache_key] = result
            
            # Simple cache size management
            if len(self._memory_cache) > self.cache_config['max_cache_size']:
                # Remove oldest entries (simplified LRU)
                keys_to_remove = list(self._memory_cache.keys())[:10]
                for key in keys_to_remove:
                    del self._memory_cache[key]
    
    def execute(self, input_data, context=None):
        """Execute with caching"""
        
        # Generate cache key
        cache_key = self.cache_key(input_data, context)
        
        # Try to get from cache
        cached_result = self.get_from_cache(cache_key)
        
        if cached_result is not None:
            self.logger.info(f"Cache hit for key: {cache_key}")
            cached_result['_cache_hit'] = True
            return cached_result
        
        # Cache miss - execute normally
        self.logger.info(f"Cache miss for key: {cache_key}")
        result = self.process_data(input_data, context)
        
        # Store in cache
        result['_cache_hit'] = False
        self.store_in_cache(cache_key, result)
        
        return result
    
    def process_data(self, data: Any, context: Dict) -> Dict:
        """Override in subclasses for specific processing logic"""
        return {'processed_data': f"Processed: {data}"}

def cached_method(ttl: int = 3600, cache_key_func: Callable = None):
    """Decorator for caching method results"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(self, *args, **kwargs)
            else:
                # Default cache key generation
                key_data = f"{func.__name__}:{args}:{kwargs}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try cache
            if hasattr(self, 'get_from_cache'):
                cached_result = self.get_from_cache(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Execute and cache
            result = func(self, *args, **kwargs)
            
            if hasattr(self, 'store_in_cache'):
                self.store_in_cache(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator
```

### 2. Parallel Processing

```python
import concurrent.futures
import multiprocessing
from typing import List, Callable

class ParallelProcessingAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.max_workers = multiprocessing.cpu_count()
        self.chunk_size = 100
    
    def execute(self, input_data, context=None):
        """Execute with parallel processing"""
        
        processing_mode = context.get('processing_mode', 'threads')  # threads, processes, async
        max_workers = context.get('max_workers', self.max_workers)
        chunk_size = context.get('chunk_size', self.chunk_size)
        
        if isinstance(input_data, list) and len(input_data) > chunk_size:
            return self.process_large_dataset(input_data, processing_mode, max_workers, chunk_size)
        else:
            return self.process_single_item(input_data, context)
    
    def process_large_dataset(self, data_list: List, mode: str, max_workers: int, chunk_size: int) -> Dict:
        """Process large dataset with parallel processing"""
        
        # Split data into chunks
        chunks = [data_list[i:i + chunk_size] for i in range(0, len(data_list), chunk_size)]
        
        if mode == 'threads':
            return self.process_with_threads(chunks, max_workers)
        elif mode == 'processes':
            return self.process_with_processes(chunks, max_workers)
        elif mode == 'async':
            return asyncio.run(self.process_with_async(chunks, max_workers))
        else:
            raise ValueError(f"Unknown processing mode: {mode}")
    
    def process_with_threads(self, chunks: List[List], max_workers: int) -> Dict:
        """Process chunks using thread pool"""
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(self.process_chunk, chunk): i 
                for i, chunk in enumerate(chunks)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    result = future.result()
                    results.append({
                        'chunk_index': chunk_index,
                        'result': result,
                        'status': 'success'
                    })
                except Exception as e:
                    results.append({
                        'chunk_index': chunk_index,
                        'error': str(e),
                        'status': 'error'
                    })
        
        return self.aggregate_results(results)
    
    def process_with_processes(self, chunks: List[List], max_workers: int) -> Dict:
        """Process chunks using process pool"""
        
        results = []
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(process_chunk_static, chunk): i 
                for i, chunk in enumerate(chunks)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    result = future.result()
                    results.append({
                        'chunk_index': chunk_index,
                        'result': result,
                        'status': 'success'
                    })
                except Exception as e:
                    results.append({
                        'chunk_index': chunk_index,
                        'error': str(e),
                        'status': 'error'
                    })
        
        return self.aggregate_results(results)
    
    async def process_with_async(self, chunks: List[List], max_workers: int) -> Dict:
        """Process chunks using async processing"""
        
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_chunk_async(chunk: List, index: int) -> Dict:
            async with semaphore:
                try:
                    # Simulate async processing
                    await asyncio.sleep(0.1)
                    result = self.process_chunk(chunk)
                    return {
                        'chunk_index': index,
                        'result': result,
                        'status': 'success'
                    }
                except Exception as e:
                    return {
                        'chunk_index': index,
                        'error': str(e),
                        'status': 'error'
                    }
        
        # Process all chunks concurrently
        tasks = [process_chunk_async(chunk, i) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)
        
        return self.aggregate_results(results)
    
    def process_chunk(self, chunk: List) -> Dict:
        """Process individual chunk - override in subclasses"""
        
        processed_items = []
        
        for item in chunk:
            processed_item = self.process_single_item(item)
            processed_items.append(processed_item)
        
        return {
            'processed_items': processed_items,
            'chunk_size': len(chunk),
            'processing_time': 0.1  # Simulated
        }
    
    def process_single_item(self, item: Any, context: Dict = None) -> Any:
        """Process single item - override in subclasses"""
        return f"Processed: {item}"
    
    def aggregate_results(self, results: List[Dict]) -> Dict:
        """Aggregate results from parallel processing"""
        
        successful_results = [r for r in results if r['status'] == 'success']
        failed_results = [r for r in results if r['status'] == 'error']
        
        # Combine all processed items
        all_processed_items = []
        for result in successful_results:
            if 'result' in result and 'processed_items' in result['result']:
                all_processed_items.extend(result['result']['processed_items'])
        
        return {
            'total_chunks': len(results),
            'successful_chunks': len(successful_results),
            'failed_chunks': len(failed_results),
            'total_processed_items': len(all_processed_items),
            'processed_items': all_processed_items,
            'errors': [r['error'] for r in failed_results]
        }

# Static function for process pool (must be at module level)
def process_chunk_static(chunk: List) -> Dict:
    """Static function for process pool processing"""
    processed_items = [f"Processed: {item}" for item in chunk]
    
    return {
        'processed_items': processed_items,
        'chunk_size': len(chunk),
        'processing_time': 0.1
    }
```

## Testing and Quality Assurance

### 1. Agent Testing Framework

```python
import unittest
from unittest.mock import Mock, patch, MagicMock
import pytest

class AgentTestCase(unittest.TestCase):
    """Base test case for agent testing"""
    
    def setUp(self):
        """Setup test environment"""
        self.mock_services = self.create_mock_services()
        self.agent = self.create_agent_instance()
        
    def create_mock_services(self) -> Dict[str, Mock]:
        """Create mock services for testing"""
        return {
            'database': Mock(),
            'cache': Mock(),
            'logger': Mock(),
            'api_client': Mock()
        }
    
    def create_agent_instance(self):
        """Create agent instance for testing - override in subclasses"""
        return BaseAgent(services=self.mock_services)
    
    def assert_agent_execution_successful(self, result: Dict):
        """Assert that agent execution was successful"""
        self.assertIsInstance(result, dict)
        self.assertNotIn('error', result)
    
    def assert_agent_execution_failed(self, result: Dict, expected_error: str = None):
        """Assert that agent execution failed"""
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)
        
        if expected_error:
            self.assertIn(expected_error, str(result['error']))

class TestDataProcessingAgent(AgentTestCase):
    """Test case for DataProcessingAgent"""
    
    def create_agent_instance(self):
        return DataProcessingPipeline(services=self.mock_services)
    
    def test_valid_data_processing(self):
        """Test processing with valid data"""
        valid_data = {
            'id': '123',
            'name': 'Test Item',
            'value': 100
        }
        
        result = self.agent.execute(valid_data)
        
        self.assert_agent_execution_successful(result)
        self.assertIn('result', result)
        self.assertEqual(result['successful_stages'], result['total_stages'])
    
    def test_invalid_data_processing(self):
        """Test processing with invalid data"""
        invalid_data = {
            'name': 'Test Item'
            # Missing required 'id' field
        }
        
        result = self.agent.execute(invalid_data)
        
        # Should fail at validation stage
        self.assertIn('execution_trace', result)
        validation_stage = next(
            (stage for stage in result['execution_trace'] if stage['stage'] == 'validate'), 
            None
        )
        self.assertIsNotNone(validation_stage)
        self.assertEqual(validation_stage['status'], 'failed')
    
    def test_stage_failure_handling(self):
        """Test handling of stage failures"""
        # Mock a stage to fail
        original_clean_data = self.agent.clean_data
        
        def failing_clean_data(data, config):
            raise Exception("Simulated cleaning failure")
        
        self.agent.clean_data = failing_clean_data
        
        valid_data = {'id': '123', 'name': 'Test'}
        result = self.agent.execute(valid_data, context={'stop_on_failure': True})
        
        # Should stop at clean stage
        self.assertLess(result['successful_stages'], result['total_stages'])
        
        # Restore original method
        self.agent.clean_data = original_clean_data
    
    @patch('time.time')
    def test_performance_metrics(self, mock_time):
        """Test performance metrics collection"""
        # Mock time progression
        mock_time.side_effect = [0, 0.1, 0.1, 0.2, 0.2, 0.3, 0.3, 0.4]
        
        data = {'id': '123', 'name': 'Test'}
        result = self.agent.execute(data)
        
        # Check that duration is recorded for each stage
        for stage_trace in result['execution_trace']:
            if stage_trace['status'] == 'success':
                self.assertIn('duration', stage_trace)
                self.assertIsInstance(stage_trace['duration'], float)

class AgentIntegrationTest(unittest.TestCase):
    """Integration tests for agent workflows"""
    
    def setUp(self):
        """Setup integration test environment"""
        from agentmap import AgentMap
        
        self.agent_map = AgentMap()
        self.register_test_agents()
    
    def register_test_agents(self):
        """Register agents for integration testing"""
        self.agent_map.register_agent_type('data_processing', DataProcessingPipeline)
        self.agent_map.register_agent_type('state_machine', StateMachineAgent)
    
    def test_workflow_execution(self):
        """Test complete workflow execution"""
        
        test_csv = """GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
TestWorkflow,ProcessData,,Process input data,data_processing,ValidateResult,ErrorHandler,collection,processed_data,
TestWorkflow,ValidateResult,,Validate processing result,state_machine,End,ErrorHandler,processed_data,validation_result,
TestWorkflow,End,,Workflow complete,echo,,,validation_result,final_result,Processing completed successfully!
TestWorkflow,ErrorHandler,,Handle errors,echo,End,,error,error_message,Error: {error}"""
        
        # Save test CSV
        with open('test_workflow.csv', 'w') as f:
            f.write(test_csv)
        
        try:
            # Execute workflow
            result = self.agent_map.execute_csv('test_workflow.csv', initial_input={
                'id': '123',
                'name': 'Test Data',
                'value': 42
            })
            
            self.assertIsNotNone(result)
            
        finally:
            # Cleanup
            import os
            if os.path.exists('test_workflow.csv'):
                os.remove('test_workflow.csv')

# Pytest fixtures for agent testing
@pytest.fixture
def mock_services():
    """Pytest fixture for mock services"""
    return {
        'database': Mock(),
        'cache': Mock(),
        'logger': Mock(),
        'api_client': Mock()
    }

@pytest.fixture
def data_processing_agent(mock_services):
    """Pytest fixture for data processing agent"""
    return DataProcessingPipeline(services=mock_services)

# Pytest test functions
def test_agent_initialization(mock_services):
    """Test agent initialization with services"""
    agent = BaseAgent(services=mock_services)
    
    assert agent.services is not None
    assert hasattr(agent, 'logger')

def test_pipeline_agent_stages(data_processing_agent):
    """Test pipeline agent stage configuration"""
    assert len(data_processing_agent.pipeline_stages) > 0
    assert 'validate' in data_processing_agent.pipeline_stages
    assert 'clean' in data_processing_agent.pipeline_stages

@pytest.mark.parametrize("input_data,expected_success", [
    ({'id': '123', 'name': 'Valid'}, True),
    ({'name': 'Invalid'}, False),  # Missing id
    ({}, False),  # Empty data
])
def test_validation_scenarios(data_processing_agent, input_data, expected_success):
    """Test various validation scenarios"""
    result = data_processing_agent.execute(input_data)
    
    if expected_success:
        assert result['successful_stages'] == result['total_stages']
    else:
        assert result['successful_stages'] < result['total_stages']

# Performance testing
class AgentPerformanceTest(unittest.TestCase):
    """Performance tests for agents"""
    
    def test_processing_latency(self):
        """Test agent processing latency"""
        agent = DataProcessingPipeline()
        
        import time
        
        start_time = time.time()
        result = agent.execute({'id': '123', 'name': 'Performance Test'})
        end_time = time.time()
        
        latency = end_time - start_time
        
        # Assert latency is within acceptable bounds
        self.assertLess(latency, 1.0)  # Should complete within 1 second
        
        # Check execution trace for stage-level latency
        total_stage_time = sum(
            stage['duration'] for stage in result['execution_trace'] 
            if 'duration' in stage
        )
        
        self.assertLess(total_stage_time, latency)  # Stage time should be less than total time
    
    def test_memory_usage(self):
        """Test agent memory usage"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        agent = DataProcessingPipeline()
        
        # Process large dataset
        large_data = [{'id': str(i), 'name': f'Item {i}'} for i in range(1000)]
        result = agent.execute(large_data)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for this test)
        self.assertLess(memory_increase, 100 * 1024 * 1024)
    
    def test_concurrent_execution(self):
        """Test concurrent agent execution"""
        import threading
        import queue
        
        agent = DataProcessingPipeline()
        results_queue = queue.Queue()
        
        def execute_agent(data):
            result = agent.execute(data)
            results_queue.put(result)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            data = {'id': str(i), 'name': f'Concurrent Test {i}'}
            thread = threading.Thread(target=execute_agent, args=(data,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # All executions should complete successfully
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertEqual(result['successful_stages'], result['total_stages'])

if __name__ == '__main__':
    # Run unittest tests
    unittest.main()
```

This comprehensive agent development guide provides advanced patterns and techniques for building sophisticated agents in AgentMap. The patterns can be combined and customized based on specific requirements.

For deployment and production considerations, see the [Security Guide](/docs/guides/advanced/security) and [Performance Optimization Guide](/docs/guides/advanced/performance).
