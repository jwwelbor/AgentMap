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

def get_default_routing_config():
    """Get default routing configuration."""
    return {
        # Global routing settings
        "enabled": os.environ.get("AGENTMAP_ROUTING_ENABLED", "false").lower() == "true",
        
        # Provider × Complexity Matrix
        "routing_matrix": {
            "anthropic": {
                "low": os.environ.get("AGENTMAP_ANTHROPIC_LOW_MODEL", "claude-3-haiku-20240307"),
                "medium": os.environ.get("AGENTMAP_ANTHROPIC_MEDIUM_MODEL", "claude-3-sonnet-20240229"),
                "high": os.environ.get("AGENTMAP_ANTHROPIC_HIGH_MODEL", "claude-3-opus-20240229"),
                "critical": os.environ.get("AGENTMAP_ANTHROPIC_CRITICAL_MODEL", "claude-3-opus-20240229")
            },
            "openai": {
                "low": os.environ.get("AGENTMAP_OPENAI_LOW_MODEL", "gpt-3.5-turbo"),
                "medium": os.environ.get("AGENTMAP_OPENAI_MEDIUM_MODEL", "gpt-4-turbo"),
                "high": os.environ.get("AGENTMAP_OPENAI_HIGH_MODEL", "gpt-4"),
                "critical": os.environ.get("AGENTMAP_OPENAI_CRITICAL_MODEL", "gpt-4")
            },
            "google": {
                "low": os.environ.get("AGENTMAP_GOOGLE_LOW_MODEL", "gemini-1.0-pro"),
                "medium": os.environ.get("AGENTMAP_GOOGLE_MEDIUM_MODEL", "gemini-1.0-pro"),
                "high": os.environ.get("AGENTMAP_GOOGLE_HIGH_MODEL", "gemini-1.5-pro"),
                "critical": os.environ.get("AGENTMAP_GOOGLE_CRITICAL_MODEL", "gemini-1.5-pro")
            }
        },
        
        # Default task types
        "task_types": {
            "general": {
                "description": "General purpose tasks",
                "provider_preference": ["anthropic", "openai", "google"],
                "default_complexity": "medium",
                "complexity_keywords": {
                    "low": ["simple", "basic", "quick"],
                    "medium": ["analyze", "process", "standard"],
                    "high": ["complex", "detailed", "comprehensive", "advanced"],
                    "critical": ["urgent", "critical", "important", "emergency"]
                }
            },
            "creative_writing": {
                "description": "Creative content generation",
                "provider_preference": ["anthropic", "openai"],
                "default_complexity": "high",
                "complexity_keywords": {
                    "medium": ["write", "create", "story", "content"],
                    "high": ["creative", "narrative", "imaginative", "artistic"],
                    "critical": ["masterpiece", "publication", "professional"]
                }
            },
            "code_analysis": {
                "description": "Code review and technical analysis",
                "provider_preference": ["openai", "anthropic"],
                "default_complexity": "medium",
                "complexity_keywords": {
                    "low": ["simple", "basic", "review"],
                    "medium": ["analyze", "refactor", "optimize"],
                    "high": ["architecture", "design", "complex algorithm"],
                    "critical": ["security", "production", "critical bug"]
                }
            },
            "customer_service": {
                "description": "Customer service interactions",
                "provider_preference": ["anthropic", "openai"],
                "default_complexity": "medium",
                "complexity_keywords": {
                    "low": ["greeting", "simple question", "faq"],
                    "medium": ["support", "help", "issue", "question"],
                    "high": ["complaint", "escalation", "complex problem"],
                    "critical": ["urgent", "emergency", "executive"]
                }
            },
            "data_analysis": {
                "description": "Data processing and analysis",
                "provider_preference": ["openai", "google", "anthropic"],
                "default_complexity": "medium",
                "complexity_keywords": {
                    "low": ["simple", "summary", "basic stats"],
                    "medium": ["analyze", "trends", "patterns"],
                    "high": ["deep analysis", "insights", "correlations"],
                    "critical": ["predictive", "strategic", "business critical"]
                }
            }
        },
        
        # Complexity analysis settings
        "complexity_analysis": {
            "prompt_length_thresholds": {
                "low": int(os.environ.get("AGENTMAP_COMPLEXITY_LOW_THRESHOLD", "100")),
                "medium": int(os.environ.get("AGENTMAP_COMPLEXITY_MEDIUM_THRESHOLD", "300")),
                "high": int(os.environ.get("AGENTMAP_COMPLEXITY_HIGH_THRESHOLD", "800"))
            },
            "methods": {
                "prompt_length": os.environ.get("AGENTMAP_COMPLEXITY_LENGTH_ANALYSIS", "true").lower() == "true",
                "keyword_analysis": os.environ.get("AGENTMAP_COMPLEXITY_KEYWORD_ANALYSIS", "true").lower() == "true",
                "context_analysis": os.environ.get("AGENTMAP_COMPLEXITY_CONTEXT_ANALYSIS", "true").lower() == "true",
                "memory_analysis": os.environ.get("AGENTMAP_COMPLEXITY_MEMORY_ANALYSIS", "true").lower() == "true"
            },
            "keyword_weights": {
                "complexity_keywords": float(os.environ.get("AGENTMAP_COMPLEXITY_KEYWORD_WEIGHT", "0.4")),
                "task_specific_keywords": float(os.environ.get("AGENTMAP_TASK_KEYWORD_WEIGHT", "0.3")),
                "prompt_structure": float(os.environ.get("AGENTMAP_STRUCTURE_WEIGHT", "0.3"))
            },
            "context_analysis": {
                "memory_size_threshold": int(os.environ.get("AGENTMAP_MEMORY_COMPLEXITY_THRESHOLD", "10")),
                "input_field_count_threshold": int(os.environ.get("AGENTMAP_INPUT_COMPLEXITY_THRESHOLD", "5"))
            }
        },
        
        # Cost optimization settings
        "cost_optimization": {
            "enabled": os.environ.get("AGENTMAP_COST_OPTIMIZATION", "true").lower() == "true",
            "prefer_cost_effective": os.environ.get("AGENTMAP_PREFER_COST_EFFECTIVE", "true").lower() == "true",
            "max_cost_tier": os.environ.get("AGENTMAP_MAX_COST_TIER", "high")  # low, medium, high, critical
        },
        
        # Fallback configuration
        "fallback": {
            "default_provider": os.environ.get("AGENTMAP_FALLBACK_PROVIDER", "anthropic"),
            "default_model": os.environ.get("AGENTMAP_FALLBACK_MODEL", "claude-3-haiku-20240307"),
            "retry_with_lower_complexity": os.environ.get("AGENTMAP_RETRY_LOWER_COMPLEXITY", "true").lower() == "true"
        },
        
        # Performance settings
        "performance": {
            "enable_routing_cache": os.environ.get("AGENTMAP_ROUTING_CACHE", "true").lower() == "true",
            "cache_ttl": int(os.environ.get("AGENTMAP_ROUTING_CACHE_TTL", "300")),  # 5 minutes
            "max_cache_size": int(os.environ.get("AGENTMAP_ROUTING_CACHE_SIZE", "1000"))
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
        "routing": get_default_routing_config(),
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
