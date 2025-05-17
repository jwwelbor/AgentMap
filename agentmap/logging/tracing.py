"""
Execution tracing for LangChain/LangSmith.
"""
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger("AgentMap")

def get_tracing_config():
    """Get LangSmith tracing configuration."""
    from agentmap.config import load_config
    config = load_config()
    return config.get("tracing", {})

def should_trace_graph(graph_name):
    """Check if a specific graph should be traced."""
    config = get_tracing_config()
    
    # If tracing is disabled globally, don't trace
    if not config.get("enabled", False):
        return False
    
    # If trace_all is enabled, trace everything
    if config.get("trace_all", False):
        return True
    
    # Check if this graph is in the trace_graphs list
    trace_graphs = config.get("trace_graphs", [])
    return graph_name in trace_graphs

@contextmanager
def trace_graph(graph_name):
    """Context manager to selectively trace a graph run."""
    config = get_tracing_config()
    
    # If tracing is disabled or this graph shouldn't be traced, early return
    if not config.get("enabled", False) or not should_trace_graph(graph_name):
        yield False
        return
    
    # Try local tracing first if mode is local
    if config.get("mode", "langsmith") == "local":
        if setup_local_tracing(config):
            logger.info(f"🔍 Local LangChain tracing enabled for graph '{graph_name}'")
            yield True
            return
    
    # Otherwise, use LangSmith tracing
    # Get API key and project
    api_key = os.environ.get("LANGCHAIN_API_KEY") or config.get("langsmith_api_key")
    project = os.environ.get("LANGCHAIN_PROJECT") or config.get("project", "agentmap-development")
    
    if not api_key:
        logger.warning(f"No LangSmith API key found for tracing graph '{graph_name}'")
        yield False
        return
    
    # Store previous environment state
    prev_tracing = os.environ.get("LANGCHAIN_TRACING_V2")
    prev_project = os.environ.get("LANGCHAIN_PROJECT")
    
    try:
        # Enable tracing for this context
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        
        logger.info(f"🔍 LangSmith tracing enabled for graph '{graph_name}' (project: {project})")
        yield True
    finally:
        # Restore previous environment state
        if prev_tracing:
            os.environ["LANGCHAIN_TRACING_V2"] = prev_tracing
        else:
            os.environ.pop("LANGCHAIN_TRACING_V2", None)
            
        if prev_project:
            os.environ["LANGCHAIN_PROJECT"] = prev_project
        else:
            os.environ.pop("LANGCHAIN_PROJECT", None)

def setup_local_tracing(config):
    """Setup local LangChain tracing based on AgentMap config."""
    if not config.get("enabled", False):
        return False
        
    if config.get("mode", "langsmith") != "local":
        return False
        
    # Set environment variables for LangChain tracing
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_TRACING_V2_EXPORTER"] = config.get("local_exporter", "file")
    
    # Set directory path if provided
    if "local_directory" in config:
        dir_path = config.get("local_directory")
        # Ensure directory exists
        os.makedirs(dir_path, exist_ok=True)
        os.environ["LANGCHAIN_TRACING_V2_FILE_PATH"] = dir_path
    
    # Set project name if provided
    if "project" in config:
        os.environ["LANGCHAIN_PROJECT"] = config.get("project")
        
    return True
