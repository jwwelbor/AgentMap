"""
GraphScaffoldService for AgentMap.

Service that provides scaffolding functionality for creating agent classes and edge functions
based on CSV graph definitions. Includes service-aware scaffolding with automatic service
integration and template management.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, NamedTuple

from agentmap.services.prompt_manager_service import PromptManagerService
from agentmap.services.logging_service import LoggingService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.function_resolution_service import FunctionResolutionService


@dataclass
class ServiceAttribute:
    """Represents a service attribute to be added to an agent."""
    name: str
    type_hint: str
    documentation: str


class ServiceRequirements(NamedTuple):
    """Container for parsed service requirements."""
    services: List[str]
    protocols: List[str]
    imports: List[str]
    attributes: List[ServiceAttribute]
    usage_examples: Dict[str, str]


@dataclass
class ScaffoldOptions:
    """Configuration options for scaffolding operations."""
    graph_name: Optional[str] = None
    output_path: Optional[Path] = None
    function_path: Optional[Path] = None
    overwrite_existing: bool = False


@dataclass
class ScaffoldResult:
    """Result of scaffolding operations."""
    scaffolded_count: int
    created_files: List[Path] = field(default_factory=list)
    skipped_files: List[Path] = field(default_factory=list)
    service_stats: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class ServiceRequirementParser:
    """Parses service requirements from CSV context and maps to protocols."""
    
    def __init__(self):
        """Initialize with service-to-protocol mappings."""
        self.service_protocol_map = {
            "llm": {
                "protocol": "LLMServiceUser",
                "import": "from agentmap.services import LLMServiceUser",
                "attribute": "llm_service",
                "type_hint": "'LLMService'",
                "doc": "LLM service for calling language models"
            },
            "csv": {
                "protocol": "CSVServiceUser", 
                "import": "from agentmap.services import CSVServiceUser",
                "attribute": "csv_service",
                "type_hint": "'CSVStorageService'",
                "doc": "CSV storage service for CSV file operations"
            },
            "json": {
                "protocol": "JSONServiceUser",
                "import": "from agentmap.services import JSONServiceUser", 
                "attribute": "json_service",
                "type_hint": "'JSONStorageService'",
                "doc": "JSON storage service for JSON file operations"
            },
            "file": {
                "protocol": "FileServiceUser",
                "import": "from agentmap.services import FileServiceUser",
                "attribute": "file_service", 
                "type_hint": "'FileStorageService'",
                "doc": "File storage service for general file operations"
            },
            "vector": {
                "protocol": "VectorServiceUser",
                "import": "from agentmap.services import VectorServiceUser",
                "attribute": "vector_service",
                "type_hint": "'VectorStorageService'", 
                "doc": "Vector storage service for similarity search and embeddings"
            },
            "memory": {
                "protocol": "MemoryServiceUser",
                "import": "from agentmap.services import MemoryServiceUser",
                "attribute": "memory_service",
                "type_hint": "'MemoryStorageService'",
                "doc": "Memory storage service for in-memory data operations"
            },
            "node_registry": {
                "protocol": "NodeRegistryUser",
                "import": "from agentmap.services import NodeRegistryUser",
                "attribute": "node_registry",
                "type_hint": "Dict[str, Dict[str, Any]]",
                "doc": "Node registry for orchestrator agents to route between nodes"
            },
            "storage": {
                "protocol": "StorageServiceUser", 
                "import": "from agentmap.services import StorageServiceUser",
                "attribute": "storage_service",
                "type_hint": "Optional[StorageService]",
                "doc": "Generic storage service (backward compatibility)"
            }
        }
    
    def parse_services(self, context: Any) -> ServiceRequirements:
        """
        Parse service requirements from context.
        
        Args:
            context: Context from CSV (string, dict, or None)
            
        Returns:
            ServiceRequirements with parsed service information
        """
        services = self._extract_services_list(context)
        
        if not services:
            return ServiceRequirements([], [], [], [], {})
        
        # Validate services
        invalid_services = [s for s in services if s not in self.service_protocol_map]
        if invalid_services:
            raise ValueError(f"Unknown services: {invalid_services}. Available: {list(self.service_protocol_map.keys())}")
        
        protocols = []
        imports = []
        attributes = []
        usage_examples = {}
        
        for service in services:
            service_info = self.service_protocol_map[service]
            protocols.append(service_info["protocol"])
            imports.append(service_info["import"])
            
            attributes.append(ServiceAttribute(
                name=service_info["attribute"],
                type_hint=service_info["type_hint"], 
                documentation=service_info["doc"]
            ))
            
            usage_examples[service] = self._get_usage_example(service)
        
        return ServiceRequirements(
            services=services,
            protocols=protocols,
            imports=list(set(imports)),  # Remove duplicates
            attributes=attributes,
            usage_examples=usage_examples
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
    
    def _get_usage_example(self, service: str) -> str:
        """Get usage example for a service."""
        examples = {
            "llm": """# Call language model
            if hasattr(self, 'llm_service') and self.llm_service:
                response = self.llm_service.call_llm(
                    provider="openai",
                    messages=[{"role": "user", "content": query}]
                )""",
            "csv": """# Read CSV data
            if hasattr(self, 'csv_service') and self.csv_service:
                data = self.csv_service.read("data.csv")
                
                # Write CSV data  
                result = self.csv_service.write("output.csv", processed_data)""",
            "json": """# Read JSON data
            if hasattr(self, 'json_service') and self.json_service:
                data = self.json_service.read("data.json")
                
                # Write JSON data
                result = self.json_service.write("output.json", processed_data)""",
            "file": """# Read file
            if hasattr(self, 'file_service') and self.file_service:
                content = self.file_service.read("document.txt")
                
                # Write file
                result = self.file_service.write("output.txt", processed_content)""",
            "vector": """# Search for similar documents
            if hasattr(self, 'vector_service') and self.vector_service:
                similar_docs = self.vector_service.read(
                    collection="documents",
                    query="search query"
                )
                
                # Add documents to vector store
                result = self.vector_service.write(
                    collection="documents", 
                    data=[{"content": "text", "metadata": {...}}]
                )""",
            "memory": """# Store data in memory
            if hasattr(self, 'memory_service') and self.memory_service:
                self.memory_service.write("session", {"key": "value"})
                
                # Retrieve data from memory  
                data = self.memory_service.read("session")""",
            "node_registry": """# Get available nodes (for orchestrator agents)
            if hasattr(self, 'node_registry') and self.node_registry:
                available_nodes = self.node_registry
                
                # Example usage in routing logic
                for node_name, metadata in available_nodes.items():
                    if "data_processing" in metadata.get("description", ""):
                        return node_name""",
            "storage": """# Generic storage operations
            if hasattr(self, 'storage_service') and self.storage_service:
                data = self.storage_service.read("collection_name")
                result = self.storage_service.write("collection_name", data)"""
        }
        
        return examples.get(service, f"            # Use {service} service\n            # TODO: Add usage example")


class GraphScaffoldService:
    """
    Service for scaffolding agent classes and edge functions from CSV graph definitions.
    
    Provides service-aware scaffolding capabilities with automatic service integration,
    template management, and comprehensive error handling.
    """
    
    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        prompt_manager: PromptManagerService,
        function_resolution_service: FunctionResolutionService
    ):
        """Initialize service with dependency injection."""
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.prompt_manager = prompt_manager
        self.service_parser = ServiceRequirementParser()
        self.function_service = function_resolution_service
        self.logger.info("[GraphScaffoldService] Initialized")
    
    def scaffold_agents_from_csv(
        self, 
        csv_path: Path, 
        options: Optional[ScaffoldOptions] = None
    ) -> ScaffoldResult:
        """
        Scaffold agents and functions from CSV file with service awareness.
        
        Args:
            csv_path: Path to CSV file containing graph definitions
            options: Scaffolding options (uses defaults if None)
            
        Returns:
            ScaffoldResult with scaffolding details
        """
        options = options or ScaffoldOptions()
        self.logger.info(f"[GraphScaffoldService] Scaffolding from CSV: {csv_path}")
        
        try:
            # Get scaffold paths from app config
            agents_path = options.output_path or self.config.custom_agents_path
            functions_path = options.function_path or self.config.functions_path
            
            # Create directories if they don't exist
            agents_path.mkdir(parents=True, exist_ok=True)
            functions_path.mkdir(parents=True, exist_ok=True)
            
            # Collect information about agents and functions
            agent_info = self._collect_agent_info(csv_path, options.graph_name)
            func_info = self._collect_function_info(csv_path, options.graph_name)
            
            # Initialize result tracking
            result = ScaffoldResult(
                scaffolded_count=0,
                service_stats={"with_services": 0, "without_services": 0}
            )
            
            # Scaffold agents
            for agent_type, info in agent_info.items():
                try:
                    created_path = self._scaffold_agent(
                        agent_type, info, agents_path, options.overwrite_existing
                    )
                    
                    if created_path:
                        result.created_files.append(created_path)
                        result.scaffolded_count += 1
                        
                        # Track service stats
                        service_reqs = self.service_parser.parse_services(info.get("context"))
                        if service_reqs.services:
                            result.service_stats["with_services"] += 1
                        else:
                            result.service_stats["without_services"] += 1
                    else:
                        result.skipped_files.append(agents_path / f"{agent_type.lower()}_agent.py")
                        
                except Exception as e:
                    error_msg = f"Failed to scaffold agent {agent_type}: {str(e)}"
                    self.logger.error(f"[GraphScaffoldService] {error_msg}")
                    result.errors.append(error_msg)
            
            # Scaffold functions
            for func_name, info in func_info.items():
                try:
                    created_path = self._scaffold_function(
                        func_name, info, functions_path, options.overwrite_existing
                    )
                    
                    if created_path:
                        result.created_files.append(created_path)
                        result.scaffolded_count += 1
                    else:
                        result.skipped_files.append(functions_path / f"{func_name}.py")
                        
                except Exception as e:
                    error_msg = f"Failed to scaffold function {func_name}: {str(e)}"
                    self.logger.error(f"[GraphScaffoldService] {error_msg}")
                    result.errors.append(error_msg)
            
            # Log service statistics
            if result.service_stats["with_services"] > 0 or result.service_stats["without_services"] > 0:
                self.logger.info(
                    f"[GraphScaffoldService] ✅ Scaffolded agents: "
                    f"{result.service_stats['with_services']} with services, "
                    f"{result.service_stats['without_services']} without services"
                )
            
            self.logger.info(
                f"[GraphScaffoldService] ✅ Scaffolding complete: "
                f"{result.scaffolded_count} created, {len(result.skipped_files)} skipped, "
                f"{len(result.errors)} errors"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to scaffold from CSV {csv_path}: {str(e)}"
            self.logger.error(f"[GraphScaffoldService] {error_msg}")
            
            return ScaffoldResult(
                scaffolded_count=0,
                errors=[error_msg]
            )
    
    def scaffold_agent_class(
        self, 
        agent_type: str, 
        info: Dict[str, Any],
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Scaffold individual agent class file.
        
        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            output_path: Optional custom output path
            
        Returns:
            Path to created file, or None if file already exists
        """
        output_path = output_path or self.config.custom_agents_path
        return self._scaffold_agent(agent_type, info, output_path, overwrite=False)
    
    def scaffold_edge_function(
        self, 
        func_name: str, 
        info: Dict[str, Any],
        func_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Scaffold edge function file.
        
        Args:
            func_name: Name of function to scaffold
            info: Function information dictionary
            func_path: Optional custom function path
            
        Returns:
            Path to created file, or None if file already exists
        """
        func_path = func_path or self.config.functions_path
        return self._scaffold_function(func_name, info, func_path, overwrite=False)
    
    def get_scaffold_paths(self, graph_name: Optional[str] = None) -> Dict[str, Path]:
        """
        Get standard scaffold paths using app config.
        
        Args:
            graph_name: Optional graph name (unused but kept for API consistency)
            
        Returns:
            Dictionary with scaffold paths
        """
        return {
            "agents_path": self.config.custom_agents_path,
            "functions_path": self.config.functions_path,
            "csv_path": self.config.csv_path
        }
    
    def _collect_agent_info(self, csv_path: Path, graph_name: Optional[str] = None) -> Dict[str, Dict]:
        """
        Collect information about agents from the CSV file.
        
        Args:
            csv_path: Path to the CSV file
            graph_name: Optional graph name to filter by
            
        Returns:
            Dictionary mapping agent types to their information
        """
        # Import here to avoid circular dependencies
        from agentmap.agents import get_agent_class
        
        agent_info: Dict[str, Dict] = {}
        
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows that don't match our graph filter
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue
                    
                # Collect agent information
                agent_type = row.get("AgentType", "").strip()
                if agent_type and not get_agent_class(agent_type):
                    node_name = row.get("Node", "").strip()
                    context = row.get("Context", "").strip()
                    prompt = row.get("Prompt", "").strip()
                    input_fields = [x.strip() for x in row.get("Input_Fields", "").split("|") if x.strip()]
                    output_field = row.get("Output_Field", "").strip()
                    description = row.get("Description", "").strip() 
                    
                    if agent_type not in agent_info:
                        agent_info[agent_type] = {
                            "agent_type": agent_type,
                            "node_name": node_name,
                            "context": context,
                            "prompt": prompt,
                            "input_fields": input_fields,
                            "output_field": output_field,
                            "description": description
                        }
        
        return agent_info
    
    def _collect_function_info(self, csv_path: Path, graph_name: Optional[str] = None) -> Dict[str, Dict]:
        """
        Collect information about functions from the CSV file.
        
        Args:
            csv_path: Path to the CSV file
            graph_name: Optional graph name to filter by
            
        Returns:
            Dictionary mapping function names to their information
        """
        
        func_info: Dict[str, Dict] = {}
        
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows that don't match our graph filter
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue
                    
                # Collect function information
                for col in ["Edge", "Success_Next", "Failure_Next"]:
                    func = self.function_service.extract_func_ref(row.get(col, ""))
                    if func:
                        node_name = row.get("Node", "").strip()
                        context = row.get("Context", "").strip()
                        input_fields = [x.strip() for x in row.get("Input_Fields", "").split("|") if x.strip()]
                        output_field = row.get("Output_Field", "").strip()
                        success_next = row.get("Success_Next", "").strip()
                        failure_next = row.get("Failure_Next", "").strip()
                        description = row.get("Description", "").strip()
                        
                        if func not in func_info:
                            func_info[func] = {
                                "node_name": node_name,
                                "context": context,
                                "input_fields": input_fields,
                                "output_field": output_field,
                                "success_next": success_next,
                                "failure_next": failure_next,
                                "description": description
                            }
        
        return func_info
    
    def _scaffold_agent(
        self, 
        agent_type: str, 
        info: Dict, 
        output_path: Path,
        overwrite: bool = False
    ) -> Optional[Path]:
        """
        Scaffold agent class file with service awareness.
        
        Args:
            agent_type: Type of agent to scaffold
            info: Information about the agent
            output_path: Directory to create agent class in
            overwrite: Whether to overwrite existing files
            
        Returns:
            Path to created file, or None if file already exists and overwrite=False
        """
        class_name = agent_type + "Agent"
        file_name = f"{agent_type.lower()}_agent.py"
        file_path = output_path / file_name
        
        if file_path.exists() and not overwrite:
            return None
        
        try:
            # Parse service requirements from context
            service_reqs = self.service_parser.parse_services(info.get("context"))
            
            if service_reqs.services:
                self.logger.debug(
                    f"[GraphScaffoldService] Scaffolding {agent_type} with services: "
                    f"{', '.join(service_reqs.services)}"
                )
            
            # Load and format template
            template_vars = self._prepare_agent_template_variables(agent_type, info, service_reqs)
            
            # Use PromptManager to load and format template
            formatted_template = self.prompt_manager.format_prompt(
                "file:scaffold/agent_template.txt", 
                template_vars
            )
            
            # Write enhanced template
            with file_path.open("w") as out:
                out.write(formatted_template)
            
            services_info = f" with services: {', '.join(service_reqs.services)}" if service_reqs.services else ""
            self.logger.debug(f"[GraphScaffoldService] ✅ Scaffolded agent: {file_path}{services_info}")
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"[GraphScaffoldService] Failed to scaffold agent {agent_type}: {e}")
            raise
    
    def _scaffold_function(
        self, 
        func_name: str, 
        info: Dict, 
        func_path: Path,
        overwrite: bool = False
    ) -> Optional[Path]:
        """
        Create a scaffold file for a function.
        
        Args:
            func_name: Name of function to scaffold
            info: Information about the function
            func_path: Directory to create function module in
            overwrite: Whether to overwrite existing files
            
        Returns:
            Path to created file, or None if file already exists and overwrite=False
        """
        file_name = f"{func_name}.py"
        file_path = func_path / file_name
        
        if file_path.exists() and not overwrite:
            return None
        
        # Generate context fields documentation
        context_fields = self._generate_context_fields(info["input_fields"], info["output_field"])
        
        # Prepare template variables
        template_vars = {
            "func_name": func_name,
            "context": info["context"] or "No context provided",
            "context_fields": context_fields,
            "success_node": info["success_next"] or "None",
            "failure_node": info["failure_next"] or "None",
            "node_name": info["node_name"],
            "description": info["description"] or ""
        }
        
        # Use PromptManager to load and format template
        formatted_template = self.prompt_manager.format_prompt(
            "file:scaffold/function_template.txt",
            template_vars
        )
        
        # Create function file
        with file_path.open("w") as out:
            out.write(formatted_template)
        
        self.logger.debug(f"[GraphScaffoldService] ✅ Scaffolded function: {file_path}")
        return file_path
    
    def _generate_context_fields(self, input_fields: List[str], output_field: str) -> str:
        """
        Generate documentation about available fields in the state.
        
        Args:
            input_fields: List of input field names
            output_field: Output field name
            
        Returns:
            String containing documentation lines
        """
        context_fields = []
        
        for field in input_fields:
            context_fields.append(f"    - {field}: Input from previous node")
        
        if output_field:
            context_fields.append(f"    - {output_field}: Expected output to generate")
        
        if not context_fields:
            context_fields = ["    No specific fields defined in the CSV"]
        
        return "\n".join(context_fields)
    
    def _prepare_agent_template_variables(
        self, 
        agent_type: str, 
        info: Dict, 
        service_reqs: ServiceRequirements
    ) -> Dict[str, str]:
        """Prepare all template variables for agent formatting."""
        
        # Basic info
        class_name = agent_type + "Agent"
        input_fields = ", ".join(info["input_fields"]) if info["input_fields"] else "None specified"
        output_field = info["output_field"] or "None specified"
        
        # Service-related variables
        if service_reqs.protocols:
            protocols_str = ", " + ", ".join(service_reqs.protocols)
            class_definition = f"class {class_name}(BaseAgent{protocols_str}):"
            service_description = f" with {', '.join(service_reqs.services)} capabilities"
        else:
            class_definition = f"class {class_name}(BaseAgent):"
            service_description = ""
        
        # Imports
        if service_reqs.imports:
            imports = "\n" + "\n".join(service_reqs.imports)
        else:
            imports = ""
        
        # Service attributes
        if service_reqs.attributes:
            service_attrs = ["\n        # Service attributes (automatically injected during graph building)"]
            for attr in service_reqs.attributes:
                service_attrs.append(f"        self.{attr.name}: {attr.type_hint} = None")
            service_attributes = "\n".join(service_attrs)
        else:
            service_attributes = ""
        
        # Services documentation
        if service_reqs.services:
            services_doc_lines = ["", "    Available Services:"]
            for attr in service_reqs.attributes:
                services_doc_lines.append(f"    - self.{attr.name}: {attr.documentation}")
            services_doc = "\n".join(services_doc_lines)
        else:
            services_doc = ""
        
        # Input field access
        if info["input_fields"]:
            access_lines = []
            for field in info["input_fields"]:
                access_lines.append(f"            {field} = processed_inputs.get(\"{field}\")")
            input_field_access = "\n".join(access_lines)
        else:
            input_field_access = "            # No specific input fields defined in the CSV"
        
        # Service usage examples
        if service_reqs.services:
            usage_lines = []
            for service in service_reqs.services:
                if service in service_reqs.usage_examples:
                    usage_lines.append(f"            # {service.upper()} SERVICE:")
                    example_lines = service_reqs.usage_examples[service].split('\n')
                    for example_line in example_lines:
                        if example_line.strip():
                            usage_lines.append(f"            {example_line}")
                    usage_lines.append("")
            service_usage_examples = "\n".join(usage_lines)
        else:
            service_usage_examples = "            # No services configured"
        
        # Usage examples section
        if service_reqs.services:
            usage_section_lines = [
                "",
                "# ===== SERVICE USAGE EXAMPLES =====",
                "#",
                "# This agent has access to the following services:",
                "#"
            ]
            
            for service in service_reqs.services:
                usage_section_lines.append(f"# {service.upper()} SERVICE:")
                if service in service_reqs.usage_examples:
                    example_lines = service_reqs.usage_examples[service].split('\n')
                    for example_line in example_lines:
                        usage_section_lines.append(f"# {example_line}")
                usage_section_lines.append("#")
            
            usage_examples_section = "\n".join(usage_section_lines)
        else:
            usage_examples_section = ""
        
        return {
            "agent_type": agent_type,
            "class_name": class_name,
            "class_definition": class_definition,
            "service_description": service_description,
            "imports": imports,
            "description": info.get("description", "") or "No description provided",
            "node_name": info["node_name"],
            "input_fields": input_fields,
            "output_field": output_field,
            "services_doc": services_doc,
            "prompt_doc": f"\n    Default prompt: {info['prompt']}" if info.get("prompt") else "",
            "service_attributes": service_attributes,
            "input_field_access": input_field_access,
            "service_usage_examples": service_usage_examples,
            "context": info.get("context", "") or "No context provided",
            "usage_examples_section": usage_examples_section
        }
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the scaffold service for debugging.
        
        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphScaffoldService",
            "config_available": self.config is not None,
            "prompt_manager_available": self.prompt_manager is not None,
            "custom_agents_path": str(self.config.custom_agents_path),
            "functions_path": str(self.config.functions_path),
            "csv_path": str(self.config.csv_path),
            "service_parser_available": self.service_parser is not None,
            "supported_services": list(self.service_parser.service_protocol_map.keys()),
            "template_files": [
                "scaffold/agent_template.txt",
                "scaffold/function_template.txt"
            ]
        }
