# src/agentmap/validation/models.py
"""
Pydantic models for validating CSV and configuration files.
"""
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator


class CSVRowModel(BaseModel):
    """Pydantic model for validating individual CSV rows."""
    
    # Required fields
    GraphName: str = Field(min_length=1, description="Name of the graph")
    Node: str = Field(min_length=1, description="Name of the node")
    
    # Optional core fields
    AgentType: Optional[str] = Field(default=None, description="Type of agent")
    Prompt: Optional[str] = Field(default=None, description="Agent prompt or instructions")
    Description: Optional[str] = Field(default=None, description="Node description")
    
    # Input/Output fields
    Input_Fields: Optional[str] = Field(default=None, description="Pipe-separated input field names")
    Output_Field: Optional[str] = Field(default=None, description="Output field name")
    Context: Optional[str] = Field(default=None, description="Additional context for the agent")
    
    # Routing fields
    Edge: Optional[str] = Field(default=None, description="Direct edge target")
    Success_Next: Optional[str] = Field(default=None, description="Target node on success")
    Failure_Next: Optional[str] = Field(default=None, description="Target node on failure")
    
    @field_validator('GraphName', 'Node')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        """Validate required fields are not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or just whitespace")
        return v.strip()
    
    @field_validator('Input_Fields')
    @classmethod
    def validate_input_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate input fields format (pipe-separated)."""
        if v is None:
            return v
        
        # Split by pipe and validate each field name
        fields = [f.strip() for f in v.split('|') if f.strip()]
        
        # Check for valid field names (basic validation)
        for field in fields:
            if not field.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid field name: '{field}'. Use alphanumeric characters, underscore, or dash only.")
        
        return '|'.join(fields)
    
    @field_validator('Output_Field')
    @classmethod
    def validate_output_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate output field name."""
        if v is None:
            return v
        
        v = v.strip()
        if v and not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Invalid output field name: '{v}'. Use alphanumeric characters, underscore, or dash only.")
        
        return v
    
    @model_validator(mode='after')
    def validate_routing_logic(self) -> 'CSVRowModel':
        """Validate routing logic constraints."""
        # Check for conflicting edge definitions
        has_direct_edge = bool(self.Edge)
        has_conditional_edges = bool(self.Success_Next or self.Failure_Next)
        
        if has_direct_edge and has_conditional_edges:
            raise ValueError(
                "Cannot have both Edge and Success/Failure_Next defined. "
                "Use either direct routing (Edge) or conditional routing (Success/Failure_Next)."
            )
        
        return self


class PathsConfigModel(BaseModel):
    """Validation model for paths configuration."""
    custom_agents: Optional[str] = Field(default="agentmap/agents/custom")
    functions: Optional[str] = Field(default="agentmap/functions") 
    compiled_graphs: Optional[str] = Field(default="compiled_graphs")


class LLMProviderConfigModel(BaseModel):
    """Validation model for individual LLM provider configuration."""
    api_key: Optional[str] = Field(default="")
    model: Optional[str] = Field(default=None)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    
    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        """Validate temperature is in reasonable range."""
        if v is not None and (v < 0.0 or v > 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v


class LLMConfigModel(BaseModel):
    """Validation model for LLM configuration section."""
    openai: Optional[LLMProviderConfigModel] = Field(default=None)
    anthropic: Optional[LLMProviderConfigModel] = Field(default=None)
    google: Optional[LLMProviderConfigModel] = Field(default=None)


class MemoryConfigModel(BaseModel):
    """Validation model for memory configuration."""
    enabled: Optional[bool] = Field(default=False)
    default_type: Optional[str] = Field(default="buffer")
    buffer_window_size: Optional[int] = Field(default=5, ge=1)
    max_token_limit: Optional[int] = Field(default=2000, ge=100)
    memory_key: Optional[str] = Field(default="conversation_memory")


class PromptsConfigModel(BaseModel):
    """Validation model for prompts configuration."""
    directory: Optional[str] = Field(default="prompts")
    registry_file: Optional[str] = Field(default="prompts/registry.yaml")
    enable_cache: Optional[bool] = Field(default=True)


class TrackingConfigModel(BaseModel):
    """Validation model for execution tracking configuration."""
    enabled: Optional[bool] = Field(default=True)
    track_outputs: Optional[bool] = Field(default=False)
    track_inputs: Optional[bool] = Field(default=False)


class SuccessPolicyConfigModel(BaseModel):
    """Validation model for success policy configuration."""
    type: Optional[str] = Field(default="all_nodes")
    critical_nodes: Optional[List[str]] = Field(default_factory=list)
    custom_function: Optional[str] = Field(default="")
    
    @field_validator('type')
    @classmethod
    def validate_policy_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate success policy type."""
        if v is not None:
            valid_types = ["all_nodes", "final_node", "critical_nodes", "custom"]
            if v not in valid_types:
                raise ValueError(f"Invalid success policy type: '{v}'. Must be one of: {valid_types}")
        return v


class ExecutionConfigModel(BaseModel):
    """Validation model for execution configuration."""
    tracking: Optional[TrackingConfigModel] = Field(default=None)
    success_policy: Optional[SuccessPolicyConfigModel] = Field(default=None)


class TracingConfigModel(BaseModel):
    """Validation model for tracing configuration."""
    enabled: Optional[bool] = Field(default=False)
    mode: Optional[str] = Field(default="langsmith")
    local_exporter: Optional[str] = Field(default="file")
    local_directory: Optional[str] = Field(default="./traces")
    project: Optional[str] = Field(default="your_project_name")
    langsmith_api_key: Optional[str] = Field(default="")
    trace_all: Optional[bool] = Field(default=False)
    trace_graphs: Optional[List[str]] = Field(default_factory=list)
    
    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        """Validate tracing mode."""
        if v is not None and v not in ["local", "langsmith"]:
            raise ValueError("Tracing mode must be 'local' or 'langsmith'")
        return v
    
    @field_validator('local_exporter')
    @classmethod
    def validate_local_exporter(cls, v: Optional[str]) -> Optional[str]:
        """Validate local exporter type."""
        if v is not None and v not in ["file", "csv"]:
            raise ValueError("Local exporter must be 'file' or 'csv'")
        return v


class ConfigModel(BaseModel):
    """Complete validation model for AgentMap configuration."""
    
    # Core settings
    csv_path: Optional[str] = Field(default="examples/SingleNodeGraph.csv")
    autocompile: Optional[bool] = Field(default=False)
    storage_config_path: Optional[str] = Field(default="storage_config.yaml")
    
    # Configuration sections
    paths: Optional[PathsConfigModel] = Field(default=None)
    llm: Optional[LLMConfigModel] = Field(default=None)
    memory: Optional[MemoryConfigModel] = Field(default=None)
    prompts: Optional[PromptsConfigModel] = Field(default=None)
    execution: Optional[ExecutionConfigModel] = Field(default=None)
    tracing: Optional[TracingConfigModel] = Field(default=None)
    
    # Allow additional fields for extensibility
    class Config:
        extra = "allow"  # Allow additional fields not defined in the model
    
    @field_validator('csv_path')
    @classmethod
    def validate_csv_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate CSV path format."""
        if v is not None and not v.endswith('.csv'):
            raise ValueError("CSV path must end with '.csv'")
        return v
