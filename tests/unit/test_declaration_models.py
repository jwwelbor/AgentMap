"""
Unit tests for declaration domain models.

Tests model creation, helper methods, serialization, and data integrity
for all declaration models without loading any implementations.
"""

import unittest

from agentmap.models.declaration_models import (
    AgentDeclaration,
    ProtocolRequirement,
    ServiceDeclaration,
    ServiceRequirement,
)


class TestServiceRequirement(unittest.TestCase):
    """Test ServiceRequirement model functionality."""

    def test_basic_creation(self):
        """Test basic ServiceRequirement creation."""
        req = ServiceRequirement(name="test_service")

        self.assertEqual(req.name, "test_service")
        self.assertFalse(req.optional)
        self.assertIsNone(req.fallback)
        self.assertIsNone(req.version)

    def test_creation_with_all_fields(self):
        """Test ServiceRequirement creation with all fields."""
        req = ServiceRequirement(
            name="test_service",
            optional=True,
            fallback="fallback_service",
            version="1.0.0",
        )

        self.assertEqual(req.name, "test_service")
        self.assertTrue(req.optional)
        self.assertEqual(req.fallback, "fallback_service")
        self.assertEqual(req.version, "1.0.0")

    def test_from_string_basic(self):
        """Test creating ServiceRequirement from string."""
        req = ServiceRequirement.from_string("test_service")

        self.assertEqual(req.name, "test_service")
        self.assertFalse(req.optional)
        self.assertIsNone(req.version)

    def test_from_string_with_version(self):
        """Test creating ServiceRequirement from string with version."""
        req = ServiceRequirement.from_string("test_service:1.2.3")

        self.assertEqual(req.name, "test_service")
        self.assertEqual(req.version, "1.2.3")
        self.assertFalse(req.optional)

    def test_from_dict_basic(self):
        """Test creating ServiceRequirement from dictionary."""
        data = {"name": "test_service"}
        req = ServiceRequirement.from_dict(data)

        self.assertEqual(req.name, "test_service")
        self.assertFalse(req.optional)

    def test_from_dict_full(self):
        """Test creating ServiceRequirement from full dictionary."""
        data = {
            "name": "test_service",
            "optional": True,
            "fallback": "backup_service",
            "version": "2.0.0",
        }
        req = ServiceRequirement.from_dict(data)

        self.assertEqual(req.name, "test_service")
        self.assertTrue(req.optional)
        self.assertEqual(req.fallback, "backup_service")
        self.assertEqual(req.version, "2.0.0")


class TestProtocolRequirement(unittest.TestCase):
    """Test ProtocolRequirement model functionality."""

    def test_basic_creation(self):
        """Test basic ProtocolRequirement creation."""
        req = ProtocolRequirement(name="TestProtocol")

        self.assertEqual(req.name, "TestProtocol")
        self.assertIsNone(req.version)
        self.assertFalse(req.implements)
        self.assertFalse(req.requires)

    def test_creation_with_all_fields(self):
        """Test ProtocolRequirement creation with all fields."""
        req = ProtocolRequirement(
            name="TestProtocol", version="1.0", implements=True, requires=False
        )

        self.assertEqual(req.name, "TestProtocol")
        self.assertEqual(req.version, "1.0")
        self.assertTrue(req.implements)
        self.assertFalse(req.requires)

    def test_from_string_basic(self):
        """Test creating ProtocolRequirement from string."""
        req = ProtocolRequirement.from_string("TestProtocol")

        self.assertEqual(req.name, "TestProtocol")
        self.assertIsNone(req.version)

    def test_from_string_with_version(self):
        """Test creating ProtocolRequirement from string with version."""
        req = ProtocolRequirement.from_string("TestProtocol:2.1")

        self.assertEqual(req.name, "TestProtocol")
        self.assertEqual(req.version, "2.1")

    def test_from_dict_full(self):
        """Test creating ProtocolRequirement from dictionary."""
        data = {
            "name": "TestProtocol",
            "version": "1.5",
            "implements": True,
            "requires": True,
        }
        req = ProtocolRequirement.from_dict(data)

        self.assertEqual(req.name, "TestProtocol")
        self.assertEqual(req.version, "1.5")
        self.assertTrue(req.implements)
        self.assertTrue(req.requires)


class TestAgentDeclaration(unittest.TestCase):
    """Test AgentDeclaration model functionality."""

    def test_basic_creation(self):
        """Test basic AgentDeclaration creation."""
        decl = AgentDeclaration(
            agent_type="test_agent", class_path="test.module.TestAgent"
        )

        self.assertEqual(decl.agent_type, "test_agent")
        self.assertEqual(decl.class_path, "test.module.TestAgent")
        self.assertEqual(len(decl.service_requirements), 0)
        self.assertEqual(len(decl.protocol_requirements), 0)
        self.assertEqual(len(decl.capabilities), 0)
        self.assertEqual(len(decl.metadata), 0)
        self.assertEqual(len(decl.config), 0)
        self.assertEqual(decl.source, "")

    def test_creation_with_requirements(self):
        """Test AgentDeclaration creation with service and protocol requirements."""
        service_req = ServiceRequirement(name="logging_service")
        protocol_req = ProtocolRequirement(name="TestProtocol", requires=True)

        decl = AgentDeclaration(
            agent_type="test_agent",
            class_path="test.module.TestAgent",
            service_requirements=[service_req],
            protocol_requirements=[protocol_req],
            capabilities={"test", "example"},
            source="test_source",
        )

        self.assertEqual(len(decl.service_requirements), 1)
        self.assertEqual(decl.service_requirements[0].name, "logging_service")
        self.assertEqual(len(decl.protocol_requirements), 1)
        self.assertEqual(decl.protocol_requirements[0].name, "TestProtocol")
        self.assertEqual(decl.capabilities, {"test", "example"})
        self.assertEqual(decl.source, "test_source")

    def test_get_required_services(self):
        """Test get_required_services helper method."""
        required_service = ServiceRequirement(name="logging_service", optional=False)
        optional_service = ServiceRequirement(name="config_service", optional=True)

        decl = AgentDeclaration(
            agent_type="test_agent",
            class_path="test.module.TestAgent",
            service_requirements=[required_service, optional_service],
        )

        required_services = decl.get_required_services()
        self.assertEqual(required_services, ["logging_service"])

    def test_get_all_services(self):
        """Test get_all_services helper method."""
        required_service = ServiceRequirement(name="logging_service", optional=False)
        optional_service = ServiceRequirement(name="config_service", optional=True)

        decl = AgentDeclaration(
            agent_type="test_agent",
            class_path="test.module.TestAgent",
            service_requirements=[required_service, optional_service],
        )

        all_services = decl.get_all_services()
        self.assertEqual(set(all_services), {"logging_service", "config_service"})

    def test_get_required_protocols(self):
        """Test get_required_protocols helper method."""
        required_protocol = ProtocolRequirement(name="RequiredProtocol", requires=True)
        implemented_protocol = ProtocolRequirement(
            name="ImplementedProtocol", implements=True
        )

        decl = AgentDeclaration(
            agent_type="test_agent",
            class_path="test.module.TestAgent",
            protocol_requirements=[required_protocol, implemented_protocol],
        )

        required_protocols = decl.get_required_protocols()
        self.assertEqual(required_protocols, ["RequiredProtocol"])


class TestServiceDeclaration(unittest.TestCase):
    """Test ServiceDeclaration model functionality."""

    def test_basic_creation(self):
        """Test basic ServiceDeclaration creation."""
        decl = ServiceDeclaration(
            service_name="test_service", class_path="test.module.TestService"
        )

        self.assertEqual(decl.service_name, "test_service")
        self.assertEqual(decl.class_path, "test.module.TestService")
        self.assertEqual(len(decl.required_dependencies), 0)
        self.assertEqual(len(decl.optional_dependencies), 0)
        self.assertEqual(len(decl.implements_protocols), 0)
        self.assertEqual(len(decl.requires_protocols), 0)
        self.assertTrue(decl.singleton)
        self.assertFalse(decl.lazy_load)
        self.assertIsNone(decl.factory_method)
        self.assertEqual(len(decl.metadata), 0)
        self.assertEqual(len(decl.config), 0)
        self.assertEqual(decl.source, "")

    def test_creation_with_all_fields(self):
        """Test ServiceDeclaration creation with all fields."""
        decl = ServiceDeclaration(
            service_name="test_service",
            class_path="test.module.TestService",
            required_dependencies=["logging_service", "config_service"],
            optional_dependencies=["storage_service"],
            implements_protocols=["ServiceProtocol"],
            requires_protocols=["DependencyProtocol"],
            singleton=False,
            lazy_load=True,
            factory_method="create_service",
            metadata={"type": "business"},
            config={"enabled": True},
            source="yaml_file",
        )

        self.assertEqual(decl.service_name, "test_service")
        self.assertEqual(decl.class_path, "test.module.TestService")
        self.assertEqual(
            decl.required_dependencies, ["logging_service", "config_service"]
        )
        self.assertEqual(decl.optional_dependencies, ["storage_service"])
        self.assertEqual(decl.implements_protocols, ["ServiceProtocol"])
        self.assertEqual(decl.requires_protocols, ["DependencyProtocol"])
        self.assertFalse(decl.singleton)
        self.assertTrue(decl.lazy_load)
        self.assertEqual(decl.factory_method, "create_service")
        self.assertEqual(decl.metadata["type"], "business")
        self.assertEqual(decl.config["enabled"], True)
        self.assertEqual(decl.source, "yaml_file")

    def test_dataclass_behavior(self):
        """Test that models behave correctly as dataclasses."""
        decl1 = ServiceDeclaration(
            service_name="test_service", class_path="test.module.TestService"
        )

        decl2 = ServiceDeclaration(
            service_name="test_service", class_path="test.module.TestService"
        )

        # Test equality
        self.assertEqual(decl1, decl2)

        # Test that field defaults work correctly
        decl3 = ServiceDeclaration(
            service_name="different_service", class_path="test.module.TestService"
        )

        self.assertNotEqual(decl1, decl3)


if __name__ == "__main__":
    unittest.main()
