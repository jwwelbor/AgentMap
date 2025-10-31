"""Storage container part with configuration and storage managers."""

from __future__ import annotations

from dependency_injector import containers, providers


class StorageContainer(containers.DeclarativeContainer):
    """Provides storage configuration and related services."""

    config_service = providers.Dependency()
    app_config_service = providers.Dependency()
    availability_cache_service = providers.Dependency()
    logging_service = providers.Dependency()
    file_path_service = providers.Dependency()

    @staticmethod
    def _create_storage_config_service(
        config_service,
        app_config_service,
        availability_cache_service,
    ):
        from agentmap.exceptions.service_exceptions import (
            StorageConfigurationNotAvailableException,
        )
        from agentmap.services.config.storage_config_service import StorageConfigService

        storage_config_path = app_config_service.get_storage_config_path()
        try:
            return StorageConfigService(
                config_service,
                storage_config_path,
                availability_cache_service,
            )
        except StorageConfigurationNotAvailableException:
            return None

    storage_config_service = providers.Singleton(
        _create_storage_config_service,
        config_service,
        app_config_service,
        availability_cache_service,
    )

    @staticmethod
    def _create_blob_storage_service(
        storage_config_service,
        logging_service,
        availability_cache_service,
    ):
        if storage_config_service is None:
            logging_service.get_logger("agentmap.blob_storage").info(
                "Storage configuration not available - blob storage service disabled",
            )
            return None
        if availability_cache_service is None:
            logging_service.get_logger("agentmap.blob_storage").warning(
                "Availability cache service not available - blob storage service disabled",
            )
            return None
        try:
            from agentmap.services.storage.blob_storage_service import (
                BlobStorageService,
            )

            return BlobStorageService(
                storage_config_service,
                logging_service,
                availability_cache_service,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logging_service.get_logger("agentmap.blob_storage").warning(
                f"Blob storage service disabled: {exc}"
            )
            return None

    blob_storage_service = providers.Singleton(
        _create_blob_storage_service,
        storage_config_service,
        logging_service,
        availability_cache_service,
    )

    @staticmethod
    def _create_json_storage_service(storage_config_service, logging_service):
        if storage_config_service is None:
            logging_service.get_logger("agentmap.json_storage").info(
                "Storage configuration not available - json storage service disabled",
            )
            return None
        try:
            from agentmap.services.storage.json_service import JSONStorageService

            return JSONStorageService(
                "json",
                storage_config_service,
                logging_service,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logging_service.get_logger("agentmap.json_storage").warning(
                f"JSON storage service disabled: {exc}"
            )
            return None

    json_storage_service = providers.Singleton(
        _create_json_storage_service,
        storage_config_service,
        logging_service,
    )

    @staticmethod
    def _create_storage_service_manager(
        storage_config_service,
        logging_service,
        file_path_service,
        blob_storage_service,
    ):
        from agentmap.exceptions.service_exceptions import (
            StorageConfigurationNotAvailableException,
        )
        from agentmap.services.storage.manager import StorageServiceManager

        if storage_config_service is None:
            logging_service.get_logger("agentmap.storage").info(
                "Storage configuration not available - storage services disabled",
            )
            return None
        try:
            return StorageServiceManager(
                storage_config_service,
                logging_service,
                file_path_service,
                blob_storage_service,
            )
        except StorageConfigurationNotAvailableException as exc:
            logging_service.get_logger("agentmap.storage").warning(
                f"Storage services disabled: {exc}"
            )
            return None

    storage_service_manager = providers.Singleton(
        _create_storage_service_manager,
        storage_config_service,
        logging_service,
        file_path_service,
        blob_storage_service,
    )

    system_storage_manager = providers.Singleton(
        "agentmap.services.storage.system_manager.SystemStorageManager",
        app_config_service,
        logging_service,
        file_path_service,
    )

    storage_available = providers.Callable(lambda: True)
