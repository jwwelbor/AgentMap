# test_state_adapter.py
from typing import Optional

import pytest
from pydantic import BaseModel

from agentmap.state.adapter import StateAdapter


def test_state_adapter_get_value():
    """Test that StateAdapter can get values from different state types."""
    class _TestModel(BaseModel):
        name: str
        value: Optional[int] = None

    # Test with dict
    dict_state = {"name": "test", "value": 123}
    assert StateAdapter.get_value(dict_state, "name") == "test"
    assert StateAdapter.get_value(dict_state, "value") == 123
    assert StateAdapter.get_value(dict_state, "missing", "default") == "default"
    
    # Test with Pydantic model
    model_state = _TestModel(name="test", value=123)
    assert StateAdapter.get_value(model_state, "name") == "test"
    assert StateAdapter.get_value(model_state, "value") == 123
    assert StateAdapter.get_value(model_state, "missing", "default") == "default"

def test_state_adapter_set_value():
    """Test that StateAdapter can set values in different state types."""
    class _TestModel(BaseModel):
        name: str
        value: Optional[int] = None


    # Test with dict
    dict_state = {"name": "test"}
    new_dict = StateAdapter.set_value(dict_state, "value", 123)
    assert new_dict["name"] == "test"
    assert new_dict["value"] == 123
    assert dict_state != new_dict  # Original should be unchanged
    
    # Test with Pydantic model
    model_state = _TestModel(name="test")
    new_model = StateAdapter.set_value(model_state, "value", 123)
    assert new_model.name == "test"
    assert new_model.value == 123
    assert model_state != new_model  # Original should be unchanged