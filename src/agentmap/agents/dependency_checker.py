# dependency_checker.py
"""
Dependency checker for AgentMap.

This module provides utilities for checking if required dependencies are installed,
with specific functions for different dependency groups.
"""
from typing import Dict, List, Tuple
import importlib
import logging

logger = logging.getLogger(__name__)

# Define dependency groups
LLM_DEPENDENCIES = {
    "openai": ["openai>=1.0.0"],  # Specify minimum version
    "anthropic": ["anthropic"],
    "google": ["google.generativeai", "langchain_google_genai"],
    "langchain": ["langchain"]
}

STORAGE_DEPENDENCIES = {
    "csv": ["pandas"],
    "vector": ["langchain", "chromadb"],
    "firebase": ["firebase_admin"],
    "azure_blob": ["azure-storage-blob"],
    "aws_s3": ["boto3"],
    "gcp_storage": ["google-cloud-storage"]
}

def check_dependency(pkg_name: str) -> bool:
    """Check if a single dependency is installed."""
    try:
        # Handle special cases like google.generativeai
        if "." in pkg_name:
            parts = pkg_name.split(".")
            # Try to import the top-level package
            importlib.import_module(parts[0])
            # Then try the full path
            importlib.import_module(pkg_name)
        else:
            # Extract version requirement if present
            if ">=" in pkg_name:
                name, version = pkg_name.split(">=")
                mod = importlib.import_module(name)
                if hasattr(mod, "__version__"):
                    from packaging import version as pkg_version
                    if pkg_version.parse(mod.__version__) < pkg_version.parse(version):
                        logger.debug(f"Package {name} version {mod.__version__} is lower than required {version}")
                        return False
            else:
                importlib.import_module(pkg_name)
        return True
    except (ImportError, ModuleNotFoundError):
        logger.debug(f"Dependency check failed for: {pkg_name}")
        return False

def check_llm_dependencies(provider: str = None) -> Tuple[bool, List[str]]:
    """
    Check if LLM dependencies are installed.
    
    Args:
        provider: Optional specific provider to check (openai, anthropic, google)
        
    Returns:
        Tuple of (all_available, missing_packages)
    """
    if provider:
        # Check specific provider
        dependencies = LLM_DEPENDENCIES.get(provider.lower(), [])
        if not dependencies:
            logger.warning(f"Unknown LLM provider: {provider}")
            return False, [f"unknown-provider:{provider}"]
    else:
        # Check core dependencies needed for any LLM
        dependencies = LLM_DEPENDENCIES.get("langchain", [])
    
    missing = []
    for pkg in dependencies:
        if not check_dependency(pkg):
            missing.append(pkg)
    
    return len(missing) == 0, missing

def check_storage_dependencies(storage_type: str = None) -> Tuple[bool, List[str]]:
    """
    Check if storage dependencies are installed.
    
    Args:
        storage_type: Optional specific storage type to check
        
    Returns:
        Tuple of (all_available, missing_packages)
    """
    if storage_type:
        # Check specific storage type
        dependencies = STORAGE_DEPENDENCIES.get(storage_type.lower(), [])
        if not dependencies:
            logger.warning(f"Unknown storage type: {storage_type}")
            return False, [f"unknown-storage:{storage_type}"]
    else:
        # Check core dependencies needed for any storage
        dependencies = STORAGE_DEPENDENCIES.get("csv", [])
    
    missing = []
    for pkg in dependencies:
        if not check_dependency(pkg):
            missing.append(pkg)
    
    return len(missing) == 0, missing

def get_llm_installation_guide(provider: str = None) -> str:
    """Get a friendly installation guide for LLM dependencies."""
    if provider:
        provider_lower = provider.lower()
        if provider_lower == "openai":
            return "pip install 'agentmap[openai]' or pip install openai>=1.0.0 langchain"
        elif provider_lower == "anthropic":
            return "pip install 'agentmap[anthropic]' or pip install anthropic langchain"
        elif provider_lower == "google" or provider_lower == "gemini":
            return "pip install 'agentmap[google]' or pip install google-generativeai langchain-google-genai"
        else:
            return f"pip install 'agentmap[llm]' or install the specific package for {provider}"
    else:
        return "pip install 'agentmap[llm]' for all LLM support"