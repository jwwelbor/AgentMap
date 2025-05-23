# AgentMap Agent Contract

This document defines the interface and behavior that all agents in the AgentMap ecosystem must follow. This contract ensures extensibility and configurability without enforcing domain-specific implementation details.

## 🧩 Architecture Overview

```mermaid
flowchart TB
    subgraph "Agent Execution"
        A[BaseAgent.run] --> B[Extract Inputs]
        B --> C[Call process]
        C --> D[Set Output]
        D --> E[Return Updated State]
        
        C -.-> F[Error Handling]
        F --> G[Set Error]
        G --> E
    end
    
    subgraph "Agent Implementations"
        I[DefaultAgent] --> K[process]
        J[CustomAgent] --> L[process]
        M[EchoAgent] --> N[process]
    end
    
    A -.-> I
    A -.-> J
    A -.-> M
```

## 🧱 Base Requirements

### Class Definition
All agents must inherit from `BaseAgent` which defines the common interface:

```python
class BaseAgent:
    def __init__(self, name: str, prompt: str, context: dict = None):
        self.name = name
        self.prompt = prompt
        self.context = context or {}
        self.prompt_template = prompt
        
        # Extract input_fields and output_field from context if available
        self.input_fields = self.context.get("input_fields", [])
        self.output_field = self.context.get("output_field", "output")
        
        # Create state manager
        self.state_manager = StateManager(self.input_fields, self.output_field)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return an output value.
        Subclasses must implement this method.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Output value for the output_field
        """
        raise NotImplementedError("Subclasses must implement process()")
    
    def run(self, state: Any) -> Any:
        """
        Run the agent on the state, extracting inputs and setting outputs.
        
        Args:
            state: Current state object (can be dict, Pydantic model, etc.)
            
        Returns:
            Updated state with output field and success flag
        """
        # Extract inputs
        inputs = self.state_manager.get_inputs(state)
        
        try:
            # Process inputs to get output
            output = self.process(inputs)
            
            # Update state with output
            return self.state_manager.set_output(state, output, success=True)
        except Exception as e:
            # Handle errors
            error_msg = f"Error in {self.name}: {str(e)}"
            logger.error(error_msg)
            
            # Set error in state
            error_state = StateAdapter.set_value(state, "error", error_msg)
            return self.state_manager.set_output(error_state, None, success=False)
```

### Required Implementation

All agents **must** implement:
```python
def process(self, inputs: Dict[str, Any]) -> Any:
    """Process the inputs and return a result."""
```

This method takes a dictionary of extracted inputs and returns a value (or structure) that will be stored in the agent's output field.

## 🔁 State Management

### State Lifecycle

```mermaid
flowchart LR
    A[Initial State] --> B[Input Extraction]
    B --> C[Agent Processing]
    C --> D[Output Integration]
    D --> E[Updated State]
    
    C -.-> F[Error Handling]
    F --> G[Error Integration]
    G --> E
```

State flows through the system as follows:

1. **Input Extraction**: The `state_manager.get_inputs()` method extracts relevant fields from the state
2. **Agent Processing**: The agent's `process()` method transforms inputs to an output
3. **Output Integration**: The `state_manager.set_output()` method integrates the output into the state
4. **Success/Failure Handling**: The `last_action_success` flag is set based on processing outcome

### State Components

The state dictionary typically contains:
- Input fields from the initial state
- Output fields from each node's execution
- System fields like `last_action_success`
- Optional memory fields for stateful agents
- Error information when exceptions occur

## 🛠️ Configuration

### Constructor Parameters

- `name`: Node name from the graph
- `prompt`: A text prompt, which may be templated
- `context`: Additional configuration and settings

### Context Dictionary

The context dictionary can be used to provide configuration options:

- `input_fields`: List of input field names to extract from state
- `output_field`: Field name to store the agent's output
- Agent-specific configuration parameters

Example context:
```python
context = {
    "input_fields": ["query", "history"],
    "output_field": "response",
    "model": "gpt-3.5-turbo",
    "temperature": 0.7,
    "memory": {
        "type": "buffer",
        "memory_key": "chat_history"
    }
}
```

## 📋 Example Implementation

Here's a complete example of a simple agent implementation:

```python
class EchoAgent(BaseAgent):
    """Echo agent that simply returns input data unchanged."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Echo back the input data unchanged.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            The input data unchanged
        """
        logger.info(f"[EchoAgent] '{self.name}' received inputs: {inputs} and prompt: '{self.prompt}'")
        
        # If there are inputs, return the first one
        if inputs:
            # Return all inputs as a dictionary to maintain structure
            return inputs
        
        # Default return if no inputs
        return "No input provided to echo"
```

## ❗ Do Not:

- Do **not** override the `run` method unless you have a very specific reason
- Do **not** assume any specific keys exist in the `state`
- Do **not** modify `context` during execution
- Do **not** hardcode any data that could come from CSV or config
- Do **not** persist state between executions unless specifically implementing a memory module

## 🧪 Testability Tip

To test an agent, provide a minimal `context` and test the `process` method directly:

```python
def test_echo_agent():
    # Set up
    agent = EchoAgent("Echo", "{input}", {"input_fields": ["input"], "output_field": "echoed"})
    inputs = {"input": "Hello, world!"}
    
    # Test process method directly
    result = agent.process(inputs)
    
    # Verify
    assert result["input"] == "Hello, world!"
```

## 🔄 Integration Flow

```mermaid
sequenceDiagram
    participant Graph as GraphRunner
    participant State as StateManager
    participant Agent as Agent
    
    Graph->>State: Initialize state
    Graph->>Agent: Call run(state)
    Agent->>State: Extract inputs
    State-->>Agent: Input dictionary
    Agent->>Agent: Call process(inputs)
    Agent->>State: Set output & success flag
    State-->>Agent: Updated state
    Agent-->>Graph: Return updated state
    Graph->>Graph: Determine next node
```

The framework is responsible for:
1. Initializing the state
2. Passing state to the agent's `run` method
3. Determining the next node based on the agent's result

The agent is responsible for:
1. Extracting inputs from state
2. Processing inputs to generate an output
3. Integrating the output back into the state
4. Setting success/failure flags appropriately

## 📦 Framework Compliance Summary

| Component | Required By Agent | Provided By Framework |
|------------------|-------------------|------------------------|
| `name: str` | ✅ | ✅ from CSV |
| `prompt: str` | ✅ | ✅ from CSV |
| `context: dict` | ✅ | ✅ from loader/init |
| `state: dict` | ✅ | ✅ from graph runtime |
| `process()` implementation | ✅ | ❌ |
| `run()` implementation | ❌ | ✅ from BaseAgent |
| State management | ❌ | ✅ from StateManager |
| Error handling | ❌ | ✅ from BaseAgent |