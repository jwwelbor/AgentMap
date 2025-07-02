"""
Authentication service for AgentMap API.

This module provides authentication functionality supporting multiple
authentication methods (API keys, JWT, Supabase) following clean
architecture principles with configurable authentication.
"""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

from agentmap.services.logging_service import LoggingService


@dataclass
class AuthContext:
    """Authentication context containing validated identity information."""

    authenticated: bool
    auth_method: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    permissions: List[str] = None
    metadata: Dict[str, str] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.permissions is None:
            self.permissions = []
        if self.metadata is None:
            self.metadata = {}


class AuthService:
    """
    Authentication service providing multiple authentication methods.

    Supports API keys, JWT tokens, and Supabase authentication with
    configurable per-endpoint protection and graceful degradation.
    """

    def __init__(self, auth_config: Dict[str, any], logging_service: LoggingService):
        """
        Initialize authentication service.

        Args:
            auth_config: Authentication configuration dictionary
            logging_service: Logging service for audit trails
        """
        self.config = auth_config
        self.logger = logging_service.get_class_logger(self)
        self.enabled = auth_config.get("enabled", True)

        # Load API keys configuration
        self._api_keys = self._load_api_keys()

        # JWT configuration (for future implementation)
        self.jwt_secret = auth_config.get("jwt", {}).get("secret")
        self.jwt_algorithm = auth_config.get("jwt", {}).get("algorithm", "HS256")

        # Supabase configuration (for future implementation)
        self.supabase_url = auth_config.get("supabase", {}).get("url")
        self.supabase_key = auth_config.get("supabase", {}).get("anon_key")

        self.logger.info(
            f"[AuthService] Initialized with {len(self._api_keys)} API keys"
        )

    def _load_api_keys(self) -> Dict[str, Dict[str, any]]:
        """
        Load API keys from configuration and environment variables.

        Returns:
            Dictionary mapping API key hashes to key metadata
        """
        api_keys = {}

        # Load from config file
        config_keys = self.config.get("api_keys", {})
        for key_name, key_config in config_keys.items():
            if isinstance(key_config, dict):
                key_value = key_config.get("key")
                if key_value:
                    key_hash = self._hash_api_key(key_value)
                    api_keys[key_hash] = {
                        "name": key_name,
                        "permissions": key_config.get("permissions", []),
                        "user_id": key_config.get("user_id", key_name),
                        "expires_at": key_config.get("expires_at"),
                        "metadata": key_config.get("metadata", {}),
                    }

        # Load from environment variables (pattern: AGENTMAP_API_KEY_<n>)
        for env_var, env_value in os.environ.items():
            if env_var.startswith("AGENTMAP_API_KEY_"):
                key_name = env_var.replace("AGENTMAP_API_KEY_", "").lower()
                key_hash = self._hash_api_key(env_value)
                api_keys[key_hash] = {
                    "name": key_name,
                    "permissions": [
                        "read",
                        "write",
                    ],  # Default permissions for env keys
                    "user_id": key_name,
                    "expires_at": None,
                    "metadata": {"source": "environment"},
                }

        self.logger.debug(f"[AuthService] Loaded {len(api_keys)} API keys")
        return api_keys

    def _hash_api_key(self, api_key: str) -> str:
        """
        Hash API key for secure storage and comparison.

        Args:
            api_key: Raw API key value

        Returns:
            Hashed API key for secure comparison
        """
        # Use SHA-256 for hashing API keys
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    def _constant_time_compare(self, a: str, b: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks.

        Args:
            a: First string
            b: Second string

        Returns:
            True if strings are equal
        """
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

    def validate_api_key(self, api_key: str) -> AuthContext:
        """
        Validate API key and return authentication context.

        Args:
            api_key: API key to validate

        Returns:
            AuthContext with validation results
        """
        if not self.enabled:
            self.logger.debug("[AuthService] Authentication disabled, allowing access")
            return AuthContext(
                authenticated=True,
                auth_method="disabled",
                user_id="system",
                permissions=["admin"],
            )

        if not api_key:
            self.logger.warning("[AuthService] Empty API key provided")
            return AuthContext(authenticated=False, auth_method="api_key")

        # Hash the provided key for comparison
        key_hash = self._hash_api_key(api_key)

        # Find matching key
        for stored_hash, key_info in self._api_keys.items():
            if self._constant_time_compare(key_hash, stored_hash):
                # Check expiration
                if key_info.get("expires_at"):
                    try:
                        expires_at = datetime.fromisoformat(key_info["expires_at"])
                        if datetime.now() > expires_at:
                            self.logger.warning(
                                f"[AuthService] Expired API key used: {key_info['name']}"
                            )
                            return AuthContext(
                                authenticated=False, auth_method="api_key"
                            )
                    except ValueError:
                        self.logger.error(
                            f"[AuthService] Invalid expiration date for key: {key_info['name']}"
                        )

                self.logger.info(
                    f"[AuthService] Successful API key authentication: {key_info['name']}"
                )
                return AuthContext(
                    authenticated=True,
                    auth_method="api_key",
                    user_id=key_info["user_id"],
                    username=key_info["name"],
                    permissions=key_info["permissions"],
                    metadata=key_info["metadata"],
                    expires_at=(
                        datetime.fromisoformat(key_info["expires_at"])
                        if key_info.get("expires_at")
                        else None
                    ),
                )

        self.logger.warning("[AuthService] Invalid API key provided")
        return AuthContext(authenticated=False, auth_method="api_key")

    def validate_jwt(self, token: str) -> AuthContext:
        """
        Validate JWT token (stub for future implementation).

        Args:
            token: JWT token to validate

        Returns:
            AuthContext with validation results
        """
        if not self.enabled:
            return AuthContext(
                authenticated=True,
                auth_method="disabled",
                user_id="system",
                permissions=["admin"],
            )

        # TODO: Implement JWT validation
        # This would include:
        # - Token signature verification
        # - Expiration checking
        # - Claims extraction
        # - Permission mapping

        self.logger.info("[AuthService] JWT validation not yet implemented")
        return AuthContext(authenticated=False, auth_method="jwt")

    def validate_supabase_token(self, token: str) -> AuthContext:
        """
        Validate Supabase authentication token (stub for future implementation).

        Args:
            token: Supabase token to validate

        Returns:
            AuthContext with validation results
        """
        if not self.enabled:
            return AuthContext(
                authenticated=True,
                auth_method="disabled",
                user_id="system",
                permissions=["admin"],
            )

        # TODO: Implement Supabase token validation
        # This would include:
        # - Supabase API integration
        # - Token verification against Supabase service
        # - User profile extraction
        # - Role-based permission mapping

        self.logger.info("[AuthService] Supabase validation not yet implemented")
        return AuthContext(authenticated=False, auth_method="supabase")

    def generate_api_key(self, length: int = 32) -> str:
        """
        Generate a secure API key.

        Args:
            length: Length of the API key

        Returns:
            Secure random API key
        """
        return secrets.token_urlsafe(length)

    def is_authentication_enabled(self) -> bool:
        """
        Check if authentication is enabled.

        Returns:
            True if authentication is enabled
        """
        return self.enabled

    def get_public_endpoints(self) -> List[str]:
        """
        Get list of public endpoints that don't require authentication.

        Returns:
            List of public endpoint patterns
        """
        return self.config.get(
            "public_endpoints", ["/health", "/docs", "/openapi.json", "/redoc", "/"]
        )

    def validate_permissions(
        self, auth_context: AuthContext, required_permissions: List[str]
    ) -> bool:
        """
        Validate that authentication context has required permissions.

        Args:
            auth_context: Authentication context
            required_permissions: List of required permissions

        Returns:
            True if user has all required permissions
        """
        if not auth_context.authenticated:
            return False

        # Admin permission grants all access
        if "admin" in auth_context.permissions:
            return True

        # Check if user has all required permissions
        return all(perm in auth_context.permissions for perm in required_permissions)

    def get_auth_stats(self) -> Dict[str, any]:
        """
        Get authentication statistics for monitoring.

        Returns:
            Dictionary with authentication statistics
        """
        active_keys = sum(
            1
            for key_info in self._api_keys.values()
            if not key_info.get("expires_at")
            or datetime.fromisoformat(key_info["expires_at"]) > datetime.now()
        )

        return {
            "enabled": self.enabled,
            "total_api_keys": len(self._api_keys),
            "active_api_keys": active_keys,
            "jwt_configured": bool(self.jwt_secret),
            "supabase_configured": bool(self.supabase_url and self.supabase_key),
            "public_endpoints_count": len(self.get_public_endpoints()),
        }
