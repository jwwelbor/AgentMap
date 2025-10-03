import json
from typing import Any, Dict, List, Optional

from agentmap.models.scaffold_types import (
    ServiceAttribute,
    ServiceRequirements,
)


class ServiceRequirementsParser:
    """Parses service requirements from CSV context and maps to protocols."""

    def __init__(self):
        """Initialize with service-to-protocol mappings."""
        # Define both approaches - automatically choose based on requested services
        self.unified_service_map = {
            "llm": {
                "protocol": "LLMCapableAgent",
                "import": "from agentmap.services.protocols import LLMCapableAgent",
                "attribute": "llm_service",
                "type_hint": "LLMServiceProtocol",
                "doc": "LLM service for calling language models",
            },
            "storage": {
                "protocol": "StorageCapableAgent",
                "import": "from agentmap.services.protocols import StorageCapableAgent",
                "attribute": "storage_service",
                "type_hint": "StorageServiceProtocol",
                "doc": "Generic storage service (supports all storage types)",
            },
        }

        self.separate_service_map = {
            "llm": {
                "protocol": "LLMCapableAgent",
                "import": "from agentmap.services.protocols import LLMCapableAgent",
                "attribute": "llm_service",
                "type_hint": "LLMServiceProtocol",
                "doc": "LLM service for calling language models",
            },
            "csv": {
                "protocol": "CSVCapableAgent",
                "import": "from agentmap.services.protocols import CSVCapableAgent",
                "attribute": "csv_service",
                "type_hint": "Any  # CSV storage service",
                "doc": "CSV storage service for CSV file operations",
            },
            "json": {
                "protocol": "JSONCapableAgent",
                "import": "from agentmap.services.protocols import JSONCapableAgent",
                "attribute": "json_service",
                "type_hint": "Any  # JSON storage service",
                "doc": "JSON storage service for JSON file operations",
            },
            "file": {
                "protocol": "FileCapableAgent",
                "import": "from agentmap.services.protocols import FileCapableAgent",
                "attribute": "file_service",
                "type_hint": "Any  # File storage service",
                "doc": "File storage service for general file operations",
            },
            "vector": {
                "protocol": "VectorCapableAgent",
                "import": "from agentmap.services.protocols import VectorCapableAgent",
                "attribute": "vector_service",
                "type_hint": "Any  # Vector storage service",
                "doc": "Vector storage service for similarity search and embeddings",
            },
            "memory": {
                "protocol": "MemoryCapableAgent",
                "import": "from agentmap.services.protocols import MemoryCapableAgent",
                "attribute": "memory_service",
                "type_hint": "Any  # Memory storage service",
                "doc": "Memory storage service for in-memory data operations",
            },
            "storage": {
                "protocol": "StorageCapableAgent",
                "import": "from agentmap.services.protocols import StorageCapableAgent",
                "attribute": "storage_service",
                "type_hint": "StorageServiceProtocol",
                "doc": "Generic storage service (supports all storage types)",
            },
        }

    def parse_services(self, context: Any) -> ServiceRequirements:
        """
        Parse service requirements from context with automatic architecture detection.

        Logic:
        - If "storage" is requested → use unified StorageCapableAgent
        - If specific types (csv, json, file, vector, memory) → use separate service protocols
        - LLM always uses LLMCapableAgent

        Args:
            context: Context from CSV (string, dict, or None)

        Returns:
            ServiceRequirements with automatically determined service information
        """
        services = self._extract_services_list(context)

        if not services:
            return ServiceRequirements([], [], [], [], {})

        # Determine architecture approach automatically
        "storage" in services
        specific_storage_types = {"csv", "json", "file", "vector", "memory"}
        set(services) & specific_storage_types

        # Build service protocol map based on what's requested
        service_protocol_map = {}
        unknown_services = []

        for service in services:
            if service == "llm":
                # LLM always uses the same protocol
                service_protocol_map[service] = self.separate_service_map[service]
            elif service == "storage":
                # Explicit storage request → use unified approach
                service_protocol_map[service] = self.unified_service_map[service]
            elif service in specific_storage_types:
                # Specific storage type → use separate service approach
                service_protocol_map[service] = self.separate_service_map[service]
            elif service == "node_registry":
                # Node registry service → use separate service approach
                service_protocol_map[service] = self.separate_service_map[service]
            else:
                # Unknown service - collect it
                unknown_services.append(service)

        # If there are unknown services, raise error with all of them
        if unknown_services:
            raise ValueError(
                f"Unknown services: {unknown_services}. Available: {list(self.separate_service_map.keys())}"
            )

        # Build ServiceRequirements
        protocols = []
        imports = []
        attributes = []
        usage_examples = {}

        for service in services:
            if service in service_protocol_map:
                service_info = service_protocol_map[service]
                protocols.append(service_info["protocol"])
                imports.append(service_info["import"])

                attributes.append(
                    ServiceAttribute(
                        name=service_info["attribute"],
                        type_hint=service_info["type_hint"],
                        documentation=service_info["doc"],
                    )
                )

                usage_examples[service] = self._get_usage_example(
                    service, service_protocol_map
                )

        # Remove duplicate protocols and imports
        unique_protocols = []
        seen_protocols = set()
        for protocol in protocols:
            if protocol not in seen_protocols:
                unique_protocols.append(protocol)
                seen_protocols.add(protocol)

        unique_imports = list(set(imports))

        return ServiceRequirements(
            services=services,
            protocols=unique_protocols,
            imports=unique_imports,
            attributes=attributes,
            usage_examples=usage_examples,
        )

    def _extract_services_list(self, context: Any) -> List[str]:
        """Extract services list from various context formats."""
        if not context:
            return []

        # Handle dict context
        if isinstance(context, dict):
            return context.get("services", [])

        # Handle string context
        if isinstance(context, str):
            # Try parsing as JSON
            if context.strip().startswith("{"):
                try:
                    parsed = json.loads(context)
                    return parsed.get("services", [])
                except json.JSONDecodeError:
                    pass

            # Handle comma-separated services in string
            if "services:" in context:
                # Extract services from key:value format
                for part in context.split(","):
                    if part.strip().startswith("services:"):
                        services_str = part.split(":", 1)[1].strip()
                        return [s.strip() for s in services_str.split("|")]

        return []

    def _get_usage_example(
        self, service: str, service_protocol_map: Dict[str, Dict[str, str]]
    ) -> str:
        """Get usage example for a service based on the chosen protocol approach."""
        service_info = service_protocol_map.get(service, {})
        attribute = service_info.get("attribute", f"{service}_service")

        # Determine if this is unified storage or separate service
        is_unified_storage = (
            attribute == "storage_service"
            and service_info.get("protocol") == "StorageCapableAgent"
        )

        if service == "llm":
            return """# Call language model
            if hasattr(self, 'llm_service') and self.llm_service:
                response = self.llm_service.call_llm(
                    provider="openai",  # or "anthropic", "google"
                    messages=[{{"role": "user", "content": inputs.get("query")}}],
                    model="gpt-4"  # optional
                )
                return response.get("content")"""

        elif service == "storage" or is_unified_storage:
            # Unified storage approach
            if service == "storage":
                return """# Generic storage operations (supports all types)
            if hasattr(self, 'storage_service') and self.storage_service:
                # Read from any storage type
                csv_data = self.storage_service.read("csv", "input.csv")
                json_data = self.storage_service.read("json", "config.json")
                
                # Write to any storage type
                self.storage_service.write("json", "output.json", processed_data)
                return processed_data"""
            else:
                # Specific type using unified storage
                service_upper = service.upper()
                return f"""# {service_upper} storage using unified service
            if hasattr(self, 'storage_service') and self.storage_service:
                data = self.storage_service.read("{service}", "input.{service}")
                
                # Write {service_upper} data  
                result = self.storage_service.write("{service}", "output.{service}", processed_data)
                return result"""

        else:
            # Separate service approach
            examples = {
                "csv": """# Read CSV data
            if hasattr(self, 'csv_service') and self.csv_service:
                data = self.csv_service.read("data.csv")
                
                # Write CSV data  
                result = self.csv_service.write("output.csv", processed_data)
                return result""",
                "json": """# Read JSON data
            if hasattr(self, 'json_service') and self.json_service:
                data = self.json_service.read("data.json")
                
                # Write JSON data
                result = self.json_service.write("output.json", processed_data)
                return result""",
                "file": """# Read file
            if hasattr(self, 'file_service') and self.file_service:
                content = self.file_service.read("document.txt")
                
                # Write file
                result = self.file_service.write("output.txt", processed_content)
                return result""",
                "vector": """# Search for similar documents
            if hasattr(self, 'vector_service') and self.vector_service:
                similar_docs = self.vector_service.search(
                    collection="documents",
                    query="search query"
                )
                
                # Add documents to vector store
                result = self.vector_service.add(
                    collection="documents", 
                    documents=[{{"content": "text", "metadata": {{...}}}}]
                )
                return result""",
                "memory": """# Store data in memory
            if hasattr(self, 'memory_service') and self.memory_service:
                self.memory_service.set("session_key", {{"key": "value"}})
                
                # Retrieve data from memory  
                data = self.memory_service.get("session_key")
                return data""",
                "node_registry": """# Access node registry for routing decisions
            if hasattr(self, 'node_registry') and self.node_registry:
                # Get information about available nodes
                available_nodes = list(self.node_registry.keys())
                
                # Get specific node metadata
                node_info = self.node_registry.get("target_node")
                if node_info:
                    node_type = node_info["type"]
                    description = node_info["description"]
                    
                # Use for dynamic routing decisions
                if "error_handler" in self.node_registry:
                    return "error_handler"  # Route to error handling node
                else:
                    return "default_next"  # Fallback routing""",
            }

            return examples.get(
                service,
                f"            # Use {service} service\n            # TODO: Add usage example",
            )
