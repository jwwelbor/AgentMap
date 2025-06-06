"""
Service Interface Auditor for AgentMap Fresh Test Suite.

This utility automatically documents actual service interfaces and methods,
ensuring tests are built against real APIs rather than phantom methods.
It analyzes existing services using reflection and generates test templates
based on actual method signatures and dependencies.
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


class ServiceInterfaceAuditor:
    """
    Auditor for documenting actual service interfaces.
    
    Uses reflection to analyze service classes and extract their real
    interfaces, preventing tests from being written against phantom methods.
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
                    
                # Get type annotation if available
                type_annotation = 'Any'
                if param.annotation != inspect.Parameter.empty:
                    if hasattr(param.annotation, '__name__'):
                        type_annotation = param.annotation.__name__
                    else:
                        type_annotation = str(param.annotation)
                
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
    
    def generate_test_template(self, service_info: ServiceInfo) -> str:
        """
        Generate a test template based on actual service interface.
        
        Args:
            service_info: Service interface information
            
        Returns:
            String containing test template code
        """
        template_lines = [
            '"""',
            f'Unit tests for {service_info.class_name}.',
            '',
            'These tests are generated based on actual service interface analysis',
            'to ensure we test real methods, not phantom methods.',
            '"""',
            '',
            'import unittest',
            'from unittest.mock import Mock, patch',
            '',
            f'from {service_info.module_path} import {service_info.class_name}',
            'from tests.utils.mock_factory import MockServiceFactory',
            'from agentmap.migration_utils import MockLoggingService, MockAppConfigService',
            '',
            '',
            f'class Test{service_info.class_name}(unittest.TestCase):',
            f'    """Unit tests for {service_info.class_name} with mocked dependencies."""',
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
        
        # Generate test methods for each public method
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
            
            # Add specific test if we can infer the behavior
            if method.return_type and method.return_type != 'Any':
                template_lines.extend([
                    f'    def test_{method.name}_returns_expected_type(self):',
                    f'        """Test that {method.name} returns expected type."""',
                    f'        # TODO: Implement actual test based on method behavior',
                    f'        # Expected return type: {method.return_type}',
                    f'        # Method signature: {method.signature}',
                    '        pass',
                    ''
                ])
        
        template_lines.extend([
            '',
            'if __name__ == "__main__":',
            '    unittest.main()'
        ])
        
        return '\n'.join(template_lines)
    
    def generate_test_data_summary(self, service_info: ServiceInfo) -> Dict[str, Any]:
        """
        Generate a summary of test data for a service.
        
        Args:
            service_info: Service interface information
            
        Returns:
            Dictionary containing test planning information
        """
        return {
            'service_name': service_info.class_name,
            'module_path': service_info.module_path,
            'total_public_methods': len(service_info.public_methods),
            'total_private_methods': len(service_info.private_methods),
            'total_properties': len(service_info.properties),
            'dependencies_count': len(service_info.dependencies),
            'public_method_names': [m.name for m in service_info.public_methods],
            'dependencies': [f"{name}: {type_}" for name, type_ in service_info.dependencies],
            'test_complexity': self._estimate_test_complexity(service_info),
            'testing_recommendations': self._generate_testing_recommendations(service_info)
        }
    
    def _estimate_test_complexity(self, service_info: ServiceInfo) -> str:
        """Estimate the complexity of testing this service."""
        public_methods = len(service_info.public_methods)
        dependencies = len(service_info.dependencies)
        
        if public_methods <= 5 and dependencies <= 3:
            return "LOW"
        elif public_methods <= 10 and dependencies <= 6:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _generate_testing_recommendations(self, service_info: ServiceInfo) -> List[str]:
        """Generate testing recommendations for a service."""
        recommendations = []
        
        recommendations.append("Use MockServiceFactory for consistent dependency mocking")
        recommendations.append("Follow MockLoggingService → MockLogger → .calls verification pattern")
        
        if len(service_info.dependencies) > 5:
            recommendations.append("Consider using @patch for complex dependency injection")
        
        facade_methods = ['run_', 'execute_', 'get_', 'create_']
        if any(method.name.startswith(prefix) for method in service_info.public_methods for prefix in facade_methods):
            recommendations.append("Focus on facade coordination patterns, test delegation not implementation")
        
        if any('tracking' in method.name.lower() for method in service_info.public_methods):
            recommendations.append("Test tracking state changes and data collection")
        
        if len(service_info.public_methods) > 8:
            recommendations.append("Consider grouping related tests into separate test classes")
        
        return recommendations
    
    def print_service_summary(self, service_info: ServiceInfo) -> None:
        """Print a human-readable summary of service interface."""
        print(f"\n📋 Service Interface Summary: {service_info.class_name}")
        print("=" * 60)
        print(f"Module: {service_info.module_path}")
        print(f"Dependencies: {len(service_info.dependencies)}")
        
        if service_info.dependencies:
            for dep_name, dep_type in service_info.dependencies:
                print(f"  - {dep_name}: {dep_type}")
        
        print(f"\nPublic Methods: {len(service_info.public_methods)}")
        for method in service_info.public_methods:
            print(f"  ✅ {method.name}() -> {method.return_type}")
        
        if service_info.private_methods:
            print(f"\nPrivate Methods: {len(service_info.private_methods)}")
            for method in service_info.private_methods[:5]:  # Show first 5
                print(f"  🔒 {method.name}()")
            if len(service_info.private_methods) > 5:
                print(f"  ... and {len(service_info.private_methods) - 5} more")
        
        if service_info.properties:
            print(f"\nProperties: {len(service_info.properties)}")
            for prop in service_info.properties:
                print(f"  📊 {prop.name}")


def main():
    """Main function to demonstrate the service interface auditor."""
    auditor = ServiceInterfaceAuditor()
    
    print("🔍 AgentMap Service Interface Auditor")
    print("=" * 50)
    print("Analyzing actual service interfaces to prevent phantom method testing...")
    
    # Audit key AgentMap services
    services = auditor.audit_agentmap_services()
    
    print(f"\n📊 Audit Summary: {len(services)} services analyzed")
    
    # Print summary for each service
    for service_name, service_info in services.items():
        auditor.print_service_summary(service_info)
    
    print("\n✅ Service interface audit complete!")
    print("Use auditor.generate_test_template(service_info) to create test templates.")


if __name__ == "__main__":
    main()
