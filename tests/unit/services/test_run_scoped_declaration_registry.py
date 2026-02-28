"""
Unit tests for RunScopedDeclarationRegistry and scoped registry factory method.

Tests the thread-safe, immutable registry for per-graph-run isolation that
eliminates race conditions in concurrent graph execution.

Follows project testing patterns using MockServiceFactory and unittest.TestCase.
"""

import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import MappingProxyType
from typing import Set

from agentmap.models.declaration_models import (
    AgentDeclaration,
    ProtocolRequirement,
    ServiceDeclaration,
    ServiceRequirement,
)
from agentmap.models.graph_bundle import GraphBundle

# Import will fail initially - this is expected in TDD (RED phase)
try:
    from agentmap.services.declaration_registry_service import (
        DeclarationRegistryService,
        RunScopedDeclarationRegistry,
    )
except ImportError:
    # Expected during RED phase - class doesn't exist yet
    RunScopedDeclarationRegistry = None
    DeclarationRegistryService = None

from tests.utils.mock_service_factory import MockServiceFactory


class TestRunScopedDeclarationRegistryImmutability(unittest.TestCase):
    """Test immutability of RunScopedDeclarationRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        if RunScopedDeclarationRegistry is None:
            self.skipTest("RunScopedDeclarationRegistry not yet implemented")

        self.test_agent_decl = AgentDeclaration(
            agent_type="TestAgent",
            class_path="agentmap.agents.TestAgent",
            service_requirements=[
                ServiceRequirement(name="logging_service"),
                ServiceRequirement(name="llm_service"),
            ],
            protocol_requirements=[
                ProtocolRequirement(name="LLMCapableAgent", requires=True),
            ],
        )

        self.test_service_decl = ServiceDeclaration(
            service_name="test_service",
            class_path="agentmap.services.TestService",
            required_dependencies=["logging_service"],
            implements_protocols=["TestProtocol"],
        )

    def test_agents_dict_is_immutable(self):
        """Test that agents dictionary cannot be modified after creation."""
        agents = {"TestAgent": self.test_agent_decl}
        services = {"test_service": self.test_service_decl}

        registry = RunScopedDeclarationRegistry(agents=agents, services=services)

        # Attempting to modify should raise TypeError
        with self.assertRaises(TypeError):
            registry._agents["NewAgent"] = self.test_agent_decl

        with self.assertRaises(TypeError):
            del registry._agents["TestAgent"]

    def test_services_dict_is_immutable(self):
        """Test that services dictionary cannot be modified after creation."""
        agents = {"TestAgent": self.test_agent_decl}
        services = {"test_service": self.test_service_decl}

        registry = RunScopedDeclarationRegistry(agents=agents, services=services)

        # Attempting to modify should raise TypeError
        with self.assertRaises(TypeError):
            registry._services["new_service"] = self.test_service_decl

        with self.assertRaises(TypeError):
            del registry._services["test_service"]

    def test_original_dicts_not_affected_by_registry(self):
        """Test that modifications to original dicts don't affect registry."""
        agents = {"TestAgent": self.test_agent_decl}
        services = {"test_service": self.test_service_decl}

        registry = RunScopedDeclarationRegistry(agents=agents, services=services)

        # Modify original dicts
        another_agent = AgentDeclaration(
            agent_type="AnotherAgent",
            class_path="agentmap.agents.AnotherAgent",
        )
        agents["AnotherAgent"] = another_agent

        # Registry should NOT contain the new agent
        self.assertIsNone(registry.get_agent_declaration("AnotherAgent"))
        self.assertNotIn("AnotherAgent", list(registry.get_all_agent_types()))

    def test_uses_mapping_proxy_type(self):
        """Test that internal storage uses MappingProxyType for immutability."""
        agents = {"TestAgent": self.test_agent_decl}
        services = {"test_service": self.test_service_decl}

        registry = RunScopedDeclarationRegistry(agents=agents, services=services)

        self.assertIsInstance(registry._agents, MappingProxyType)
        self.assertIsInstance(registry._services, MappingProxyType)


class TestRunScopedDeclarationRegistryReadMethods(unittest.TestCase):
    """Test read-only methods of RunScopedDeclarationRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        if RunScopedDeclarationRegistry is None:
            self.skipTest("RunScopedDeclarationRegistry not yet implemented")

        self.test_agent_decl = AgentDeclaration(
            agent_type="TestAgent",
            class_path="agentmap.agents.TestAgent",
            service_requirements=[
                ServiceRequirement(name="logging_service"),
                ServiceRequirement(name="llm_service"),
            ],
            protocol_requirements=[
                ProtocolRequirement(name="LLMCapableAgent", requires=True),
            ],
        )

        self.llm_agent_decl = AgentDeclaration(
            agent_type="LLMAgent",
            class_path="agentmap.agents.LLMAgent",
            service_requirements=[
                ServiceRequirement(name="llm_service"),
                ServiceRequirement(name="prompt_manager_service"),
            ],
        )

        self.test_service_decl = ServiceDeclaration(
            service_name="test_service",
            class_path="agentmap.services.TestService",
            required_dependencies=["logging_service"],
            implements_protocols=["TestProtocol"],
        )

        self.llm_service_decl = ServiceDeclaration(
            service_name="llm_service",
            class_path="agentmap.services.LLMService",
            required_dependencies=["logging_service", "config_service"],
            implements_protocols=["LLMServiceProtocol"],
        )

        self.logging_service_decl = ServiceDeclaration(
            service_name="logging_service",
            class_path="agentmap.services.LoggingService",
            required_dependencies=[],
            implements_protocols=["LoggingServiceProtocol"],
        )

        self.agents = {
            "TestAgent": self.test_agent_decl,
            "LLMAgent": self.llm_agent_decl,
        }
        self.services = {
            "test_service": self.test_service_decl,
            "llm_service": self.llm_service_decl,
            "logging_service": self.logging_service_decl,
        }

        self.registry = RunScopedDeclarationRegistry(
            agents=self.agents, services=self.services
        )

    def test_get_agent_declaration_returns_correct_declaration(self):
        """Test get_agent_declaration returns the correct declaration."""
        result = self.registry.get_agent_declaration("TestAgent")

        self.assertIsNotNone(result)
        self.assertEqual(result.agent_type, "TestAgent")
        self.assertEqual(result.class_path, "agentmap.agents.TestAgent")

    def test_get_agent_declaration_returns_none_for_missing(self):
        """Test get_agent_declaration returns None for non-existent agent."""
        result = self.registry.get_agent_declaration("NonExistentAgent")

        self.assertIsNone(result)

    def test_get_service_declaration_returns_correct_declaration(self):
        """Test get_service_declaration returns the correct declaration."""
        result = self.registry.get_service_declaration("llm_service")

        self.assertIsNotNone(result)
        self.assertEqual(result.service_name, "llm_service")
        self.assertEqual(result.class_path, "agentmap.services.LLMService")

    def test_get_service_declaration_returns_none_for_missing(self):
        """Test get_service_declaration returns None for non-existent service."""
        result = self.registry.get_service_declaration("nonexistent_service")

        self.assertIsNone(result)

    def test_get_all_agent_types(self):
        """Test get_all_agent_types returns all registered agent types."""
        result = self.registry.get_all_agent_types()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIn("TestAgent", result)
        self.assertIn("LLMAgent", result)

    def test_get_all_service_names(self):
        """Test get_all_service_names returns all registered service names."""
        result = self.registry.get_all_service_names()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertIn("test_service", result)
        self.assertIn("llm_service", result)
        self.assertIn("logging_service", result)

    def test_get_services_by_protocols(self):
        """Test get_services_by_protocols returns services implementing given protocols."""
        result = self.registry.get_services_by_protocols({"LLMServiceProtocol"})

        self.assertIsInstance(result, set)
        self.assertIn("llm_service", result)
        self.assertNotIn("test_service", result)

    def test_get_services_by_protocols_multiple_protocols(self):
        """Test get_services_by_protocols with multiple protocols."""
        result = self.registry.get_services_by_protocols(
            {"LLMServiceProtocol", "TestProtocol"}
        )

        self.assertIn("llm_service", result)
        self.assertIn("test_service", result)

    def test_get_services_by_protocols_empty_result(self):
        """Test get_services_by_protocols returns empty set for unknown protocols."""
        result = self.registry.get_services_by_protocols({"UnknownProtocol"})

        self.assertIsInstance(result, set)
        self.assertEqual(len(result), 0)


class TestRunScopedDeclarationRegistryRequirementResolution(unittest.TestCase):
    """Test requirement resolution in RunScopedDeclarationRegistry."""

    def setUp(self):
        """Set up test fixtures with dependency chains."""
        if RunScopedDeclarationRegistry is None:
            self.skipTest("RunScopedDeclarationRegistry not yet implemented")

        # Agent with service requirements
        self.llm_agent_decl = AgentDeclaration(
            agent_type="LLMAgent",
            class_path="agentmap.agents.LLMAgent",
            service_requirements=[
                ServiceRequirement(name="llm_service"),
                ServiceRequirement(name="prompt_manager_service"),
            ],
            protocol_requirements=[
                ProtocolRequirement(name="LLMServiceProtocol", requires=True),
            ],
        )

        # Services with dependencies
        self.llm_service_decl = ServiceDeclaration(
            service_name="llm_service",
            class_path="agentmap.services.LLMService",
            required_dependencies=["logging_service", "config_service"],
            implements_protocols=["LLMServiceProtocol"],
        )

        self.prompt_manager_decl = ServiceDeclaration(
            service_name="prompt_manager_service",
            class_path="agentmap.services.PromptManagerService",
            required_dependencies=["logging_service"],
            implements_protocols=["PromptServiceProtocol"],
        )

        self.logging_service_decl = ServiceDeclaration(
            service_name="logging_service",
            class_path="agentmap.services.LoggingService",
            required_dependencies=[],
            implements_protocols=["LoggingServiceProtocol"],
        )

        self.config_service_decl = ServiceDeclaration(
            service_name="config_service",
            class_path="agentmap.services.ConfigService",
            required_dependencies=["logging_service"],
            implements_protocols=["ConfigServiceProtocol"],
        )

        self.agents = {"LLMAgent": self.llm_agent_decl}
        self.services = {
            "llm_service": self.llm_service_decl,
            "prompt_manager_service": self.prompt_manager_decl,
            "logging_service": self.logging_service_decl,
            "config_service": self.config_service_decl,
        }

        self.registry = RunScopedDeclarationRegistry(
            agents=self.agents, services=self.services
        )

    def test_resolve_agent_requirements_returns_all_services(self):
        """Test resolve_agent_requirements includes direct and transitive dependencies."""
        result = self.registry.resolve_agent_requirements({"LLMAgent"})

        self.assertIn("services", result)
        self.assertIn("protocols", result)
        self.assertIn("missing", result)

        # Should include direct dependencies
        self.assertIn("llm_service", result["services"])
        self.assertIn("prompt_manager_service", result["services"])

        # Should include transitive dependencies
        self.assertIn("logging_service", result["services"])
        self.assertIn("config_service", result["services"])

    def test_resolve_agent_requirements_includes_protocols(self):
        """Test resolve_agent_requirements includes required protocols."""
        result = self.registry.resolve_agent_requirements({"LLMAgent"})

        self.assertIn("LLMServiceProtocol", result["protocols"])

    def test_resolve_agent_requirements_missing_agents_tracked(self):
        """Test resolve_agent_requirements tracks missing agent declarations."""
        result = self.registry.resolve_agent_requirements(
            {"LLMAgent", "NonExistentAgent"}
        )

        self.assertIn("NonExistentAgent", result["missing"])
        self.assertNotIn("LLMAgent", result["missing"])

    def test_resolve_agent_requirements_empty_set(self):
        """Test resolve_agent_requirements with empty agent set."""
        result = self.registry.resolve_agent_requirements(set())

        self.assertEqual(result["services"], set())
        self.assertEqual(result["protocols"], set())
        self.assertEqual(result["missing"], set())

    def test_resolve_service_dependencies(self):
        """Test resolve_service_dependencies follows dependency chain."""
        result = self.registry.resolve_service_dependencies({"llm_service"})

        self.assertIn("llm_service", result)
        self.assertIn("logging_service", result)
        self.assertIn("config_service", result)

    def test_resolve_service_dependencies_handles_missing(self):
        """Test resolve_service_dependencies handles missing service declarations."""
        result = self.registry.resolve_service_dependencies(
            {"llm_service", "nonexistent_service"}
        )

        # Should still resolve known services
        self.assertIn("llm_service", result)
        self.assertIn("logging_service", result)

    def test_get_protocol_service_map(self):
        """Test get_protocol_service_map returns correct mapping."""
        result = self.registry.get_protocol_service_map()

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("LLMServiceProtocol"), "llm_service")
        self.assertEqual(result.get("LoggingServiceProtocol"), "logging_service")


class TestRunScopedDeclarationRegistryThreadSafety(unittest.TestCase):
    """Test thread safety of RunScopedDeclarationRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        if RunScopedDeclarationRegistry is None:
            self.skipTest("RunScopedDeclarationRegistry not yet implemented")

        # Create many agents and services for concurrent access
        self.agents = {}
        self.services = {}

        for i in range(100):
            self.agents[f"Agent{i}"] = AgentDeclaration(
                agent_type=f"Agent{i}",
                class_path=f"agentmap.agents.Agent{i}",
                service_requirements=[
                    ServiceRequirement(name=f"service_{i % 10}"),
                ],
            )
            self.services[f"service_{i}"] = ServiceDeclaration(
                service_name=f"service_{i}",
                class_path=f"agentmap.services.Service{i}",
                required_dependencies=[],
                implements_protocols=[f"Protocol{i}"],
            )

        self.registry = RunScopedDeclarationRegistry(
            agents=self.agents, services=self.services
        )

    def test_concurrent_reads_do_not_fail(self):
        """Test that concurrent reads from multiple threads don't cause errors."""
        results = []
        errors = []

        def read_agent(agent_type: str):
            try:
                decl = self.registry.get_agent_declaration(agent_type)
                results.append((agent_type, decl is not None))
            except Exception as e:
                errors.append((agent_type, str(e)))

        def read_service(service_name: str):
            try:
                decl = self.registry.get_service_declaration(service_name)
                results.append((service_name, decl is not None))
            except Exception as e:
                errors.append((service_name, str(e)))

        # Run concurrent reads
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(100):
                futures.append(executor.submit(read_agent, f"Agent{i}"))
                futures.append(executor.submit(read_service, f"service_{i}"))

            for future in as_completed(futures):
                future.result()  # Re-raise any exceptions

        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors during concurrent reads: {errors}")
        self.assertEqual(len(results), 200)  # 100 agents + 100 services

    def test_concurrent_resolve_requirements(self):
        """Test concurrent calls to resolve_agent_requirements."""
        results = []
        errors = []

        def resolve_for_agent(agent_type: str):
            try:
                result = self.registry.resolve_agent_requirements({agent_type})
                results.append((agent_type, result))
            except Exception as e:
                errors.append((agent_type, str(e)))

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(100):
                futures.append(executor.submit(resolve_for_agent, f"Agent{i}"))

            for future in as_completed(futures):
                future.result()

        self.assertEqual(
            len(errors), 0, f"Errors during concurrent resolution: {errors}"
        )
        self.assertEqual(len(results), 100)


class TestCreateScopedRegistryForBundle(unittest.TestCase):
    """Test the factory method create_scoped_registry_for_bundle."""

    def setUp(self):
        """Set up test fixtures."""
        if DeclarationRegistryService is None:
            self.skipTest("DeclarationRegistryService not available")

        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.mock_app_config = self.mock_factory.create_mock_app_config_service()

        # Create declaration registry service
        self.registry_service = DeclarationRegistryService(
            app_config_service=self.mock_app_config,
            logging_service=self.mock_logging,
        )

        # Set up test declarations
        self.test_agent_decl = AgentDeclaration(
            agent_type="TestAgent",
            class_path="agentmap.agents.TestAgent",
            service_requirements=[
                ServiceRequirement(name="llm_service"),
            ],
        )

        self.other_agent_decl = AgentDeclaration(
            agent_type="OtherAgent",
            class_path="agentmap.agents.OtherAgent",
            service_requirements=[
                ServiceRequirement(name="storage_service"),
            ],
        )

        self.llm_service_decl = ServiceDeclaration(
            service_name="llm_service",
            class_path="agentmap.services.LLMService",
            required_dependencies=["logging_service"],
            implements_protocols=["LLMServiceProtocol"],
        )

        self.storage_service_decl = ServiceDeclaration(
            service_name="storage_service",
            class_path="agentmap.services.StorageService",
            required_dependencies=["logging_service"],
            implements_protocols=["StorageServiceProtocol"],
        )

        self.logging_service_decl = ServiceDeclaration(
            service_name="logging_service",
            class_path="agentmap.services.LoggingService",
            required_dependencies=[],
            implements_protocols=["LoggingServiceProtocol"],
        )

        # Add declarations to service
        self.registry_service.add_agent_declaration(self.test_agent_decl)
        self.registry_service.add_agent_declaration(self.other_agent_decl)
        self.registry_service.add_service_declaration(self.llm_service_decl)
        self.registry_service.add_service_declaration(self.storage_service_decl)
        self.registry_service.add_service_declaration(self.logging_service_decl)

    def _create_test_bundle(
        self,
        graph_name: str = "test_graph",
        required_agents: Set[str] = None,
        required_services: Set[str] = None,
    ) -> GraphBundle:
        """Create a test bundle."""
        return GraphBundle.create_metadata(
            graph_name=graph_name,
            nodes={},
            required_agents=required_agents or set(),
            required_services=required_services or set(),
            function_mappings={},
            csv_hash="test_hash",
        )

    def test_create_scoped_registry_returns_run_scoped_registry(self):
        """Test that factory method returns RunScopedDeclarationRegistry."""
        bundle = self._create_test_bundle(
            required_agents={"TestAgent"},
            required_services={"llm_service"},
        )

        if not hasattr(self.registry_service, "create_scoped_registry_for_bundle"):
            self.skipTest("create_scoped_registry_for_bundle not yet implemented")

        scoped_registry = self.registry_service.create_scoped_registry_for_bundle(
            bundle
        )

        self.assertIsInstance(scoped_registry, RunScopedDeclarationRegistry)

    def test_create_scoped_registry_filters_agents_for_bundle(self):
        """Test that factory method filters agents based on bundle requirements."""
        bundle = self._create_test_bundle(
            required_agents={"TestAgent"},  # Only TestAgent, not OtherAgent
            required_services={"llm_service"},
        )

        if not hasattr(self.registry_service, "create_scoped_registry_for_bundle"):
            self.skipTest("create_scoped_registry_for_bundle not yet implemented")

        scoped_registry = self.registry_service.create_scoped_registry_for_bundle(
            bundle
        )

        # Should contain TestAgent
        self.assertIsNotNone(scoped_registry.get_agent_declaration("TestAgent"))

        # Should NOT contain OtherAgent (not in bundle requirements)
        self.assertIsNone(scoped_registry.get_agent_declaration("OtherAgent"))

    def test_create_scoped_registry_filters_services_for_bundle(self):
        """Test that factory method filters services based on bundle requirements."""
        bundle = self._create_test_bundle(
            required_agents={"TestAgent"},
            required_services={"llm_service"},  # Only llm_service, not storage_service
        )

        if not hasattr(self.registry_service, "create_scoped_registry_for_bundle"):
            self.skipTest("create_scoped_registry_for_bundle not yet implemented")

        scoped_registry = self.registry_service.create_scoped_registry_for_bundle(
            bundle
        )

        # Should contain llm_service
        self.assertIsNotNone(scoped_registry.get_service_declaration("llm_service"))

        # Should NOT contain storage_service (not in bundle requirements)
        self.assertIsNone(scoped_registry.get_service_declaration("storage_service"))

    def test_create_scoped_registry_includes_core_infrastructure_services(self):
        """Test that factory method always includes core infrastructure services."""
        bundle = self._create_test_bundle(
            required_agents={"TestAgent"},
            required_services={"llm_service"},
        )

        if not hasattr(self.registry_service, "create_scoped_registry_for_bundle"):
            self.skipTest("create_scoped_registry_for_bundle not yet implemented")

        scoped_registry = self.registry_service.create_scoped_registry_for_bundle(
            bundle
        )

        # Should include logging_service as core infrastructure
        self.assertIsNotNone(scoped_registry.get_service_declaration("logging_service"))

    def test_create_scoped_registry_does_not_modify_singleton_state(self):
        """Test that factory method does NOT modify the singleton's internal state."""
        bundle = self._create_test_bundle(
            required_agents={"TestAgent"},
            required_services={"llm_service"},
        )

        if not hasattr(self.registry_service, "create_scoped_registry_for_bundle"):
            self.skipTest("create_scoped_registry_for_bundle not yet implemented")

        # Capture original state
        original_agents = set(self.registry_service.get_all_agent_types())
        original_services = set(self.registry_service.get_all_service_names())

        # Create scoped registry
        scoped_registry = self.registry_service.create_scoped_registry_for_bundle(
            bundle
        )

        # Verify singleton state is unchanged
        after_agents = set(self.registry_service.get_all_agent_types())
        after_services = set(self.registry_service.get_all_service_names())

        self.assertEqual(original_agents, after_agents)
        self.assertEqual(original_services, after_services)

        # OtherAgent should still exist in singleton but not in scoped registry
        self.assertIsNotNone(self.registry_service.get_agent_declaration("OtherAgent"))
        self.assertIsNone(scoped_registry.get_agent_declaration("OtherAgent"))

    def test_multiple_scoped_registries_are_independent(self):
        """Test that multiple scoped registries created from same singleton are independent."""
        bundle1 = self._create_test_bundle(
            graph_name="graph1",
            required_agents={"TestAgent"},
            required_services={"llm_service"},
        )

        bundle2 = self._create_test_bundle(
            graph_name="graph2",
            required_agents={"OtherAgent"},
            required_services={"storage_service"},
        )

        if not hasattr(self.registry_service, "create_scoped_registry_for_bundle"):
            self.skipTest("create_scoped_registry_for_bundle not yet implemented")

        scoped1 = self.registry_service.create_scoped_registry_for_bundle(bundle1)
        scoped2 = self.registry_service.create_scoped_registry_for_bundle(bundle2)

        # Registry 1 should have TestAgent but not OtherAgent
        self.assertIsNotNone(scoped1.get_agent_declaration("TestAgent"))
        self.assertIsNone(scoped1.get_agent_declaration("OtherAgent"))

        # Registry 2 should have OtherAgent but not TestAgent
        self.assertIsNotNone(scoped2.get_agent_declaration("OtherAgent"))
        self.assertIsNone(scoped2.get_agent_declaration("TestAgent"))

        # Services should also be isolated
        self.assertIsNotNone(scoped1.get_service_declaration("llm_service"))
        self.assertIsNone(scoped1.get_service_declaration("storage_service"))

        self.assertIsNotNone(scoped2.get_service_declaration("storage_service"))
        self.assertIsNone(scoped2.get_service_declaration("llm_service"))


class TestConcurrentGraphRunsGetIsolatedRegistries(unittest.TestCase):
    """Integration test for concurrent graph runs with isolated registries."""

    def setUp(self):
        """Set up test fixtures."""
        if DeclarationRegistryService is None:
            self.skipTest("DeclarationRegistryService not available")

        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.mock_app_config = self.mock_factory.create_mock_app_config_service()

        self.registry_service = DeclarationRegistryService(
            app_config_service=self.mock_app_config,
            logging_service=self.mock_logging,
        )

        # Add many declarations
        for i in range(10):
            self.registry_service.add_agent_declaration(
                AgentDeclaration(
                    agent_type=f"Agent{i}",
                    class_path=f"agentmap.agents.Agent{i}",
                    service_requirements=[
                        ServiceRequirement(name=f"service_{i}"),
                    ],
                )
            )
            self.registry_service.add_service_declaration(
                ServiceDeclaration(
                    service_name=f"service_{i}",
                    class_path=f"agentmap.services.Service{i}",
                    required_dependencies=[],
                    implements_protocols=[f"Protocol{i}"],
                )
            )

    def test_concurrent_scoped_registry_creation(self):
        """Test that concurrent scoped registry creation produces isolated registries."""
        if not hasattr(self.registry_service, "create_scoped_registry_for_bundle"):
            self.skipTest("create_scoped_registry_for_bundle not yet implemented")

        results = {}
        errors = []

        def create_and_verify_scoped_registry(bundle_id: int):
            try:
                # Each bundle requests different agents/services
                bundle = GraphBundle.create_metadata(
                    graph_name=f"graph_{bundle_id}",
                    nodes={},
                    required_agents={f"Agent{bundle_id}"},
                    required_services={f"service_{bundle_id}"},
                    function_mappings={},
                    csv_hash=f"hash_{bundle_id}",
                )

                scoped = self.registry_service.create_scoped_registry_for_bundle(bundle)

                # Verify isolation: only requested agent/service should be present
                has_own_agent = (
                    scoped.get_agent_declaration(f"Agent{bundle_id}") is not None
                )
                has_other_agent = (
                    scoped.get_agent_declaration(f"Agent{(bundle_id + 1) % 10}")
                    is not None
                )

                results[bundle_id] = {
                    "has_own_agent": has_own_agent,
                    "has_other_agent": has_other_agent,
                }
            except Exception as e:
                errors.append((bundle_id, str(e)))

        # Run concurrent creations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(create_and_verify_scoped_registry, i))

            for future in as_completed(futures):
                future.result()

        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors: {errors}")

        # Verify each registry got only its own declarations
        for bundle_id, result in results.items():
            self.assertTrue(
                result["has_own_agent"], f"Bundle {bundle_id} should have its own agent"
            )
            self.assertFalse(
                result["has_other_agent"],
                f"Bundle {bundle_id} should NOT have other agent",
            )


class TestGraphBundleScopedRegistryField(unittest.TestCase):
    """Test that GraphBundle correctly stores scoped_registry field."""

    def test_graph_bundle_has_scoped_registry_field(self):
        """Test that GraphBundle has the scoped_registry field."""
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="test_hash",
        )

        # Should have scoped_registry field initialized to None
        self.assertTrue(hasattr(bundle, "scoped_registry"))
        self.assertIsNone(bundle.scoped_registry)

    def test_graph_bundle_scoped_registry_can_be_set(self):
        """Test that scoped_registry can be assigned to GraphBundle."""
        if RunScopedDeclarationRegistry is None:
            self.skipTest("RunScopedDeclarationRegistry not yet implemented")

        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="test_hash",
        )

        # Create a scoped registry
        scoped = RunScopedDeclarationRegistry(agents={}, services={})

        # Should be able to assign it
        bundle.scoped_registry = scoped
        self.assertIsNotNone(bundle.scoped_registry)
        self.assertIs(bundle.scoped_registry, scoped)


if __name__ == "__main__":
    unittest.main()
