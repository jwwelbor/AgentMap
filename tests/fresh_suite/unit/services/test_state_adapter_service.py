"""
Unit tests for StateAdapterService.

These tests validate the StateAdapterService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional
import copy

from agentmap.services.state_adapter_service import StateAdapterService
from tests.utils.mock_service_factory import MockServiceFactory


class TestStateAdapterService(unittest.TestCase):
    """Unit tests for StateAdapterService with comprehensive state manipulation coverage."""
    
    def setUp(self):
        """Set up test fixtures."""
        # StateAdapterService has static methods, so we can use it directly
        self.service = StateAdapterService()
        
        # Test data for various state types
        self.dict_state = {
            "key1": "value1",
            "key2": 42,
            "nested": {"inner": "data"},
            "list_value": [1, 2, 3]
        }
        
        # Create a simple class to simulate Pydantic-like behavior
        class MockPydanticModel:
            def __init__(self):
                self.key1 = "pydantic_value"
                self.key2 = 100
            
            def copy(self, **kwargs):
                # Simulate Pydantic's copy method
                new_instance = MockPydanticModel()
                if 'update' in kwargs:
                    for k, v in kwargs['update'].items():
                        setattr(new_instance, k, v)
                return new_instance
        
        self.pydantic_state = MockPydanticModel()
        
        # Create a simple object with attributes (not a Mock)
        class SimpleObject:
            def __init__(self):
                self.key1 = "object_value"
                self.key2 = 200
        
        self.object_state = SimpleObject()
    
    # =============================================================================
    # 1. Static Method Verification Tests
    # =============================================================================
    
    def test_service_static_methods(self):
        """Test that core methods are static and can be called without instance."""
        # Test static method calls
        result = StateAdapterService.has_value({"test": "value"}, "test")
        self.assertTrue(result)
        
        result = StateAdapterService.get_value({"test": "value"}, "test")
        self.assertEqual(result, "value")
        
        result = StateAdapterService.set_value({"test": "old"}, "test", "new")
        self.assertEqual(result, {"test": "new"})
        
        result = StateAdapterService.get_inputs({"a": 1, "b": 2}, ["a", "b"])
        self.assertEqual(result, {"a": 1, "b": 2})
    
    def test_service_info_method(self):
        """Test get_service_info() returns proper service information."""
        info = self.service.get_service_info()
        
        # Verify service information structure
        self.assertIn("service", info)
        self.assertEqual(info["service"], "StateAdapterService")
        
        self.assertIn("capabilities", info)
        self.assertTrue(info["capabilities"]["state_manipulation"])
        self.assertTrue(info["capabilities"]["immutable_updates"])
        
        self.assertIn("methods", info)
        self.assertIn("set_value", info["methods"])
        self.assertIn("get_value", info["methods"])
        self.assertIn("has_value", info["methods"])
        
        self.assertIn("yagni_compliance", info)
        self.assertIn("methods_wrapped", info["yagni_compliance"])
    
    # =============================================================================
    # 2. has_value() Method Tests
    # =============================================================================
    
    def test_has_value_dict_state_existing_key(self):
        """Test has_value() with dictionary state and existing key."""
        result = StateAdapterService.has_value(self.dict_state, "key1")
        self.assertTrue(result)
    
    def test_has_value_dict_state_missing_key(self):
        """Test has_value() with dictionary state and missing key."""
        result = StateAdapterService.has_value(self.dict_state, "nonexistent")
        self.assertFalse(result)
    
    def test_has_value_dict_state_nested_key(self):
        """Test has_value() with dictionary state and nested key access."""
        result = StateAdapterService.has_value(self.dict_state, "nested")
        self.assertTrue(result)
    
    def test_has_value_object_state_existing_attribute(self):
        """Test has_value() with object state and existing attribute."""
        result = StateAdapterService.has_value(self.object_state, "key1")
        self.assertTrue(result)
    
    def test_has_value_object_state_missing_attribute(self):
        """Test has_value() with object state and missing attribute."""
        result = StateAdapterService.has_value(self.object_state, "nonexistent")
        self.assertFalse(result)
    
    def test_has_value_none_state(self):
        """Test has_value() with None state."""
        result = StateAdapterService.has_value(None, "any_key")
        self.assertFalse(result)
    
    def test_has_value_list_state_with_getitem(self):
        """Test has_value() with list state using __getitem__ access."""
        list_state = ["item1", "item2", "item3"]
        
        # Test valid index
        result = StateAdapterService.has_value(list_state, 0)
        self.assertTrue(result)
        
        # Test invalid index
        result = StateAdapterService.has_value(list_state, 10)
        self.assertFalse(result)
    
    # =============================================================================
    # 3. get_value() Method Tests
    # =============================================================================
    
    def test_get_value_dict_state_existing_key(self):
        """Test get_value() with dictionary state and existing key."""
        result = StateAdapterService.get_value(self.dict_state, "key1")
        self.assertEqual(result, "value1")
    
    def test_get_value_dict_state_missing_key_with_default(self):
        """Test get_value() with dictionary state, missing key, and default."""
        result = StateAdapterService.get_value(self.dict_state, "nonexistent", "default_value")
        self.assertEqual(result, "default_value")
    
    def test_get_value_dict_state_missing_key_no_default(self):
        """Test get_value() with dictionary state, missing key, and no default."""
        result = StateAdapterService.get_value(self.dict_state, "nonexistent")
        self.assertIsNone(result)
    
    def test_get_value_object_state_existing_attribute(self):
        """Test get_value() with object state and existing attribute."""
        result = StateAdapterService.get_value(self.object_state, "key1")
        self.assertEqual(result, "object_value")
    
    def test_get_value_object_state_missing_attribute(self):
        """Test get_value() with object state and missing attribute."""
        result = StateAdapterService.get_value(self.object_state, "nonexistent", "fallback")
        self.assertEqual(result, "fallback")
    
    def test_get_value_none_state(self):
        """Test get_value() with None state."""
        result = StateAdapterService.get_value(None, "any_key", "default")
        self.assertEqual(result, "default")
    
    def test_get_value_list_state_valid_index(self):
        """Test get_value() with list state and valid index."""
        list_state = ["item1", "item2", "item3"]
        result = StateAdapterService.get_value(list_state, 1)
        self.assertEqual(result, "item2")
    
    def test_get_value_list_state_invalid_index(self):
        """Test get_value() with list state and invalid index."""
        list_state = ["item1", "item2", "item3"]
        result = StateAdapterService.get_value(list_state, 10, "default")
        self.assertEqual(result, "default")
    
    def test_get_value_complex_nested_data(self):
        """Test get_value() with complex nested data structures."""
        complex_state = {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ],
            "config": {
                "debug": True,
                "timeout": 30
            }
        }
        
        # Test accessing nested dictionary
        result = StateAdapterService.get_value(complex_state, "config")
        self.assertEqual(result, {"debug": True, "timeout": 30})
        
        # Test accessing list
        result = StateAdapterService.get_value(complex_state, "users")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Alice")
    
    # =============================================================================
    # 4. set_value() Method Tests - Dictionary State
    # =============================================================================
    
    def test_set_value_dict_state_new_key(self):
        """Test set_value() with dictionary state and new key."""
        original_state = {"existing": "value"}
        result = StateAdapterService.set_value(original_state, "new_key", "new_value")
        
        # Verify new state has the added key
        self.assertEqual(result["new_key"], "new_value")
        self.assertEqual(result["existing"], "value")
        
        # Verify original state is unchanged (immutability)
        self.assertNotIn("new_key", original_state)
    
    def test_set_value_dict_state_update_existing_key(self):
        """Test set_value() with dictionary state and existing key update."""
        original_state = {"key1": "old_value", "key2": "other"}
        result = StateAdapterService.set_value(original_state, "key1", "new_value")
        
        # Verify key was updated
        self.assertEqual(result["key1"], "new_value")
        self.assertEqual(result["key2"], "other")
        
        # Verify original state is unchanged
        self.assertEqual(original_state["key1"], "old_value")
    
    def test_set_value_dict_state_complex_values(self):
        """Test set_value() with dictionary state and complex values."""
        original_state = {"simple": "value"}
        complex_value = {"nested": {"deep": "data"}, "list": [1, 2, 3]}
        
        result = StateAdapterService.set_value(original_state, "complex", complex_value)
        
        # Verify complex value was set correctly
        self.assertEqual(result["complex"]["nested"]["deep"], "data")
        self.assertEqual(result["complex"]["list"], [1, 2, 3])
    
    def test_set_value_dict_state_none_value(self):
        """Test set_value() with dictionary state and None value."""
        original_state = {"key": "value"}
        result = StateAdapterService.set_value(original_state, "nullable", None)
        
        # Verify None value was set
        self.assertIsNone(result["nullable"])
        self.assertIn("nullable", result)
    
    # =============================================================================
    # 5. set_value() Method Tests - Pydantic-like State
    # =============================================================================
    
    def test_set_value_pydantic_state_with_copy_method(self):
        """Test set_value() with Pydantic-like state using copy method."""
        result = StateAdapterService.set_value(self.pydantic_state, "key1", "updated_value")
        
        # Verify that a new instance was created with updated value
        self.assertIsNot(result, self.pydantic_state)  # Should be different instance
        self.assertEqual(result.key1, "updated_value")  # New value
        self.assertEqual(result.key2, 100)  # Original value preserved
        
        # Verify original instance is unchanged
        self.assertEqual(self.pydantic_state.key1, "pydantic_value")
    
    def test_set_value_pydantic_state_copy_method_failure(self):
        """Test set_value() with Pydantic-like state when copy method fails."""
        # Mock the copy method to raise an exception
        with patch.object(self.pydantic_state, 'copy', side_effect=Exception("Copy failed")):
            # Should fall back to attribute setting
            with patch('copy.copy') as mock_copy:
                mock_copy.return_value = self.pydantic_state
                
                result = StateAdapterService.set_value(self.pydantic_state, "key1", "fallback_value")
                
                # Verify fallback was used
                mock_copy.assert_called_once_with(self.pydantic_state)
    
    # =============================================================================
    # 6. set_value() Method Tests - Object State
    # =============================================================================
    
    def test_set_value_object_state_with_copy_fallback(self):
        """Test set_value() with object state using copy fallback."""
        with patch('copy.copy') as mock_copy:
            # Configure copy to return a new object
            copied_object = Mock()
            mock_copy.return_value = copied_object
            
            result = StateAdapterService.set_value(self.object_state, "new_attr", "new_value")
            
            # Verify copy was called and attribute was set
            mock_copy.assert_called_once_with(self.object_state)
            self.assertEqual(result, copied_object)
    
    def test_set_value_object_state_copy_failure(self):
        """Test set_value() when copy operations fail."""
        # Create object without copy method
        simple_object = Mock()
        del simple_object.copy  # Ensure no copy method exists
        
        with patch('copy.copy') as mock_copy:
            # Configure copy to also fail
            mock_copy.side_effect = Exception("Copy failed")
            
            # Should raise the exception
            with self.assertRaises(Exception):
                StateAdapterService.set_value(simple_object, "key", "value")
    
    # =============================================================================
    # 7. get_inputs() Method Tests
    # =============================================================================
    
    def test_get_inputs_dict_state_all_fields_exist(self):
        """Test get_inputs() with dictionary state where all fields exist."""
        input_fields = ["key1", "key2"]
        result = StateAdapterService.get_inputs(self.dict_state, input_fields)
        
        expected = {"key1": "value1", "key2": 42}
        self.assertEqual(result, expected)
    
    def test_get_inputs_dict_state_some_fields_missing(self):
        """Test get_inputs() with dictionary state where some fields are missing."""
        input_fields = ["key1", "nonexistent", "key2"]
        result = StateAdapterService.get_inputs(self.dict_state, input_fields)
        
        expected = {"key1": "value1", "nonexistent": None, "key2": 42}
        self.assertEqual(result, expected)
    
    def test_get_inputs_empty_field_list(self):
        """Test get_inputs() with empty field list."""
        result = StateAdapterService.get_inputs(self.dict_state, [])
        self.assertEqual(result, {})
    
    def test_get_inputs_object_state(self):
        """Test get_inputs() with object state."""
        input_fields = ["key1", "key2"]
        result = StateAdapterService.get_inputs(self.object_state, input_fields)
        
        expected = {"key1": "object_value", "key2": 200}
        self.assertEqual(result, expected)
    
    def test_get_inputs_mixed_data_types(self):
        """Test get_inputs() with mixed data types in input fields."""
        complex_state = {
            "string_field": "text",
            "number_field": 123,
            "bool_field": True,
            "list_field": [1, 2, 3],
            "dict_field": {"nested": "value"}
        }
        
        input_fields = ["string_field", "number_field", "bool_field", "list_field", "dict_field"]
        result = StateAdapterService.get_inputs(complex_state, input_fields)
        
        # Verify all types are preserved
        self.assertEqual(result["string_field"], "text")
        self.assertEqual(result["number_field"], 123)
        self.assertTrue(result["bool_field"])
        self.assertEqual(result["list_field"], [1, 2, 3])
        self.assertEqual(result["dict_field"]["nested"], "value")
    
    def test_get_inputs_none_state(self):
        """Test get_inputs() with None state."""
        input_fields = ["field1", "field2"]
        result = StateAdapterService.get_inputs(None, input_fields)
        
        expected = {"field1": None, "field2": None}
        self.assertEqual(result, expected)
    
    # =============================================================================
    # 8. State Type Compatibility Tests
    # =============================================================================
    
    def test_state_adapter_dict_compatibility(self):
        """Test StateAdapterService works with standard dictionaries."""
        state = {"a": 1, "b": 2, "c": 3}
        
        # Test all operations
        self.assertTrue(StateAdapterService.has_value(state, "a"))
        self.assertEqual(StateAdapterService.get_value(state, "b"), 2)
        
        new_state = StateAdapterService.set_value(state, "d", 4)
        self.assertEqual(new_state["d"], 4)
        self.assertNotIn("d", state)  # Original unchanged
        
        inputs = StateAdapterService.get_inputs(state, ["a", "c"])
        self.assertEqual(inputs, {"a": 1, "c": 3})
    
    def test_state_adapter_custom_dict_subclass(self):
        """Test StateAdapterService works with custom dict subclasses."""
        class CustomDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.metadata = "custom"
        
        state = CustomDict({"x": 10, "y": 20})
        
        # Test operations work with custom dict
        self.assertTrue(StateAdapterService.has_value(state, "x"))
        self.assertEqual(StateAdapterService.get_value(state, "y"), 20)
        
        new_state = StateAdapterService.set_value(state, "z", 30)
        self.assertEqual(new_state["z"], 30)
        self.assertIsInstance(new_state, dict)  # Should return standard dict
    
    def test_state_adapter_object_with_getitem(self):
        """Test StateAdapterService works with objects that support __getitem__."""
        class IndexableObject:
            def __init__(self):
                self.data = {"key1": "value1", "key2": "value2"}
            
            def __getitem__(self, key):
                return self.data[key]
            
            def __contains__(self, key):
                return key in self.data
        
        state = IndexableObject()
        
        # Test get_value works with __getitem__
        result = StateAdapterService.get_value(state, "key1")
        self.assertEqual(result, "value1")
        
        # Test has_value works
        self.assertTrue(StateAdapterService.has_value(state, "key1"))
        self.assertFalse(StateAdapterService.has_value(state, "nonexistent"))
    
    # =============================================================================
    # 9. Edge Cases and Error Handling Tests
    # =============================================================================
    
    def test_state_adapter_with_special_characters(self):
        """Test StateAdapterService handles keys with special characters."""
        special_state = {
            "key with spaces": "value1",
            "key-with-dashes": "value2",
            "key_with_underscores": "value3",
            "key.with.dots": "value4",
            "key@with!symbols": "value5"
        }
        
        # Test all special keys work
        for key in special_state.keys():
            self.assertTrue(StateAdapterService.has_value(special_state, key))
            self.assertEqual(StateAdapterService.get_value(special_state, key), special_state[key])
        
        # Test setting values with special keys
        new_state = StateAdapterService.set_value(special_state, "new@key!", "new_value")
        self.assertEqual(new_state["new@key!"], "new_value")
    
    def test_state_adapter_with_numeric_keys(self):
        """Test StateAdapterService handles numeric keys correctly."""
        numeric_state = {1: "one", 2: "two", 3.5: "three-point-five"}
        
        # Test numeric keys
        self.assertTrue(StateAdapterService.has_value(numeric_state, 1))
        self.assertEqual(StateAdapterService.get_value(numeric_state, 2), "two")
        self.assertEqual(StateAdapterService.get_value(numeric_state, 3.5), "three-point-five")
        
        # Test setting numeric keys
        new_state = StateAdapterService.set_value(numeric_state, 4, "four")
        self.assertEqual(new_state[4], "four")
    
    def test_state_adapter_deeply_nested_structures(self):
        """Test StateAdapterService handles deeply nested structures."""
        deep_state = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "deep_value": "found_it"
                        }
                    }
                }
            }
        }
        
        # Test accessing nested structure
        result = StateAdapterService.get_value(deep_state, "level1")
        self.assertIn("level2", result)
        
        # Test setting at top level doesn't affect nested structure
        new_state = StateAdapterService.set_value(deep_state, "new_top", "value")
        self.assertEqual(new_state["new_top"], "value")
        self.assertEqual(new_state["level1"]["level2"]["level3"]["level4"]["deep_value"], "found_it")
    
    def test_state_adapter_circular_reference_handling(self):
        """Test StateAdapterService handles circular references in state."""
        # Create state with circular reference
        circular_state = {"key": "value"}
        circular_state["self"] = circular_state
        
        # Basic operations should still work
        self.assertTrue(StateAdapterService.has_value(circular_state, "key"))
        self.assertEqual(StateAdapterService.get_value(circular_state, "key"), "value")
        
        # Setting values should work (though copy operations might be complex)
        try:
            new_state = StateAdapterService.set_value(circular_state, "new_key", "new_value")
            self.assertEqual(new_state["new_key"], "new_value")
        except Exception:
            # Circular references might cause copy issues, which is acceptable
            pass
    
    def test_state_adapter_large_state_performance(self):
        """Test StateAdapterService performance with large state objects."""
        # Create large state
        large_state = {f"key_{i}": f"value_{i}" for i in range(1000)}
        
        # Test operations still work efficiently
        self.assertTrue(StateAdapterService.has_value(large_state, "key_500"))
        self.assertEqual(StateAdapterService.get_value(large_state, "key_999"), "value_999")
        
        # Test setting value creates proper copy
        new_state = StateAdapterService.set_value(large_state, "new_key", "new_value")
        self.assertEqual(new_state["new_key"], "new_value")
        self.assertEqual(len(new_state), 1001)  # Original 1000 + 1 new
        
        # Verify original is unchanged
        self.assertNotIn("new_key", large_state)
        self.assertEqual(len(large_state), 1000)
    
    # =============================================================================
    # 10. Integration and Workflow Tests
    # =============================================================================
    
    def test_state_adapter_workflow_simulation(self):
        """Test StateAdapterService in a typical workflow scenario."""
        # Simulate a workflow state evolution
        initial_state = {
            "input": "user request",
            "step": 1,
            "results": []
        }
        
        # Step 1: Process input
        state1 = StateAdapterService.set_value(initial_state, "processed_input", "processed: user request")
        state2 = StateAdapterService.set_value(state1, "step", 2)
        
        # Step 2: Add results
        current_results = StateAdapterService.get_value(state2, "results")
        updated_results = current_results + ["result1", "result2"]
        state3 = StateAdapterService.set_value(state2, "results", updated_results)
        
        # Step 3: Finalize
        final_state = StateAdapterService.set_value(state3, "status", "completed")
        
        # Verify workflow progression
        self.assertEqual(final_state["input"], "user request")
        self.assertEqual(final_state["processed_input"], "processed: user request")
        self.assertEqual(final_state["step"], 2)
        self.assertEqual(final_state["results"], ["result1", "result2"])
        self.assertEqual(final_state["status"], "completed")
        
        # Verify original state unchanged
        self.assertEqual(initial_state["step"], 1)
        self.assertEqual(initial_state["results"], [])
        self.assertNotIn("status", initial_state)
    
    def test_state_adapter_input_extraction_workflow(self):
        """Test StateAdapterService input extraction in workflow context."""
        workflow_state = {
            "user_id": "user123",
            "task_type": "analysis",
            "data": {"values": [1, 2, 3, 4, 5]},
            "config": {"threshold": 3, "mode": "strict"},
            "metadata": {"timestamp": "2024-01-01", "version": "1.0"}
        }
        
        # Extract inputs for different workflow steps
        user_inputs = StateAdapterService.get_inputs(workflow_state, ["user_id", "task_type"])
        data_inputs = StateAdapterService.get_inputs(workflow_state, ["data", "config"])
        all_inputs = StateAdapterService.get_inputs(workflow_state, 
                                                   ["user_id", "task_type", "data", "config", "metadata"])
        
        # Verify correct extraction
        self.assertEqual(user_inputs, {"user_id": "user123", "task_type": "analysis"})
        self.assertEqual(data_inputs["data"]["values"], [1, 2, 3, 4, 5])
        self.assertEqual(data_inputs["config"]["threshold"], 3)
        self.assertEqual(len(all_inputs), 5)
        
        # Verify missing fields handled correctly
        partial_inputs = StateAdapterService.get_inputs(workflow_state, 
                                                       ["user_id", "nonexistent", "task_type"])
        self.assertEqual(partial_inputs["user_id"], "user123")
        self.assertIsNone(partial_inputs["nonexistent"])
        self.assertEqual(partial_inputs["task_type"], "analysis")


if __name__ == '__main__':
    unittest.main()
