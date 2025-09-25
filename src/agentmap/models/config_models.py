from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# --- ConfigModel Definitions ---


class PathsConfigModel(BaseModel):
    custom_agents: Optional[str] = "agentmap/custom_agents"
    functions: Optional[str] = "agentmap/custom_functions"
    compiled_graphs: Optional[str] = "agentmap/compiled_graphs"


class LLMProviderConfigModel(BaseModel):
    api_key: Optional[str] = ""
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)


class LLMConfigModel(BaseModel):
    openai: Optional[LLMProviderConfigModel] = None
    anthropic: Optional[LLMProviderConfigModel] = None
    google: Optional[LLMProviderConfigModel] = None


class MemoryConfigModel(BaseModel):
    enabled: Optional[bool] = False
    default_type: Optional[str] = "buffer"
    buffer_window_size: Optional[int] = Field(default=5, ge=1)
    max_token_limit: Optional[int] = Field(default=2000, ge=100)
    memory_key: Optional[str] = "conversation_memory"


class PromptsConfigModel(BaseModel):
    directory: Optional[str] = "prompts"
    registry_file: Optional[str] = "prompts/registry.yaml"
    enable_cache: Optional[bool] = True


class TrackingConfigModel(BaseModel):
    enabled: Optional[bool] = True
    track_outputs: Optional[bool] = False
    track_inputs: Optional[bool] = False


class SuccessPolicyConfigModel(BaseModel):
    type: Optional[str] = "all_nodes"
    critical_nodes: Optional[List[str]] = []
    custom_function: Optional[str] = ""

    @field_validator("type")
    @classmethod
    def valid_policy(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["all_nodes", "final_node", "critical_nodes", "custom"]:
            raise ValueError(f"Invalid success policy type: '{v}'")
        return v


class ExecutionConfigModel(BaseModel):
    tracking: Optional[TrackingConfigModel] = None
    success_policy: Optional[SuccessPolicyConfigModel] = None


class TracingConfigModel(BaseModel):
    enabled: Optional[bool] = False
    mode: Optional[str] = "langsmith"
    local_exporter: Optional[str] = "file"
    local_directory: Optional[str] = "./traces"
    project: Optional[str] = "your_project_name"
    langsmith_api_key: Optional[str] = ""
    trace_all: Optional[bool] = False
    trace_graphs: Optional[List[str]] = []

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["local", "langsmith"]:
            raise ValueError("Tracing mode must be 'local' or 'langsmith'")
        return v

    @field_validator("local_exporter")
    @classmethod
    def valid_exporter(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["file", "csv"]:
            raise ValueError("Local exporter must be 'file' or 'csv'")
        return v


class ConfigModel(BaseModel):
    csv_path: Optional[str] = None
    storage_config_path: Optional[str] = None

    paths: Optional[PathsConfigModel] = None
    llm: Optional[LLMConfigModel] = None
    memory: Optional[MemoryConfigModel] = None
    prompts: Optional[PromptsConfigModel] = None
    execution: Optional[ExecutionConfigModel] = None
    tracing: Optional[TracingConfigModel] = None

    class Config:
        extra = "allow"

    @field_validator("csv_path")
    @classmethod
    def ensure_csv(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.endswith(".csv"):
            raise ValueError("CSV path must end with '.csv'")
        return v
