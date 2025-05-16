"""
Default configuration values for AgentMap.
"""
import os

def get_default_paths_config():
    """Get default path configuration."""
    return {
        "custom_agents": os.environ.get("AGENTMAP_CUSTOM_AGENTS_PATH", "agentmap/agents/custom"),
        "functions": os.environ.get("AGENTMAP_FUNCTIONS_PATH", "agentmap/functions"),
        "compiled_graphs": os.environ.get("AGENTMAP_COMPILED_GRAPHS_PATH", "compiled_graphs")
    }

def get_default_llm_config():
    """Get default LLM configuration."""
    return {
        "openai": {
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "model": os.environ.get("AGENTMAP_OPENAI_MODEL", "gpt-3.5-turbo"),
            "temperature": float(os.environ.get("AGENTMAP_OPENAI_TEMPERATURE", "0.7"))
        },
        "anthropic": {
            "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "model": os.environ.get("AGENTMAP_ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
            "temperature": float(os.environ.get("AGENTMAP_ANTHROPIC_TEMPERATURE", "0.7"))
        },
        "google": {
            "api_key": os.environ.get("GOOGLE_API_KEY", ""),
            "model": os.environ.get("AGENTMAP_GOOGLE_MODEL", "gemini-1.0-pro"),
            "temperature": float(os.environ.get("AGENTMAP_GOOGLE_TEMPERATURE", "0.7"))
        }
    }

def get_default_memory_config():
    """Get default memory configuration."""
    return {
        "enabled": False,
        "default_type": "buffer",
        "buffer_window_size": 5,
        "max_token_limit": 2000,
        "memory_key": "conversation_memory"
    }

def get_default_prompts_config():
    """Get default prompts configuration."""
    return {
        "directory": os.environ.get("AGENTMAP_PROMPTS_DIR", "prompts"),
        "registry_file": os.environ.get("AGENTMAP_PROMPT_REGISTRY", "prompts/registry.yaml"),
        "enable_cache": os.environ.get("AGENTMAP_PROMPT_CACHE", "true").lower() == "true"
    }

def get_default_execution_config():
    """Get default execution configuration."""
    return {
        # Execution tracking settings
        "tracking": {
            "enabled": os.environ.get("AGENTMAP_TRACKING_ENABLED", "true").lower() == "true",
            "track_outputs": os.environ.get("AGENTMAP_TRACKING_OUTPUTS", "false").lower() == "true",
            "track_inputs": os.environ.get("AGENTMAP_TRACKING_INPUTS", "false").lower() == "true",
        },
        # Success policy settings
        "success_policy": {
            "type": os.environ.get("AGENTMAP_SUCCESS_POLICY", "all_nodes"),  # Options: "all_nodes", "final_node", "critical_nodes", "custom"
            "critical_nodes": [],  # List of critical node names (for "critical_nodes" policy)
            "custom_function": "",  # For "custom" policy - module path to function
        }
    }

def get_default_config():
    """Get the complete default configuration."""
    return {
        "csv_path": os.environ.get("AGENTMAP_CSV_PATH", "examples/SingleNodeGraph.csv"),
        "autocompile": os.environ.get("AGENTMAP_AUTOCOMPILE", "false").lower() == "true",
        "storage_config_path": os.environ.get("AGENTMAP_STORAGE_CONFIG", "storage_config.yaml"),
        "paths": get_default_paths_config(),
        "llm": get_default_llm_config(),
        "memory": get_default_memory_config(),
        "prompts": get_default_prompts_config(),
        "execution": get_default_execution_config(),
        "tracing": get_default_tracing_config()
    }

def get_default_tracing_config():
    """Get default tracing configuration."""
    return {
        "enabled": os.environ.get("AGENTMAP_TRACING_ENABLED", "false").lower() == "true",
        "mode": os.environ.get("AGENTMAP_TRACING_MODE", "langsmith"),  # "local" or "langsmith"
        "local_exporter": os.environ.get("AGENTMAP_TRACING_EXPORTER", "file"),  # "file" or "csv"
        "local_directory": os.environ.get("AGENTMAP_TRACING_DIRECTORY", "./traces"),
        "project": os.environ.get("LANGCHAIN_PROJECT", "your_project_name"),
        "langsmith_api_key": os.environ.get("LANGCHAIN_API_KEY", ""),
        "trace_all": os.environ.get("AGENTMAP_TRACE_ALL", "false").lower() == "true",
        "trace_graphs": []  # List of graph names to trace
    }
