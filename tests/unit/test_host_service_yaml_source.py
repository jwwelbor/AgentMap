"""
Unit tests for HostServiceYAMLSource and bootstrap_from_declarations.
"""

import unittest
from pathlib import Path
from typing import Any, Dict, Protocol, runtime_checkable
from unittest.mock import MagicMock, patch

from agentmap.models.declaration_models import ServiceDeclaration
from agentmap.services.declaration_sources import HostServiceYAMLSource
from agentmap.services.host_service_registry import (
    HostServiceRegistry,
    _import_class,
    _topological_sort,
    bootstrap_from_declarations,
)

# ============================================================================
# Test fixtures
# ============================================================================


@runtime_checkable
class FakeProtocol(Protocol):
    def configure_fake_service(self, service: Any) -> None: ...


class FakeService:
    def __init__(self, **kwargs: Any):
        self.config = kwargs

    @classmethod
    def create(cls, **kwargs: Any) -> "FakeService":
        return cls(**kwargs)


class FakeServiceWithDeps:
    def __init__(self, dep_service: Any = None, **kwargs: Any):
        self.dep_service = dep_service
        self.config = kwargs


# ============================================================================
# HostServiceYAMLSource tests
# ============================================================================


class TestHostServiceYAMLSource(unittest.TestCase):
    """Tests for HostServiceYAMLSource."""

    def _make_source(self, custom_agents_path: Path = None) -> HostServiceYAMLSource:
        mock_config = MagicMock()
        mock_config.get_custom_agents_path.return_value = custom_agents_path or Path(
            "/nonexistent"
        )

        mock_parser = MagicMock()
        mock_parser.parse_service.side_effect = (
            lambda name, data, source: ServiceDeclaration(
                service_name=name,
                class_path=data.get("class_path", ""),
                implements_protocols=data.get("implements", []),
                config=data.get("config", {}),
                source=source,
            )
        )

        mock_logging = MagicMock()
        mock_logger = MagicMock()
        mock_logging.get_class_logger.return_value = mock_logger

        return HostServiceYAMLSource(mock_config, mock_parser, mock_logging)

    def test_load_agents_returns_empty(self):
        source = self._make_source()
        self.assertEqual(source.load_agents(), {})

    def test_load_services_missing_file(self):
        source = self._make_source(Path("/nonexistent"))
        self.assertEqual(source.load_services(), {})

    def test_load_services_valid_yaml(self):
        yaml_content = {
            "version": "1.0",
            "services": {
                "my_service": {
                    "class_path": "myapp.services.MyService",
                    "implements": ["myapp.protocols.MyProtocol"],
                    "config": {"key": "value"},
                }
            },
        }

        source = self._make_source()
        with patch("agentmap.services.declaration_sources.host_service_yaml_source.load_yaml_file", return_value=yaml_content):
            services = source.load_services()

        self.assertIn("my_service", services)
        decl = services["my_service"]
        self.assertEqual(decl.class_path, "myapp.services.MyService")
        self.assertEqual(decl.implements_protocols, ["myapp.protocols.MyProtocol"])
        self.assertEqual(decl.config, {"key": "value"})
        self.assertTrue(
            decl.source.startswith(HostServiceYAMLSource.HOST_SERVICES_SOURCE_PREFIX)
        )

    def test_load_services_no_services_section(self):
        source = self._make_source()
        with patch("agentmap.services.declaration_sources.host_service_yaml_source.load_yaml_file", return_value={"version": "1.0"}):
            services = source.load_services()
        self.assertEqual(services, {})

    def test_normalize_service_data(self):
        source = self._make_source()
        raw = {
            "class_path": "a.b.C",
            "implements": ["x.y.P"],
            "dependencies": ["other_svc"],
            "config": {"k": "v"},
            "factory_method": "create",
        }
        normalized = source._normalize_service_data(raw)
        self.assertEqual(normalized["class_path"], "a.b.C")
        self.assertEqual(normalized["implements"], ["x.y.P"])
        self.assertEqual(normalized["dependencies"], ["other_svc"])
        self.assertEqual(normalized["config"], {"k": "v"})
        self.assertEqual(normalized["factory_method"], "create")


# ============================================================================
# _import_class tests
# ============================================================================


class TestImportClass(unittest.TestCase):
    def test_import_existing_class(self):
        cls = _import_class("pathlib.Path")
        self.assertIs(cls, Path)

    def test_import_nonexistent_module(self):
        with self.assertRaises(ImportError):
            _import_class("nonexistent.module.Cls")

    def test_import_nonexistent_class(self):
        with self.assertRaises(ImportError):
            _import_class("pathlib.NonexistentClass")

    def test_import_no_module(self):
        with self.assertRaises(ImportError):
            _import_class("JustAName")


# ============================================================================
# _topological_sort tests
# ============================================================================


class TestTopologicalSort(unittest.TestCase):
    def _make_decl(self, deps: list) -> ServiceDeclaration:
        return ServiceDeclaration(
            service_name="x",
            class_path="x.X",
            required_dependencies=deps,
        )

    def test_no_deps(self):
        decls = {
            "a": self._make_decl([]),
            "b": self._make_decl([]),
        }
        result = _topological_sort(decls)
        self.assertEqual(set(result), {"a", "b"})

    def test_linear_deps(self):
        decls = {
            "a": self._make_decl([]),
            "b": self._make_decl(["a"]),
            "c": self._make_decl(["b"]),
        }
        result = _topological_sort(decls)
        self.assertEqual(result.index("a"), 0)
        self.assertLess(result.index("b"), result.index("c"))

    def test_circular_deps_raises(self):
        decls = {
            "a": self._make_decl(["b"]),
            "b": self._make_decl(["a"]),
        }
        with self.assertRaises(ValueError) as ctx:
            _topological_sort(decls)
        self.assertIn("Circular dependency", str(ctx.exception))


# ============================================================================
# bootstrap_from_declarations tests
# ============================================================================


class TestBootstrapFromDeclarations(unittest.TestCase):
    def _make_mock_registry(self) -> HostServiceRegistry:
        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        return HostServiceRegistry(mock_logging)

    def _make_decl_registry(
        self, declarations: Dict[str, ServiceDeclaration]
    ) -> MagicMock:
        mock = MagicMock()
        mock.get_all_service_names.return_value = list(declarations.keys())
        mock.get_service_declaration.side_effect = lambda name: declarations.get(name)
        return mock

    def test_no_host_declarations(self):
        """No services with host_services source prefix."""
        decl = ServiceDeclaration(
            service_name="builtin_svc",
            class_path="x.X",
            source="builtin",
        )
        decl_registry = self._make_decl_registry({"builtin_svc": decl})
        host_registry = self._make_mock_registry()
        logger = MagicMock()

        count = bootstrap_from_declarations(decl_registry, host_registry, logger=logger)
        self.assertEqual(count, 0)

    def test_bootstrap_simple_service(self):
        """Bootstrap a single service with no deps."""
        source = f"{HostServiceYAMLSource.HOST_SERVICES_SOURCE_PREFIX}/path"
        decl = ServiceDeclaration(
            service_name="fake_service",
            class_path=f"{__name__}.FakeService",
            implements_protocols=[f"{__name__}.FakeProtocol"],
            config={"key": "val"},
            source=source,
        )
        decl_registry = self._make_decl_registry({"fake_service": decl})
        host_registry = self._make_mock_registry()
        logger = MagicMock()

        count = bootstrap_from_declarations(decl_registry, host_registry, logger=logger)
        self.assertEqual(count, 1)

        # Verify registered in host registry
        self.assertTrue(host_registry.is_service_registered("fake_service"))
        provider = host_registry.get_service_provider("fake_service")
        self.assertIsInstance(provider, FakeService)
        self.assertEqual(provider.config, {"key": "val"})

    def test_bootstrap_with_factory_method(self):
        """Bootstrap using a factory method."""
        source = f"{HostServiceYAMLSource.HOST_SERVICES_SOURCE_PREFIX}/path"
        decl = ServiceDeclaration(
            service_name="factory_svc",
            class_path=f"{__name__}.FakeService",
            factory_method="create",
            config={"x": 1},
            source=source,
        )
        decl_registry = self._make_decl_registry({"factory_svc": decl})
        host_registry = self._make_mock_registry()
        logger = MagicMock()

        count = bootstrap_from_declarations(decl_registry, host_registry, logger=logger)
        self.assertEqual(count, 1)
        provider = host_registry.get_service_provider("factory_svc")
        self.assertIsInstance(provider, FakeService)

    def test_bootstrap_with_dependencies(self):
        """Bootstrap services with inter-service dependencies."""
        source = f"{HostServiceYAMLSource.HOST_SERVICES_SOURCE_PREFIX}/path"
        dep_decl = ServiceDeclaration(
            service_name="dep_service",
            class_path=f"{__name__}.FakeService",
            source=source,
        )
        main_decl = ServiceDeclaration(
            service_name="main_service",
            class_path=f"{__name__}.FakeServiceWithDeps",
            required_dependencies=["dep_service"],
            source=source,
        )
        decl_registry = self._make_decl_registry(
            {"dep_service": dep_decl, "main_service": main_decl}
        )
        host_registry = self._make_mock_registry()
        logger = MagicMock()

        count = bootstrap_from_declarations(decl_registry, host_registry, logger=logger)
        self.assertEqual(count, 2)

        main_instance = host_registry.get_service_provider("main_service")
        self.assertIsInstance(main_instance, FakeServiceWithDeps)
        self.assertIsInstance(main_instance.dep_service, FakeService)

    def test_bootstrap_bad_class_path(self):
        """Bad class path logs error, doesn't crash."""
        source = f"{HostServiceYAMLSource.HOST_SERVICES_SOURCE_PREFIX}/path"
        decl = ServiceDeclaration(
            service_name="bad_svc",
            class_path="nonexistent.module.BadClass",
            source=source,
        )
        decl_registry = self._make_decl_registry({"bad_svc": decl})
        host_registry = self._make_mock_registry()
        logger = MagicMock()

        count = bootstrap_from_declarations(decl_registry, host_registry, logger=logger)
        self.assertEqual(count, 0)
        logger.error.assert_called()

    def test_bootstrap_config_merge_with_app_config(self):
        """App config values serve as defaults; YAML config wins."""
        source = f"{HostServiceYAMLSource.HOST_SERVICES_SOURCE_PREFIX}/path"
        decl = ServiceDeclaration(
            service_name="cfg_svc",
            class_path=f"{__name__}.FakeService",
            config={"key": "from_yaml", "yaml_only": True},
            source=source,
        )
        decl_registry = self._make_decl_registry({"cfg_svc": decl})
        host_registry = self._make_mock_registry()
        logger = MagicMock()

        mock_app_config = MagicMock()
        mock_app_config.get_host_service_config.return_value = {
            "configuration": {"key": "from_app", "app_only": True}
        }

        count = bootstrap_from_declarations(
            decl_registry,
            host_registry,
            app_config_service=mock_app_config,
            logger=logger,
        )
        self.assertEqual(count, 1)
        instance = host_registry.get_service_provider("cfg_svc")
        # YAML wins for "key"
        self.assertEqual(instance.config["key"], "from_yaml")
        # App config provides defaults for keys not in YAML
        self.assertTrue(instance.config["app_only"])
        # YAML-only key preserved
        self.assertTrue(instance.config["yaml_only"])


# ============================================================================
# HostProtocolConfigurationService lazy bootstrap tests
# ============================================================================


class TestHostProtocolConfigurationServiceBootstrap(unittest.TestCase):
    def test_lazy_bootstrap_called_once(self):
        """_ensure_services_bootstrapped runs only on first call."""
        from agentmap.services.host_protocol_configuration_service import (
            HostProtocolConfigurationService,
        )

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_logging.get_logger.return_value = MagicMock()

        mock_registry = MagicMock()
        mock_registry.list_registered_services.return_value = []

        mock_decl_registry = MagicMock()
        mock_decl_registry.get_all_service_names.return_value = []

        svc = HostProtocolConfigurationService(
            host_service_registry=mock_registry,
            logging_service=mock_logging,
            declaration_registry_service=mock_decl_registry,
        )

        agent = MagicMock()
        agent.name = "test_agent"

        # Call twice
        svc.configure_host_protocols(agent)
        svc.configure_host_protocols(agent)

        # Declaration registry should have been queried exactly once for bootstrap
        mock_decl_registry.get_all_service_names.assert_called_once()

    def test_no_declaration_registry_skips_bootstrap(self):
        """Without declaration_registry_service, bootstrap is silently skipped."""
        from agentmap.services.host_protocol_configuration_service import (
            HostProtocolConfigurationService,
        )

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_logging.get_logger.return_value = MagicMock()

        mock_registry = MagicMock()
        mock_registry.list_registered_services.return_value = []

        svc = HostProtocolConfigurationService(
            host_service_registry=mock_registry,
            logging_service=mock_logging,
            declaration_registry_service=None,
        )

        agent = MagicMock()
        agent.name = "test_agent"

        # Should not raise
        count = svc.configure_host_protocols(agent)
        self.assertEqual(count, 0)


# ============================================================================
# HostServiceConfigurator bug fix test
# ============================================================================


class TestHostServiceConfiguratorBugFix(unittest.TestCase):
    def test_calls_configure_host_protocols(self):
        """Verify the bug fix: calls configure_host_protocols, not configure_agent."""
        from agentmap.services.agent.host_service_configurator import (
            HostServiceConfigurator,
        )

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_protocol_svc = MagicMock()
        mock_protocol_svc.configure_host_protocols.return_value = 3

        configurator = HostServiceConfigurator(
            logging_service=mock_logging,
            host_protocol_configuration_service=mock_protocol_svc,
        )

        agent = MagicMock()
        result = configurator.configure_host_services(agent)

        mock_protocol_svc.configure_host_protocols.assert_called_once_with(
            agent, required_services=None
        )
        self.assertEqual(result, 3)

    def test_passes_required_services_filter(self):
        """Verify required_services is forwarded."""
        from agentmap.services.agent.host_service_configurator import (
            HostServiceConfigurator,
        )

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_protocol_svc = MagicMock()
        mock_protocol_svc.configure_host_protocols.return_value = 1

        configurator = HostServiceConfigurator(
            logging_service=mock_logging,
            host_protocol_configuration_service=mock_protocol_svc,
        )

        agent = MagicMock()
        services_filter = {"database_service"}
        configurator.configure_host_services(agent, required_services=services_filter)

        mock_protocol_svc.configure_host_protocols.assert_called_once_with(
            agent, required_services=services_filter
        )


if __name__ == "__main__":
    unittest.main()
