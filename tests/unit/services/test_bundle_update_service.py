"""
Unit tests for BundleUpdateService.

Tests the bundle update functionality for resolving missing declarations,
updating changed class paths, removing obsolete mappings, and service requirement updates.
Follows project testing patterns using MockServiceFactory for dependencies.
"""

import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Set, Dict, Any

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.declaration_models import AgentDeclaration
from agentmap.services.graph.bundle_update_service import BundleUpdateService
from tests.utils.mock_service_factory import MockServiceFactory


class TestBundleUpdateService(unittest.TestCase):
    """Test BundleUpdateService functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        
        # Create mock services
        self.mock_declaration_registry = Mock()
        self.mock_custom_agent_declaration_manager = self.mock_factory.create_mock_custom_agent_declaration_manager()
        self.mock_graph_bundle_service = Mock()
        self.mock_file_path_service = self.mock_factory.create_mock_file_path_service()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        
        # Create service under test
        self.bundle_update_service = BundleUpdateService(
            declaration_registry_service=self.mock_declaration_registry,
            custom_agent_declaration_manager=self.mock_custom_agent_declaration_manager,
            graph_bundle_service=self.mock_graph_bundle_service,
            file_path_service=self.mock_file_path_service,
            logging_service=self.mock_logging
        )

    def _create_test_bundle(
        self,
        graph_name: str = "test_graph",
        agent_mappings: Dict[str, str] = None,
        custom_agents: Set[str] = None,
        missing_declarations: Set[str] = None,
        required_services: Set[str] = None
    ) -> GraphBundle:
        """Create a test bundle with specified properties."""
        bundle = GraphBundle.create_metadata(
            graph_name=graph_name,
            nodes={},
            required_agents=set(),
            required_services=required_services or set(),
            function_mappings={},
            csv_hash="test_hash"
        )
        
        # Set optional properties
        bundle.agent_mappings = agent_mappings or {}
        bundle.custom_agents = custom_agents or set()
        bundle.missing_declarations = missing_declarations or set()
        
        return bundle

    def _create_test_declaration(
        self,
        agent_type: str,
        class_path: str,
        source: str = "test_source"
    ) -> AgentDeclaration:
        """Create a test agent declaration."""
        return AgentDeclaration(
            agent_type=agent_type,
            class_path=class_path,
            source=source
        )

    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.bundle_update_service)
        self.assertEqual(
            self.bundle_update_service.declaration_registry, 
            self.mock_declaration_registry
        )
        self.assertEqual(
            self.bundle_update_service.custom_agent_declaration_manager, 
            self.mock_custom_agent_declaration_manager
        )
        self.assertEqual(
            self.bundle_update_service.graph_bundle_service, 
            self.mock_graph_bundle_service
        )
        self.assertEqual(
            self.bundle_update_service.file_path_service, 
            self.mock_file_path_service
        )

    def test_update_bundle_with_missing_declarations_resolved(self):
        """Test update with missing declarations that get resolved."""
        # Arrange
        bundle = self._create_test_bundle(
            missing_declarations={"missing_agent", "another_missing"}
        )
        
        # Configure mock to return declarations for missing agents
        missing_decl = self._create_test_declaration(
            "missing_agent", "agentmap.agents.MissingAgent"
        )
        another_decl = self._create_test_declaration(
            "another_missing", "agentmap.agents.AnotherAgent"
        )
        
        def get_declaration_side_effect(agent_type):
            if agent_type == "missing_agent":
                return missing_decl
            elif agent_type == "another_missing":
                return another_decl
            return None
        
        self.mock_declaration_registry.get_agent_declaration.side_effect = get_declaration_side_effect
        
        # Configure service requirements resolution
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": {"logging_service", "new_service"},
            "protocols": set(),
            "missing": set()
        }
        self.mock_declaration_registry.calculate_load_order.return_value = [
            "logging_service", "new_service"
        ]
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=False
        )
        
        # Assert
        self.assertEqual(result, bundle)
        self.assertIn("missing_agent", bundle.agent_mappings)
        self.assertIn("another_missing", bundle.agent_mappings)
        self.assertEqual(bundle.agent_mappings["missing_agent"], "agentmap.agents.MissingAgent")
        self.assertEqual(bundle.agent_mappings["another_missing"], "agentmap.agents.AnotherAgent")
        self.assertIn("missing_agent", bundle.custom_agents)
        self.assertIn("another_missing", bundle.custom_agents)
        self.assertEqual(len(bundle.missing_declarations), 0)
        self.assertIn("new_service", bundle.required_services)

    def test_update_bundle_with_changed_class_paths(self):
        """Test update with changed class paths."""
        # Arrange
        bundle = self._create_test_bundle(
            agent_mappings={
                "existing_agent": "old.path.ExistingAgent",
                "unchanged_agent": "correct.path.UnchangedAgent"
            },
            custom_agents={"existing_agent", "unchanged_agent"}
        )
        
        # Configure mock to return updated declaration for existing_agent
        updated_decl = self._create_test_declaration(
            "existing_agent", "new.path.ExistingAgent"
        )
        unchanged_decl = self._create_test_declaration(
            "unchanged_agent", "correct.path.UnchangedAgent"
        )
        
        def get_declaration_side_effect(agent_type):
            if agent_type == "existing_agent":
                return updated_decl
            elif agent_type == "unchanged_agent":
                return unchanged_decl
            return None
        
        self.mock_declaration_registry.get_agent_declaration.side_effect = get_declaration_side_effect
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": set(),
            "protocols": set(),
            "missing": set()
        }
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=False
        )
        
        # Assert
        self.assertEqual(result, bundle)
        self.assertEqual(bundle.agent_mappings["existing_agent"], "new.path.ExistingAgent")
        self.assertEqual(bundle.agent_mappings["unchanged_agent"], "correct.path.UnchangedAgent")
        self.assertIn("existing_agent", bundle.custom_agents)
        self.assertIn("unchanged_agent", bundle.custom_agents)

    def test_update_bundle_with_removed_declarations(self):
        """Test update with removed declarations."""
        # Arrange
        bundle = self._create_test_bundle(
            agent_mappings={
                "existing_agent": "agentmap.agents.ExistingAgent",
                "removed_agent": "agentmap.agents.RemovedAgent"
            },
            custom_agents={"existing_agent", "removed_agent"}
        )
        
        # Configure mock to return None for removed_agent (no longer exists)
        existing_decl = self._create_test_declaration(
            "existing_agent", "agentmap.agents.ExistingAgent"
        )
        
        def get_declaration_side_effect(agent_type):
            if agent_type == "existing_agent":
                return existing_decl
            elif agent_type == "removed_agent":
                return None  # Agent no longer exists
            return None
        
        self.mock_declaration_registry.get_agent_declaration.side_effect = get_declaration_side_effect
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": set(),
            "protocols": set(),
            "missing": set()
        }
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=False
        )
        
        # Assert
        self.assertEqual(result, bundle)
        self.assertIn("existing_agent", bundle.agent_mappings)
        self.assertNotIn("removed_agent", bundle.agent_mappings)
        self.assertIn("existing_agent", bundle.custom_agents)
        self.assertNotIn("removed_agent", bundle.custom_agents)
        self.assertIn("removed_agent", bundle.missing_declarations)

    def test_update_service_requirements(self):
        """Test service requirement updates."""
        # Arrange
        bundle = self._create_test_bundle(
            missing_declarations={"new_agent"},
            required_services={"existing_service"}
        )
        
        # Configure mock to resolve missing agent
        new_decl = self._create_test_declaration(
            "new_agent", "agentmap.agents.NewAgent"
        )
        self.mock_declaration_registry.get_agent_declaration.return_value = new_decl
        
        # Configure service requirements resolution
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": {"logging_service", "storage_service"},
            "protocols": set(),
            "missing": set()
        }
        self.mock_declaration_registry.calculate_load_order.return_value = [
            "existing_service", "logging_service", "storage_service"
        ]
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=False
        )
        
        # Assert
        self.assertEqual(result, bundle)
        self.assertIn("logging_service", bundle.required_services)
        self.assertIn("storage_service", bundle.required_services)
        self.assertIn("existing_service", bundle.required_services)
        self.assertEqual(
            bundle.service_load_order,
            ["existing_service", "logging_service", "storage_service"]
        )

    def test_persistence_flag_true_with_changes(self):
        """Test persistence flag (persist=True) with changes."""
        # Arrange
        bundle = self._create_test_bundle(
            missing_declarations={"new_agent"}
        )
        
        # Configure mock to resolve missing agent
        new_decl = self._create_test_declaration(
            "new_agent", "agentmap.agents.NewAgent"
        )
        self.mock_declaration_registry.get_agent_declaration.return_value = new_decl
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": {"new_service"},
            "protocols": set(),
            "missing": set()
        }
        self.mock_declaration_registry.calculate_load_order.return_value = ["new_service"]
        
        # Configure successful save
        save_result = Mock()
        save_result.success = True
        self.mock_graph_bundle_service.save_bundle.return_value = save_result
        
        # Mock Path operations
        with patch('pathlib.Path') as mock_path:
            mock_cache_dir = Mock()
            mock_path.return_value = mock_cache_dir
            mock_cache_dir.__truediv__ = Mock(return_value=Path("test_bundle.json"))
            
            # Act
            result = self.bundle_update_service.update_bundle_from_declarations(
                bundle, persist=True
            )
        
        # Assert
        self.assertEqual(result, bundle)
        self.mock_graph_bundle_service.save_bundle.assert_called_once()

    def test_persistence_flag_false_no_save(self):
        """Test persistence flag (persist=False) does not save."""
        # Arrange
        bundle = self._create_test_bundle(
            missing_declarations={"new_agent"}
        )
        
        # Configure mock to resolve missing agent
        new_decl = self._create_test_declaration(
            "new_agent", "agentmap.agents.NewAgent"
        )
        self.mock_declaration_registry.get_agent_declaration.return_value = new_decl
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": set(),
            "protocols": set(),
            "missing": set()
        }
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=False
        )
        
        # Assert
        self.assertEqual(result, bundle)
        self.mock_graph_bundle_service.save_bundle.assert_not_called()

    def test_no_persistence_when_no_changes(self):
        """Test no persistence when there are no changes."""
        # Arrange
        bundle = self._create_test_bundle(
            agent_mappings={"existing_agent": "agentmap.agents.ExistingAgent"},
            custom_agents={"existing_agent"}
        )
        
        # Configure mock to return same declaration (no change)
        existing_decl = self._create_test_declaration(
            "existing_agent", "agentmap.agents.ExistingAgent"
        )
        self.mock_declaration_registry.get_agent_declaration.return_value = existing_decl
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": set(),
            "protocols": set(),
            "missing": set()
        }
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=True
        )
        
        # Assert
        self.assertEqual(result, bundle)
        self.mock_graph_bundle_service.save_bundle.assert_not_called()

    def test_bundle_initialization_with_none_values(self):
        """Test bundle initialization when properties are None."""
        # Arrange - Create bundle with None values
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="test_hash"
        )
        bundle.agent_mappings = None
        bundle.custom_agents = None
        bundle.missing_declarations = None
        
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": set(),
            "protocols": set(),
            "missing": set()
        }
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=False
        )
        
        # Assert - Properties should be initialized
        self.assertEqual(result, bundle)
        self.assertIsInstance(bundle.agent_mappings, dict)
        self.assertIsInstance(bundle.custom_agents, set)
        self.assertIsInstance(bundle.missing_declarations, set)

    def test_last_updated_timestamp_set(self):
        """Test that last_updated timestamp is set during update."""
        # Arrange
        bundle = self._create_test_bundle(
            missing_declarations={"new_agent"}
        )
        # Bundle doesn't initially have last_updated attribute
        original_timestamp = getattr(bundle, 'last_updated', None)
        
        new_decl = self._create_test_declaration(
            "new_agent", "agentmap.agents.NewAgent"
        )
        self.mock_declaration_registry.get_agent_declaration.return_value = new_decl
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": set(),
            "protocols": set(),
            "missing": set()
        }
        
        # Act
        with patch('agentmap.services.graph.bundle_update_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.isoformat.return_value = "2023-01-01T10:00:00"
            mock_datetime.now.return_value = mock_now
            
            result = self.bundle_update_service.update_bundle_from_declarations(
                bundle, persist=False
            )
        
        # Assert
        self.assertEqual(result, bundle)
        self.assertEqual(bundle.last_updated, "2023-01-01T10:00:00")
        # Verify timestamp was set (original was None, new one is set)
        self.assertIsNone(original_timestamp)
        self.assertIsNotNone(bundle.last_updated)

    def test_get_update_summary_preview(self):
        """Test get_update_summary for preview functionality."""
        # Arrange
        bundle = self._create_test_bundle(
            graph_name="preview_graph",
            agent_mappings={"existing_agent": "old.path.Agent"},
            missing_declarations={"missing_agent"}
        )
        
        # Configure mock declarations
        missing_decl = self._create_test_declaration(
            "missing_agent", "agentmap.agents.MissingAgent"
        )
        updated_decl = self._create_test_declaration(
            "existing_agent", "new.path.Agent"
        )
        
        def get_declaration_side_effect(agent_type):
            if agent_type == "missing_agent":
                return missing_decl
            elif agent_type == "existing_agent":
                return updated_decl
            return None
        
        self.mock_declaration_registry.get_agent_declaration.side_effect = get_declaration_side_effect
        
        # Act
        summary = self.bundle_update_service.get_update_summary(bundle)
        
        # Assert
        self.assertEqual(summary["bundle_name"], "preview_graph")
        self.assertEqual(summary["current_mappings"], 1)
        self.assertIn("missing_agent", summary["missing_declarations"])
        self.assertIn("missing_agent", summary["would_resolve"])
        self.assertIn("existing_agent", summary["would_update"])

    def test_persistence_error_handling(self):
        """Test error handling when persistence fails."""
        # Arrange
        bundle = self._create_test_bundle(
            missing_declarations={"new_agent"}
        )
        
        new_decl = self._create_test_declaration(
            "new_agent", "agentmap.agents.NewAgent"
        )
        self.mock_declaration_registry.get_agent_declaration.return_value = new_decl
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": set(),
            "protocols": set(),
            "missing": set()
        }
        
        # Configure failed save
        save_result = Mock()
        save_result.success = False
        save_result.error = "Save failed"
        self.mock_graph_bundle_service.save_bundle.return_value = save_result
        
        # Mock Path operations
        with patch('pathlib.Path') as mock_path:
            mock_cache_dir = Mock()
            mock_path.return_value = mock_cache_dir
            mock_cache_dir.__truediv__ = Mock(return_value=Path("test_bundle.json"))
            
            # Act - Should not raise exception
            result = self.bundle_update_service.update_bundle_from_declarations(
                bundle, persist=True
            )
        
        # Assert - Update should still succeed, just persistence failed
        self.assertEqual(result, bundle)
        self.assertIn("new_agent", bundle.agent_mappings)

    def test_complex_update_scenario(self):
        """Test complex scenario with all types of updates."""
        # Arrange - Bundle with mixed scenarios
        bundle = self._create_test_bundle(
            agent_mappings={
                "unchanged_agent": "agentmap.agents.UnchangedAgent",
                "updated_agent": "old.path.UpdatedAgent",
                "removed_agent": "agentmap.agents.RemovedAgent"
            },
            custom_agents={"unchanged_agent", "updated_agent", "removed_agent"},
            missing_declarations={"new_agent"},
            required_services={"existing_service"}
        )
        
        # Configure mock declarations
        unchanged_decl = self._create_test_declaration(
            "unchanged_agent", "agentmap.agents.UnchangedAgent"
        )
        updated_decl = self._create_test_declaration(
            "updated_agent", "new.path.UpdatedAgent"
        )
        new_decl = self._create_test_declaration(
            "new_agent", "agentmap.agents.NewAgent"
        )
        
        def get_declaration_side_effect(agent_type):
            if agent_type == "unchanged_agent":
                return unchanged_decl
            elif agent_type == "updated_agent":
                return updated_decl
            elif agent_type == "removed_agent":
                return None  # Removed
            elif agent_type == "new_agent":
                return new_decl
            return None
        
        self.mock_declaration_registry.get_agent_declaration.side_effect = get_declaration_side_effect
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": {"logging_service", "new_service"},
            "protocols": set(),
            "missing": set()
        }
        self.mock_declaration_registry.calculate_load_order.return_value = [
            "existing_service", "logging_service", "new_service"
        ]
        
        # Act
        result = self.bundle_update_service.update_bundle_from_declarations(
            bundle, persist=False
        )
        
        # Assert all changes
        self.assertEqual(result, bundle)
        
        # Unchanged agent should remain
        self.assertIn("unchanged_agent", bundle.agent_mappings)
        self.assertEqual(bundle.agent_mappings["unchanged_agent"], "agentmap.agents.UnchangedAgent")
        
        # Updated agent should have new path
        self.assertIn("updated_agent", bundle.agent_mappings)
        self.assertEqual(bundle.agent_mappings["updated_agent"], "new.path.UpdatedAgent")
        
        # Removed agent should be missing
        self.assertNotIn("removed_agent", bundle.agent_mappings)
        self.assertNotIn("removed_agent", bundle.custom_agents)
        self.assertIn("removed_agent", bundle.missing_declarations)
        
        # New agent should be added
        self.assertIn("new_agent", bundle.agent_mappings)
        self.assertEqual(bundle.agent_mappings["new_agent"], "agentmap.agents.NewAgent")
        self.assertIn("new_agent", bundle.custom_agents)
        self.assertNotIn("new_agent", bundle.missing_declarations)
        
        # Services should be updated
        self.assertIn("existing_service", bundle.required_services)
        self.assertIn("logging_service", bundle.required_services)
        self.assertIn("new_service", bundle.required_services)


if __name__ == "__main__":
    unittest.main()
