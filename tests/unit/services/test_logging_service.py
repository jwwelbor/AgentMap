"""Logging service helper contract tests."""

from agentmap.services.logging_service import _get_bootstrap_logger


def test_bootstrap_logger_without_name_uses_module_name():
    logger = _get_bootstrap_logger()

    assert logger.name == "bootstrap.agentmap.services.logging_service"
