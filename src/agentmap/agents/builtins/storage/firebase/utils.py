"""
Firebase utility functions.

This module provides helper functions for working with Firebase,
including configuration loading, credential handling, and data conversion.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple, List

from firebase_admin import credentials, initialize_app, delete_app, get_app
from firebase_admin.exceptions import FirebaseError

from agentmap.config import load_storage_config



def get_firebase_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Firebase configuration from storage config file.
    
    Args:
        config_path: Optional path to custom config file
        
    Returns:
        Firebase configuration dictionary
        
    Raises:
        ValueError: If Firebase configuration is not found
    """
    storage_config = load_storage_config(config_path)
    firebase_config = storage_config.get("firebase", {})
    
    if not firebase_config:
        raise ValueError("Firebase configuration not found in storage config")
    
    return firebase_config


def resolve_env_value(value: Any) -> Any:
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


def get_firebase_credentials(auth_config: Dict[str, Any]) -> credentials.Certificate:
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
    service_account_path = resolve_env_value(
        auth_config.get("service_account_key", "")
    )
    
    if service_account_path:
        if os.path.exists(service_account_path):
            return credentials.Certificate(service_account_path)
        else:
            raise ValueError(f"Service account key file not found: {service_account_path}")
    
    # Try API key auth
    api_key = resolve_env_value(auth_config.get("api_key", ""))
    email = resolve_env_value(auth_config.get("email", ""))
    password = resolve_env_value(auth_config.get("password", ""))
    
    if api_key and email and password:
        return credentials.ApplicationDefault()
    
    # Fall back to application default credentials
    try:
        return credentials.ApplicationDefault()
    except Exception as e:
        raise ValueError(
            f"No valid Firebase credentials found: {str(e)}. Please provide a service account key "
            "or set up application default credentials."
        )


def initialize_firebase_app(
    firebase_config: Dict[str, Any],
    app_name: Optional[str] = None
) -> Any:
    """
    Initialize Firebase app with provided configuration.
    
    Args:
        firebase_config: Firebase configuration
        app_name: Optional app name
        
    Returns:
        Firebase app
    """
    # Get default project
    default_project = resolve_env_value(
        firebase_config.get("default_project", "")
    )
    
    if not default_project:
        logger.warning("No default Firebase project specified in config")
    
    # Get auth credentials
    auth_config = firebase_config.get("auth", {})
    cred = get_firebase_credentials(auth_config)
    
    # Use default app name if not provided
    if not app_name:
        app_name = "agentmap-default"
    
    # Initialize the app
    try:
        # Check if app already exists
        app = get_app(app_name)
        self.log_debug(f"Using existing Firebase app: {app_name}")
    except ValueError:
        # Create new app
        app = initialize_app(
            credential=cred,
            name=app_name,
            options={"projectId": default_project} if default_project else None
        )
        self.log_debug(f"Initialized new Firebase app: {app_name}")
    
    return app


def resolve_firebase_collection(
    collection: str,
    firebase_config: Dict[str, Any]
) -> Tuple[str, Dict[str, Any], str]:
    """
    Resolve collection name to Firebase path and options.
    
    Args:
        collection: Collection name from agent inputs
        firebase_config: Firebase configuration
        
    Returns:
        Tuple of (path, collection_config, db_type)
        
    Raises:
        ValueError: If collection not found in config
    """
    # Check in Firestore collections
    firestore_collections = firebase_config.get("firestore", {}).get("collections", {})
    if collection in firestore_collections:
        return (
            firestore_collections[collection].get("collection_path", collection),
            firestore_collections[collection],
            "firestore"
        )
    
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


def convert_firebase_error(error: Exception) -> Exception:
    """
    Convert Firebase-specific errors to standard exceptions.
    
    Args:
        error: Original Firebase error
        
    Returns:
        Converted exception
    """
    if isinstance(error, FirebaseError):
        if "PERMISSION_DENIED" in str(error):
            return PermissionError(f"Firebase permission denied: {str(error)}")
        elif "NOT_FOUND" in str(error):
            return FileNotFoundError(f"Firebase resource not found: {str(error)}")
        
    return error


def format_document_snapshot(
    doc_snapshot: Any,
    include_id: bool = True
) -> Dict[str, Any]:
    """
    Format a Firestore document snapshot as a dictionary.
    
    Args:
        doc_snapshot: Firestore document snapshot
        include_id: Whether to include document ID in result
        
    Returns:
        Document data as dictionary
    """
    if hasattr(doc_snapshot, "to_dict"):
        # Firestore DocumentSnapshot
        data = doc_snapshot.to_dict() or {}
        if include_id and hasattr(doc_snapshot, "id"):
            data["id"] = doc_snapshot.id
        return data
    
    # Realtime DB data
    if isinstance(doc_snapshot, dict):
        return doc_snapshot
    elif doc_snapshot is None:
        return {}
    else:
        # Scalar value
        return {"value": doc_snapshot}


def format_query_results(
    results: Any,
    db_type: str
) -> List[Dict[str, Any]]:
    """
    Format query results as a list of dictionaries.
    
    Args:
        results: Query results
        db_type: Database type ("firestore" or "realtime")
        
    Returns:
        List of document dictionaries
    """
    formatted_results = []
    
    if db_type == "firestore":
        # Firestore query results
        for doc in results:
            data = format_document_snapshot(doc)
            formatted_results.append(data)
    else:
        # Realtime DB results
        if isinstance(results, dict):
            for key, value in results.items():
                data = format_document_snapshot(value)
                data["id"] = key
                formatted_results.append(data)
        elif isinstance(results, list):
            for i, item in enumerate(results):
                data = format_document_snapshot(item)
                if "id" not in data:
                    data["id"] = str(i)
                formatted_results.append(data)
        elif results is not None:
            # Single value
            formatted_results.append({"value": results})
    
    return formatted_results