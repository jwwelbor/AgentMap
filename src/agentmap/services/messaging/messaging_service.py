# src/agentmap/services/messaging_service.py

import json
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from agentmap.exceptions import (
    MessagingConnectionError,
    MessagingOperationError,
    MessagingServiceUnavailableError,
)
from agentmap.models.storage.types import StorageResult
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.availability_cache_service import AvailabilityCacheService
from agentmap.services.logging_service import LoggingService


class CloudProvider(Enum):
    """Supported cloud providers for messaging."""

    GCP = "gcp"
    AWS = "aws"
    AZURE = "azure"
    LOCAL = "local"  # For testing/development


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class CloudMessageAdapter(Protocol):
    """Protocol for cloud-specific message adapters."""

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """Publish message to cloud topic."""
        ...

    async def create_topic(self, topic_name: str) -> StorageResult:
        """Create topic if it doesn't exist."""
        ...

    def get_provider(self) -> CloudProvider:
        """Get the cloud provider type."""
        ...


class MessagingService:
    """
    Service for publishing messages to cloud message queues/topics.

    Provides cloud-agnostic interface for message publishing with
    support for multiple cloud providers.
    """

    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        availability_cache: AvailabilityCacheService,
    ):
        """Initialize messaging service with configuration."""
        self.config = app_config_service
        self.availability_cache = availability_cache
        self.logger = logging_service.get_class_logger(self)

        # Load messaging configuration
        self.messaging_config = self._load_messaging_config()
        self.adapters: Dict[CloudProvider, CloudMessageAdapter] = {}

        # Available providers (populated during initialization)
        self._available_providers: Dict[str, bool] = {}

        # Initialize adapters with availability checking
        self._initialize_adapters()

    def _load_messaging_config(self) -> Dict[str, Any]:
        """Load messaging configuration from app config."""
        try:
            config = self.config.get_messaging_config()
            if not config:
                # Default configuration
                config = {
                    "default_provider": "local",
                    "providers": {
                        "local": {"enabled": True, "storage_path": "data/messages"}
                    },
                    "message_templates": {},
                    "retry_policy": {"max_retries": 3, "backoff_seconds": [1, 2, 4]},
                }
            return config
        except Exception as e:
            self.logger.warning(f"Failed to load messaging config: {e}, using defaults")
            return {}

    def _initialize_adapters(self):
        """Initialize cloud-specific adapters based on configuration and availability."""
        providers_config = self.messaging_config.get("providers", {})

        for provider_name, provider_config in providers_config.items():
            if not provider_config.get("enabled", False):
                continue

            try:
                provider = CloudProvider(provider_name)

                # Check availability with caching
                if self._check_provider_availability(provider):
                    adapter = self._create_adapter(provider, provider_config)
                    if adapter:
                        self.adapters[provider] = adapter
                        self._available_providers[provider_name] = True
                        self.logger.info(
                            f"Initialized {provider.value} messaging adapter"
                        )
                    else:
                        self._available_providers[provider_name] = False
                        self.logger.warning(
                            f"Failed to create adapter for {provider_name}"
                        )
                else:
                    self._available_providers[provider_name] = False
                    self.logger.debug(
                        f"Provider {provider_name} not available (cached)"
                    )

            except ValueError:
                self.logger.warning(f"Unknown provider: {provider_name}")
                self._available_providers[provider_name] = False
            except Exception as e:
                self.logger.error(f"Failed to initialize {provider_name} adapter: {e}")
                self._available_providers[provider_name] = False

    def _check_provider_availability(self, provider: CloudProvider) -> bool:
        """
        Check and cache provider availability.

        Args:
            provider: CloudProvider to check

        Returns:
            True if provider is available, False otherwise
        """
        provider_name = provider.value

        # Try to get from cache first
        cached_result = self.availability_cache.get_availability(
            "dependency.messaging", provider_name
        )

        if cached_result is not None:
            return cached_result.get("available", False)

        # Not in cache, perform actual check
        try:
            available = self._check_provider_dependencies(provider)
            # Cache the result
            self.availability_cache.set_availability(
                "dependency.messaging",
                provider_name,
                {"available": available, "provider": provider_name},
            )
            return available
        except Exception as e:
            self.logger.debug(f"Error checking {provider_name} availability: {e}")
            # Cache the failure
            self.availability_cache.set_availability(
                "dependency.messaging",
                provider_name,
                {"available": False, "provider": provider_name, "error": str(e)},
            )
            return False

    def _check_provider_dependencies(self, provider: CloudProvider) -> bool:
        """Check if provider dependencies are available."""
        if provider == CloudProvider.GCP:
            return self._check_gcp_availability()
        elif provider == CloudProvider.AWS:
            return self._check_aws_availability()
        elif provider == CloudProvider.AZURE:
            return self._check_azure_availability()
        elif provider == CloudProvider.LOCAL:
            return True  # Local always available
        return False

    @staticmethod
    def _check_gcp_availability() -> bool:
        """Check if GCP messaging SDK is available."""
        try:
            import google.cloud.pubsub_v1  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def _check_aws_availability() -> bool:
        """Check if AWS messaging SDK is available."""
        try:
            import boto3  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def _check_azure_availability() -> bool:
        """Check if Azure messaging SDK is available."""
        try:
            import azure.servicebus  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_adapter(
        self, provider: CloudProvider, config: Dict[str, Any]
    ) -> Optional[CloudMessageAdapter]:
        """Create cloud-specific adapter."""
        try:
            if provider == CloudProvider.GCP:
                from agentmap.services.messaging.gcp_adapter import GCPMessageAdapter

                return GCPMessageAdapter(config, self.logger)
            elif provider == CloudProvider.AWS:
                from agentmap.services.messaging.aws_adapter import AWSMessageAdapter

                return AWSMessageAdapter(config, self.logger)
            elif provider == CloudProvider.AZURE:
                from agentmap.services.messaging.azure_adapter import (
                    AzureMessageAdapter,
                )

                return AzureMessageAdapter(config, self.logger)
            elif provider == CloudProvider.LOCAL:
                from agentmap.services.messaging.local_adapter import (
                    LocalMessageAdapter,
                )

                return LocalMessageAdapter(config, self.logger)
        except ImportError as e:
            self.logger.debug(f"Import failed for {provider.value} adapter: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create {provider.value} adapter: {e}")
            return None

        return None

    async def publish_message(
        self,
        topic: str,
        message_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        provider: Optional[CloudProvider] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        thread_id: Optional[str] = None,
    ) -> StorageResult:
        """
        Publish a message to a cloud topic.

        Args:
            topic: Topic/queue name to publish to
            message_type: Type of message (e.g., "task_request", "graph_trigger")
            payload: Message payload data
            metadata: Optional metadata for the message
            provider: Specific provider to use (or use default)
            priority: Message priority
            thread_id: Thread ID for correlation

        Returns:
            StorageResult indicating success/failure

        Raises:
            MessagingServiceUnavailableError: If no suitable provider is available
        """
        # Select provider
        if provider is None:
            provider_name = self.messaging_config.get("default_provider", "local")
            try:
                provider = CloudProvider(provider_name)
            except ValueError:
                raise MessagingServiceUnavailableError(
                    f"Invalid default provider: {provider_name}"
                )

        adapter = self.adapters.get(provider)
        if not adapter:
            available_providers = [p.value for p in self.adapters.keys()]
            raise MessagingServiceUnavailableError(
                f"No adapter available for provider: {provider.value}. "
                f"Available providers: {', '.join(available_providers)}"
            )

        # Build standardized message format
        message = self._build_message(
            message_type=message_type,
            payload=payload,
            metadata=metadata,
            thread_id=thread_id,
            priority=priority,
        )

        # Add message attributes for filtering/routing
        attributes = {
            "message_type": message_type,
            "priority": priority.value,
            "source": "agentmap",
            "timestamp": datetime.utcnow().isoformat(),
        }
        if thread_id:
            attributes["thread_id"] = thread_id

        # Publish with retry logic
        return await self._publish_with_retry(
            adapter=adapter, topic=topic, message=message, attributes=attributes
        )

    def _build_message(
        self,
        message_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
        thread_id: Optional[str],
        priority: MessagePriority,
    ) -> Dict[str, Any]:
        """Build standardized message format."""
        return {
            "version": "1.0",
            "message_id": self._generate_message_id(),
            "message_type": message_type,
            "timestamp": datetime.utcnow().isoformat(),
            "thread_id": thread_id,
            "priority": priority.value,
            "payload": payload,
            "metadata": metadata or {},
            "source": {"system": "agentmap", "version": self._get_agentmap_version()},
        }

    async def _publish_with_retry(
        self,
        adapter: CloudMessageAdapter,
        topic: str,
        message: Dict[str, Any],
        attributes: Dict[str, str],
    ) -> StorageResult:
        """Publish message with retry logic."""
        retry_config = self.messaging_config.get("retry_policy", {})
        max_retries = retry_config.get("max_retries", 3)
        backoff = retry_config.get("backoff_seconds", [1, 2, 4])

        for attempt in range(max_retries):
            try:
                result = await adapter.publish(topic, message, attributes)
                if result.success:
                    self.logger.info(
                        f"Message published to {topic} via {adapter.get_provider().value}"
                    )
                    return result

                self.logger.warning(
                    f"Publish attempt {attempt + 1} failed: {result.error}"
                )

            except Exception as e:
                self.logger.error(f"Publish attempt {attempt + 1} exception: {e}")

            # Wait before retry (if not last attempt)
            if attempt < max_retries - 1:
                import asyncio

                wait_time = backoff[min(attempt, len(backoff) - 1)]
                await asyncio.sleep(wait_time)

        # All retries failed
        return StorageResult(
            success=False,
            error=f"Failed to publish after {max_retries} attempts",
            operation="publish_message",
        )

    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        import uuid

        return str(uuid.uuid4())

    def _get_agentmap_version(self) -> str:
        """Get AgentMap version."""
        # TODO: Get from package version
        return "0.1.0"

    def apply_template(
        self, template_name: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply a message template with variables.

        Templates allow consistent message formatting across
        different use cases.
        """
        templates = self.messaging_config.get("message_templates", {})
        template = templates.get(template_name)

        if not template:
            self.logger.warning(f"Template '{template_name}' not found")
            return variables

        # Deep copy template and replace variables
        import copy
        import string

        result = copy.deepcopy(template)

        def replace_vars(obj):
            """Recursively replace template variables."""
            if isinstance(obj, str):
                template_obj = string.Template(obj)
                return template_obj.safe_substitute(**variables)
            elif isinstance(obj, dict):
                return {k: replace_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_vars(item) for item in obj]
            return obj

        return replace_vars(result)

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information for debugging."""
        return {
            "service": "MessagingService",
            "default_provider": self.messaging_config.get("default_provider"),
            "available_adapters": [p.value for p in self.adapters.keys()],
            "available_providers": self._available_providers,
            "templates_configured": len(
                self.messaging_config.get("message_templates", {})
            ),
            "retry_policy": self.messaging_config.get("retry_policy", {}),
        }

    def get_available_providers(self) -> List[str]:
        """
        Get list of available messaging providers.

        Returns:
            List of provider names that are available
        """
        return [
            provider
            for provider, available in self._available_providers.items()
            if available
        ]
