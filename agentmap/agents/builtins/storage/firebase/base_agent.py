"""
Firebase document storage agent base implementation.

This module provides Firebase-specific implementations of document storage operations,
supporting both Firestore and Realtime Database.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from firebase_admin import credentials, firestore, db, initialize_app, delete_app, get_app
from firebase_admin.exceptions import FirebaseError

from agentmap.agents.builtins.storage.document.base_agent import DocumentStorageAgent
from agentmap.agents.builtins.storage.document.path_mixin import DocumentPathMixin
from agentmap.config import load_storage_config
from agentmap.exceptions import CollectionNotFoundError, StorageConnectionError, StorageConfigurationError, StorageOperationError
from agentmap.logging import get_logger

logger = get_logger(__name__)


class FirebaseDocumentAgent(DocumentStorageAgent, DocumentPathMixin):
    """
    Base class for Firebase document storage operations.
    
    Provides shared functionality for connecting to Firebase and resolving collections,
    with support for both Firestore and Realtime Database.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the Firebase document agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including input/output field configuration
        """
        super().__init__(name, prompt, context)
        self._app = None
        self._firestore_db = None
        self._realtime_db = None
        self._db_type = None  # "firestore" or "realtime"
        self._current_project = None
    
    def _initialize_client(self) -> None:
        """Initialize Firebase client using storage configuration."""
        try:
            # Load Firebase configuration
            storage_config = load_storage_config()
            firebase_config = storage_config.get("firebase", {})
            
            if not firebase_config:
                raise StorageConfigurationError("Firebase configuration not found in storage config")
            
            # Initialize Firebase app
            self._init_firebase_app(firebase_config)
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase client: {str(e)}")
            raise
    
    def _init_firebase_app(self, firebase_config: Dict[str, Any]) -> None:
        """
        Initialize Firebase app with the provided configuration.
        
        Args:
            firebase_config: Firebase configuration from storage config
        """
        # Get default project
        default_project = self._resolve_env_value(
            firebase_config.get("default_project", "")
        )
        
        if not default_project:
            logger.warning("No default Firebase project specified in config")
        
        # Get auth credentials
        auth_config = firebase_config.get("auth", {})
        cred = self._get_firebase_credentials(auth_config)
        
        # Initialize the app
        app_name = f"agentmap-{self.name}"
        try:
            # Check if app already exists
            self._app = get_app(app_name)
            logger.debug(f"Using existing Firebase app: {app_name}")
        except ValueError:
            # Create new app
            self._app = initialize_app(
                credential=cred,
                name=app_name,
                options={"projectId": default_project} if default_project else None
            )
            logger.debug(f"Initialized new Firebase app: {app_name}")
        
        # Store current project
        self._current_project = default_project
    
    def _get_firebase_credentials(self, auth_config: Dict[str, Any]) -> credentials.Certificate:
        """
        Get Firebase credentials from auth configuration.
        
        Args:
            auth_config: Auth section of Firebase config
            
        Returns:
            Firebase credentials object
            
        Raises:
            ValueError: If no valid credentials are found
        """
        # Try service account key first
        service_account_path = self._resolve_env_value(
            auth_config.get("service_account_key", "")
        )
        
        if service_account_path:
            if os.path.exists(service_account_path):
                return credentials.Certificate(service_account_path)
            else:
                raise StorageConfigurationError(f"Service account key file not found: {service_account_path}")
        
        # Try API key auth
        api_key = self._resolve_env_value(auth_config.get("api_key", ""))
        email = self._resolve_env_value(auth_config.get("email", ""))
        password = self._resolve_env_value(auth_config.get("password", ""))
        
        if api_key and email and password:
            return credentials.ApplicationDefault()
        
        # Fall back to application default credentials
        try:
            return credentials.ApplicationDefault()
        except Exception:
            raise StorageConfigurationError(
                "No valid Firebase credentials found. Please provide a service account key "
                "or set up application default credentials."
            )
    
    def _resolve_env_value(self, value: str) -> str:
        """
        Resolve environment variable references in config values.
        
        Args:
            value: Config value, possibly containing env: prefix
            
        Returns:
            Resolved value
        """
        if not isinstance(value, str):
            return value
            
        if value.startswith("env:"):
            env_var = value[4:]
            env_value = os.environ.get(env_var, "")
            if not env_value:
                logger.warning(f"Environment variable not found: {env_var}")
            return env_value
        
        return value
    
    def _resolve_collection_path(self, collection: str) -> Tuple[str, Dict[str, Any], str]:
        """
        Resolve collection name to Firebase path and options.
        
        Args:
            collection: Collection name from agent inputs
            
        Returns:
            Tuple of (path, collection_config, db_type)
            
        Raises:
            ValueError: If collection not found in config
        """
        storage_config = load_storage_config()
        firebase_config = storage_config.get("firebase", {})
        
        # Check in Firestore collections
        firestore_collections = firebase_config.get("firestore", {}).get("collections", {})
        if collection in firestore_collections:
            return (
                firestore_collections[collection].get("collection_path", collection),
                firestore_collections[collection],
                "firestore"
            )
        else:
            raise CollectionNotFoundError(f"Collection '{collection}' not found in Firebase config")
        
        # Check in Realtime DB collections
        realtime_collections = firebase_config.get("realtime_db", {}).get("collections", {})
        if collection in realtime_collections:
            return (
                realtime_collections[collection].get("path", collection),
                realtime_collections[collection],
                "realtime"
            )
        
        # Default to using collection name directly
        logger.warning(f"Collection '{collection}' not found in Firebase config, using directly")
        return collection, {}, "firestore"
    
    def _get_db_reference(self, collection: str) -> Tuple[Any, str, Dict[str, Any]]:
        """
        Get appropriate database reference based on collection name.
        
        Args:
            collection: Collection name from agent inputs
            
        Returns:
            Tuple of (db_reference, path, config)
        """
        # Resolve collection to path and type
        path, config, db_type = self._resolve_collection_path(collection)
        
        # Check for project override
        project_id = self._resolve_env_value(config.get("project_id", ""))
        if project_id and project_id != self._current_project:
            logger.debug(f"Using project override: {project_id}")
            # TODO: Handle project override with new Firebase app
            
        
        # Get appropriate database reference
        if db_type == "firestore":
            return self._get_firestore_reference(path), path, config
        else:
            return self._get_realtime_reference(path, config), path, config
    
    def _get_firestore_reference(self, path: str) -> firestore.CollectionReference:
        """
        Get Firestore collection reference.
        
        Args:
            path: Collection path
            
        Returns:
            Firestore collection reference
        """
        if not self._firestore_db:
            self._firestore_db = firestore.client(app=self._app)
        
        # Handle nested collection paths (e.g. "users/123/posts")
        parts = path.split("/")
        if len(parts) % 2 == 0:
            # Even number of parts means it ends with a document reference
            logger.warning(f"Path '{path}' should be a collection path, not a document path")
            # Make it a collection by adding a default subcollection
            path = f"{path}/items"
            parts.append("items")
        
        ref = self._firestore_db
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Collection reference
                ref = ref.collection(part)
            else:
                # Document reference
                ref = ref.document(part)
        
        return ref
    
    def _get_realtime_reference(self, path: str, config: Dict[str, Any]) -> db.Reference:
        """
        Get Realtime Database reference.
        
        Args:
            path: Database path
            config: Collection configuration
            
        Returns:
            Realtime DB reference
        """
        if not self._realtime_db:
            # Check for database URL in config
            db_url = self._resolve_env_value(config.get("db_url", ""))
            if not db_url:
                # Fall back to default database URL
                self._realtime_db = db.reference(app=self._app)
            else:
                self._realtime_db = db.reference(app=self._app, url=db_url)
        
        return self._realtime_db.child(path)
    
    def _convert_firebase_error(self, error: Exception) -> Exception:
        """
        Convert Firebase-specific errors to standard exceptions.
        
        Args:
            error: Original Firebase error
            
        Returns:
            Converted exception
        """
        if isinstance(error, FirebaseError):
            if "PERMISSION_DENIED" in str(error):
                return StorageOperationError(f"Firebase permission denied: {str(error)}")
            elif "NOT_FOUND" in str(error):
                return StorageOperationError(f"Firebase resource not found: {str(error)}")
            
        return error
    
    def __del__(self):
        """Clean up Firebase resources on deletion."""
        try:
            if self._app:
                app_name = self._app.name
                delete_app(self._app)
                logger.debug(f"Deleted Firebase app: {app_name}")
        except Exception:
            pass
