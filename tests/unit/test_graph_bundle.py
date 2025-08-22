"""
Unit tests for GraphBundle model.

Tests the metadata-only storage functionality and backwards compatibility
of the GraphBundle model according to TDD principles.
"""

import pytest
import warnings
from unittest.mock import Mock, patch
from typing import Dict, Set

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node



class TestGraphBundleMetadataOnlyFormat:
    """Test suite for new metadata-only GraphBundle format."""

    def test_create_metadata_factory_method(self):
        """Test creating GraphBundle with create_metadata factory method."""
        # Arrange
        test_nodes = {
            "node1": Node(name="node1", context={"instance": Mock()}, agent_type="test_agent"),
            "node2": Node(name="node2", agent_type="another_agent")
        }
        
        # Act
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes=test_nodes,
            required_agents={"test_agent", "another_agent"},
            required_services={"service1", "service2"},
            function_mappings={"func1": "implementation1"},
            csv_hash="abc123hash",
            version_hash="v1.0.0"
        )
        
        # Assert
        assert bundle.graph_name == "test_graph"
        assert bundle.required_agents == {"test_agent", "another_agent"}
        assert bundle.required_services == {"service1", "service2"}
        assert bundle.function_mappings == {"func1": "implementation1"}
        assert bundle.csv_hash == "abc123hash"
        assert bundle.version_hash == "v1.0.0"
        
        # Verify agent instances are stripped
        assert "instance" not in bundle.nodes["node1"].context
        
        # Verify it's detected as metadata-only format
        assert bundle.is_metadata_only
        assert not bundle.is_legacy_format
        
        # Verify new fields have defaults
        assert bundle.entry_point is None
        assert bundle.service_load_order == []
        assert bundle.agent_mappings == {}
        assert bundle.builtin_agents == set()
        assert bundle.custom_agents == set()
        assert bundle.graph_structure == {}
        assert bundle.protocol_mappings == {}
        assert bundle.validation_metadata == {}
        assert bundle.bundle_format == "metadata-v1"
        assert bundle.created_at is not None

    def test_direct_constructor_with_new_fields(self):
        """Test creating GraphBundle directly with new field parameters."""
        # Arrange
        test_nodes = {"node1": Node(name="node1", agent_type="test")}
        
        # Act
        bundle = GraphBundle(
            graph_name="direct_graph",
            nodes=test_nodes,
            required_agents={"test_agent"},
            required_services={"test_service"},
            function_mappings={"func": "impl"},
            csv_hash="direct_hash"
        )
        
        # Assert
        assert bundle.graph_name == "direct_graph"
        assert bundle.nodes == test_nodes
        assert bundle.required_agents == {"test_agent"}
        assert not bundle.is_legacy_format

    def test_partial_new_fields_with_defaults(self):
        """Test that partial new fields get sensible defaults."""
        # Act
        bundle = GraphBundle(graph_name="partial_graph")
        
        # Assert
        assert bundle.graph_name == "partial_graph"
        assert bundle.nodes == {}
        assert bundle.required_agents == set()
        assert bundle.required_services == set()
        assert bundle.function_mappings == {}
        assert bundle.csv_hash == "unknown_hash"
        
        # Verify new fields get defaults
        assert bundle.entry_point is None
        assert bundle.service_load_order == []
        assert bundle.agent_mappings == {}
        assert bundle.builtin_agents == set()
        assert bundle.custom_agents == set()
        assert bundle.graph_structure == {}
        assert bundle.protocol_mappings == {}
        assert bundle.validation_metadata == {}
        assert bundle.bundle_format == "metadata-v1"
        assert bundle.created_at is not None
    
    def test_create_metadata_with_enhanced_fields(self):
        """Test creating GraphBundle with all enhanced metadata fields."""
        # Arrange
        test_nodes = {
            "start": Node(name="start", agent_type="LLMAgent"),
            "process": Node(name="process", agent_type="Default")
        }
        test_nodes["start"].add_edge("default", "process")
        
        # Act
        bundle = GraphBundle.create_metadata(
            graph_name="enhanced_graph",
            entry_point="start",
            nodes=test_nodes,
            required_agents={"LLMAgent", "Default"},
            required_services={"LoggingService", "LLMService"},
            service_load_order=["LoggingService", "LLMService"],
            function_mappings={"process_data": "module.function"},
            csv_hash="enhanced_hash",
            version_hash="v2.0.0",
            # Phase 1: Agent mappings
            agent_mappings={"LLMAgent": "agentmap.agents.llm_agent.LLMAgent"},
            builtin_agents={"LLMAgent", "Default"},
            custom_agents=set(),
            # Phase 2: Optimization metadata
            graph_structure={"node_count": 2, "is_dag": True},
            protocol_mappings={"LLMServiceProtocol": "LLMService"},
            # Phase 3: Validation metadata
            validation_metadata={"node_hashes": {"start": "abc123"}}
        )
        
        # Assert core fields
        assert bundle.graph_name == "enhanced_graph"
        assert bundle.entry_point == "start"
        assert len(bundle.nodes) == 2
        assert "start" in bundle.nodes
        assert "process" in bundle.nodes
        
        # Assert Phase 1 fields
        assert bundle.service_load_order == ["LoggingService", "LLMService"]
        assert bundle.agent_mappings == {"LLMAgent": "agentmap.agents.llm_agent.LLMAgent"}
        assert bundle.builtin_agents == {"LLMAgent", "Default"}
        assert bundle.custom_agents == set()
        
        # Assert Phase 2 fields
        assert bundle.graph_structure == {"node_count": 2, "is_dag": True}
        assert bundle.protocol_mappings == {"LLMServiceProtocol": "LLMService"}
        
        # Assert Phase 3 fields
        assert bundle.validation_metadata == {"node_hashes": {"start": "abc123"}}
        
        # Assert format metadata
        assert bundle.bundle_format == "metadata-v1"
        assert bundle.created_at is not None
        
        # Verify it's still detected as metadata-only format
        assert bundle.is_metadata_only
        assert not bundle.is_legacy_format


class TestGraphBundleCoreFunctionality:
    """Test core functionality that works across both formats."""

    def test_prepare_nodes_for_storage_removes_agent_instances(self):
        """Test that prepare_nodes_for_storage removes agent instances from context."""
        # Arrange
        mock_agent = Mock()
        test_node = Node(
            name="test_node",
            context={
                "instance": mock_agent,
                "other_data": "should_remain",
                "config": {"key": "value"}
            },
            agent_type="test_agent"
        )
        nodes = {"test_node": test_node}
        
        # Act
        prepared_nodes = GraphBundle.prepare_nodes_for_storage(nodes)
        
        # Assert
        assert "instance" not in prepared_nodes["test_node"].context
        assert prepared_nodes["test_node"].context["other_data"] == "should_remain"
        assert prepared_nodes["test_node"].context["config"] == {"key": "value"}
        
        # Verify original node is unchanged (deep copy)
        assert "instance" in test_node.context

    def test_prepare_nodes_for_storage_handles_none_context(self):
        """Test prepare_nodes_for_storage handles nodes with None context."""
        # Arrange
        test_node = Node(name="test_node", context=None, agent_type="test_agent")
        nodes = {"test_node": test_node}
        
        # Act
        prepared_nodes = GraphBundle.prepare_nodes_for_storage(nodes)
        
        # Assert
        assert prepared_nodes["test_node"].context is None
        assert prepared_nodes["test_node"].name == "test_node"

    def test_get_service_load_order_with_services(self):
        """Test get_service_load_order returns services in sorted order."""
        # Arrange
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services={"zebra_service", "alpha_service", "beta_service"},
            function_mappings={},
            csv_hash="hash123"
        )
        
        # Act
        load_order = bundle.get_service_load_order()
        
        # Assert
        assert isinstance(load_order, list)
        assert set(load_order) == {"zebra_service", "alpha_service", "beta_service"}
        assert load_order == sorted(load_order)
    
    def test_get_service_load_order_with_precalculated_order(self):
        """Test get_service_load_order uses pre-calculated order when available."""
        # Arrange
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services={"service_c", "service_a", "service_b"},
            service_load_order=["service_c", "service_a", "service_b"],  # Dependency order (different from alphabetical)
            function_mappings={},
            csv_hash="hash123"
        )
        
        # Act
        load_order = bundle.get_service_load_order()
        
        # Assert - should use pre-calculated order, not sorted order
        assert load_order == ["service_c", "service_a", "service_b"]
        assert load_order != sorted(list(bundle.required_services))  # sorted would be ["service_a", "service_b", "service_c"]

    def test_get_service_load_order_legacy_format(self):
        """Test get_service_load_order works with legacy format."""
        # Arrange
        bundle = GraphBundle(graph=Mock())  # Legacy format
        
        # Act
        load_order = bundle.get_service_load_order()
        
        # Assert
        assert load_order == []  # Should return empty list for legacy format

    def test_empty_constructor_defaults(self):
        """Test creating completely empty GraphBundle gets safe defaults."""
        # Act
        bundle = GraphBundle()
        
        # Assert
        assert bundle.graph_name == "empty_graph"
        assert bundle.nodes == {}
        assert bundle.required_agents == set()
        assert bundle.required_services == set()
        assert bundle.function_mappings == {}
        assert bundle.csv_hash == "empty_hash"


class TestGraphBundleProperties:
    """Test GraphBundle property methods."""

    def test_is_metadata_only_property(self):
        """Test is_metadata_only property correctly identifies format."""
        # Metadata-only format
        metadata_bundle = GraphBundle.create_metadata(
            graph_name="test",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="hash"
        )
        assert metadata_bundle.is_metadata_only
        
        # Legacy format
        legacy_bundle = GraphBundle(graph=Mock())
        assert not legacy_bundle.is_metadata_only

    def test_is_legacy_format_property(self):
        """Test is_legacy_format property correctly identifies format."""
        # Legacy format with graph
        legacy_bundle = GraphBundle(graph=Mock())
        assert legacy_bundle.is_legacy_format
        
        # Legacy format with node_registry
        legacy_bundle2 = GraphBundle(node_instances={})
        assert legacy_bundle2.is_legacy_format
        
        # Metadata-only format
        metadata_bundle = GraphBundle.create_metadata(
            graph_name="test",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="hash"
        )
        assert not metadata_bundle.is_legacy_format


class TestGraphBundleMigration:
    """Test migration utilities and backwards compatibility."""

    def test_create_from_legacy_with_metadata(self):
        """Test create_from_legacy factory method with additional metadata."""
        # Arrange
        mock_graph = Mock()
        mock_graph.nodes = {
            "node1": Node(name="node1", context={"instance": Mock()})
        }
        
        # Act
        bundle = GraphBundle.create_from_legacy(
            graph=mock_graph,
            node_registry={},
            version_hash="v1.0",
            graph_name="migrated_graph",
            required_agents={"test_agent"},
            required_services={"test_service"},
            function_mappings={"func": "impl"},
            csv_hash="migration_hash"
        )
        
        # Assert
        assert bundle.graph == mock_graph  # Legacy field preserved
        assert bundle.graph_name == "migrated_graph"  # New metadata used
        assert bundle.required_agents == {"test_agent"}
        assert bundle.csv_hash == "migration_hash"


@pytest.mark.integration
class TestGraphBundleIntegration:
    """Integration tests for GraphBundle with serialization and other components."""

    def test_metadata_bundle_serialization_compatibility(self):
        """Test that metadata-only GraphBundle can be serialized."""
        import pickle
        
        # Arrange
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={"node1": Node(name="node1", context={"data": "test"})},
            required_agents={"test_agent"},
            required_services={"test_service"},
            function_mappings={"func": "impl"},
            csv_hash="test_hash"
        )
        
        # Act & Assert
        serialized = pickle.dumps(bundle)
        deserialized = pickle.loads(serialized)
        
        assert deserialized.graph_name == "test_graph"
        assert "node1" in deserialized.nodes
        assert deserialized.is_metadata_only
