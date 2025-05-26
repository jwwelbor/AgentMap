# This file creates scaffolds for agents and functions
# agentmap/scaffold.py

"""
Agent scaffolding utility for AgentMap.
Creates Python class files for custom agents and function stubs based on CSV input.
Enhanced with service-aware scaffolding for automatic service integration.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, NamedTuple, Any
from dataclasses import dataclass

from agentmap.agents import get_agent_class
from agentmap.config import (get_csv_path, get_custom_agents_path, get_functions_path)
from agentmap.utils.common import extract_func_ref
from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.config.configuration import Configuration
from agentmap.logging.service import LoggingService

# ===== SERVICE-AWARE SCAFFOLDING COMPONENTS =====

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

# ===== TEMPLATE MANAGEMENT =====

def load_template(template_name: str) -> str:
    """Load a template file from the templates directory."""
    templates_dir = Path(__file__).parent.parent / "templates"
    template_path = templates_dir / f"{template_name}.py.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Template {template_name} not found at {template_path}")
    return template_path.read_text()

def prepare_template_variables(agent_type: str, info: Dict, service_reqs: ServiceRequirements) -> Dict[str, str]:
    """Prepare all template variables for formatting."""
    
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

# ===== DATA COLLECTION FUNCTIONS =====

def collect_agent_info(
    csv_path: Path, 
    graph_name: Optional[str] = None
) -> Dict[str, Dict]:
    """
    Collect information about agents from the CSV file.
    
    Args:
        csv_path: Path to the CSV file
        graph_name: Optional graph name to filter by
        
    Returns:
        Dictionary mapping agent types to their information
    """
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

def collect_function_info(
    csv_path: Path, 
    graph_name: Optional[str] = None
) -> Dict[str, Dict]:
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
                func = extract_func_ref(row.get(col, ""))
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

# ===== LEGACY SUPPORT FUNCTIONS =====

def generate_field_access(input_fields: List[str]) -> str:
    """
    Generate code to access fields from the inputs dictionary.
    
    Args:
        input_fields: List of input field names
        
    Returns:
        String containing lines of Python code to access fields
    """
    access_lines = []
    for field in input_fields:
        access_lines.append(f"            {field} = processed_inputs.get(\"{field}\")")
    
    if not access_lines:
        access_lines = ["            # No specific input fields defined in the CSV"]
    
    return "\n".join(access_lines)

def generate_context_fields(input_fields: List[str], output_field: str) -> str:
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

# ===== ENHANCED SCAFFOLDING FUNCTIONS =====

def scaffold_agent(
    agent_type: str, 
    info: Dict, 
    output_path: Path,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Enhanced scaffold_agent function with automatic service detection.
    
    Args:
        agent_type: Type of agent to scaffold
        info: Information about the agent
        output_path: Directory to create agent class in
        logger: Optional logger instance
        
    Returns:
        True if agent was scaffolded, False if it already existed
    """
    class_name = agent_type + "Agent"
    file_name = f"{agent_type.lower()}_agent.py"
    path = output_path / file_name
    
    if path.exists():
        return False
    
    try:
        # Parse service requirements from context
        parser = ServiceRequirementParser()
        service_reqs = parser.parse_services(info.get("context"))
        
        if logger and service_reqs.services:
            logger.debug(f"Scaffolding {agent_type} with services: {', '.join(service_reqs.services)}")
        
        # Load and format template
        template = load_template("agent_template")
        
        # Prepare template variables
        template_vars = prepare_template_variables(agent_type, info, service_reqs)
        
        # Format template
        formatted_template = template.format(**template_vars)
        
        # Write enhanced template
        with path.open("w") as out:
            out.write(formatted_template)
        
        if logger:
            services_info = f" with services: {', '.join(service_reqs.services)}" if service_reqs.services else ""
            logger.debug(f"Scaffolded agent: {path}{services_info}")
        
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to scaffold agent {agent_type}: {e}")
        raise

def scaffold_function(
    func_name: str, 
    info: Dict, 
    func_path: Path,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Create a scaffold file for a function.
    
    Args:
        func_name: Name of function to scaffold
        info: Information about the function
        func_path: Directory to create function module in
        logger: Optional logger instance
        
    Returns:
        True if function was scaffolded, False if it already existed
    """
    file_name = f"{func_name}.py"
    path = func_path / file_name
    
    if path.exists():
        return False
    
    # Generate context fields documentation
    context_fields = generate_context_fields(info["input_fields"], info["output_field"])
    
    # Load template
    template = load_template("function_template")
    
    # Create function file
    with path.open("w") as out:
        out.write(template.format(
            func_name=func_name,
            context=info["context"] or "No context provided",
            context_fields=context_fields,
            success_node=info["success_next"] or "None",
            failure_node=info["failure_next"] or "None",
            node_name=info["node_name"],
            description=info["description"] or ""
        ))
    
    if logger:
        logger.debug(f"Scaffolded function: {path}")
    return True

def scaffold_agents(
    csv_path: Path,
    output_path: Path,
    func_path: Path, 
    graph_name: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> int:
    """
    Scaffold agents and functions from the CSV with service awareness.
    
    Args:
        csv_path: Path to CSV file
        output_path: Directory to create agent classes in
        func_path: Directory to create function modules in
        graph_name: Optional graph name to filter by
        logger: Optional logger instance
    
    Returns:
        Number of agents or functions scaffolded
    """
    # Create directories if they don't exist
    output_path.mkdir(parents=True, exist_ok=True)
    func_path.mkdir(parents=True, exist_ok=True)

    # Collect information about agents and functions
    agent_info = collect_agent_info(csv_path, graph_name)
    func_info = collect_function_info(csv_path, graph_name)
    
    # Scaffold agents
    scaffolded_count = 0
    service_stats = {"with_services": 0, "without_services": 0}
    
    for agent_type, info in agent_info.items():
        try:
            # Check if agent has services
            parser = ServiceRequirementParser()
            service_reqs = parser.parse_services(info.get("context"))
            
            if service_reqs.services:
                service_stats["with_services"] += 1
            else:
                service_stats["without_services"] += 1
            
            if scaffold_agent(agent_type, info, output_path, logger):
                scaffolded_count += 1
                
        except Exception as e:
            if logger:
                logger.error(f"Failed to scaffold agent {agent_type}: {e}")
    
    # Scaffold functions
    for func_name, info in func_info.items():
        if scaffold_function(func_name, info, func_path, logger):
            scaffolded_count += 1
    
    # Log service statistics
    if logger and (service_stats["with_services"] > 0 or service_stats["without_services"] > 0):
        logger.info(f"Scaffolded agents: {service_stats['with_services']} with services, "
                   f"{service_stats['without_services']} without services")
    
    return scaffolded_count

def validate_service_availability(services: List[str], logger: Optional[logging.Logger] = None) -> Dict[str, bool]:
    """
    Validate that requested services are available in the current environment.
    
    Args:
        services: List of service names to validate
        logger: Optional logger for warnings
        
    Returns:
        Dictionary mapping service names to availability status
    """
    availability = {}
    
    for service in services:
        try:
            if service == "llm":
                from agentmap.services import LLMService
                availability[service] = True
            elif service in ["csv", "json", "file", "vector", "memory"]:
                from agentmap.services.storage import StorageServiceManager
                availability[service] = True
            elif service == "node_registry":
                from agentmap.services import NodeRegistryService
                availability[service] = True
            else:
                availability[service] = False
                
        except ImportError as e:
            availability[service] = False
            if logger:
                logger.warning(f"Service '{service}' not available: {e}")
    
    return availability
