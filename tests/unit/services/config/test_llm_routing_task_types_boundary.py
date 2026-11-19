"""Tests for validating dynamic task routing configuration values."""

from unittest.mock import Mock

from agentmap.services.config.llm_routing_task_types import (
    get_complexity_keywords,
    get_default_complexity,
    get_provider_preference,
    load_task_types,
    validate_task_type_config,
)


def test_task_type_validation_rejects_values_that_disagree_with_return_types():
    logger = Mock()

    assert not validate_task_type_config(
        "general",
        {
            "provider_preference": ["anthropic", 7],
            "default_complexity": "medium",
            "complexity_keywords": {},
        },
        logger,
    )
    assert not validate_task_type_config(
        "general",
        {
            "provider_preference": ["anthropic"],
            "default_complexity": 7,
            "complexity_keywords": {},
        },
        logger,
    )
    assert not validate_task_type_config(
        "general",
        {
            "provider_preference": ["anthropic"],
            "default_complexity": "medium",
            "complexity_keywords": {"medium": [1]},
        },
        logger,
    )


def test_task_type_getters_fall_back_for_unvalidated_inputs():
    task_types = {
        "general": {
            "provider_preference": "anthropic",
            "default_complexity": None,
            "complexity_keywords": {"medium": "standard"},
        }
    }

    assert get_provider_preference(task_types, "general") == ["anthropic"]
    assert get_default_complexity(task_types, "general") == "medium"
    assert get_complexity_keywords(task_types, "general") == {}


def test_task_type_loader_skips_non_mapping_user_definitions():
    logger = Mock()

    loaded = load_task_types({"task_types": {"broken": None}}, logger)

    assert "broken" not in loaded
    assert "general" in loaded
