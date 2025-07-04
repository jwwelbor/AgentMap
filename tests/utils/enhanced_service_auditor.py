"""
Enhanced Service Interface Auditor for AgentMap Fresh Test Suite.

This utility automatically documents actual service interfaces and methods with
enhanced return type analysis, ensuring tests are built against real APIs with
sophisticated type-aware test generation.
"""

import inspect
import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Tuple, Set
import ast
import sys


@dataclass
class MethodInfo:
    """Information about a service method."""
    name: str
    signature: str
    parameters: List[Tuple[str, str]]  # (name, type_annotation)
    return_type: Optional[str]
    docstring: Optional[str]
    is_public: bool
    is_property: bool


@dataclass
class ServiceInfo:
    """Complete information about a service class."""
    class_name: str
    module_path: str
    init_signature: str
    dependencies: List[Tuple[str, str]]  # (param_name, type_annotation)
    public_methods: List[MethodInfo]
    private_methods: List[MethodInfo]
    properties: List[MethodInfo]
    base_classes: List[str]
    docstring: Optional[str]


class EnhancedServiceInterfaceAuditor:
    """
    Enhanced auditor for documenting actual service interfaces with return type analysis.
    
    Uses reflection to analyze service classes and extract their real
    interfaces with enhanced return type parsing for better test generation.
    """
    
    def __init__(self):
        """Initialize the auditor."""
        self.audited_services: Dict[str, ServiceInfo] = {}
        self.service_registry: Dict[str, Type] = {}
    
    def audit_service_interface(self, service_class: Type) -> ServiceInfo:
        """
        Audit a service class and document its actual interface.
        
        Args:
            service_class: The service class to analyze
            
        Returns:
            ServiceInfo containing complete interface documentation
        """
        class_name = service_class.__name__
        
        # Check cache first
        if class_name in self.audited_services:
            return self.audited_services[class_name]
        
        # Extract basic class information
        module_path = service_class.__module__
        docstring = inspect.getdoc(service_class)
        base_classes = [base.__name__ for base in service_class.__bases__ if base != object]
        
        # Analyze __init__ method and dependencies
        init_signature, dependencies = self._analyze_init_method(service_class)
        
        # Analyze all methods
        public_methods, private_methods, properties = self._analyze_methods(service_class)
        
        # Create service info
        service_info = ServiceInfo(
            class_name=class_name,
            module_path=module_path,
            init_signature=init_signature,
            dependencies=dependencies,
            public_methods=public_methods,
            private_methods=private_methods,
            properties=properties,
            base_classes=base_classes,
            docstring=docstring
        )
        
        # Cache the result
        self.audited_services[class_name] = service_info
        self.service_registry[class_name] = service_class
        
        return service_info
    
    def audit_service_by_path(self, module_path: str, class_name: str) -> ServiceInfo:
        """
        Audit a service by importing it from a module path.
        
        Args:
            module_path: Python module path (e.g., 'agentmap.services.execution_tracking_service')
            class_name: Name of the service class
            
        Returns:
            ServiceInfo for the service
        """
        try:
            module = importlib.import_module(module_path)
            service_class = getattr(module, class_name)
            return self.audit_service_interface(service_class)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Could not import {class_name} from {module_path}: {e}")
    
    def audit_agentmap_services(self) -> Dict[str, ServiceInfo]:
        """
        Audit all key AgentMap services.
        
        Returns:
            Dictionary mapping service names to their interface information
        """
        key_services = [
            ('agentmap.services.execution_tracking_service', 'ExecutionTrackingService'),
            ('agentmap.services.graph_runner_service', 'GraphRunnerService'),
            ('agentmap.services.graph_definition_service', 'GraphDefinitionService'),
            ('agentmap.services.compilation_service', 'CompilationService'),
            ('agentmap.services.graph_execution_service', 'GraphExecutionService'),
            ('agentmap.services.graph_bundle_service', 'GraphBundleService'),
            ('agentmap.services.llm_service', 'LLMService'),
            ('agentmap.services.node_registry_service', 'NodeRegistryService'),
            ('agentmap.services.logging_service', 'LoggingService'),
            ('agentmap.services.config.app_config_service', 'AppConfigService'),
        ]
        
        results = {}
        
        for module_path, class_name in key_services:
            try:
                service_info = self.audit_service_by_path(module_path, class_name)
                results[class_name] = service_info
                print(f"✅ Audited {class_name}: {len(service_info.public_methods)} public methods")
            except Exception as e:
                print(f"❌ Failed to audit {class_name}: {e}")
                continue
        
        return results
    
    def _analyze_init_method(self, service_class: Type) -> Tuple[str, List[Tuple[str, str]]]:
        """
        Analyze the __init__ method to extract signature and dependencies.
        
        Args:
            service_class: Service class to analyze
            
        Returns:
            Tuple of (signature_string, dependencies_list)
        """
        try:
            init_method = service_class.__init__
            signature = inspect.signature(init_method)
            signature_str = str(signature)
            
            # Extract dependencies (parameters other than 'self')
            dependencies = []
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                    
                # Enhanced type annotation parsing
                type_annotation = self._parse_type_annotation(param.annotation)
                dependencies.append((param_name, type_annotation))
            
            return signature_str, dependencies
            
        except Exception as e:
            return f"Error analyzing __init__: {e}", []
    
    def _analyze_methods(self, service_class: Type) -> Tuple[List[MethodInfo], List[MethodInfo], List[MethodInfo]]:
        """
        Analyze all methods of a service class.
        
        Args:
            service_class: Service class to analyze
            
        Returns:
            Tuple of (public_methods, private_methods, properties)
        """
        public_methods = []
        private_methods = []
        properties = []
        
        # Get all members of the class
        for name, method in inspect.getmembers(service_class):
            # Skip special methods except for important ones
            if name.startswith('__') and name not in ('__init__', '__call__'):
                continue
            
            # Check if it's a property
            if isinstance(method, property):
                method_info = self._create_method_info(name, method, is_property=True)
                properties.append(method_info)
                continue
            
            # Check if it's a callable method
            if not callable(method):
                continue
            
            # Skip if it's not actually defined in this class
            if hasattr(method, '__qualname__') and service_class.__name__ not in method.__qualname__:
                continue
            
            # Create method info
            is_public = not name.startswith('_')
            method_info = self._create_method_info(name, method, is_property=False)
            
            if is_public:
                public_methods.append(method_info)
            else:
                private_methods.append(method_info)
        
        return public_methods, private_methods, properties
    
    def _create_method_info(self, name: str, method: Any, is_property: bool = False) -> MethodInfo:
        """
        Create MethodInfo for a method or property with enhanced return type analysis.
        
        Args:
            name: Method name
            method: Method object
            is_property: Whether this is a property
            
        Returns:
            MethodInfo instance
        """
        try:
            if is_property:
                # Handle property
                return MethodInfo(
                    name=name,
                    signature=f"@property def {name}(self)",
                    parameters=[],
                    return_type="Unknown",
                    docstring=inspect.getdoc(method.fget) if method.fget else None,
                    is_public=not name.startswith('_'),
                    is_property=True
                )
            else:
                # Handle regular method
                signature = inspect.signature(method)
                signature_str = f"def {name}{signature}"
                
                # Extract parameters with enhanced type parsing
                parameters = []
                for param_name, param in signature.parameters.items():
                    if param_name == 'self':
                        continue
                        
                    type_annotation = self._parse_type_annotation(param.annotation)
                    parameters.append((param_name, type_annotation))
                
                # Extract return type with enhanced parsing
                return_type = self._parse_type_annotation(signature.return_annotation)
                
                return MethodInfo(
                    name=name,
                    signature=signature_str,
                    parameters=parameters,
                    return_type=return_type,
                    docstring=inspect.getdoc(method),
                    is_public=not name.startswith('_'),
                    is_property=False
                )
                
        except Exception as e:
            # Fallback for problematic methods
            return MethodInfo(
                name=name,
                signature=f"def {name}(...) # Error analyzing: {e}",
                parameters=[],
                return_type="Unknown",
                docstring=None,
                is_public=not name.startswith('_'),
                is_property=is_property
            )
    
    def _parse_type_annotation(self, annotation) -> str:
        """
        Parse type annotation with enhanced handling of complex types.
        
        Args:
            annotation: Type annotation from inspect
            
        Returns:
            String representation of the type
        """
        if annotation == inspect.Parameter.empty or annotation == inspect.Signature.empty:
            return 'Any'
        
        # Handle simple types with __name__
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        
        # Handle string annotations
        if isinstance(annotation, str):
            return annotation
        
        # Handle complex types (Optional, Dict, List, etc.)
        annotation_str = str(annotation)
        
        # Clean up common typing patterns
        if 'typing.' in annotation_str:
            annotation_str = annotation_str.replace('typing.', '')
        
        # Simplify Union types
        if 'Union[' in annotation_str and ', NoneType]' in annotation_str:
            # Convert Union[SomeType, NoneType] to Optional[SomeType]
            type_part = annotation_str.split('Union[')[1].split(', NoneType]')[0]
            annotation_str = f'Optional[{type_part}]'
        
        return annotation_str
    
    def generate_enhanced_test_template(self, service_info: ServiceInfo) -> str:
        """
        Generate enhanced test template with return type aware assertions.
        
        Args:
            service_info: Service interface information
            
        Returns:
            String containing enhanced test template code
        """
        template_lines = [
            '"""',
            f'Enhanced unit tests for {service_info.class_name}.',
            '',
            'These tests are generated with enhanced return type analysis',
            'to ensure sophisticated test assertions based on actual method signatures.',
            '"""',
            '',
            'import unittest',
            'from unittest.mock import Mock, patch',
            '',
            f'from {service_info.module_path} import {service_info.class_name}',
            'from tests.utils.mock_service_factory import MockServiceFactory',
            'from agentmap.migration_utils import MockLoggingService, MockAppConfigService',
            '',
            '',
            f'class Test{service_info.class_name}(unittest.TestCase):',
            f'    """Enhanced unit tests for {service_info.class_name} with return type awareness."""',
            '',
            '    def setUp(self):',
            '        """Set up test fixtures with mocked dependencies."""',
            '        # Create mock services using established patterns',
            '        self.mock_logging_service = MockLoggingService()',
            '        self.mock_config_service = MockAppConfigService()',
            ''
        ]
        
        # Add mock setup for each dependency
        for dep_name, dep_type in service_info.dependencies:
            if 'logging' in dep_name.lower():
                continue  # Already handled above
            elif 'config' in dep_name.lower():
                continue  # Already handled above
            else:
                template_lines.append(f'        self.mock_{dep_name} = Mock(spec={dep_type})')
        
        template_lines.extend([
            '',
            '        # Create service instance with mocked dependencies',
            f'        self.service = {service_info.class_name}('
        ])
        
        # Add constructor arguments
        dep_args = []
        for dep_name, dep_type in service_info.dependencies:
            if 'logging' in dep_name.lower():
                dep_args.append(f'{dep_name}=self.mock_logging_service')
            elif 'config' in dep_name.lower():
                dep_args.append(f'{dep_name}=self.mock_config_service')
            else:
                dep_args.append(f'{dep_name}=self.mock_{dep_name}')
        
        if dep_args:
            template_lines.append('            ' + ',\n            '.join(dep_args))
        
        template_lines.extend([
            '        )',
            '',
            '    def test_service_initialization(self):',
            '        """Test that service initializes correctly with all dependencies."""',
            f'        # Verify service is properly configured',
            f'        self.assertIsNotNone(self.service)',
            f'        self.assertEqual(self.service.logger.name, "{service_info.class_name}")',
            '',
            '        # Verify initialization log message',
            '        logger_calls = self.service.logger.calls',
            f'        self.assertTrue(any("[{service_info.class_name}] Initialized" in call[1]',
            '                          for call in logger_calls if call[0] == "info"))',
            ''
        ])
        
        # Generate enhanced test methods for each public method
        for method in service_info.public_methods:
            if method.name == '__init__':
                continue
                
            template_lines.extend([
                f'    def test_{method.name}_method_exists(self):',
                f'        """Test that {method.name} method exists and is callable."""',
                f'        self.assertTrue(hasattr(self.service, "{method.name}"))',
                f'        self.assertTrue(callable(getattr(self.service, "{method.name}")))',
                ''
            ])
            
            # Generate enhanced test based on return type analysis
            if method.return_type and method.return_type not in ['Any', 'Unknown']:
                test_assertions = self._generate_return_type_assertions(method)
                template_lines.extend([
                    f'    def test_{method.name}_returns_expected_type(self):',
                    f'        """Test that {method.name} returns expected type: {method.return_type}."""',
                    f'        # Method signature: {method.signature}'
                ])
                
                # Add setup comments and assertions based on return type
                template_lines.extend(test_assertions)
                template_lines.append('')
        
        template_lines.extend([
            '',
            'if __name__ == "__main__":',
            '    unittest.main()'
        ])
        
        return '\n'.join(template_lines)
    
    def _generate_return_type_assertions(self, method: MethodInfo) -> List[str]:
        """
        Generate sophisticated test assertions based on method return type.
        
        Args:
            method: Method information including return type
            
        Returns:
            List of test assertion lines
        """
        assertions = []
        return_type = method.return_type
        
        # Mock setup based on method name patterns
        if 'create' in method.name.lower():
            assertions.append('        # Mock dependencies for creation method')
            assertions.append('        # TODO: Set up required mocks for creation')
        elif 'get' in method.name.lower():
            assertions.append('        # Mock dependencies for getter method') 
            assertions.append('        # TODO: Set up return values for getter')
        
        assertions.append('')
        assertions.append(f'        # Call the method')
        
        # Generate method call based on parameters
        if len(method.parameters) == 0:
            assertions.append(f'        result = self.service.{method.name}()')
        else:
            # Create basic parameter setup
            assertions.append('        # TODO: Set up method parameters')
            param_list = ', '.join([f'{name}=mock_{name}' for name, _ in method.parameters[:2]])
            if len(method.parameters) > 2:
                param_list += ', ...'
            assertions.append(f'        # result = self.service.{method.name}({param_list})')
            assertions.append(f'        result = self.service.{method.name}()  # Simplified call')
        
        assertions.append('')
        
        # Generate sophisticated assertions based on return type
        if return_type == 'None':
            assertions.append('        # Method returns None')
            assertions.append('        self.assertIsNone(result)')
        elif 'ExecutionTracker' in return_type:
            assertions.extend([
                '        # Verify ExecutionTracker return type and basic structure',
                '        from agentmap.services.execution_tracking_service import ExecutionTrackingService',
                '        self.assertIsInstance(result, ExecutionTracker)',
                '        self.assertIsNotNone(result.start_time)',
                '        self.assertIsInstance(result.node_executions, list)'
            ])
        elif 'ExecutionResult' in return_type:
            assertions.extend([
                '        # Verify ExecutionResult return type and structure',
                '        from agentmap.models.execution_result import ExecutionResult',
                '        self.assertIsInstance(result, ExecutionResult)',
                '        self.assertIsNotNone(result.graph_name)',
                '        self.assertIsInstance(result.success, bool)'
            ])
        elif 'Graph' in return_type and 'str' not in return_type:
            assertions.extend([
                '        # Verify Graph return type and structure',
                '        from agentmap.models.graph import Graph',
                '        self.assertIsInstance(result, Graph)',
                '        self.assertIsNotNone(result.name)',
                '        self.assertIsInstance(result.nodes, dict)'
            ])
        elif 'Dict' in return_type:
            assertions.append('        # Verify dictionary return type')
            assertions.append('        self.assertIsInstance(result, dict)')
            if 'str' in return_type:
                assertions.extend([
                    '        # Verify dictionary structure with string keys',
                    '        if result:  # If not empty',
                    '            for key in result.keys():',
                    '                self.assertIsInstance(key, str)'
                ])
        elif 'List' in return_type:
            assertions.extend([
                '        # Verify list return type',
                '        self.assertIsInstance(result, list)'
            ])
        elif 'Optional' in return_type:
            inner_type = return_type.replace('Optional[', '').replace(']', '')
            assertions.extend([
                '        # Verify optional return type (can be None)',
                f'        if result is not None:',
                f'            # TODO: Add specific assertion for {inner_type} when not None'
            ])
            if inner_type in ['str', 'int', 'bool', 'float']:
                assertions.append(f'            self.assertIsInstance(result, {inner_type})')
        elif return_type in ['str', 'int', 'bool', 'float']:
            assertions.extend([
                f'        # Verify {return_type} return type',
                f'        self.assertIsInstance(result, {return_type})'
            ])
        else:
            assertions.extend([
                f'        # Verify return type: {return_type}',
                '        self.assertIsNotNone(result)',
                f'        # TODO: Add specific assertion for {return_type}'
            ])
        
        return assertions
    
    def print_enhanced_service_summary(self, service_info: ServiceInfo) -> None:
        """Print enhanced summary with return type analysis."""
        print(f"\n📋 Enhanced Service Summary: {service_info.class_name}")
        print("=" * 60)
        print(f"Module: {service_info.module_path}")
        print(f"Dependencies: {len(service_info.dependencies)}")
        
        if service_info.dependencies:
            for dep_name, dep_type in service_info.dependencies:
                print(f"  - {dep_name}: {dep_type}")
        
        print(f"\nPublic Methods: {len(service_info.public_methods)}")
        for method in service_info.public_methods:
            # Enhanced display with parameter info
            param_info = ""
            if method.parameters:
                param_types = [f"{name}: {type_}" for name, type_ in method.parameters[:2]]
                if len(method.parameters) > 2:
                    param_types.append("...")
                param_info = f"({', '.join(param_types)})"
            
            print(f"  ✅ {method.name}{param_info} -> {method.return_type}")
        
        # Return type analysis
        return_types = [method.return_type for method in service_info.public_methods]
        unique_return_types = list(set(return_types))
        if len(unique_return_types) > 1:
            print(f"\nReturn Type Distribution:")
            for rt in unique_return_types:
                count = return_types.count(rt)
                print(f"  📊 {rt}: {count} method{'s' if count != 1 else ''}")


def main():
    """Demonstrate the enhanced service interface auditor."""
    auditor = EnhancedServiceInterfaceAuditor()
    
    print("🔍 Enhanced AgentMap Service Interface Auditor")
    print("=" * 60)
    print("Analyzing service interfaces with sophisticated return type analysis...")
    
    # Audit key AgentMap services
    services = auditor.audit_agentmap_services()
    
    print(f"\n📊 Enhanced Audit Summary: {len(services)} services analyzed")
    
    # Print enhanced summary for each service
    for service_name, service_info in services.items():
        auditor.print_enhanced_service_summary(service_info)
    
    print("\n✅ Enhanced service interface audit complete!")
    print("Use auditor.generate_enhanced_test_template(service_info) for sophisticated test generation.")


if __name__ == "__main__":
    main()
