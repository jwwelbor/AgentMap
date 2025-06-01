# agentmap/logging/__init__.py
# Logging module with DI-based LoggingService
# For legacy imports, use: from agentmap.logging.service import LoggingService

from agentmap.logging.tracking import ExecutionTracker, evaluate_success_policy


__all__ = [
    'ExecutionTracker',
    'evaluate_success_policy'
]
