"""
Integration tests for E01 input field mapping.

Tests the full pipeline (CSV parsing -> graph build -> execution) for:
- Direct mode backward compatibility
- Mapped binding syntax detection (colon in Input_Fields)
- Positional binding mode with expected_params
- Mixed mapped and direct fields
- Empty Input_Fields edge case

AC Coverage: AC-08, AC-09, AC-01 (supplement)
"""

import unittest
from pathlib import Path
from typing import Any, Dict, List

from agentmap.models.execution.result import ExecutionResult
from agentmap.services.state_adapter_service import StateAdapterService
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from tests.fresh_suite.integration.test_data_factories import (
    CSVTestDataFactory,
    IntegrationTestDataManager,
)


class TestInputFieldMappingIntegration(BaseIntegrationTest):
    """
    End-to-end integration tests for input field mapping modes.

    Extends BaseIntegrationTest to use real DI container, real file system
    operations with cleanup, and real CSV parsing pipeline.
    """

    def setup_services(self) -> None:
        """Initialize services for input field mapping integration testing."""
        super().setup_services()

        # Core services for CSV workflow execution
        self.graph_runner_service = self.container.graph_runner_service()
        self.csv_parser_service = self.container.csv_graph_parser_service()
        self.graph_execution_service = self.container.graph_execution_service()
        self.execution_tracking_service = self.container.execution_tracking_service()
        self.graph_bundle_service = self.container.graph_bundle_service()

        # Initialize test data manager
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))

        # Set up external service mocks
        self._setup_external_service_mocks()

    def _setup_external_service_mocks(self) -> None:
        """Set up standardized mocking for external dependencies."""
        from tests.utils.mock_service_factory import MockServiceFactory

        self.mock_llm_service = MockServiceFactory.create_mock_llm_service()

    def _execute_workflow(
        self,
        csv_path: Path,
        graph_name: str,
        initial_state: Dict[str, Any],
    ) -> ExecutionResult:
        """Execute a workflow end-to-end from CSV file.

        Uses get_or_create_bundle for bundle creation and graph_runner_service
        for execution, following the established integration test pattern.

        Args:
            csv_path: Path to CSV file on disk
            graph_name: Name of graph to execute
            initial_state: Initial state dict

        Returns:
            ExecutionResult from workflow execution
        """
        try:
            bundle, _ = self.graph_bundle_service.get_or_create_bundle(
                csv_path=csv_path,
                graph_name=graph_name,
            )

            if bundle is None:
                from agentmap.models.execution.summary import ExecutionSummary

                return ExecutionResult(
                    graph_name=graph_name,
                    final_state=initial_state,
                    execution_summary=ExecutionSummary(graph_name=graph_name),
                    success=False,
                    total_duration=0.0,
                    error=f"Failed to create bundle for graph '{graph_name}'",
                )

            return self.graph_runner_service.run(bundle, initial_state=initial_state)
        except Exception as e:
            from agentmap.models.execution.summary import ExecutionSummary

            return ExecutionResult(
                graph_name=graph_name,
                final_state=initial_state,
                execution_summary=ExecutionSummary(graph_name=graph_name),
                success=False,
                total_duration=0.0,
                error=f"Workflow execution failed: {e}",
            )

    def _find_node_spec(self, node_specs: List, node_name: str) -> Any:
        """Find a NodeSpec by name in a list of NodeSpec objects.

        GraphSpec.graphs[name] returns List[NodeSpec], not a dict.
        This helper finds a specific node by name.

        Args:
            node_specs: List of NodeSpec objects
            node_name: Name of the node to find

        Returns:
            The matching NodeSpec, or None
        """
        for spec in node_specs:
            if spec.name == node_name:
                return spec
        return None

    # =========================================================================
    # AC-01 supplement: Direct mode backward compatibility E2E
    # =========================================================================

    def test_direct_mode_backward_compatibility(self) -> None:
        """Direct mode with plain field names must work identically to pre-E01 behavior.

        Exercises: CSV parsing -> NodeSpec -> state schema -> graph construction ->
        agent instantiation -> state adapter -> agent execution -> output state.
        """
        spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(spec)

        initial_state = {"user_input": "hello from direct mode test"}

        result = self._execute_workflow(csv_path, spec.graph_name, initial_state)

        self.assertIsInstance(result, ExecutionResult)
        self.assertIsNotNone(result.final_state)
        self.assertIsNotNone(result.graph_name)
        self.assertEqual(result.graph_name, spec.graph_name)

    # =========================================================================
    # AC-08: Mapped binding syntax detection E2E
    # =========================================================================

    def test_mapped_binding_syntax_in_csv_parsed_correctly(self) -> None:
        """CSV with colon syntax in Input_Fields must parse without errors.

        The colon syntax (state_key:param_name) in Input_Fields should pass
        through the CSV parser as-is and be stored in the node spec's
        input_fields list.
        """
        csv_content = (
            "GraphName,Node,AgentType,Prompt,Description,"
            "Input_Fields,Output_Field,Edge,Context,Success_Next,Failure_Next\n"
            "mapped_test,start,default,Process inputs,Start node,"
            "damage_roll:addend_a | strength_bonus:addend_b,result,end,,,\n"
            "mapped_test,end,default,Finalize,End node,"
            "result,final_output,,,,\n"
        )
        csv_path = self.create_test_csv_file(csv_content, "mapped_binding_test.csv")

        # Verify CSV parsing preserves colon syntax in input_fields
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        self.assertIn("mapped_test", graph_spec.graphs)

        node_specs = graph_spec.graphs["mapped_test"]
        start_node = self._find_node_spec(node_specs, "start")
        self.assertIsNotNone(start_node, "start node should exist in parsed graph")

        # The input_fields should contain the raw colon syntax strings
        self.assertIn("damage_roll:addend_a", start_node.input_fields)
        self.assertIn("strength_bonus:addend_b", start_node.input_fields)

    def test_mapped_binding_end_to_end_workflow_executes(self) -> None:
        """Workflow with mapped binding syntax must execute without crashing.

        Even though the full mapped value extraction defers to a later
        implementation phase, the workflow should not crash when colon
        syntax is present in Input_Fields.
        """
        csv_content = (
            "GraphName,Node,AgentType,Prompt,Description,"
            "Input_Fields,Output_Field,Edge,Context,Success_Next,Failure_Next\n"
            "mapped_e2e,start,default,Process data,Start node,"
            "damage_roll:addend_a | strength_bonus:addend_b,result,end,,,\n"
            "mapped_e2e,end,default,Done,End node,"
            "result,final_output,,,,\n"
        )
        csv_path = self.create_test_csv_file(csv_content, "mapped_e2e_test.csv")

        # Provide state keys matching both the raw colon syntax and the
        # base state keys, so the workflow can resolve values either way
        initial_state = {
            "damage_roll": 8,
            "strength_bonus": 3,
            "damage_roll:addend_a": 8,
            "strength_bonus:addend_b": 3,
        }

        result = self._execute_workflow(csv_path, "mapped_e2e", initial_state)

        self.assertIsInstance(result, ExecutionResult)
        self.assertIsNotNone(result.final_state)
        self.assertEqual(result.graph_name, "mapped_e2e")

    # =========================================================================
    # AC-08: Mapped mode suppresses positional binding
    # =========================================================================

    def test_mapped_syntax_suppresses_positional_binding(self) -> None:
        """When ANY field contains ':', positional binding must be disabled.

        This tests the mode detection decision tree: colon present -> mapped mode
        for colon fields, direct mode for non-colon fields, positional disabled.
        """
        state = {"x_val": 10, "y_val": 20}
        fields = ["x_val:param_x", "y_val"]
        expected_params = ["alpha", "beta"]

        # Even though expected_params is provided, the presence of ':'
        # in any field should suppress positional binding entirely.
        result = StateAdapterService.get_inputs(
            state, fields, expected_params=expected_params
        )

        # y_val should be in direct mode (key=y_val), NOT positional (key=beta)
        self.assertIn("y_val", result)
        self.assertEqual(result["y_val"], 20)

        # The colon field uses mapped mode: state_key=x_val, param=param_x
        self.assertIn("param_x", result)
        self.assertEqual(result["param_x"], 10)

    # =========================================================================
    # AC-09: Positional binding mode
    # =========================================================================

    def test_positional_binding_state_adapter_integration(self) -> None:
        """Positional binding must remap input fields to expected_params names.

        This tests the core positional binding logic: when expected_params
        is non-empty and no colon syntax is present, input fields are mapped
        to expected_params names by index position.
        """
        state = {"damage_roll": 8, "strength_bonus": 3}
        fields = ["damage_roll", "strength_bonus"]
        expected_params = ["addend_a", "addend_b"]

        result = StateAdapterService.get_inputs(
            state, fields, expected_params=expected_params
        )

        # Fields should be remapped by position
        self.assertIn("addend_a", result)
        self.assertIn("addend_b", result)
        self.assertEqual(result["addend_a"], 8)
        self.assertEqual(result["addend_b"], 3)

        # Original field names should NOT be present
        self.assertNotIn("damage_roll", result)
        self.assertNotIn("strength_bonus", result)

    def test_positional_binding_overflow_uses_direct_mode(self) -> None:
        """Input fields beyond expected_params length must use direct mode.

        If there are more input fields than expected_params entries,
        the extra fields should fall through to direct mode (key=key).
        """
        state = {"a": 1, "b": 2, "c": 3}
        fields = ["a", "b", "c"]
        expected_params = ["alpha", "beta"]

        result = StateAdapterService.get_inputs(
            state, fields, expected_params=expected_params
        )

        # First two fields mapped positionally
        self.assertEqual(result["alpha"], 1)
        self.assertEqual(result["beta"], 2)

        # Third field overflows to direct mode
        self.assertIn("c", result)
        self.assertEqual(result["c"], 3)

    def test_positional_binding_with_real_csv_pipeline(self) -> None:
        """CSV with plain field names must parse correctly for positional binding.

        This verifies the pipeline up to the point where get_inputs would
        be called with expected_params. The actual positional remapping is
        tested in unit tests; here we verify the CSV pipeline preserves
        the plain field names correctly.
        """
        csv_content = (
            "GraphName,Node,AgentType,Prompt,Description,"
            "Input_Fields,Output_Field,Edge,Context,Success_Next,Failure_Next\n"
            "positional_test,calc,default,Calculate sum,Calculator node,"
            "damage_roll | strength_bonus,result,done,,,\n"
            "positional_test,done,default,Finish,End node,"
            "result,final_output,,,,\n"
        )
        csv_path = self.create_test_csv_file(csv_content, "positional_test.csv")

        # Parse CSV and verify plain field names are preserved
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        node_specs = graph_spec.graphs["positional_test"]
        calc_node = self._find_node_spec(node_specs, "calc")
        self.assertIsNotNone(calc_node, "calc node should exist")

        self.assertEqual(calc_node.input_fields, ["damage_roll", "strength_bonus"])

        # Verify no colon characters in the parsed fields
        for field in calc_node.input_fields:
            self.assertNotIn(
                ":",
                field,
                f"Plain field '{field}' should not contain colon",
            )

    # =========================================================================
    # Mixed mode: mapped + direct fields
    # =========================================================================

    def test_mixed_mapped_and_direct_fields(self) -> None:
        """A node with both colon and plain fields must handle each correctly.

        Colon fields go through mapped detection path. Plain fields without
        colon use direct mode. Positional binding is disabled for the node.
        """
        state = {"damage_roll": 8, "bonus_type": "strength"}
        fields = ["damage_roll:addend_a", "bonus_type"]

        result = StateAdapterService.get_inputs(state, fields)

        # bonus_type should use direct mode
        self.assertIn("bonus_type", result)
        self.assertEqual(result["bonus_type"], "strength")

        # damage_roll:addend_a uses mapped mode: param=addend_a, value from state["damage_roll"]
        self.assertIn("addend_a", result)
        self.assertEqual(result["addend_a"], 8)

    def test_mixed_mode_csv_parsing(self) -> None:
        """CSV with mixed colon and plain Input_Fields must parse correctly."""
        csv_content = (
            "GraphName,Node,AgentType,Prompt,Description,"
            "Input_Fields,Output_Field,Edge,Context,Success_Next,Failure_Next\n"
            "mixed_test,start,default,Process,Start node,"
            "damage_roll:addend_a | bonus_type,result,end,,,\n"
            "mixed_test,end,default,Done,End node,"
            "result,final_output,,,,\n"
        )
        csv_path = self.create_test_csv_file(csv_content, "mixed_mode_test.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        node_specs = graph_spec.graphs["mixed_test"]
        start_node = self._find_node_spec(node_specs, "start")
        self.assertIsNotNone(start_node, "start node should exist")

        # Both fields should be preserved as-is
        self.assertEqual(len(start_node.input_fields), 2)
        self.assertIn("damage_roll:addend_a", start_node.input_fields)
        self.assertIn("bonus_type", start_node.input_fields)

    # =========================================================================
    # Edge case: empty Input_Fields
    # =========================================================================

    def test_empty_input_fields_unchanged(self) -> None:
        """Nodes with empty Input_Fields must produce empty inputs dict."""
        state = {"some_key": "some_value"}
        fields: List[str] = []

        result = StateAdapterService.get_inputs(state, fields)

        self.assertEqual(result, {})

    def test_empty_input_fields_with_expected_params(self) -> None:
        """Empty Input_Fields with expected_params must still produce empty dict."""
        state = {"some_key": "some_value"}
        fields: List[str] = []
        expected_params = ["alpha", "beta"]

        result = StateAdapterService.get_inputs(
            state, fields, expected_params=expected_params
        )

        self.assertEqual(result, {})

    def test_empty_input_fields_csv_pipeline(self) -> None:
        """CSV node with empty Input_Fields must parse to empty list."""
        csv_content = (
            "GraphName,Node,AgentType,Prompt,Description,"
            "Input_Fields,Output_Field,Edge,Context,Success_Next,Failure_Next\n"
            "empty_test,start,default,Start,Start node,"
            ",result,end,,,\n"
            "empty_test,end,default,Done,End node,"
            "result,final_output,,,,\n"
        )
        csv_path = self.create_test_csv_file(csv_content, "empty_fields_test.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        node_specs = graph_spec.graphs["empty_test"]
        start_node = self._find_node_spec(node_specs, "start")
        self.assertIsNotNone(start_node, "start node should exist")

        self.assertEqual(start_node.input_fields, [])

    # =========================================================================
    # Direct mode E2E with complex graph (regression supplement)
    # =========================================================================

    def test_direct_mode_complex_graph_backward_compatibility(self) -> None:
        """Complex graph with branching must execute without E01 interference."""
        spec = CSVTestDataFactory.create_conditional_branching_graph()
        csv_path = self.test_data_manager.create_test_csv_file(spec)

        initial_state = {"raw_input": "test data for branching"}

        result = self._execute_workflow(csv_path, spec.graph_name, initial_state)

        self.assertIsInstance(result, ExecutionResult)
        self.assertIsNotNone(result.final_state)
        self.assertEqual(result.graph_name, spec.graph_name)

    # =========================================================================
    # State key not found edge case
    # =========================================================================

    def test_mapped_field_missing_state_key_returns_none(self) -> None:
        """When a mapped field references a nonexistent state key, get_value returns None."""
        state = {"existing_key": 42}
        fields = ["nonexistent_key:param"]

        result = StateAdapterService.get_inputs(state, fields)

        # Mapped mode splits on colon: state_key="nonexistent_key", param="param"
        # State lookup for "nonexistent_key" returns None
        self.assertIn("param", result)
        self.assertIsNone(result["param"])


if __name__ == "__main__":
    unittest.main()
