"""Boundary tests for dynamically imported workflow functions."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agentmap.exceptions.service_exceptions import FunctionResolutionException
from agentmap.services.function_resolution_service import FunctionResolutionService


def test_non_callable_module_attribute_is_rejected():
    service = FunctionResolutionService(Path("functions"))
    imported_module = SimpleNamespace(not_callable=42)

    with patch("builtins.__import__", return_value=imported_module):
        with pytest.raises(FunctionResolutionException, match="not callable"):
            service.load_function("not_callable")
