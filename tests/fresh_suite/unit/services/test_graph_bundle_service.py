"""
Unit tests for GraphBundleService enhancements.

Tests the new metadata-only bundle creation functionality and backwards compatibility.
Follows TDD principles - tests written first to drive implementation.
"""

import hashlib
import json
import pickle
import tempfile
import warnings
from pathlib import Path
from typing import Dict, Set
from unittest.mock import Mock, MagicMock, patch, call

import pytest

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.models.graph_spec import GraphSpec, NodeSpec
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.types import StorageResult, WriteMode


class TestGraphBundleServiceMetadataEnhancements:
    """Test suite for metadata-only bundle creation functionality."""

    @pytest.fixture
    def mock_logging_service(self):
        """Create mock logging service."""
        mock_logging = Mock(spec=LoggingService)
        mock_logger = Mock()
        mock_logging.get_class_logger.return_value = mock_logger
        return mock_logging

    @pytest.fixture
    def mock_protocol_analyzer(self):
        """Create mock protocol requirements analyzer."""
        return Mock()

    @pytest.fixture
    def mock_di_analyzer(self):
        """Create mock DI container analyzer."""
        return Mock()

    @pytest.fixture
    def mock_agent_factory(self):
        """Create mock agent factory service."""
        return Mock()

    @pytest.fixture
    def mock_json_storage_service(self):
        """Create mock JSON storage service."""
        mock_service = Mock()
        # Mock successful write operation
        mock_service.write.return_value = StorageResult(
            success=True,
            operation="write",
            collection="test.json",
            document_id=None,
            error=None
        )
        # Mock successful read operation
        mock_service.read.return_value = {
            "format": "metadata",
            "graph_name": "test_graph",
            "nodes": {},
            "required_agents": [],
            "required_services": [],
            "function_mappings": {},
            "csv_hash": "test_hash",
            "version_hash": None
        }
        return mock_service

    @pytest.fixture
    def enhanced_service(self, mock_logging_service, 
                        mock_protocol_analyzer, mock_di_analyzer, 
                        mock_agent_factory, mock_json_storage_service):
        """Create enhanced GraphBundleService with all dependencies."""
        return GraphBundleService(
            logging_service=mock_logging_service,
            protocol_requirements_analyzer=mock_protocol_analyzer,
            di_container_analyzer=mock_di_analyzer,
            agent_factory_service=mock_agent_factory,
            json_storage_service=mock_json_storage_service
        )

    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV content for testing."""
        return """GraphName,Node,AgentType,Prompt,Description,Context,Input_Fields,Output_Field
test_graph,node1,LLMAgent,Test prompt,Test node,,input1,output1
test_graph,node2,ValidationAgent,Validate prompt,Validation node,,output1,final_output
"""

    @pytest.fixture
    def sample_nodes(self):
        """Sample nodes for testing."""
        return {
            "node1": Node(
                name="node1",
                agent_type="LLMAgent",
                prompt="Test prompt",
                description="Test node",
                inputs=["input1"],
                output="output1"
            ),
            "node2": Node(
                name="node2", 
                agent_type="ValidationAgent",
                prompt="Validate prompt",
                description="Validation node",
                inputs=["output1"],
                output="final_output"
            )
        }
    
    @pytest.fixture
    def sample_graph_spec(self):
        """Sample GraphSpec for testing."""
        spec = GraphSpec(file_path="test.csv", total_rows=2)
        spec.add_node_spec(NodeSpec(
            name="node1",
            graph_name="test_graph",
            agent_type="LLMAgent",
            prompt="Test prompt",
            description="Test node",
            input_fields=["input1"],
            output_field="output1"
        ))
        spec.add_node_spec(NodeSpec(
            name="node2",
            graph_name="test_graph",
            agent_type="ValidationAgent",
            prompt="Validate prompt",
            description="Validation node",
            input_fields=["output1"],
            output_field="final_output"
        ))
        return spec

    def test_save_bundle_with_json_storage_service(self, enhanced_service, mock_json_storage_service):
        """Test saving bundle using JSON storage service."""
        # Arrange
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={"node1": Node(name="node1", agent_type="TestAgent")},
            required_agents={"TestAgent"},
            required_services={"test_service"},
            function_mappings={},
            csv_hash="test_hash"
        )
        path = Path("test_bundle.json")
        
        # Act
        enhanced_service.save_bundle(bundle, path)
        
        # Assert
        mock_json_storage_service.write.assert_called_once()
        call_args = mock_json_storage_service.write.call_args
        assert call_args.kwargs['collection'] == str(path)
        assert call_args.kwargs['mode'] == WriteMode.WRITE
        assert isinstance(call_args.kwargs['data'], dict)
        assert call_args.kwargs['data']['format'] == 'metadata'
        assert call_args.kwargs['data']['graph_name'] == 'test_graph'

    def test_load_bundle_with_json_storage_service(self, enhanced_service, mock_json_storage_service):
        """Test loading bundle using JSON storage service."""
        # Arrange
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_bundle.json"
            # Create an empty file so it exists
            path.touch()
            
            mock_json_storage_service.read.return_value = {
                "format": "metadata",
                "graph_name": "test_graph",
                "nodes": {
                    "node1": {
                        "name": "node1",
                        "agent_type": "TestAgent",
                        "context": {},
                        "inputs": [],
                        "output": None,
                        "prompt": None,
                        "description": None,
                        "edges": {}
                    }
                },
                "required_agents": ["TestAgent"],
                "required_services": ["test_service"],
                "function_mappings": {},
                "csv_hash": "test_hash",
                "version_hash": None
            }
            
            # Act
            result = enhanced_service.load_bundle(path)
            
            # Assert
            mock_json_storage_service.read.assert_called_once_with(collection=str(path))
            assert isinstance(result, GraphBundle)
            assert result.graph_name == "test_graph"
            assert result.is_metadata_only is True
            assert "node1" in result.nodes

    def test_save_bundle_without_json_storage_service_raises_error(self, mock_logging_service):
        """Test that saving metadata bundle without JSON storage service raises an error."""
        # Arrange
        service = GraphBundleService(
            logging_service=mock_logging_service,
            json_storage_service=None  # No JSON storage service
        )
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="test_hash"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_bundle.json"
            
            # Act & Assert - should raise ValueError
            with pytest.raises(ValueError, match="json_storage_service is required"):
                service.save_bundle(bundle, path)

    def test_load_bundle_without_json_storage_service_raises_error(self, mock_logging_service):
        """Test that loading JSON bundle without JSON storage service raises an error."""
        # Arrange
        service = GraphBundleService(
            logging_service=mock_logging_service,
            json_storage_service=None  # No JSON storage service
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_bundle.json"
            
            # Create a test bundle file
            data = {
                "format": "metadata",
                "graph_name": "test_graph",
                "nodes": {},
                "required_agents": [],
                "required_services": [],
                "function_mappings": {},
                "csv_hash": "test_hash",
                "version_hash": None
            }
            with open(path, 'w') as f:
                json.dump(data, f)
            
            # Act
            result = service.load_bundle(path)
            
            # Assert - should return None (error logged) because json_storage_service is required
            assert result is None

    def test_save_legacy_bundle_pickle_format(self, enhanced_service):
        """Test saving legacy bundle in pickle format."""
        # Arrange
        graph = {"name": "test_graph"}
        node_registry = {"node1": {"name": "node1"}}
        bundle = GraphBundle(
            graph=graph,
            node_instances=node_registry,
            version_hash="test_hash"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_bundle.pkl"
            
            # Act
            enhanced_service.save_bundle(bundle, path)
            
            # Assert - file should be created as pickle
            assert path.exists()
            with open(path, 'rb') as f:
                data = pickle.load(f)
            assert data['graph'] == graph
            assert data['node_registry'] == node_registry

    def test_load_legacy_bundle_pickle_format(self, enhanced_service):
        """Test loading legacy bundle from pickle format."""
        # Arrange
        graph = {"name": "test_graph"}
        node_registry = {"node1": {"name": "node1"}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_bundle.pkl"
            
            # Create a pickle bundle file
            data = {
                "graph": graph,
                "node_registry": node_registry,
                "version_hash": "test_hash"
            }
            with open(path, 'wb') as f:
                pickle.dump(data, f)
            
            # Act
            result = enhanced_service.load_bundle(path)
            
            # Assert
            assert isinstance(result, GraphBundle)
            assert result.graph == graph
            assert result.node_instances == node_registry
            assert result.is_metadata_only is False

    def test_create_metadata_bundle_from_spec_success(self, enhanced_service, sample_graph_spec,
                                                      mock_protocol_analyzer, mock_di_analyzer):
        """Test successful creation of metadata-only bundle from GraphSpec."""
        # Arrange
        graph_name = "test_graph"
        csv_hash = "test_hash_value"
        
        mock_protocol_analyzer.analyze_graph_requirements.return_value = {
            "required_agents": {"LLMAgent", "ValidationAgent"},
            "required_services": {"llm_service", "storage_service"}
        }
        mock_di_analyzer.build_full_dependency_tree.return_value = {
            "llm_service", "storage_service", "logging_service", "config_service"
        }
        
        # Act
        result = enhanced_service.create_metadata_bundle_from_spec(
            sample_graph_spec, graph_name, csv_hash
        )
        
        # Assert
        assert isinstance(result, GraphBundle)
        assert result.is_metadata_only is True
        assert result.graph_name == graph_name
        assert result.csv_hash == csv_hash
        assert result.required_agents == {"LLMAgent", "ValidationAgent"}
        assert result.required_services == {
            "llm_service", "storage_service", "logging_service", "config_service"
        }
        assert len(result.nodes) == 2
        assert "node1" in result.nodes
        assert "node2" in result.nodes
        
        # Verify service calls
        mock_protocol_analyzer.analyze_graph_requirements.assert_called_once()
        mock_di_analyzer.build_full_dependency_tree.assert_called_once_with({
            "llm_service", "storage_service"
        })

    def test_create_metadata_bundle_from_nodes_success(self, enhanced_service, sample_nodes,
                                                       mock_protocol_analyzer, mock_di_analyzer):
        """Test successful creation of metadata-only bundle from nodes dict."""
        # Arrange
        graph_name = "test_graph"
        csv_hash = "test_hash_value"
        
        mock_protocol_analyzer.analyze_graph_requirements.return_value = {
            "required_agents": {"LLMAgent", "ValidationAgent"},
            "required_services": {"llm_service"}
        }
        mock_di_analyzer.build_full_dependency_tree.return_value = {"llm_service", "logging_service"}
        
        # Act
        result = enhanced_service.create_metadata_bundle_from_nodes(
            sample_nodes, graph_name, csv_hash
        )
        
        # Assert
        assert isinstance(result, GraphBundle)
        assert result.is_metadata_only is True
        assert result.graph_name == graph_name
        assert result.csv_hash == csv_hash
        assert result.required_agents == {"LLMAgent", "ValidationAgent"}
        assert result.required_services == {"llm_service", "logging_service"}

    def test_create_metadata_bundle_from_spec_no_graphs(self, enhanced_service, mock_protocol_analyzer):
        """Test error handling when GraphSpec has no graphs."""
        # Arrange
        empty_spec = GraphSpec(file_path="test.csv", total_rows=0)
        
        # Act & Assert
        with pytest.raises(ValueError, match="No graphs found in GraphSpec"):
            enhanced_service.create_metadata_bundle_from_spec(empty_spec, "test_graph")

    def test_create_metadata_bundle_from_spec_without_dependencies(self, mock_logging_service):
        """Test that creating metadata bundle without dependencies raises error."""
        # Arrange
        service = GraphBundleService(
            logging_service=mock_logging_service,
            protocol_requirements_analyzer=None,  # Missing dependency
            agent_factory_service=None  # Missing dependency
        )
        spec = GraphSpec(file_path="test.csv", total_rows=1)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Enhanced dependencies required"):
            service.create_metadata_bundle_from_spec(spec, "test_graph")

    def test_create_metadata_bundle_from_nodes_without_dependencies(self, mock_logging_service):
        """Test that creating metadata bundle from nodes without dependencies raises error."""
        # Arrange
        service = GraphBundleService(
            logging_service=mock_logging_service,
            protocol_requirements_analyzer=None,  # Missing dependency
            agent_factory_service=None  # Missing dependency
        )
        nodes = {"node1": Node(name="node1")}
        
        # Act & Assert
        with pytest.raises(ValueError, match="Enhanced dependencies required"):
            service.create_metadata_bundle_from_nodes(nodes, "test_graph")

    def test_verify_csv_metadata_bundle(self, enhanced_service, sample_csv_content):
        """Test CSV verification for metadata bundles."""
        # Arrange
        csv_hash = hashlib.md5(sample_csv_content.encode()).hexdigest()
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash=csv_hash
        )
        
        # Act
        result = enhanced_service.verify_csv(bundle, sample_csv_content)
        
        # Assert
        assert result is True

    def test_verify_csv_legacy_bundle(self, enhanced_service, sample_csv_content):
        """Test CSV verification for legacy bundles."""
        # Arrange
        version_hash = hashlib.md5(sample_csv_content.encode()).hexdigest()
        bundle = GraphBundle(
            graph={},
            node_instances={},
            version_hash=version_hash
        )
        
        # Act
        result = enhanced_service.verify_csv(bundle, sample_csv_content)
        
        # Assert
        assert result is True

    def test_validate_bundle_valid(self, enhanced_service, sample_csv_content):
        """Test bundle validation with matching hash."""
        # Arrange
        csv_hash = hashlib.md5(sample_csv_content.encode()).hexdigest()
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash=csv_hash
        )
        
        # Act
        result = enhanced_service.validate_bundle(bundle, sample_csv_content)
        
        # Assert
        assert result is True

    def test_validate_bundle_invalid(self, enhanced_service, sample_csv_content):
        """Test bundle validation with non-matching hash."""
        # Arrange
        bundle = GraphBundle.create_metadata(
            graph_name="test_graph",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="old_hash"
        )
        
        # Act
        result = enhanced_service.validate_bundle(bundle, sample_csv_content)
        
        # Assert
        assert result is False

    def test_legacy_create_bundle_still_works(self, enhanced_service):
        """Test that legacy create_bundle method still works but shows deprecation warning."""
        # Arrange
        simple_graph = {"name": "test_graph"}
        node_registry = {"node1": {"name": "node1"}}
        csv_content = "test,csv,content"
        
        # Act & Assert
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            result = enhanced_service.create_bundle(
                graph=simple_graph,
                node_registry=node_registry,
                csv_content=csv_content
            )
            
            # Should issue deprecation warnings (one from create_bundle, one from GraphBundle)
            assert len(w) >= 1
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert any("create_bundle is deprecated" in str(warning.message) for warning in deprecation_warnings)
        
        # Should still create bundle
        assert isinstance(result, GraphBundle)
        assert result.graph == simple_graph
        assert result.node_instances == node_registry

    def test_backwards_compatibility_constructor(self, mock_logging_service):
        """Test that old constructor still works."""
        # Arrange & Act
        service = GraphBundleService(logger=mock_logging_service.get_class_logger(GraphBundleService))
        
        # Assert
        assert service is not None
        assert hasattr(service, 'create_bundle')
        assert hasattr(service, 'save_bundle')
        assert hasattr(service, 'load_bundle')

    def test_dependency_injection_in_enhanced_constructor(self, mock_logging_service,
                                                         mock_protocol_analyzer,
                                                         mock_di_analyzer, mock_agent_factory,
                                                         mock_json_storage_service):
        """Test that enhanced constructor properly injects all dependencies."""
        # Act
        service = GraphBundleService(
            logging_service=mock_logging_service,
            protocol_requirements_analyzer=mock_protocol_analyzer,
            di_container_analyzer=mock_di_analyzer,
            agent_factory_service=mock_agent_factory,
            json_storage_service=mock_json_storage_service
        )
        
        # Assert
        assert service.protocol_requirements_analyzer == mock_protocol_analyzer
        assert service.di_container_analyzer == mock_di_analyzer
        assert service.agent_factory_service == mock_agent_factory
        assert service.json_storage_service == mock_json_storage_service
        assert hasattr(service, 'logger')


class TestGraphBundleServiceErrorHandling:
    """Test suite for error handling in GraphBundleService."""

    @pytest.fixture
    def enhanced_service(self):
        """Create service with mock dependencies for error testing."""
        mock_logging = Mock()
        mock_logger = Mock()
        mock_logging.get_class_logger.return_value = mock_logger
        
        # Create mock JSON storage service
        mock_json_storage = Mock()
        mock_json_storage.write.return_value = StorageResult(
            success=False,
            operation="write",
            collection="test.json",
            document_id=None,
            error="Write failed"
        )
        
        return GraphBundleService(
            logging_service=mock_logging,
            protocol_requirements_analyzer=Mock(),
            di_container_analyzer=Mock(),
            agent_factory_service=Mock(),
            json_storage_service=mock_json_storage
        )

    def test_save_bundle_json_service_error(self, enhanced_service):
        """Test error handling when JSON storage service fails."""
        # Arrange
        bundle = GraphBundle.create_metadata(
            graph_name="test",
            nodes={},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="test"
        )
        
        # Act & Assert
        with pytest.raises(IOError, match="Failed to save GraphBundle"):
            enhanced_service.save_bundle(bundle, Path("test.json"))

    def test_load_bundle_nonexistent_file(self, enhanced_service):
        """Test loading bundle from nonexistent file."""
        # Act
        result = enhanced_service.load_bundle(Path("nonexistent.json"))
        
        # Assert
        assert result is None

    def test_load_bundle_json_service_returns_none(self, enhanced_service):
        """Test loading bundle when JSON service returns None."""
        # Arrange
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.json"
            path.touch()  # Create the file
            enhanced_service.json_storage_service.read.return_value = None
            
            # Act
            result = enhanced_service.load_bundle(path)
            
            # Assert
            assert result is None

    def test_validate_bundle_with_none_bundle(self, enhanced_service):
        """Test bundle validation with None bundle."""
        # Act
        result = enhanced_service.validate_bundle(None, "csv_content")
        
        # Assert
        assert result is False
