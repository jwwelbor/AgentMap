"""
Parallel Bundle System Integration Tests.

Integration tests that use the actual runtime API to validate parallel edge handling.
Tests run through the same code path as the CLI, ensuring real-world usage patterns.

Test Coverage:
- Bundle creation with parallel edges via runtime API
- Serialization/deserialization of List[str] edges
- Parallel metadata validation through runtime workflows
- Legacy bundle loading (backward compatibility)
"""

import unittest
import json
from pathlib import Path
from typing import Dict, Any

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.models.graph import Graph
from agentmap.models.node import Node

# Import runtime API - this is what the CLI uses
from agentmap import runtime_api


class TestParallelBundleSystemIntegration(BaseIntegrationTest):
    """Integration tests for bundle system with parallel edges."""

    def setup_services(self):
        """Initialize services for bundle system tests."""
        super().setup_services()

        # Initialize runtime API with test configuration
        runtime_api.ensure_initialized(config_file=str(self.test_config_path))

        # CRITICAL: Use the SAME container that runtime_api uses to avoid cache misses
        # The runtime_api.inspect_graph() uses RuntimeManager.get_container()
        # We must use the same container to access the same GraphRegistryService cache
        from agentmap.runtime.init_ops import get_container
        runtime_container = get_container()
        self.graph_bundle_service = runtime_container.graph_bundle_service()

        self.assert_service_created(self.graph_bundle_service, "GraphBundleService")

    # =============================================================================
    # Bundle Creation with Parallel Edges
    # =============================================================================

    def test_create_bundle_with_parallel_edges(self):
        """Test creating bundle from CSV with parallel edges via runtime API."""
        print("\n=== Testing Bundle Creation with Parallel Edges ===")

        csv_content = """GraphName,Node,AgentType,Edge,Output_Field
ParallelBundle,Start,input,ProcessA|ProcessB|ProcessC,input_data
ParallelBundle,ProcessA,echo,End,result_a
ParallelBundle,ProcessB,echo,End,result_b
ParallelBundle,ProcessC,echo,End,result_c
ParallelBundle,End,output,,"""

        csv_path = self._create_csv(csv_content, "parallel_bundle.csv")

        # Use runtime API to inspect the graph (validates structure via parsing)
        # Note: validate_workflow doesn't yet support parallel edge syntax (pipe-separated)
        # Pass CSV file path directly to avoid path resolution issues
        inspect_result = runtime_api.inspect_graph(
            graph_name="ParallelBundle",
            csv_file=str(csv_path),
            config_file=str(self.test_config_path)
        )

        self.assertTrue(inspect_result["success"], "Inspection should succeed")
        self.assertEqual(inspect_result["outputs"]["resolved_name"], "ParallelBundle")
        self.assertEqual(inspect_result["outputs"]["total_nodes"], 5)

        # Get the bundle to verify parallel edges structure
        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="ParallelBundle",
            config_path=str(self.test_config_path)
        )

        # Verify bundle uses new metadata-only format
        self.assertIsNotNone(bundle.nodes, "Bundle should have nodes in metadata format")
        self.assertEqual(bundle.graph_name, "ParallelBundle")

        # Verify parallel edges in nodes
        start_node = bundle.nodes.get("Start")
        self.assertIsNotNone(start_node, "Start node should exist")
        self.assertTrue(start_node.is_parallel_edge("default"), "Start node should have parallel edges")

        print("✅ Bundle created with parallel edges via runtime API")

    def test_bundle_serialization_with_parallel(self):
        """Test bundle caching and metadata preservation with parallel edges."""
        print("\n=== Testing Bundle Caching with Parallel Edges ===")

        csv_content = """GraphName,Node,AgentType,Success_Next,Failure_Next
SerializationTest,Start,validator,SuccessA|SuccessB,ErrorA|ErrorB
SerializationTest,SuccessA,echo,End,
SerializationTest,SuccessB,echo,End,
SerializationTest,ErrorA,echo,End,
SerializationTest,ErrorB,echo,End,
SerializationTest,End,output,,"""

        csv_path = self._create_csv(csv_content, "serialization_test.csv")

        # Use runtime API to inspect the graph - this creates and caches the bundle
        inspect_result = runtime_api.inspect_graph(
            graph_name="SerializationTest",
            csv_file=str(csv_path),
            config_file=str(self.test_config_path)
        )
        self.assertTrue(inspect_result["success"], "Inspection should succeed")

        # Get bundle - should be loaded from cache since inspect_graph already created it
        bundle, loaded_from_cache = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="SerializationTest",
            config_path=str(self.test_config_path)
        )

        # Verify bundle was loaded from cache (inspect_graph already created it)
        self.assertTrue(loaded_from_cache, "Bundle should be loaded from cache after inspect_graph")
        self.assertIsNotNone(bundle.nodes, "Bundle should have nodes")

        # Verify parallel edge structure in Start node
        start_node = bundle.nodes.get("Start")
        self.assertIsNotNone(start_node, "Start node should exist")

        # Check success edges are parallel
        self.assertTrue(start_node.is_parallel_edge("success"), "Success edges should be parallel")
        success_targets = start_node.get_edge_targets("success")
        self.assertEqual(set(success_targets), {"SuccessA", "SuccessB"}, "Success targets should match")

        # Check failure edges are parallel
        self.assertTrue(start_node.is_parallel_edge("failure"), "Failure edges should be parallel")
        failure_targets = start_node.get_edge_targets("failure")
        self.assertEqual(set(failure_targets), {"ErrorA", "ErrorB"}, "Failure targets should match")

        # Get bundle again - should be loaded from cache
        bundle2, created2 = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="SerializationTest",
            config_path=str(self.test_config_path)
        )

        # Verify bundle was loaded from cache
        self.assertTrue(created2, "Bundle should be loaded from cache on second call")
        self.assertEqual(bundle2.graph_name, bundle.graph_name, "Cached bundle should match")

        # Verify parallel edges preserved in cached bundle
        cached_start_node = bundle2.nodes.get("Start")
        self.assertTrue(cached_start_node.is_parallel_edge("success"), "Cached success edges should be parallel")
        self.assertTrue(cached_start_node.is_parallel_edge("failure"), "Cached failure edges should be parallel")

        print("✅ Bundle caching preserves parallel edges")

    def test_bundle_deserialization_with_parallel(self):
        """Test bundle deserialization restores parallel edges."""
        print("\n=== Testing Bundle Deserialization with Parallel ===")

        csv_content = """GraphName,Node,AgentType,Edge
DeserializationTest,Start,input,ProcessA|ProcessB|ProcessC
DeserializationTest,ProcessA,echo,End
DeserializationTest,ProcessB,echo,End
DeserializationTest,ProcessC,echo,End
DeserializationTest,End,output,"""

        csv_path = self._create_csv(csv_content, "deserialization_test.csv")

        # Use runtime API to inspect the graph (validates structure without strict validation)
        inspect_result = runtime_api.inspect_graph(
            graph_name="DeserializationTest",
            csv_file=str(csv_path),
            config_file=str(self.test_config_path)
        )
        self.assertTrue(inspect_result["success"], "Inspection should succeed")

        # Get original bundle
        original_bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="DeserializationTest",
            config_path=str(self.test_config_path)
        )

        # Serialize
        bundle_path = Path(self.temp_dir) / "bundles" / "deserialization_test.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph_bundle_service.save_bundle(original_bundle, str(bundle_path))

        # Deserialize
        loaded_bundle = self.graph_bundle_service.load_bundle(str(bundle_path))

        # Verify loaded bundle
        self.assertIsNotNone(loaded_bundle, "Bundle should load successfully")
        self.assertEqual(loaded_bundle.graph_name, "DeserializationTest")

        # Verify parallel edges are restored using new metadata format
        self.assertIsNotNone(loaded_bundle.nodes, "Loaded bundle should have nodes")
        start_node = loaded_bundle.nodes.get("Start")
        self.assertIsNotNone(start_node, "Start node should exist")
        self.assertTrue(start_node.is_parallel_edge("default"), "Start node should have parallel edges")

        targets = start_node.get_edge_targets("default")
        self.assertEqual(set(targets), {"ProcessA", "ProcessB", "ProcessC"})

        print("✅ Bundle deserialization restores parallel edges")

    # =============================================================================
    # Parallel Metadata
    # =============================================================================

    def test_parallel_metadata_detection(self):
        """Test that bundle metadata includes parallel routing information via runtime API."""
        print("\n=== Testing Parallel Metadata Detection ===")

        csv_content = """GraphName,Node,AgentType,Edge
MetadataTest,Start,input,FanOut
MetadataTest,FanOut,distributor,ProcessA|ProcessB|ProcessC
MetadataTest,ProcessA,echo,End
MetadataTest,ProcessB,echo,End
MetadataTest,ProcessC,echo,End
MetadataTest,End,output,"""

        csv_path = self._create_csv(csv_content, "metadata_test.csv")

        # Use runtime API to inspect the graph
        inspect_result = runtime_api.inspect_graph(
            graph_name="MetadataTest",
            csv_file=str(csv_path),
            config_file=str(self.test_config_path)
        )

        self.assertTrue(inspect_result["success"], "Inspection should succeed")
        self.assertEqual(inspect_result["outputs"]["total_nodes"], 6)

        # Get bundle to verify parallel edges in detail
        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="MetadataTest",
            config_path=str(self.test_config_path)
        )

        # Verify bundle has parallel metadata using new format
        self.assertIsNotNone(bundle.nodes, "Bundle should have nodes")

        # Check if any node has parallel edges
        has_parallel = any(
            node.is_parallel_edge("default") or
            node.is_parallel_edge("success") or
            node.is_parallel_edge("failure")
            for node in bundle.nodes.values()
        )

        self.assertTrue(has_parallel, "Graph should have parallel edges")

        print("✅ Parallel metadata detected via runtime API")

    def test_max_parallelism_calculation(self):
        """Test calculation of maximum parallelism in bundle via runtime API."""
        print("\n=== Testing Max Parallelism Calculation ===")

        csv_content = """GraphName,Node,AgentType,Edge
MaxParallelism,Start,input,FanOut1
MaxParallelism,FanOut1,distributor,A1|A2
MaxParallelism,A1,echo,FanOut2
MaxParallelism,A2,echo,FanOut2
MaxParallelism,FanOut2,distributor,B1|B2|B3|B4
MaxParallelism,B1,echo,End
MaxParallelism,B2,echo,End
MaxParallelism,B3,echo,End
MaxParallelism,B4,echo,End
MaxParallelism,End,output,"""

        csv_path = self._create_csv(csv_content, "max_parallelism.csv")

        # Use runtime API to inspect the workflow
        # Note: validate_workflow doesn't yet support parallel edge syntax (pipe-separated)
        inspect_result = runtime_api.inspect_graph(
            graph_name="MaxParallelism",
            csv_file=str(csv_path),
            config_file=str(self.test_config_path)
        )
        self.assertTrue(inspect_result["success"], "Inspection should succeed")
        self.assertEqual(inspect_result["outputs"]["total_nodes"], 10)

        # Get bundle to analyze parallelism
        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="MaxParallelism",
            config_path=str(self.test_config_path)
        )

        # Verify bundle uses new metadata format
        self.assertIsNotNone(bundle.nodes, "Bundle should have nodes")

        # Find max parallelism (FanOut2 has 4 parallel targets)
        max_parallel = 0
        for node in bundle.nodes.values():
            for edge_type in ["default", "success", "failure"]:
                targets = node.get_edge_targets(edge_type)
                if len(targets) > max_parallel:
                    max_parallel = len(targets)

        self.assertEqual(max_parallel, 4, "Max parallelism should be 4")

        print("✅ Max parallelism calculated correctly via runtime API")

    # =============================================================================
    # Backward Compatibility
    # =============================================================================

    def test_legacy_bundle_loading(self):
        """Test that bundles without parallel edges still load correctly via runtime API."""
        print("\n=== Testing Legacy Bundle Loading ===")

        csv_content = """GraphName,Node,AgentType,Edge
LegacyBundle,Start,input,Process1
LegacyBundle,Process1,echo,Process2
LegacyBundle,Process2,echo,End
LegacyBundle,End,output,"""

        csv_path = self._create_csv(csv_content, "legacy_bundle.csv")

        # Use runtime API to inspect the legacy workflow
        # Legacy bundles don't have parallel edges, so we can use inspect
        inspect_result = runtime_api.inspect_graph(
            graph_name="LegacyBundle",
            csv_file=str(csv_path),
            config_file=str(self.test_config_path)
        )
        self.assertTrue(inspect_result["success"], "Inspection should succeed")

        # Get bundle
        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="LegacyBundle",
            config_path=str(self.test_config_path)
        )

        # Serialize and reload
        bundle_path = Path(self.temp_dir) / "bundles" / "legacy_bundle.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)

        self.graph_bundle_service.save_bundle(bundle, str(bundle_path))
        loaded_bundle = self.graph_bundle_service.load_bundle(str(bundle_path))

        # Verify bundle uses new metadata format
        self.assertIsNotNone(loaded_bundle.nodes, "Loaded bundle should have nodes")

        # Verify all edges are single targets (strings or single-element lists)
        for node in loaded_bundle.nodes.values():
            for edge_type in ["default", "success", "failure"]:
                if node.edges.get(edge_type):
                    edge_value = node.edges[edge_type]
                    # Legacy bundles should have string edges or not be parallel
                    if isinstance(edge_value, list):
                        self.assertEqual(len(edge_value), 1,
                                       "Legacy bundles should not have multi-target lists")

        print("✅ Legacy bundle loaded correctly via runtime API")

    def test_mixed_bundle_compatibility(self):
        """Test bundle with mix of parallel and sequential edges via runtime API."""
        print("\n=== Testing Mixed Bundle Compatibility ===")

        csv_content = """GraphName,Node,AgentType,Edge
MixedBundle,Start,input,Sequential1
MixedBundle,Sequential1,echo,ParallelFanOut
MixedBundle,ParallelFanOut,distributor,ProcessA|ProcessB|ProcessC
MixedBundle,ProcessA,echo,Sequential2
MixedBundle,ProcessB,echo,Sequential2
MixedBundle,ProcessC,echo,Sequential2
MixedBundle,Sequential2,echo,End
MixedBundle,End,output,"""

        csv_path = self._create_csv(csv_content, "mixed_bundle.csv")

        # Use runtime API to inspect the mixed workflow
        # Note: validate_workflow doesn't yet support parallel edge syntax (pipe-separated)
        inspect_result = runtime_api.inspect_graph(
            graph_name="MixedBundle",
            csv_file=str(csv_path),
            config_file=str(self.test_config_path)
        )
        self.assertTrue(inspect_result["success"], "Inspection should succeed")
        self.assertEqual(inspect_result["outputs"]["total_nodes"], 8)

        # Get bundle for detailed edge testing
        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="MixedBundle",
            config_path=str(self.test_config_path)
        )

        # Serialize and reload
        bundle_path = Path(self.temp_dir) / "bundles" / "mixed_bundle.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)

        self.graph_bundle_service.save_bundle(bundle, str(bundle_path))
        loaded_bundle = self.graph_bundle_service.load_bundle(str(bundle_path))

        # Verify bundle uses new metadata format
        self.assertIsNotNone(loaded_bundle.nodes, "Loaded bundle should have nodes")

        # Sequential1 should have single target
        sequential1 = loaded_bundle.nodes.get("Sequential1")
        self.assertIsNotNone(sequential1, "Sequential1 node should exist")
        self.assertFalse(sequential1.is_parallel_edge("default"), "Sequential1 should not have parallel edges")

        # ParallelFanOut should have parallel targets
        parallel_fanout = loaded_bundle.nodes.get("ParallelFanOut")
        self.assertIsNotNone(parallel_fanout, "ParallelFanOut node should exist")
        self.assertTrue(parallel_fanout.is_parallel_edge("default"), "ParallelFanOut should have parallel edges")

        print("✅ Mixed bundle compatibility verified via runtime API")

    # =============================================================================
    # Helper Methods
    # =============================================================================

    def _create_csv(self, content: str, filename: str) -> Path:
        """
        Create a test CSV file in the CSV repository path.

        This ensures the runtime API can find the CSV using standard resolution.
        """
        # Use the CSV repository path from the test configuration
        csv_repo_path = Path(self.temp_dir) / "storage" / "csv"
        csv_repo_path.mkdir(parents=True, exist_ok=True)

        csv_path = csv_repo_path / filename
        csv_path.write_text(content, encoding='utf-8')
        return csv_path


if __name__ == '__main__':
    unittest.main()
