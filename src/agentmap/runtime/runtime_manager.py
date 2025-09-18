"""
Runtime State Management

This module provides thread-safe runtime state management for AgentMap,
implementing a singleton pattern for DI container lifecycle management.
"""

import threading
from typing import Optional

from agentmap.di import initialize_di
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized


class RuntimeManager:
    """
    Thread-safe, idempotent runtime container manager.

    This class owns the DI container for the process and exposes simple helpers
    for initialization, access, and lifecycle management. Uses a singleton pattern
    with thread safety to ensure only one container instance exists per process.
    """

    _lock = threading.RLock()
    _is_initialized = False
    _container = None

    @classmethod
    def initialize(
        cls, *, refresh: bool = False, config_file: Optional[str] = None
    ) -> None:
        """
        Initialize the DI container once for the process.

        This method is idempotent - calling it multiple times won't reinitialize
        unless refresh=True is explicitly set. Thread-safe using RLock.

        Args:
            refresh: Rebuild the container even if we already initialized.
            config_file: Optional path to config file for DI bootstrap.

        Raises:
            AgentMapNotInitialized: If initialization fails for any reason.
        """
        with cls._lock:
            if cls._is_initialized and not refresh:
                return

            try:
                cls._container = initialize_di(config_file)
                cls._is_initialized = True
            except Exception as e:
                cls._is_initialized = False
                cls._container = None
                raise AgentMapNotInitialized(f"Initialization failed: {e}") from e

    @classmethod
    def is_initialized(cls) -> bool:
        """
        Return True if the runtime has been initialized.

        Returns:
            bool: True if container is initialized and ready for use.
        """
        return cls._is_initialized

    @classmethod
    def get_container(cls):
        """
        Return the DI container or raise if uninitialized.

        Returns:
            ApplicationContainer: The initialized DI container.

        Raises:
            AgentMapNotInitialized: If runtime not initialized or container is None.
        """
        if not cls._is_initialized or cls._container is None:
            raise AgentMapNotInitialized(
                "Runtime not initialized. Call RuntimeManager.initialize() first."
            )
        return cls._container

    @classmethod
    def reset(cls) -> None:
        """
        Reset runtime state (primarily for tests).

        This method clears the initialization state and container reference,
        allowing for clean reinitialization. Thread-safe using RLock.
        """
        with cls._lock:
            cls._is_initialized = False
            cls._container = None
