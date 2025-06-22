Based on the failing tests, the problem appears to be that the JSON service is incorrectly removing legitimate ID fields from documents when reading them back.
Let me first analyze the current JSON service behavior to understand exactly what's happening:Prun_test_methodRequest{
  `verbose`: true,
  `test_file`: `tests/fresh_suite/integration/test_storage_service_coordination.py`,
  `test_class`: `TestStorageServiceCoordination`,
  `test_method`: `test_automatic_storage_type_selection`,
  `project_name`: `AgentMap`
}Response{
  "success": false,
  "return_code": 1,
  "command": "cd /d C:\\Users\\jwwel\\Documents\\code\\AgentMap && C:\\Python312\\Scripts\\poetry.exe -P C:\\Users\\jwwel\\Documents\\code\\AgentMap run pytest -v --tb=short --disable-warnings tests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection -v",
  "summary": {
    "total": 1,
    "passed": 0,
    "failed": 1,
    "skipped": 0,
    "errors": 0,
    "duration": 2.86
  },
  "project_path": "C:\\Users\\jwwel\\Documents\\code\\AgentMap",
  "used_poetry": true,
  "execution_time": 4.339364,
  "warnings": [
    "======================== 1 failed, 1 warning in 2.86s ========================="
  ],
  "output": "============================= test session starts =============================\nplatform win32 -- Python 3.12.10, pytest-8.4.0, pluggy-1.6.0 -- C:\\Users\\jwwel\\Documents\\code\\AgentMap\\.venv\\Scripts\\python.exe\ncachedir: .pytest_cache\nrootdir: C:\\Users\\jwwel\\Documents\\code\\AgentMap\nconfigfile: pytest.ini\nplugins: anyio-4.9.0, langsmith-0.3.42, cov-6.1.1, mock-3.14.0\ncollecting ... collected 1 item\n\ntests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection FAILED [100%]\n\n================================== FAILURES ===================================\n____ TestStorageServiceCoordination.test_automatic_storage_type_selection _____\ntests\\fresh_suite\\integration\\test_storage_service_coordination.py:376: in test_automatic_storage_type_selection\n    self.assertEqual(read_data, scenario[\"data\"])\nE   AssertionError: {'nested': {'value': 'test'}} != {'id': 1, 'nested': {'value': 'test'}}\nE   - {'nested': {'value': 'test'}}\nE   + {'id': 1, 'nested': {'value': 'test'}}\nE   ?  +++++++++\n---------------------------- Captured stdout call -----------------------------\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Initialized\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Default providers initialized\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Initialized\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Initialized with FeaturesRegistryService coordination\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Initialized with all dependencies\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Service status: {'agent_registry_service': True, 'features_registry_service': True, 'dependency_checker_service': True, 'app_config_service': True, 'logging_service': True, 'all_dependencies_injected': True}\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: \\U0001f680 [ApplicationBootstrapService] Starting application bootstrap\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registering core agents\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered default agent: DefaultAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: default\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'echo': EchoAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: echo\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'branching': BranchingAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: branching\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'failure': FailureAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: failure\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'success': SuccessAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: success\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'input': InputAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: input\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'graph': GraphAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: graph\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registered 7/7 core agents\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Dynamically discovering custom agents\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Scanning custom agents directory: C:\\\\Users\\\\jwwel\\\\AppData\\\\Local\\\\Temp\\\\tmp9708douz\\\\custom_agents\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] No Python files found in custom agents directory\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] No custom agent classes found\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Discovering and registering LLM agents\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Feature enabled: llm\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Discovering providers for category: llm\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] All 1 imports validated successfully\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'openai' in category 'llm' validation set to: True\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check passed for: langchain_anthropic\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] All 1 imports validated successfully\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'anthropic' in category 'llm' validation set to: True\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: langchain_google_genai\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['langchain_google_genai']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'google' in category 'llm' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for llm.google: ['langchain_google_genai']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Provider discovery results for llm: {'openai': True, 'anthropic': True, 'google': False}\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'openai': OpenAIAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: openai\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'gpt': OpenAIAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: gpt\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'chatgpt': OpenAIAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: chatgpt\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registered 3 agents for LLM provider: openai\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'anthropic': AnthropicAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: anthropic\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'claude': AnthropicAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: claude\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registered 2 agents for LLM provider: anthropic\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'llm': LLMAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: llm\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered base LLM agent\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 LLM agents registered for providers: ['openai', 'anthropic']\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Discovering and registering storage agents\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Feature enabled: storage\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Discovering providers for category: storage\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] All 1 imports validated successfully\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'csv' in category 'storage' validation set to: True\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: chromadb\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['chromadb']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'vector' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.vector: ['chromadb']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: firebase_admin\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['firebase_admin']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'firebase' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.firebase: ['firebase_admin']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: azure-storage-blob\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['azure-storage-blob']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'azure_blob' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.azure_blob: ['azure-storage-blob']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: boto3\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['boto3']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'aws_s3' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.aws_s3: ['boto3']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: google-cloud-storage\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['google-cloud-storage']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'gcp_storage' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.gcp_storage: ['google-cloud-storage']\\n[DEBUG] agentmap.services.\n\n... [OUTPUT TRUNCATED FOR BREVITY] ...\n\nINFO     config.bootstrap:config_service.py:89 Loading configuration from: C:\\Users\\jwwel\\AppData\\Local\\Temp\\tmp9708douz\\integration_test_config.yaml\nINFO     config.bootstrap:config_service.py:96 Successfully loaded configuration from C:\\Users\\jwwel\\AppData\\Local\\Temp\\tmp9708douz\\integration_test_config.yaml\nINFO     config.bootstrap:config_service.py:100 Loaded configuration sections: ['execution', 'llm', 'logging', 'paths', 'routing', 'storage_config_path']\nINFO     bootstrap.app_config:app_config_service.py:71 [AppConfigService] Application configuration loaded successfully\n=========================== short test summary info ===========================\nFAILED tests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection - AssertionError: {'nested': {'value': 'test'}} != {'id': 1, 'nested': {'value': 'test'}}\n- {'nested': {'value': 'test'}}\n+ {'id': 1, 'nested': {'value': 'test'}}\n?  +++++++++\n======================== 1 failed, 1 warning in 2.86s =========================\n",
  "full_command": [
    "cmd",
    "/c",
    "cd /d C:\\Users\\jwwel\\Documents\\code\\AgentMap && C:\\Python312\\Scripts\\poetry.exe -P C:\\Users\\jwwel\\Documents\\code\\AgentMap run pytest -v --tb=short --disable-warnings tests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection -v"
  ],
  "stderr": "",
  "poetry_executable": "C:\\Python312\\Scripts\\poetry.exe"
}Unraveled JSON service's problematic ID field removal logic.17sThe issue is clear from the test failure. The test writes data {"id": 1, "nested": {"value": "test"}} with document_id="test", but when it reads it back, it only gets {"nested": {"value": "test"}} - the id: 1 field is missing.
Looking at the JSON service read method around lines 530-537 that I saw earlier, there's this logic:
python# Clean up: remove the injected ID field if it matches the document_id
# to return data as it was originally written
if isinstance(doc, dict) and doc.get(id_field) == document_id:
    doc = doc.copy()
    # Only remove the ID field if it matches the document_id we searched for
    # This prevents removing legitimate ID fields that were part of original data
    doc.pop(id_field, None)
The problem is that the logic is flawed. The test scenario is:

Test writes data {"id": 1, "nested": {"value": "test"}} with document_id="test"
JSON service stores this and internally might inject an ID field with value "test"
When reading by document_id="test", it finds the document
The cleanup logic checks if doc.get("id") == document_id
But doc.get("id") is 1 (from the original data) and document_id is "test"
Since 1 != "test", it shouldn't remove the ID field
But somehow it's still removing it

Wait, let me look at this more carefully. The comment says "Only remove the ID field if it matches the document_id we searched for" but the actual behavior suggests it's removing ID fields incorrectly.
Let me examine the JSON service code more carefully to understand the exact flow.Now I can see the exact issue. The test writes {"id": 1, "nested": {"value": "test"}} with document_id="test", but when reading it back, the id: 1 field is missing.
Let me look at the specific part of the JSON service that's causing this issue:Fread_fileRequest{
  `path`: `C:\\Users\\jwwel\\Documents\\code\\AgentMap\\src\\agentmap\\services\\storage\\json_service.py`
}Response"""
JSON Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for JSON files, with support for path-based operations and nested documents.
"""
import os
import json
import contextlib
from collections.abc import Generator
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode


class JSONStorageService(BaseStorageService):
    """
    JSON storage service implementation.
    
    Provides storage operations for JSON files with support for
    path-based access, nested documents, and query filtering.
    """
    
    # NOTE: This method is included for backward compatibility
    # The base class uses health_check(), but some code expects is_healthy()
    def is_healthy(self) -> bool:
        """
        Check if the service is healthy and ready to use.
        
        Returns:
            True if the service is healthy, False otherwise
        """
        return self.health_check()
    
    def _initialize_client(self) -> Any:
        """
        Initialize JSON client.
        
        For JSON operations, we don't need a complex client.
        Just ensure base directory exists and return a simple config.
        
        Returns:
            Configuration dict for JSON operations
        """
        base_dir = self._config.get_option("base_directory", "./data")
        encoding = self._config.get_option("encoding", "utf-8")
        
        # Ensure base directory exists
        os.makedirs(base_dir, exist_ok=True)
        
        return {
            "base_directory": base_dir,
            "encoding": encoding,
            "indent": self._config.get_option("indent", 2)
        }
    
    def _perform_health_check(self) -> bool:
        """
        Perform health check for JSON storage.
        
        Checks if base directory is accessible and we can perform
        basic JSON operations.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            base_dir = self.client["base_directory"]
            
            # Check if directory exists and is writable
            if not os.path.exists(base_dir):
                return False
            
            if not os.access(base_dir, os.W_OK):
                return False
            
            # Test basic JSON operation
            test_data = {"test": [1, 2, 3]}
            test_str = json.dumps(test_data)
            test_parsed = json.loads(test_str)
            
            if test_parsed.get("test")[0] != 1:
                return False
            
            return True
        except Exception as e:
            self._logger.debug(f"JSON health check failed: {e}")
            return False
    
    def _get_file_path(self, collection: str) -> str:
        """
        Get full file path for a collection.
        
        Args:
            collection: Collection name (can be relative or absolute path)
            
        Returns:
            Full file path
        """
        if os.path.isabs(collection):
            return collection
        
        base_dir = self.client["base_directory"]
        
        # Ensure .json extension
        if not collection.lower().endswith('.json'):
            collection = f"{collection}.json"
        
        return os.path.join(base_dir, collection)
    
    def _ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for a file path exists.
        
        Args:
            file_path: Path to file
        """
        directory = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(directory, exist_ok=True)
    
    @contextlib.contextmanager
    def _open_json_file(self, file_path: str, mode: str = 'r') -> Generator[TextIO, None, None]:
        """
        Context manager for safely opening JSON files.
        
        Args:
            file_path: Path to the JSON file
            mode: File open mode ('r' for reading, 'w' for writing)
            
        Yields:
            File object
                
        Raises:
            FileNotFoundError: If the file doesn't exist (in read mode)
            PermissionError: If the file can't be accessed
            IOError: For other file-related errors
        """
        try:
            # Ensure directory exists for write operations
            if 'w' in mode:
                self._ensure_directory_exists(file_path)
                
            with open(file_path, mode, encoding=self.client["encoding"]) as f:
                yield f
        except FileNotFoundError:
            if 'r' in mode:
                self._logger.debug(f"JSON file not found: {file_path}")
                raise
            else:
                # For write mode, create the file
                self._ensure_directory_exists(file_path)
                with open(file_path, 'w', encoding=self.client["encoding"]) as f:
                    yield f
        except (PermissionError, IOError) as e:
            self._logger.error(f"File access error for {file_path}: {str(e)}")
            raise
    
    def _read_json_file(self, file_path: str, **kwargs) -> Any:
        """
        Read and parse a JSON file.
        
        Args:
            file_path: Path to the JSON file
            **kwargs: Additional json.load parameters
            
        Returns:
            Parsed JSON data
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file contains invalid JSON
        """
        try:
            with self._open_json_file(file_path, 'r') as f:
                return json.load(f, **kwargs)
        except FileNotFoundError:
            self._logger.debug(f"JSON file not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path}: {str(e)}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _write_json_file(self, file_path: str, data: Any, **kwargs) -> None:
        """
        Write data to a JSON file.
        
        Args:
            file_path: Path to the JSON file
            data: Data to write
            **kwargs: Additional json.dump parameters
            
        Raises:
            PermissionError: If the file can't be written
            TypeError: If the data contains non-serializable objects
        """
        try:
            # Extract indent from client config if not provided
            indent = kwargs.pop('indent', self.client.get('indent', 2))
            
            with self._open_json_file(file_path, 'w') as f:
                json.dump(data, f, indent=indent, **kwargs)
            self._logger.debug(f"Successfully wrote to {file_path}")
        except TypeError as e:
            error_msg = f"Cannot serialize to JSON: {str(e)}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _apply_path(self, data: Any, path: str) -> Any:
        """
        Extract data from a nested structure using dot notation.
        
        Args:
            data: Data structure to traverse
            path: Dot-notation path (e.g., "user.address.city")
            
        Returns:
            Value at the specified path or None if not found
        """
        if not path:
            return data
            
        components = path.split('.')
        current = data
        
        for component in components:
            if current is None:
                return None
                
            # Handle arrays with numeric indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            # Handle dictionaries
            elif isinstance(current, dict):
                current = current.get(component)
            else:
                return None
                
        return current
    
    def _update_path(self, data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specified path.
        
        Args:
            data: Data structure to modify
            path: Dot-notation path (e.g., "user.address.city")
            value: New value to set
            
        Returns:
            Updated data structure
        """
        if not path:
            return value
            
        # Make a copy to avoid modifying original
        if isinstance(data, dict):
            result = data.copy()
        elif isinstance(data, list):
            result = data.copy()
        else:
            # If data is not a container, start with empty dict
            result = {}
            
        components = path.split('.')
        current = result
        
        # Navigate to the parent of the target
        for i, component in enumerate(components[:-1]):
            # Handle array indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                # Extend the list if needed
                while len(current) <= index:
                    current.append({})
                    
                # Create a nested structure if needed
                if current[index] is None:
                    if i + 1 < len(components) and components[i+1].isdigit():
                        current[index] = []  # Next level is array
                    else:
                        current[index] = {}  # Next level is dict
                        
                current = current[index]
                
            # Handle dictionary keys
            else:
                # Create nested structure if needed
                if not isinstance(current, dict):
                    if isinstance(current, list):
                        # We can't modify the structure type
                        return result
                    else:
                        # Replace with dict
                        current = {}
                        
                # Create the next level if it doesn't exist
                if component not in current:
                    if i + 1 < len(components) and components[i+1].isdigit():
                        current[component] = []  # Next level is array
                    else:
                        current[component] = {}  # Next level is dict
                        
                current = current[component]
        
        # Set the value at the final path component
        last_component = components[-1]
        
        # Handle array indices
        if last_component.isdigit() and isinstance(current, list):
            index = int(last_component)
            # Extend the list if needed
            while len(current) <= index:
                current.append(None)
            current[index] = value
        # Handle dictionary keys
        elif isinstance(current, dict):
            current[last_component] = value
        # Can't set the value in this structure
        else:
            return result
            
        return result
    
    def _delete_path(self, data: Any, path: str) -> Any:
        """
        Delete data at a specified path.
        
        Args:
            data: Data structure to modify
            path: Dot-notation path (e.g., "user.address.city")
            
        Returns:
            Updated data structure with value removed
        """
        if not path or data is None:
            return data
            
        # Make a copy to avoid modifying original
        if isinstance(data, dict):
            result = data.copy()
        elif isinstance(data, list):
            result = data.copy()
        else:
            # Cannot delete from non-container
            return data
            
        components = path.split('.')
        
        # Special case: direct key in dict
        if len(components) == 1 and isinstance(result, dict):
            if components[0] in result:
                del result[components[0]]
            return result
            
        # Special case: direct index in list
        if len(components) == 1 and components[0].isdigit() and isinstance(result, list):
            index = int(components[0])
            if 0 <= index < len(result):
                result.pop(index)
            return result
            
        # For nested paths, navigate to the parent
        current = result
        for i, component in enumerate(components[:-1]):
            # Handle array indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    # Path doesn't exist
                    return result
            # Handle dictionary keys
            elif isinstance(current, dict) and component in current:
                current = current[component]
            else:
                # Path doesn't exist
                return result
                
        # Delete from parent
        last_component = components[-1]
        
        # Handle array indices
        if last_component.isdigit() and isinstance(current, list):
            index = int(last_component)
            if 0 <= index < len(current):
                current.pop(index)
        # Handle dictionary keys
        elif isinstance(current, dict) and last_component in current:
            del current[last_component]
            
        return result
    
    def _find_document_by_id(self, data: Any, document_id: str, id_field: str = 'id') -> Optional[Dict]:
        """
        Find a document by ID in different data structures.
        
        Args:
            data: JSON data structure
            document_id: Document ID to find
            id_field: Field name to use as document identifier
            
        Returns:
            Document data or None if not found
        """
        if not data:
            return None
            
        if isinstance(data, dict):
            # Direct key lookup
            if document_id in data:
                return data[document_id]
            
            # Search for document with matching ID field
            for key, value in data.items():
                if isinstance(value, dict) and value.get(id_field) == document_id:
                    return value
        
        elif isinstance(data, list):
            # Find in array by id field
            for item in data:
                if isinstance(item, dict) and item.get(id_field) == document_id:
                    return item
        
        return None
    
    def _ensure_id_in_document(self, data: Any, document_id: str, id_field: str = 'id') -> dict:
        """
        Ensure the document has the correct ID field.
        
        Args:
            data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier
            
        Returns:
            Document with ID field
        """
        if not isinstance(data, dict):
            return {id_field: document_id, "value": data}
        
        result = data.copy()
        result[id_field] = document_id
        return result
    
    def _create_initial_structure(self, data: Any, document_id: str, id_field: str = 'id') -> Any:
        """
        Create an initial data structure for a document.
        
        Args:
            data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier
            
        Returns:
            New data structure
        """
        if isinstance(data, dict):
            # For dict data, create a list with ID field
            doc_with_id = data.copy()
            doc_with_id[id_field] = document_id
            return [doc_with_id]
        else:
            # For non-dict data, wrap it properly with id and value
            wrapped_doc = {id_field: document_id, "value": data}
            return {document_id: wrapped_doc}
    
    def _add_document_to_structure(
        self, 
        data: Any, 
        doc_data: Any, 
        document_id: str,
        id_field: str = 'id'
    ) -> Any:
        """
        Add a document to an existing data structure.
        
        Args:
            data: Current data structure
            doc_data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier
            
        Returns:
            Updated data structure
        """
        if isinstance(data, dict):
            # Add to dictionary - preserve original behavior for internal methods
            data[document_id] = doc_data
            return data
        
        elif isinstance(data, list):
            # Add to list with ID
            if isinstance(doc_data, dict):
                # Make sure document has ID
                doc_with_id = doc_data.copy()
                doc_with_id[id_field] = document_id
                data.append(doc_with_id)
            else:
                # Wrap non-dict data
                data.append({id_field: document_id, "value": doc_data})
            return data
        
        else:
            # Create new structure
            return self._create_initial_structure(doc_data, document_id, id_field)
    
    def _add_document_to_structure_simple(
        self, 
        data: Any, 
        prepared_doc: Any, 
        document_id: str
    ) -> Any:
        """
        Add a properly wrapped document to an existing data structure.
        
        Args:
            data: Current data structure
            prepared_doc: Already wrapped document data
            document_id: Document ID (for key-based storage)
            
        Returns:
            Updated data structure
        """
        if isinstance(data, dict):
            # Add to dictionary using document_id as key
            data[document_id] = prepared_doc
            return data
        
        elif isinstance(data, list):
            # Add to list
            data.append(prepared_doc)
            return data
        
        else:
            # Replace scalar with new structure
            return {document_id: prepared_doc}
    
    def _update_document_in_structure(
        self,
        data: Any,
        doc_data: Any,
        document_id: str,
        id_field: str = 'id',
        merge: bool = True
    ) -> tuple[Any, bool]:
        """
        Update a document in an existing data structure.
        
        Args:
            data: Current data structure
            doc_data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier
            merge: Whether to merge with existing document or replace entirely
            
        Returns:
            Tuple of (updated data, whether document was created)
        """
        # Find existing document
        doc = self._find_document_by_id(data, document_id, id_field)
        created_new = False
        
        if doc is None:
            # Document not found, add it
            created_new = True
            data = self._add_document_to_structure(data, doc_data, document_id, id_field)
        else:
            # Document exists, update it
            if isinstance(data, dict):
                # Dictionary with direct keys
                if document_id in data:
                    # Merge existing document with new data for UPDATE operations
                    existing_doc = data[document_id]
                    if isinstance(existing_doc, dict) and isinstance(doc_data, dict) and merge:
                        data[document_id] = self._merge_documents(existing_doc, doc_data)
                    else:
                        data[document_id] = self._ensure_id_in_document(doc_data, document_id, id_field)
                else:
                    # Find and update by ID field
                    for key, value in data.items():
                        if isinstance(value, dict) and value.get(id_field) == document_id:
                            if isinstance(value, dict) and isinstance(doc_data, dict) and merge:
                                merged_doc = self._merge_documents(value, doc_data)
                                data[key] = self._ensure_id_in_document(merged_doc, document_id, id_field)
                            else:
                                data[key] = self._ensure_id_in_document(doc_data, document_id, id_field)
                            break
            
            elif isinstance(data, list):
                # List of documents
                for i, item in enumerate(data):
                    if isinstance(item, dict) and item.get(id_field) == document_id:
                        if isinstance(item, dict) and isinstance(doc_data, dict) and merge:
                            merged_doc = self._merge_documents(item, doc_data)
                            data[i] = self._ensure_id_in_document(merged_doc, document_id, id_field)
                        else:
                            data[i] = self._ensure_id_in_document(doc_data, document_id, id_field)
                        break
        
        return data, created_new
    
    def _merge_documents(self, doc1: Dict[str, Any], doc2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two documents recursively.
        
        Args:
            doc1: First document
            doc2: Second document
            
        Returns:
            Merged document
        """
        if not isinstance(doc1, dict) or not isinstance(doc2, dict):
            return doc2
            
        result = doc1.copy()
        
        for key, value in doc2.items():
            # If both values are dicts, merge recursively
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_documents(result[key], value)
            # Otherwise, overwrite or add
            else:
                result[key] = value
                
        return result
    
    def _apply_query_filter(self, data: Any, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply query filtering to document data.
        
        Args:
            data: Document data
            query: Query parameters
            
        Returns:
            Dict with filtered data and metadata
        """
        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        sort_field = query.pop("sort", None)
        sort_order = query.pop("order", "asc").lower()
        
        # Handle empty data
        if data is None:
            return {"data": None, "count": 0, "is_collection": False}
            
        # Handle different data structures
        if isinstance(data, list):
            # Apply field filtering
            result = data
            if query:  # Only filter if there are query parameters remaining
                result = [
                    item for item in result 
                    if isinstance(item, dict) and 
                    all(
                        item.get(field) == value 
                        for field, value in query.items()
                    )
                ]
            
            # Apply sorting
            if sort_field and result:
                reverse = (sort_order == "desc")
                result.sort(
                    key=lambda x: x.get(sort_field) if isinstance(x, dict) else None,
                    reverse=reverse
                )
            
            # Apply pagination
            if offset and isinstance(offset, int) and offset > 0:
                result = result[offset:]
                
            if limit and isinstance(limit, int) and limit > 0:
                result = result[:limit]
                
            return {
                "data": result,
                "count": len(result),
                "is_collection": True
            }
            
        elif isinstance(data, dict):
            # Filter based on field values
            result = {}
            for key, value in data.items():
                if isinstance(value, dict) and all(
                    value.get(field) == query_value 
                    for field, query_value in query.items()
                ):
                    result[key] = value
            
            # Apply pagination to keys
            keys = list(result.keys())
            
            if offset and isinstance(offset, int) and offset > 0:
                keys = keys[offset:]
                
            if limit and isinstance(limit, int) and limit > 0:
                keys = keys[:limit]
                
            # Rebuild filtered dictionary
            if offset or limit:
                result = {k: result[k] for k in keys}
                
            return {
                "data": result,
                "count": len(result),
                "is_collection": True
            }
            
        # Other data types can't be filtered
        return {
            "data": data,
            "count": 0,
            "is_collection": False
        }
    
    def read(
        self, 
        collection: str, 
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Read data from JSON file.
        
        Args:
            collection: JSON file name/path
            document_id: Document ID to read
            query: Query parameters for filtering
            path: Dot-notation path for nested access
            **kwargs: Additional parameters
            
        Returns:
            Document data based on query and path
        """
        try:
            file_path = self._get_file_path(collection)
            
            if not os.path.exists(file_path):
                self._logger.debug(f"JSON file does not exist: {file_path}")
                return None
            
            # Extract service-specific parameters
            format_type = kwargs.pop('format', 'raw')
            id_field = kwargs.pop('id_field', 'id')
            
            # Read the JSON file
            data = self._read_json_file(file_path, **kwargs)
            
            # Apply document_id filter
            if document_id is not None:
                doc = self._find_document_by_id(data, document_id, id_field)
                if doc is None:
                    return None
                
                # Clean up: remove the injected ID field if it matches the document_id
                # to return data as it was originally written
                if isinstance(doc, dict) and doc.get(id_field) == document_id:
                    doc = doc.copy()
                    # Only remove the ID field if it matches the document_id we searched for
                    # This prevents removing legitimate ID fields that were part of original data
                    doc.pop(id_field, None)
                
                # Apply path extraction if needed
                if path:
                    return self._apply_path(doc, path)
                
                return doc
            
            # Apply path extraction (at collection level)
            if path:
                data = self._apply_path(data, path)
                if data is None:
                    return None
            
            # Apply query filters
            if query:
                filtered_result = self._apply_query_filter(data, query)
                data = filtered_result.get("data", data)
            
            # Return format based on request
            if format_type == 'records' and isinstance(data, dict):
                return list(data.values())
            else:
                return data
                
        except Exception as e:
            self._handle_error("read", e, collection=collection, document_id=document_id)
    
    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs
    ) -> StorageResult:
        """
        Write data to JSON file.
        
        Args:
            collection: JSON file name/path
            data: Data to write
            document_id: Document ID
            mode: Write mode (write, append, update, merge)
            path: Dot-notation path for nested updates
            **kwargs: Additional parameters
            
        Returns:
            StorageResult with operation details
        """
        # Validate mode parameter
        if not isinstance(mode, WriteMode):
            return self._create_error_result(
                "write",
                f"Unsupported write mode: {mode}",
                collection=collection
            )
        
        try:
            file_path = self._get_file_path(collection)
            
            # Extract service-specific parameters
            id_field = kwargs.pop('id_field', 'id')
            
            file_existed = os.path.exists(file_path)
            
            if mode == WriteMode.WRITE:
                # Simple write operation
                if document_id is not None:
                    # For document-based writes, read existing file and add/update document
                    current_data = None
                    if file_existed:
                        try:
                            current_data = self._read_json_file(file_path)
                        except (FileNotFoundError, ValueError):
                            current_data = None
                    
                    # Create initial structure if needed
                    if current_data is None:
                        current_data = self._create_initial_structure(data, document_id, id_field)
                    else:
                        # Prepare the document data with proper wrapping at API level
                        prepared_data = self._ensure_id_in_document(data, document_id, id_field)
                        
                        # Add document to existing structure with prepared data
                        current_data = self._add_document_to_structure_simple(
                        current_data, prepared_data, document_id
                        )
                    
                    self._write_json_file(file_path, current_data, **kwargs)
                else:
                    # Direct write (overwrite entire file)
                    self._write_json_file(file_path, data, **kwargs)
                
                return self._create_success_result(
                    "write",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path,
                    created_new=not file_existed
                )
            
            # Handle updating existing files
            current_data = None
            if file_existed:
                try:
                    current_data = self._read_json_file(file_path)
                except (FileNotFoundError, ValueError):
                    current_data = None
            
            if mode == WriteMode.UPDATE:
                # Update operation - fail if file or document doesn't exist
                if not file_existed:
                    return self._create_error_result(
                        "update",
                        f"File not found for update: {file_path}",
                        collection=collection
                    )
                
                if current_data is None:
                    return self._create_error_result(
                        "update",
                        f"Invalid JSON data in file: {file_path}",
                        collection=collection
                    )
                
                if path:
                    # Path-based update
                    if document_id:
                        # Update path in specific document
                        doc = self._find_document_by_id(current_data, document_id, id_field)
                        if doc is None:
                            return self._create_error_result(
                                "update",
                                f"Document with ID '{document_id}' not found for update",
                                collection=collection,
                                document_id=document_id
                            )
                        
                        # Update existing document
                        updated_doc = self._update_path(doc, path, data)
                        current_data = self._update_document_in_structure(
                            current_data, updated_doc, document_id, id_field
                        )[0]
                    else:
                        # Update path in entire file
                        current_data = self._update_path(current_data, path, data)
                else:
                    # Direct document update
                    if document_id is not None:
                        # Update specific document - must exist
                        doc = self._find_document_by_id(current_data, document_id, id_field)
                        if doc is None:
                            return self._create_error_result(
                                "update",
                                f"Document with ID '{document_id}' not found for update",
                                collection=collection,
                                document_id=document_id
                            )
                        
                        current_data, created_new = self._update_document_in_structure(
                            current_data, data, document_id, id_field
                        )
                    else:
                        # Update entire file
                        current_data = data
                
                self._write_json_file(file_path, current_data, **kwargs)
                return self._create_success_result(
                    "update",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path,
                    created_new=not file_existed
                )
            
            # Use appropriate structure if file doesn't exist or has invalid data
            # (Only for non-UPDATE modes)
            if current_data is None:
                if document_id is not None:
                    current_data = self._create_initial_structure(data, document_id, id_field)
                else:
                    current_data = [] if isinstance(data, list) else {}
            
            elif mode == WriteMode.APPEND:
                # Append operation
                if isinstance(current_data, list) and isinstance(data, list):
                    # Append to list
                    current_data.extend(data)
                elif isinstance(current_data, list):
                    # Append single item to list
                    current_data.append(data)
                elif isinstance(current_data, dict) and isinstance(data, dict):
                    # Merge dictionaries
                    current_data.update(data)
                elif document_id is not None:
                    # Prepare the document data with proper wrapping at API level
                    prepared_data = self._ensure_id_in_document(data, document_id, id_field)
                    
                    # Add document with ID
                    current_data = self._add_document_to_structure_simple(
                        current_data, prepared_data, document_id
                    )
                else:
                    # Can't append to incompatible structures
                    return self._create_error_result(
                        "append",
                        "Cannot append to incompatible data structure",
                        collection=collection
                    )
                
                self._write_json_file(file_path, current_data, **kwargs)
                return self._create_success_result(
                    "append",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path
                )
            
            else:
                return self._create_error_result(
                    "write",
                    f"Unsupported write mode: {mode}",
                    collection=collection
                )
                
        except Exception as e:
            error_msg = f"Write operation failed: {str(e)}"
            self._logger.error(f"[{self.provider_name}] {error_msg} (collection={collection}, mode={mode.value})")
            return self._create_error_result(
                "write",
                error_msg,
                collection=collection
            )
    
    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> StorageResult:
        """
        Delete from JSON file.
        
        Args:
            collection: JSON file name/path
            document_id: Document ID to delete
            path: Dot-notation path to delete
            query: Query for batch delete
            **kwargs: Additional parameters
            
        Returns:
            StorageResult with operation details
        """
        try:
            file_path = self._get_file_path(collection)
            
            # Extract service-specific parameters
            id_field = kwargs.pop('id_field', 'id')
            
            if not os.path.exists(file_path):
                return self._create_error_result(
                    "delete",
                    f"File not found: {file_path}",
                    collection=collection
                )
            
            # Read current data
            current_data = self._read_json_file(file_path)
            if current_data is None:
                return self._create_error_result(
                    "delete",
                    f"Invalid JSON data in file: {file_path}",
                    collection=collection
                )
            
            # Handle deleting entire file
            if document_id is None and path is None and not query:
                os.remove(file_path)
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=file_path,
                    collection_deleted=True
                )
            
            # Handle deleting specific path
            if path:
                if document_id:
                    # Delete path in specific document
                    doc = self._find_document_by_id(current_data, document_id, id_field)
                    if doc is None:
                        return self._create_error_result(
                            "delete",
                            f"Document with ID '{document_id}' not found",
                            collection=collection,
                            document_id=document_id
                        )
                    
                    # Delete path in document
                    updated_doc = self._delete_path(doc, path)
                    current_data = self._update_document_in_structure(
                        current_data, updated_doc, document_id, id_field, merge=False
                    )[0]
                else:
                    # Delete path in entire file
                    current_data = self._delete_path(current_data, path)
                
                self._write_json_file(file_path, current_data)
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path,
                    path=path
                )
            
            # Handle deleting document by ID
            if document_id is not None:
                deleted = False
                
                if isinstance(current_data, dict):
                    # Remove from dictionary
                    if document_id in current_data:
                        del current_data[document_id]
                        deleted = True
                    else:
                        # Look for document with matching ID field
                        keys_to_delete = []
                        for key, value in current_data.items():
                            if isinstance(value, dict) and value.get(id_field) == document_id:
                                keys_to_delete.append(key)
                                deleted = True
                        
                        for key in keys_to_delete:
                            del current_data[key]
                
                elif isinstance(current_data, list):
                    # Remove from list
                    original_length = len(current_data)
                    current_data = [
                        item for item in current_data 
                        if not (isinstance(item, dict) and item.get(id_field) == document_id)
                    ]
                    deleted = len(current_data) < original_length
                
                if not deleted:
                    return self._create_error_result(
                        "delete",
                        f"Document with ID '{document_id}' not found",
                        collection=collection,
                        document_id=document_id
                    )
                
                self._write_json_file(file_path, current_data)
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=file_path,
                    document_id=document_id
                )
            
            # Handle batch delete with query
            if query and isinstance(current_data, list):
                original_length = len(current_data)
                
                # Apply query filters
                filtered_result = self._apply_query_filter(current_data, query)
                filtered_data = filtered_result.get("data", [])
                
                # Keep track of deleted documents
                deleted_ids = []
                for item in current_data:
                    if isinstance(item, dict) and item.get(id_field) and item not in filtered_data:
                        deleted_ids.append(item.get(id_field))
                
                # Write back the filtered data
                self._write_json_file(file_path, filtered_data)
                
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=file_path,
                    total_affected=original_length - len(filtered_data),
                    deleted_ids=deleted_ids
                )
            
            return self._create_error_result(
                "delete",
                "Invalid delete operation",
                collection=collection
            )
            
        except Exception as e:
            error_msg = f"Delete operation failed: {str(e)}"
            self._logger.error(f"[{self.provider_name}] {error_msg} (collection={collection})")
            return self._create_error_result(
                "delete",
                error_msg,
                collection=collection
            )
    
    def exists(
        self, 
        collection: str, 
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Check if JSON file, document, or path exists.
        
        Args:
            collection: JSON file name/path
            document_id: Document ID to check
            path: Dot-notation path to check
            **kwargs: Additional parameters
            
        Returns:
            True if exists, False otherwise
        """
        try:
            file_path = self._get_file_path(collection)
            
            if not os.path.exists(file_path):
                return False
            
            # Extract service-specific parameters
            id_field = kwargs.pop('id_field', 'id')
            
            # Check file existence only
            if document_id is None and path is None:
                return True
            
            # Read the file
            data = self._read_json_file(file_path)
            if data is None:
                return False
            
            # Check document existence
            if document_id is not None:
                doc = self._find_document_by_id(data, document_id, id_field)
                if doc is None:
                    return False
                
                # Check path in document
                if path:
                    value = self._apply_path(doc, path)
                    return value is not None
                
                return True
            
            # Check path existence in file
            if path:
                value = self._apply_path(data, path)
                return value is not None
            
            return True
            
        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False
    
    def count(
        self,
        collection: str,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Count documents or items in JSON file.
        
        Args:
            collection: JSON file name/path
            query: Optional query parameters for filtering
            path: Optional path for nested counting
            **kwargs: Additional parameters
            
        Returns:
            Count of items
        """
        try:
            file_path = self._get_file_path(collection)
            
            if not os.path.exists(file_path):
                return 0
            
            # Read the file
            data = self._read_json_file(file_path)
            if data is None:
                return 0
            
            # Apply path extraction
            if path:
                data = self._apply_path(data, path)
                if data is None:
                    return 0
            
            # Apply query filtering
            if query:
                filtered_result = self._apply_query_filter(data, query)
                data = filtered_result.get("data", data)
                return filtered_result.get("count", 0)
            
            # Count based on data type
            if isinstance(data, list):
                return len(data)
            elif isinstance(data, dict):
                return len(data)
            else:
                return 1  # Scalar values count as 1
            
        except Exception as e:
            self._logger.debug(f"Error counting items: {e}")
            return 0
    
    def list_collections(self, **kwargs) -> List[str]:
        """
        List all JSON files in the base directory.
        
        Args:
            **kwargs: Additional parameters
            
        Returns:
            List of JSON file names
        """
        try:
            base_dir = self.client["base_directory"]
            
            if not os.path.exists(base_dir):
                return []
            
            json_files = []
            for item in os.listdir(base_dir):
                if item.lower().endswith('.json'):
                    json_files.append(item)
            
            return sorted(json_files)
            
        except Exception as e:
            self._logger.debug(f"Error listing collections: {e}")
            return []
Unraveled document ID storage bug in data management method54sNow I can see the exact problem! Looking at lines 530-537 in the read method:
python# Clean up: remove the injected ID field if it matches the document_id
# to return data as it was originally written
if isinstance(doc, dict) and doc.get(id_field) == document_id:
    doc = doc.copy()
    # Only remove the ID field if it matches the document_id we searched for
    # This prevents removing legitimate ID fields that were part of original data
    doc.pop(id_field, None)
The logic is:

The test writes {"id": 1, "nested": {"value": "test"}} with document_id="test"
When reading by document_id="test", it finds the document
It checks if doc.get("id") == document_id - so 1 == "test" which is False
Since they don't match, it should NOT remove the ID field

But the test is still failing, which means the ID field is still being removed somehow.
Let me look at the _find_document_by_id method to understand how the document is being found and what's happening to the ID field.
Looking at the _find_document_by_id method around line 369-389:
pythondef _find_document_by_id(self, data: Any, document_id: str, id_field: str = 'id') -> Optional[Dict]:
    """
    Find a document by ID in different data structures.
    
    Args:
        data: JSON data structure
        document_id: Document ID to find
        id_field: Field name to use as document identifier
        
    Returns:
        Document data or None if not found
    """
    if not data:
        return None
        
    if isinstance(data, dict):
        # Direct key lookup
        if document_id in data:
            return data[document_id]
        
        # Search for document with matching ID field
        for key, value in data.items():
            if isinstance(value, dict) and value.get(id_field) == document_id:
                return value
    
    elif isinstance(data, list):
        # Find in array by id field
        for item in data:
            if isinstance(item, dict) and item.get(id_field) == document_id:
                return item
    
    return None
I'm investigating a potential discrepancy in how the document is being located and processed. The method seems to have multiple search strategies that could impact how the document is found and returned.
The write method reveals some interesting details about document preparation. When a document is being added, there's a specific process of ensuring the ID is correctly embedded in the document structure. I'll examine the _ensure_id_in_document method to understand how document IDs are being handled during the write operation.
The method appears to forcibly overwrite any existing ID field with the provided document_id. This means that when a document is written, its original identifier gets replaced, potentially causing unexpected data transformations. The current implementation will always prioritize the externally provided document_id over any pre-existing identifier in the document.
This behavior could lead to significant data integrity issues, especially when working with documents that already have their own unique identifiers. The method essentially guarantees that the stored document's ID will always match the externally supplied document_id, regardless of the original document's internal structure.Now I can see the exact issue! Looking at the JSON service code, the problem is in the _ensure_id_in_document method around line 392. Here's what's happening:

Test writes {"id": 1, "nested": {"value": "test"}} with document_id="test"
The _ensure_id_in_document method overwrites the existing id: 1 field with id: "test" (the document_id)
When reading back, it finds the document with id: "test" and removes it because it matches the document_id
This leaves only {"nested": {"value": "test"}}

The bug is that _ensure_id_in_document should preserve existing ID fields, not overwrite them. Let me fix this:Fedit_fileRequest{
  `path`: `C:\\Users\\jwwel\\Documents\\code\\AgentMap\\src\\agentmap\\services\\storage\\json_service.py`,
  `edits`: [
    {
      `newText`: `    def _ensure_id_in_document(self, data: Any, document_id: str, id_field: str = 'id') -> dict:
        \"\"\"
        Ensure the document has the correct ID field.
        
        Args:
            data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier
            
        Returns:
            Document with ID field
        \"\"\"
        if not isinstance(data, dict):
            return {id_field: document_id, \"value\": data}
        
        result = data.copy()
        
        # Only inject the document_id as the ID field if the document doesn't already have one
        # This preserves legitimate ID fields that were part of the original data
        if id_field not in result:
            result[id_field] = document_id
        
        return result`,
      `oldText`: `    def _ensure_id_in_document(self, data: Any, document_id: str, id_field: str = 'id') -> dict:
        \"\"\"
        Ensure the document has the correct ID field.
        
        Args:
            data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier
            
        Returns:
            Document with ID field
        \"\"\"
        if not isinstance(data, dict):
            return {id_field: document_id, \"value\": data}
        
        result = data.copy()
        result[id_field] = document_id
        return result`
    }
  ]
}Response```diff
Index: C:\Users\jwwel\Documents\code\AgentMap\src\agentmap\services\storage\json_service.py
===================================================================
--- C:\Users\jwwel\Documents\code\AgentMap\src\agentmap\services\storage\json_service.py	original
+++ C:\Users\jwwel\Documents\code\AgentMap\src\agentmap\services\storage\json_service.py	modified
@@ -446,9 +446,14 @@
         if not isinstance(data, dict):
             return {id_field: document_id, "value": data}
         
         result = data.copy()
-        result[id_field] = document_id
+        
+        # Only inject the document_id as the ID field if the document doesn't already have one
+        # This preserves legitimate ID fields that were part of the original data
+        if id_field not in result:
+            result[id_field] = document_id
+        
         return result
     
     def _create_initial_structure(self, data: Any, document_id: str, id_field: str = 'id') -> Any:
         """
```

Thought process10sNow I also need to update the read method's cleanup logic. The current logic assumes that if doc.get(id_field) == document_id, then it was an injected ID field that should be removed. But with my fix, legitimate ID fields won't be overwritten, so this logic needs to be more sophisticated.
The cleanup logic should only remove the ID field if:

It matches the document_id (current check)
AND it was actually injected by the system (not part of the original data)

However, we can't easily determine if an ID field was injected or original after the fact.
A better approach might be to:

Keep the cleanup logic for now but make it more conservative
Only remove the ID field if it matches the document_id AND the field seems to be a system-injected identifier (like if it's a string that matches the document_id exactly)

But actually, let me think about this differently. The purpose of the cleanup is to return data "as it was originally written". But with my fix to _ensure_id_in_document, legitimate ID fields will be preserved, so we should NOT remove them on read.
The cleanup logic should only remove ID fields that were injected by the system (i.e., when the original data didn't have an ID field).
One approach is to change the cleanup logic to be more conservative - only remove the ID field if it's a string and matches the document_id exactly, indicating it was likely injected.
Actually, let me step back and think about this more fundamentally. The issue is that the JSON service is trying to be too clever with ID field management.
Looking at the failing tests, they all involve storing data that already has an id field with a different value than the document_id. The users expect to get back exactly what they stored.
I think the simplest fix is to update the read method to not remove legitimate ID fields. The cleanup logic should only remove ID fields that were clearly injected by the system.
Let me update the read method:Now I need to update the read method's cleanup logic. The current logic removes ID fields too aggressively. With my fix to _ensure_id_in_document, legitimate ID fields are preserved, so the cleanup logic should be more conservative:Fedit_fileRequest{
  `path`: `C:\\Users\\jwwel\\Documents\\code\\AgentMap\\src\\agentmap\\services\\storage\\json_service.py`,
  `edits`: [
    {
      `newText`: `                # Clean up: only remove injected ID fields, not legitimate ones from original data
                # We only remove the ID field if:
                # 1. It matches the document_id (indicating it was injected)
                # 2. AND it's a string (injected IDs are always strings from document_id)
                # 3. AND the original data likely didn't have this ID (conservative approach)
                if (isinstance(doc, dict) and 
                    doc.get(id_field) == document_id and 
                    isinstance(doc.get(id_field), str)):
                    doc = doc.copy()
                    # Only remove the ID field if it matches the document_id we searched for
                    # and appears to be a system-injected identifier
                    doc.pop(id_field, None)`,
      `oldText`: `                # Clean up: remove the injected ID field if it matches the document_id
                # to return data as it was originally written
                if isinstance(doc, dict) and doc.get(id_field) == document_id:
                    doc = doc.copy()
                    # Only remove the ID field if it matches the document_id we searched for
                    # This prevents removing legitimate ID fields that were part of original data
                    doc.pop(id_field, None)`
    }
  ]
}Response```diff
Index: C:\Users\jwwel\Documents\code\AgentMap\src\agentmap\services\storage\json_service.py
===================================================================
--- C:\Users\jwwel\Documents\code\AgentMap\src\agentmap\services\storage\json_service.py	original
+++ C:\Users\jwwel\Documents\code\AgentMap\src\agentmap\services\storage\json_service.py	modified
@@ -770,14 +770,19 @@
                 doc = self._find_document_by_id(data, document_id, id_field)
                 if doc is None:
                     return None
                 
-                # Clean up: remove the injected ID field if it matches the document_id
-                # to return data as it was originally written
-                if isinstance(doc, dict) and doc.get(id_field) == document_id:
+                # Clean up: only remove injected ID fields, not legitimate ones from original data
+                # We only remove the ID field if:
+                # 1. It matches the document_id (indicating it was injected)
+                # 2. AND it's a string (injected IDs are always strings from document_id)
+                # 3. AND the original data likely didn't have this ID (conservative approach)
+                if (isinstance(doc, dict) and 
+                    doc.get(id_field) == document_id and 
+                    isinstance(doc.get(id_field), str)):
                     doc = doc.copy()
                     # Only remove the ID field if it matches the document_id we searched for
-                    # This prevents removing legitimate ID fields that were part of original data
+                    # and appears to be a system-injected identifier
                     doc.pop(id_field, None)
                 
                 # Apply path extraction if needed
                 if path:
```

Investigated JSON data transformation test failure and root cause.4sLet me also check the issue with the other failing tests. The second test test_json_to_csv_data_transformation_coordination has this error:
AssertionError: {'value': [{'id': 1, 'name': 'Alice', 'department': 'Engineering', 'salary': 75000}, {'id': 2, 'name': 'Bob', 'department': 'Marketing', 'salary': 65000}, {'id': 3, 'name': 'Carol', 'department': 'Engineering', 'salary': 80000}]} is not an instance of <class 'list'> : JSON data should be a list
This suggests that the JSON service is wrapping list data in a dict with a "value" key, when the test expects to get the list directly.
Let me check what that test is doing to understand better.Now let me run the first failing test to see if my fix works:Prun_test_methodRequest{
  `verbose`: true,
  `test_file`: `tests/fresh_suite/integration/test_storage_service_coordination.py`,
  `test_class`: `TestStorageServiceCoordination`,
  `test_method`: `test_automatic_storage_type_selection`,
  `project_name`: `AgentMap`
}Response{
  "success": false,
  "return_code": 1,
  "command": "cd /d C:\\Users\\jwwel\\Documents\\code\\AgentMap && C:\\Python312\\Scripts\\poetry.exe -P C:\\Users\\jwwel\\Documents\\code\\AgentMap run pytest -v --tb=short --disable-warnings tests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection -v",
  "summary": {
    "total": 1,
    "passed": 0,
    "failed": 1,
    "skipped": 0,
    "errors": 0,
    "duration": 2.86
  },
  "project_path": "C:\\Users\\jwwel\\Documents\\code\\AgentMap",
  "used_poetry": true,
  "execution_time": 4.345574,
  "warnings": [
    "======================== 1 failed, 1 warning in 2.86s ========================="
  ],
  "output": "============================= test session starts =============================\nplatform win32 -- Python 3.12.10, pytest-8.4.0, pluggy-1.6.0 -- C:\\Users\\jwwel\\Documents\\code\\AgentMap\\.venv\\Scripts\\python.exe\ncachedir: .pytest_cache\nrootdir: C:\\Users\\jwwel\\Documents\\code\\AgentMap\nconfigfile: pytest.ini\nplugins: anyio-4.9.0, langsmith-0.3.42, cov-6.1.1, mock-3.14.0\ncollecting ... collected 1 item\n\ntests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection FAILED [100%]\n\n================================== FAILURES ===================================\n____ TestStorageServiceCoordination.test_automatic_storage_type_selection _____\ntests\\fresh_suite\\integration\\test_storage_service_coordination.py:376: in test_automatic_storage_type_selection\n    self.assertEqual(read_data, scenario[\"data\"])\nE   AssertionError: {'nested': {'value': 'test'}} != {'id': 1, 'nested': {'value': 'test'}}\nE   - {'nested': {'value': 'test'}}\nE   + {'id': 1, 'nested': {'value': 'test'}}\nE   ?  +++++++++\n---------------------------- Captured stdout call -----------------------------\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Initialized\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Default providers initialized\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Initialized\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Initialized with FeaturesRegistryService coordination\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Initialized with all dependencies\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Service status: {'agent_registry_service': True, 'features_registry_service': True, 'dependency_checker_service': True, 'app_config_service': True, 'logging_service': True, 'all_dependencies_injected': True}\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: \\U0001f680 [ApplicationBootstrapService] Starting application bootstrap\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registering core agents\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered default agent: DefaultAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: default\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'echo': EchoAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: echo\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'branching': BranchingAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: branching\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'failure': FailureAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: failure\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'success': SuccessAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: success\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'input': InputAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: input\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'graph': GraphAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered core agent: graph\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registered 7/7 core agents\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Dynamically discovering custom agents\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Scanning custom agents directory: C:\\\\Users\\\\jwwel\\\\AppData\\\\Local\\\\Temp\\\\tmpd76rlsfa\\\\custom_agents\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] No Python files found in custom agents directory\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] No custom agent classes found\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Discovering and registering LLM agents\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Feature enabled: llm\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Discovering providers for category: llm\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] All 1 imports validated successfully\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'openai' in category 'llm' validation set to: True\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check passed for: langchain_anthropic\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] All 1 imports validated successfully\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'anthropic' in category 'llm' validation set to: True\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: langchain_google_genai\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['langchain_google_genai']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'google' in category 'llm' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for llm.google: ['langchain_google_genai']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Provider discovery results for llm: {'openai': True, 'anthropic': True, 'google': False}\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'openai': OpenAIAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: openai\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'gpt': OpenAIAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: gpt\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'chatgpt': OpenAIAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: chatgpt\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registered 3 agents for LLM provider: openai\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'anthropic': AnthropicAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: anthropic\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'claude': AnthropicAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: claude\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Registered 2 agents for LLM provider: anthropic\\n[DEBUG] agentmap.services.agent_registry_service.AgentRegistryService: [AgentRegistryService] Registered agent 'llm': LLMAgent\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered agent: llm\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 Registered base LLM agent\\n[INFO] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] \\u2705 LLM agents registered for providers: ['openai', 'anthropic']\\n[DEBUG] agentmap.services.application_bootstrap_service.ApplicationBootstrapService: [ApplicationBootstrapService] Discovering and registering storage agents\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Feature enabled: storage\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Discovering providers for category: storage\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] All 1 imports validated successfully\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'csv' in category 'storage' validation set to: True\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: chromadb\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['chromadb']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'vector' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.vector: ['chromadb']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: firebase_admin\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['firebase_admin']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'firebase' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.firebase: ['firebase_admin']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: azure-storage-blob\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['azure-storage-blob']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'azure_blob' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.azure_blob: ['azure-storage-blob']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: boto3\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['boto3']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'aws_s3' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.aws_s3: ['boto3']\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] Dependency check failed for: google-cloud-storage\\n[DEBUG] agentmap.services.dependency_checker_service.DependencyCheckerService: [DependencyCheckerService] 1 imports failed: ['google-cloud-storage']\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Provider 'gcp_storage' in category 'storage' validation set to: False\\n[DEBUG] agentmap.services.features_registry_service.FeaturesRegistryService: [FeaturesRegistryService] Recorded missing dependencies for storage.gcp_storage: ['google-cloud-storage']\\n[DEBUG] agentmap.services.\n\n... [OUTPUT TRUNCATED FOR BREVITY] ...\n\nINFO     config.bootstrap:config_service.py:89 Loading configuration from: C:\\Users\\jwwel\\AppData\\Local\\Temp\\tmpd76rlsfa\\integration_test_config.yaml\nINFO     config.bootstrap:config_service.py:96 Successfully loaded configuration from C:\\Users\\jwwel\\AppData\\Local\\Temp\\tmpd76rlsfa\\integration_test_config.yaml\nINFO     config.bootstrap:config_service.py:100 Loaded configuration sections: ['execution', 'llm', 'logging', 'paths', 'routing', 'storage_config_path']\nINFO     bootstrap.app_config:app_config_service.py:71 [AppConfigService] Application configuration loaded successfully\n=========================== short test summary info ===========================\nFAILED tests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection - AssertionError: {'nested': {'value': 'test'}} != {'id': 1, 'nested': {'value': 'test'}}\n- {'nested': {'value': 'test'}}\n+ {'id': 1, 'nested': {'value': 'test'}}\n?  +++++++++\n======================== 1 failed, 1 warning in 2.86s =========================\n",
  "full_command": [
    "cmd",
    "/c",
    "cd /d C:\\Users\\jwwel\\Documents\\code\\AgentMap && C:\\Python312\\Scripts\\poetry.exe -P C:\\Users\\jwwel\\Documents\\code\\AgentMap run pytest -v --tb=short --disable-warnings tests/fresh_suite/integration/test_storage_service_coordination.py::TestStorageServiceCoordination::test_automatic_storage_type_selection -v"
  ],
  "stderr": "",
  "poetry_executable": "C:\\Python312\\Scripts\\poetry.exe"
}The test is still failing. Let me debug this further. 1sThe test is still failing. Let me debug this further. Let me look at the specific test to understand what it's doing:The test is still failing. Let me look at the specific test logic to understand exactly what it's doing:Fread_fileRequest{
  `path`: `C:\\Users\\jwwel\\Documents\\code\\AgentMap\	ests\\fresh_suite\\integration\	est_storage_service_coordination.py`
}Response"""
Storage Service Coordination Integration Tests.

This module tests the coordination between all storage services (MemoryService, 
FileService, JsonService, CsvService, VectorService) using the StorageManager 
and real DI container instances. Tests storage type selection, fallback mechanisms,
data migration between storage types, and concurrent storage operations.
"""

import unittest
import tempfile
import json
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.services.storage.types import WriteMode, StorageResult
from agentmap.services.storage.protocols import StorageService
from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException


class TestStorageServiceCoordination(BaseIntegrationTest):
    """
    Integration tests for StorageManager coordination of multiple storage backends.
    
    Tests real coordination between:
    - MemoryService for in-memory caching
    - FileService for file system operations
    - JsonService for structured JSON data
    - CsvService for tabular data
    - VectorService for embeddings and semantic search
    - StorageManager for coordinating all services
    """
    
    def setup_services(self):
        """Initialize storage services for coordination testing."""
        super().setup_services()
        
        # Initialize all storage services through StorageManager
        self.storage_manager = self.container.storage_service_manager()
        self.memory_service = self.storage_manager.get_service("memory")
        self.file_service = self.storage_manager.get_service("file")
        self.json_service = self.storage_manager.get_service("json")
        self.csv_service = self.storage_manager.get_service("csv")
        
        # Initialize vector service if available
        try:
            self.vector_service = self.storage_manager.get_service("vector")
        except Exception as e:
            self.logging_service.get_class_logger(self).warning(f"Vector service not available: {e}")
            self.vector_service = None
        
        # Create test data directories
        self.test_storage_dir = Path(self.temp_dir) / "storage_test"
        self.test_storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Test data for coordination scenarios
        self.test_data = {
            "simple_data": {"id": 1, "name": "test", "value": 100},
            "complex_data": {
                "user_id": "user_123",
                "profile": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "preferences": {
                        "theme": "dark",
                        "notifications": True
                    }
                },
                "activity": [
                    {"timestamp": "2025-06-01T10:00:00Z", "action": "login"},
                    {"timestamp": "2025-06-01T10:05:00Z", "action": "view_dashboard"},
                    {"timestamp": "2025-06-01T10:10:00Z", "action": "edit_profile"}
                ]
            },
            "tabular_data": [
                {"id": 1, "name": "Alice", "department": "Engineering", "salary": 75000},
                {"id": 2, "name": "Bob", "department": "Marketing", "salary": 65000},
                {"id": 3, "name": "Carol", "department": "Engineering", "salary": 80000}
            ]
        }
    
    # =============================================================================
    # 1. StorageManager Provider Registration and Discovery Tests
    # =============================================================================
    
    def test_storage_manager_provider_registration(self):
        """Test StorageManager registers and discovers all storage providers."""
        # Test provider availability
        available_providers = self.storage_manager.list_available_providers()
        
        # Verify core providers are available
        expected_core_providers = ["memory", "file", "json", "csv"]
        for provider in expected_core_providers:
            self.assertIn(provider, available_providers, 
                         f"Provider '{provider}' should be available")
            self.assertTrue(self.storage_manager.is_provider_available(provider),
                          f"Provider '{provider}' should be available via is_provider_available")
        
        # Test provider service retrieval
        for provider in expected_core_providers:
            with self.subTest(provider=provider):
                service = self.storage_manager.get_service(provider)
                self.assertIsNotNone(service, f"Should retrieve {provider} service")
                self.assertEqual(service.get_provider_name(), provider,
                               f"Service should identify as {provider} provider")
                
                # Verify service implements StorageService protocol
                self.assertTrue(hasattr(service, 'read'), f"{provider} should have read method")
                self.assertTrue(hasattr(service, 'write'), f"{provider} should have write method")
                self.assertTrue(hasattr(service, 'exists'), f"{provider} should have exists method")
                self.assertTrue(hasattr(service, 'health_check'), f"{provider} should have health_check method")
    
    def test_storage_manager_health_check_coordination(self):
        """Test StorageManager coordinates health checks across all providers."""
        # Test health check for all providers
        health_status = self.storage_manager.health_check()
        
        # Verify health status for each provider
        expected_providers = ["memory", "file", "json", "csv"]
        for provider in expected_providers:
            self.assertIn(provider, health_status, f"Health status should include {provider}")
            self.assertIsInstance(health_status[provider], bool, 
                                f"Health status for {provider} should be boolean")
        
        # Test individual provider health check
        for provider in expected_providers:
            with self.subTest(provider=provider):
                individual_health = self.storage_manager.health_check(provider)
                self.assertIn(provider, individual_health, 
                            f"Individual health check should include {provider}")
                self.assertEqual(individual_health[provider], health_status[provider],
                               f"Individual and bulk health check should match for {provider}")
    
    def test_storage_manager_service_caching_coordination(self):
        """Test StorageManager correctly caches and manages service instances."""
        # Test service caching
        memory_service1 = self.storage_manager.get_service("memory")
        memory_service2 = self.storage_manager.get_service("memory")
        
        # Should return same cached instance
        self.assertIs(memory_service1, memory_service2, 
                     "StorageManager should cache service instances")
        
        # Test cache clearing
        self.storage_manager.clear_cache("memory")
        memory_service3 = self.storage_manager.get_service("memory")
        
        # Should create new instance after cache clear
        self.assertIsNot(memory_service1, memory_service3,
                        "Should create new instance after cache clear")
        
        # Test clearing all caches
        json_service1 = self.storage_manager.get_service("json")
        self.storage_manager.clear_cache()
        json_service2 = self.storage_manager.get_service("json")
        
        self.assertIsNot(json_service1, json_service2,
                        "Should create new instances after clearing all caches")
    
    # =============================================================================
    # 2. Cross-Service Data Flow Coordination Tests
    # =============================================================================
    
    def test_memory_to_file_data_coordination(self):
        """Test coordinated data flow from memory to file storage."""
        collection = "memory_to_file_test"
        
        # Step 1: Write data to memory storage
        memory_result = self.memory_service.write(
            collection=collection,
            data=self.test_data["simple_data"],
            document_id="test_doc"
        )
        self.assertTrue(memory_result.success, "Memory write should succeed")
        
        # Step 2: Verify data exists in memory
        self.assertTrue(self.memory_service.exists(collection, "test_doc"),
                       "Data should exist in memory")
        
        # Step 3: Read from memory and write to file storage
        memory_data = self.memory_service.read(collection, "test_doc")
        file_result = self.file_service.write(
            collection=f"{collection}.json",
            data=json.dumps(memory_data, indent=2),
            document_id="test_doc"
        )
        self.assertTrue(file_result.success, "File write should succeed")
        
        # Step 4: Verify data integrity across storage types
        file_data_raw = self.file_service.read(f"{collection}.json", "test_doc")
        file_data = json.loads(file_data_raw)
        
        self.assertEqual(memory_data, file_data, 
                        "Data should be identical across memory and file storage")
        self.assertEqual(file_data["id"], 1)
        self.assertEqual(file_data["name"], "test")
        self.assertEqual(file_data["value"], 100)
    
    def test_json_to_csv_data_transformation_coordination(self):
        """Test coordinated data transformation from JSON to CSV format."""
        json_collection = "json_source"
        csv_collection = "csv_target"
        
        # Step 1: Write complex data to JSON storage
        json_result = self.json_service.write(
            collection=json_collection,
            data=self.test_data["tabular_data"],
            document_id="employee_data"
        )
        self.assertTrue(json_result.success, "JSON write should succeed")
        
        # Step 2: Read from JSON and prepare for CSV format
        json_data = self.json_service.read(json_collection, "employee_data")
        self.assertIsInstance(json_data, list, "JSON data should be a list")
        self.assertEqual(len(json_data), 3, "Should have 3 employee records")
        
        # Step 3: Write to CSV storage (CSVService handles the transformation)
        csv_result = self.csv_service.write(
            collection=csv_collection,
            data=json_data,
            document_id="employees"
        )
        self.assertTrue(csv_result.success, "CSV write should succeed")
        
        # Step 4: Verify CSV data structure and content
        csv_data = self.csv_service.read(csv_collection, "employees")
        self.assertIsInstance(csv_data, list, "CSV data should be a list")
        self.assertEqual(len(csv_data), 3, "CSV should have 3 records")
        
        # Verify first record
        first_record = csv_data[0]
        self.assertEqual(first_record["name"], "Alice")
        self.assertEqual(first_record["department"], "Engineering")
        self.assertEqual(first_record["salary"], "75000")  # CSV values are strings
        
        # Step 5: Verify data transformation preserved structure
        original_keys = set(self.test_data["tabular_data"][0].keys())
        csv_keys = set(first_record.keys())
        self.assertEqual(original_keys, csv_keys, 
                        "Column structure should be preserved in transformation")
    
    def test_multi_service_data_pipeline_coordination(self):
        """Test complex data pipeline across multiple storage services."""
        pipeline_id = "multi_service_pipeline"
        
        # Stage 1: Raw data input to memory (simulating real-time input)
        raw_data = {
            "batch_id": pipeline_id,
            "timestamp": "2025-06-01T12:00:00Z",
            "raw_records": self.test_data["tabular_data"]
        }
        
        memory_result = self.memory_service.write(
            collection="raw_input",
            data=raw_data,
            document_id=pipeline_id
        )
        self.assertTrue(memory_result.success, "Stage 1 - Memory write should succeed")
        
        # Stage 2: Process and store structured data in JSON
        memory_data = self.memory_service.read("raw_input", pipeline_id)
        processed_data = {
            "metadata": {
                "batch_id": memory_data["batch_id"],
                "processed_at": "2025-06-01T12:01:00Z",
                "record_count": len(memory_data["raw_records"])
            },
            "records": memory_data["raw_records"]
        }
        
        json_result = self.json_service.write(
            collection="processed_data",
            data=processed_data,
            document_id=pipeline_id
        )
        self.assertTrue(json_result.success, "Stage 2 - JSON write should succeed")
        
        # Stage 3: Extract tabular data for CSV analysis
        json_data = self.json_service.read("processed_data", pipeline_id)
        csv_records = json_data["records"]
        
        csv_result = self.csv_service.write(
            collection="analysis_data",
            data=csv_records,
            document_id=pipeline_id
        )
        self.assertTrue(csv_result.success, "Stage 3 - CSV write should succeed")
        
        # Stage 4: Create summary and store in file system
        csv_data = self.csv_service.read("analysis_data", pipeline_id)
        
        # Calculate summary statistics
        total_salary = sum(int(record["salary"]) for record in csv_data)
        avg_salary = total_salary / len(csv_data)
        departments = list(set(record["department"] for record in csv_data))
        
        summary = {
            "pipeline_id": pipeline_id,
            "total_records": len(csv_data),
            "average_salary": avg_salary,
            "departments": departments,
            "total_salary_budget": total_salary
        }
        
        file_result = self.file_service.write(
            collection="pipeline_summary.json",
            data=json.dumps(summary, indent=2),
            document_id=pipeline_id
        )
        self.assertTrue(file_result.success, "Stage 4 - File write should succeed")
        
        # Verification: Validate end-to-end data integrity
        final_summary_raw = self.file_service.read("pipeline_summary.json", pipeline_id)
        final_summary = json.loads(final_summary_raw)
        
        self.assertEqual(final_summary["total_records"], 3)
        self.assertEqual(final_summary["average_salary"], 73333.33333333333)
        self.assertIn("Engineering", final_summary["departments"])
        self.assertIn("Marketing", final_summary["departments"])
        self.assertEqual(final_summary["total_salary_budget"], 220000)
    
    # =============================================================================
    # 3. Storage Type Selection and Fallback Mechanisms
    # =============================================================================
    
    def test_automatic_storage_type_selection(self):
        """Test StorageManager automatic storage type selection based on data characteristics."""
        # Test data types that should route to different storage services
        test_scenarios = [
            {
                "name": "structured_json",
                "data": {"id": 1, "nested": {"value": "test"}},
                "expected_service": "json",
                "collection": "auto_select_json"
            },
            {
                "name": "tabular_data",
                "data": [{"col1": "val1", "col2": "val2"}, {"col1": "val3", "col2": "val4"}],
                "expected_service": "csv",
                "collection": "auto_select_csv"
            },
            {
                "name": "simple_text",
                "data": "This is simple text content",
                "expected_service": "file",
                "collection": "auto_select_file.txt"
            }
        ]
        
        for scenario in test_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Get service based on data characteristics
                service = self.storage_manager.get_service(scenario["expected_service"])
                
                # Write data using the selected service
                result = service.write(
                    collection=scenario["collection"],
                    data=scenario["data"],
                    document_id="test"
                )
                self.assertTrue(result.success, f"Write should succeed for {scenario['name']}")
                
                # Verify data can be read back correctly
                read_data = service.read(scenario["collection"], "test")
                
                if scenario["expected_service"] == "csv":
                    # CSV service returns list of dictionaries
                    self.assertIsInstance(read_data, list)
                    self.assertEqual(len(read_data), 2)
                elif scenario["expected_service"] == "json":
                    # JSON service preserves object structure
                    self.assertEqual(read_data, scenario["data"])
                elif scenario["expected_service"] == "file":
                    # File service returns raw text
                    self.assertEqual(read_data, scenario["data"])
    
    def test_storage_fallback_mechanism(self):
        """Test fallback to alternative storage when primary service fails."""
        primary_collection = "primary_test"
        fallback_collection = "fallback_test"
        test_data = {"id": 1, "content": "fallback test"}
        
        # Scenario 1: Primary service succeeds - no fallback needed
        primary_result = self.json_service.write(
            collection=primary_collection,
            data=test_data,
            document_id="test1"
        )
        self.assertTrue(primary_result.success, "Primary service should succeed")
        
        # Verify primary data
        primary_data = self.json_service.read(primary_collection, "test1")
        self.assertEqual(primary_data, test_data)
        
        # Scenario 2: Simulate fallback by explicitly using alternative service
        # (In a real implementation, this would be triggered by primary service failure)
        fallback_result = self.memory_service.write(
            collection=fallback_collection,
            data=test_data,
            document_id="test2"
        )
        self.assertTrue(fallback_result.success, "Fallback service should succeed")
        
        # Verify fallback data integrity
        fallback_data = self.memory_service.read(fallback_collection, "test2")
        self.assertEqual(fallback_data, test_data, 
                        "Fallback service should preserve data integrity")
        
        # Scenario 3: Test multiple fallback options
        fallback_services = [self.memory_service, self.file_service]
        successful_writes = 0
        
        for i, service in enumerate(fallback_services):
            try:
                if service == self.file_service:
                    # File service expects string data
                    service_data = json.dumps(test_data)
                else:
                    service_data = test_data
                
                result = service.write(
                    collection=f"fallback_option_{i}",
                    data=service_data,
                    document_id="fallback_test"
                )
                if result.success:
                    successful_writes += 1
            except Exception as e:
                self.logging_service.get_class_logger(self).warning(f"Fallback service {i} failed: {e}")
        
        self.assertGreater(successful_writes, 0, 
                          "At least one fallback service should succeed")
    
    def test_cross_service_data_migration(self):
        """Test data migration between different storage services."""
        migration_data = self.test_data["complex_data"]
        source_collection = "migration_source"
        target_collection = "migration_target"
        
        # Phase 1: Store data in source service (JSON)
        source_result = self.json_service.write(
            collection=source_collection,
            data=migration_data,
            document_id="migrate_test"
        )
        self.assertTrue(source_result.success, "Source storage should succeed")
        
        # Phase 2: Read from source
        source_data = self.json_service.read(source_collection, "migrate_test")
        self.assertEqual(source_data, migration_data, "Source data should match original")
        
        # Phase 3: Migrate to target service (Memory)
        migration_result = self.memory_service.write(
            collection=target_collection,
            data=source_data,
            document_id="migrate_test"
        )
        self.assertTrue(migration_result.success, "Migration should succeed")
        
        # Phase 4: Verify migration integrity
        target_data = self.memory_service.read(target_collection, "migrate_test")
        self.assertEqual(target_data, source_data, 
                        "Migrated data should match source")
        self.assertEqual(target_data["user_id"], "user_123")
        self.assertEqual(len(target_data["activity"]), 3)
        
        # Phase 5: Cleanup source after successful migration
        source_delete_result = self.json_service.delete(source_collection, "migrate_test")
        self.assertTrue(source_delete_result.success, "Source cleanup should succeed")
        
        # Verify source is cleaned up but target remains
        self.assertFalse(self.json_service.exists(source_collection, "migrate_test"),
                        "Source should be deleted")
        self.assertTrue(self.memory_service.exists(target_collection, "migrate_test"),
                       "Target should remain after migration")
    
    # =============================================================================
    # 4. Concurrent Storage Operations Tests
    # =============================================================================
    
    def test_concurrent_reads_across_services(self):
        """Test concurrent read operations across multiple storage services."""
        # Setup: Prepare data in all services
        test_scenarios = [
            ("memory", self.memory_service, "concurrent_memory", self.test_data["simple_data"]),
            ("json", self.json_service, "concurrent_json", self.test_data["complex_data"]),
            ("csv", self.csv_service, "concurrent_csv", self.test_data["tabular_data"]),
            ("file", self.file_service, "concurrent_file.txt", "Concurrent file test content")
        ]
        
        # Pre-populate all services
        for service_name, service, collection, data in test_scenarios:
            if service_name == "file":
                result = service.write(collection=collection, data=data, document_id="concurrent")
            else:
                result = service.write(collection=collection, data=data, document_id="concurrent")
            self.assertTrue(result.success, f"Setup for {service_name} should succeed")
        
        # Test concurrent reads
        def perform_read(service_info):
            service_name, service, collection, expected_data = service_info
            try:
                read_data = service.read(collection, "concurrent")
                return {
                    "service": service_name,
                    "success": True,
                    "data": read_data,
                    "expected": expected_data
                }
            except Exception as e:
                return {
                    "service": service_name,
                    "success": False,
                    "error": str(e)
                }
        
        # Execute concurrent reads
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(perform_read, scenario) for scenario in test_scenarios]
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all reads succeeded
        self.assertEqual(len(results), 4, "Should have results from all services")
        
        for result in results:
            self.assertTrue(result["success"], 
                          f"Read from {result['service']} should succeed")
            
            # Verify data integrity (considering service-specific transformations)
            if result["service"] == "csv":
                # CSV returns list of dictionaries
                self.assertIsInstance(result["data"], list)
            elif result["service"] == "file":
                # File returns string
                self.assertEqual(result["data"], result["expected"])
            else:
                # JSON and memory preserve structure
                self.assertEqual(result["data"], result["expected"])
    
    def test_concurrent_writes_across_services(self):
        """Test concurrent write operations across multiple storage services."""
        concurrent_collection = "concurrent_writes"
        
        def perform_concurrent_write(service_info):
            service_name, service, data = service_info
            try:
                start_time = time.time()
                
                result = service.write(
                    collection=f"{concurrent_collection}_{service_name}",
                    data=data,
                    document_id=f"concurrent_{service_name}"
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                return {
                    "service": service_name,
                    "success": result.success,
                    "duration": duration,
                    "result": result
                }
            except Exception as e:
                return {
                    "service": service_name,
                    "success": False,
                    "error": str(e)
                }
        
        # Prepare concurrent write scenarios
        write_scenarios = [
            ("memory", self.memory_service, {"thread": "memory", "data": "concurrent test"}),
            ("json", self.json_service, {"thread": "json", "nested": {"value": "concurrent"}}),
            ("csv", self.csv_service, [{"thread": "csv", "value": 1}, {"thread": "csv", "value": 2}]),
            ("file", self.file_service, "Concurrent file write test")
        ]
        
        # Execute concurrent writes
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(perform_concurrent_write, scenario) 
                      for scenario in write_scenarios]
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all writes succeeded
        self.assertEqual(len(results), 4, "Should have results from all services")
        
        for result in results:
            self.assertTrue(result["success"], 
                          f"Concurrent write to {result['service']} should succeed")
            self.assertLess(result["duration"], 5.0, 
                          f"Write to {result['service']} should complete within 5 seconds")
        
        # Verify data integrity after concurrent writes
        for service_name, service, original_data in write_scenarios:
            collection_name = f"{concurrent_collection}_{service_name}"
            document_id = f"concurrent_{service_name}"
            
            # Verify data exists and is readable
            self.assertTrue(service.exists(collection_name, document_id),
                          f"Data should exist in {service_name} after concurrent write")
            
            read_data = service.read(collection_name, document_id)
            
            # Verify data integrity (considering service-specific handling)
            if service_name == "csv":
                self.assertIsInstance(read_data, list)
                self.assertEqual(len(read_data), 2)
            elif service_name == "file":
                self.assertEqual(read_data, original_data)
            else:
                self.assertEqual(read_data, original_data)
    
    def test_concurrent_mixed_operations(self):
        """Test mixed concurrent operations (reads, writes, deletes) across services."""
        mixed_collection = "mixed_operations"
        
        # Setup initial data
        setup_data = [
            ("memory", self.memory_service, {"id": 1, "type": "memory"}),
            ("json", self.json_service, {"id": 2, "type": "json"}),
            ("csv", self.csv_service, [{"id": 3, "type": "csv"}]),
            ("file", self.file_service, "Initial file content")
        ]
        
        for service_name, service, data in setup_data:
            service.write(
                collection=f"{mixed_collection}_{service_name}",
                data=data,
                document_id="mixed_test"
            )
        
        def perform_mixed_operation(operation_info):
            operation_type, service_name, service = operation_info
            collection = f"{mixed_collection}_{service_name}"
            
            try:
                if operation_type == "read":
                    data = service.read(collection, "mixed_test")
                    return {"operation": "read", "service": service_name, "success": True, "data": data}
                
                elif operation_type == "write":
                    new_data = {"updated": True, "service": service_name}
                    if service_name == "csv":
                        new_data = [new_data]
                    elif service_name == "file":
                        new_data = f"Updated content for {service_name}"
                    
                    result = service.write(collection, new_data, "mixed_update")
                    return {"operation": "write", "service": service_name, "success": result.success}
                
                elif operation_type == "exists":
                    exists = service.exists(collection, "mixed_test")
                    return {"operation": "exists", "service": service_name, "success": True, "exists": exists}
                
            except Exception as e:
                return {"operation": operation_type, "service": service_name, "success": False, "error": str(e)}
        
        # Define mixed operations
        operations = [
            ("read", "memory", self.memory_service),
            ("write", "json", self.json_service),
            ("exists", "csv", self.csv_service),
            ("read", "file", self.file_service),
            ("write", "memory", self.memory_service),
            ("exists", "json", self.json_service)
        ]
        
        # Execute mixed operations concurrently
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(perform_mixed_operation, op) for op in operations]
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all operations completed
        self.assertEqual(len(results), 6, "Should complete all mixed operations")
        
        # Analyze results by operation type
        read_results = [r for r in results if r["operation"] == "read"]
        write_results = [r for r in results if r["operation"] == "write"]
        exists_results = [r for r in results if r["operation"] == "exists"]
        
        # Verify reads succeeded and returned valid data
        for read_result in read_results:
            self.assertTrue(read_result["success"], 
                          f"Read from {read_result['service']} should succeed")
            self.assertIsNotNone(read_result.get("data"), 
                               f"Read should return data from {read_result['service']}")
        
        # Verify writes succeeded
        for write_result in write_results:
            self.assertTrue(write_result["success"], 
                          f"Write to {write_result['service']} should succeed")
        
        # Verify exists checks succeeded
        for exists_result in exists_results:
            self.assertTrue(exists_result["success"], 
                          f"Exists check for {exists_result['service']} should succeed")
            self.assertTrue(exists_result.get("exists", False), 
                          f"Data should exist in {exists_result['service']}")
    
    # =============================================================================
    # 5. Service Information and Diagnostics
    # =============================================================================
    
    def test_storage_manager_service_information(self):
        """Test StorageManager provides accurate service information and diagnostics."""
        # Test getting service information for all providers
        service_info = self.storage_manager.get_service_info()
        
        # Verify information structure
        self.assertIsInstance(service_info, dict, "Service info should be a dictionary")
        
        # Test information for each expected provider
        expected_providers = ["memory", "file", "json", "csv"]
        for provider in expected_providers:
            self.assertIn(provider, service_info, f"Service info should include {provider}")
            
            provider_info = service_info[provider]
            self.assertIn("available", provider_info, f"{provider} info should include availability")
            self.assertIn("cached", provider_info, f"{provider} info should include cache status")
            self.assertIn("type", provider_info, f"{provider} info should include type")
            
            self.assertTrue(provider_info["available"], f"{provider} should be available")
            self.assertIn(provider_info["type"], ["class", "factory"], 
                         f"{provider} should have valid type")
        
        # Test individual service information
        memory_info = self.storage_manager.get_service_info("memory")
        self.assertIn("memory", memory_info, "Individual service info should include provider")
        self.assertTrue(memory_info["memory"]["available"], "Memory service should be available")
    
    def test_storage_service_coordination_diagnostics(self):
        """Test diagnostic capabilities across coordinated storage services."""
        diagnostic_collection = "diagnostics_test"
        
        # Create test data in multiple services for diagnostics
        test_services = [
            ("memory", self.memory_service, {"diag": "memory_test"}),
            ("json", self.json_service, {"diag": "json_test", "metadata": {"type": "diagnostic"}}),
            ("csv", self.csv_service, [{"diag": "csv_test", "row": 1}]),
            ("file", self.file_service, "Diagnostic file content")
        ]
        
        for service_name, service, data in test_services:
            service.write(
                collection=f"{diagnostic_collection}_{service_name}",
                data=data,
                document_id="diag_test"
            )
        
        # Run diagnostics across all services
        diagnostic_results = {}
        
        for service_name, service, expected_data in test_services:
            collection = f"{diagnostic_collection}_{service_name}"
            
            # Test health check
            health = service.health_check()
            
            # Test existence check
            exists = service.exists(collection, "diag_test")
            
            # Test read operation
            try:
                read_data = service.read(collection, "diag_test")
                read_success = True
            except Exception as e:
                read_success = False
                read_data = None
            
            diagnostic_results[service_name] = {
                "health": health,
                "exists": exists,
                "read_success": read_success,
                "data_retrieved": read_data is not None
            }
        
        # Verify diagnostic results
        for service_name, results in diagnostic_results.items():
            with self.subTest(service=service_name):
                self.assertTrue(results["health"], f"{service_name} should be healthy")
                self.assertTrue(results["exists"], f"Data should exist in {service_name}")
                self.assertTrue(results["read_success"], f"Should read from {service_name}")
                self.assertTrue(results["data_retrieved"], f"Should retrieve data from {service_name}")
        
        # Test StorageManager aggregated health check
        manager_health = self.storage_manager.health_check()
        for service_name in ["memory", "json", "csv", "file"]:
            self.assertTrue(manager_health.get(service_name, False),
                          f"Manager should report {service_name} as healthy")


if __name__ == '__main__':
    unittest.main()
