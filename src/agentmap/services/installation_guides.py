"""Installation guide utilities for DependencyCheckerService."""

from typing import Optional


class InstallationGuideHelper:
    """Helper class for generating installation guides."""

    def get_installation_guide(self, provider: str, category: str = "llm") -> str:
        """
        Get a friendly installation guide for dependencies.

        Args:
            provider: Provider name (e.g., "openai", "anthropic", "google")
            category: Category type ("llm" or "storage")

        Returns:
            Installation guide string
        """
        if category.lower() == "llm":
            return self.get_llm_installation_guide(provider)
        elif category.lower() == "storage":
            return self.get_storage_installation_guide(provider)
        else:
            return f"pip install 'agentmap[{category}]' or install the specific package for {provider}"

    def get_llm_installation_guide(self, provider: Optional[str] = None) -> str:
        """Get a friendly installation guide for LLM dependencies."""
        if not provider:
            return "pip install 'agentmap[llm]' for all LLM support"

        guides = {
            "openai": "pip install 'agentmap[openai]' or pip install openai>=1.0.0 langchain",
            "anthropic": "pip install 'agentmap[anthropic]' or pip install anthropic langchain",
            "google": "pip install 'agentmap[google]' or pip install google-generativeai langchain-google-genai",
            "gemini": "pip install 'agentmap[google]' or pip install google-generativeai langchain-google-genai",
        }
        provider_lower = provider.lower()
        default_guide = f"pip install 'agentmap[llm]' or install the specific package for {provider}"
        return guides.get(provider_lower, default_guide)

    def get_storage_installation_guide(self, storage_type: Optional[str] = None) -> str:
        """Get a friendly installation guide for storage dependencies."""
        if not storage_type:
            return "pip install 'agentmap[storage]' for all storage support"

        guides = {
            "csv": "pip install pandas",
            "vector": "pip install 'agentmap[vector]' or pip install langchain chromadb",
            "firebase": "pip install 'agentmap[firebase]' or pip install firebase-admin",
            "azure_blob": "pip install 'agentmap[azure]' or pip install azure-storage-blob",
            "aws_s3": "pip install 'agentmap[aws]' or pip install boto3",
            "gcp_storage": "pip install 'agentmap[gcp]' or pip install google-cloud-storage",
        }
        storage_lower = storage_type.lower()
        default_guide = f"pip install 'agentmap[storage]' or install the specific package for {storage_type}"
        return guides.get(storage_lower, default_guide)
