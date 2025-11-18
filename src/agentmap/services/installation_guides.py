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

    def get_storage_installation_guide(
        self, storage_type: Optional[str] = None
    ) -> str:
        """Get a friendly installation guide for storage dependencies."""
        if storage_type:
            storage_lower = storage_type.lower()
            if storage_lower == "csv":
                return "pip install pandas"
            elif storage_lower == "vector":
                return (
                    "pip install 'agentmap[vector]' or pip install langchain chromadb"
                )
            elif storage_lower == "firebase":
                return "pip install 'agentmap[firebase]' or pip install firebase-admin"
            elif storage_lower == "azure_blob":
                return "pip install 'agentmap[azure]' or pip install azure-storage-blob"
            elif storage_lower == "aws_s3":
                return "pip install 'agentmap[aws]' or pip install boto3"
            elif storage_lower == "gcp_storage":
                return "pip install 'agentmap[gcp]' or pip install google-cloud-storage"
            else:
                return f"pip install 'agentmap[storage]' or install the specific package for {storage_type}"
        else:
            return "pip install 'agentmap[storage]' for all storage support"
