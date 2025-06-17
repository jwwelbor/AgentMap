"""
HostServiceRegistry for AgentMap host application integration.

Service for managing dynamic registration of host services and protocols.
This class provides the core functionality for storing service providers, 
protocol implementations, and metadata without affecting AgentMap's core DI container.
"""

import importlib.util
import inspect
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Type, runtime_checkable

from agentmap.services.logging_service import LoggingService


class HostServiceRegistry:
    """
    Service for managing host service and protocol registration and lookup.
    
    This registry manages dynamic registration of host services and protocols,
    enabling host applications to extend AgentMap's service injection system
    while maintaining separation from core AgentMap functionality.
    """
    
    def __init__(self, logging_service: LoggingService):
        """
        Initialize registry with dependency injection.
        
        Args:
            logging_service: LoggingService instance for consistent logging
        """
        self.logger = logging_service.get_class_logger(self)
        
        # Core storage
        self._service_providers: Dict[str, Any] = {}
        self._protocol_implementations: Dict[Type[Protocol], str] = {}
        self._service_metadata: Dict[str, Dict[str, Any]] = {}
        self._protocol_cache: Dict[str, List[Type[Protocol]]] = {}
        
        self.logger.debug("[HostServiceRegistry] Initialized")
    
    def register_service_provider(
        self, 
        service_name: str, 
        provider: Any,
        protocols: Optional[List[Type[Protocol]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a service provider with optional protocol implementations.
        
        Args:
            service_name: Unique name for the service
            provider: Service provider (DI provider, factory function, or instance)
            protocols: Optional list of protocols this service implements
            metadata: Optional metadata about the service
        """
        if not service_name:
            self.logger.warning("[HostServiceRegistry] Empty service name provided")
            return
        
        if not provider:
            self.logger.warning(f"[HostServiceRegistry] Empty provider provide