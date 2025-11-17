"""Authentication configuration manager."""

from typing import Any, Dict, List

from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)


class AuthConfigManager(BaseConfigManager):
    """
    Configuration manager for authentication settings.

    Handles all authentication-related configuration including API keys,
    JWT, Supabase, public endpoints, and permissions.
    """

    def get_auth_config(self) -> Dict[str, Any]:
        """Get authentication configuration with default values."""
        auth_config = self.get_section("authentication", {})

        # Default authentication configuration
        defaults = {
            "enabled": True,
            "api_keys": {},  # API keys should be defined in config or env vars
            "jwt": {
                "secret": None,  # Should be set in environment or config
                "algorithm": "HS256",
                "expiry_hours": 24,
            },
            "supabase": {
                "url": None,  # Should be set in environment or config
                "anon_key": None,  # Should be set in environment or config
            },
            "public_endpoints": [
                "/",
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
                "/favicon.ico",
            ],
            "embedded_mode": {
                "enabled": True,  # Allow embedded mode for local development
                "bypass_auth": True,  # Bypass auth for embedded mode
            },
            "permissions": {
                "default_permissions": ["read"],
                "admin_permissions": ["read", "write", "execute", "admin"],
                "execution_permissions": ["read", "execute"],
            },
        }

        # Merge with defaults
        merged_config = self._merge_with_defaults(auth_config, defaults)

        # Log auth configuration status for visibility
        if auth_config:
            self._logger.debug(
                f"[AuthConfigManager] Authentication config loaded: enabled={merged_config.get('enabled', True)}"
            )
        else:
            self._logger.debug(
                "[AuthConfigManager] No authentication config found, using defaults"
            )

        return merged_config

    def is_authentication_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self.get_value("authentication.enabled", True)

    def get_api_keys_config(self) -> Dict[str, Any]:
        """Get API keys configuration."""
        return self.get_value("authentication.api_keys", {})

    def get_jwt_config(self) -> Dict[str, Any]:
        """Get JWT authentication configuration."""
        return self.get_value(
            "authentication.jwt",
            {"secret": None, "algorithm": "HS256", "expiry_hours": 24},
        )

    def get_supabase_auth_config(self) -> Dict[str, Any]:
        """Get Supabase authentication configuration."""
        return self.get_value(
            "authentication.supabase", {"url": None, "anon_key": None}
        )

    def get_public_endpoints(self) -> List[str]:
        """Get list of public endpoints that don't require authentication."""
        return self.get_value(
            "authentication.public_endpoints",
            ["/", "/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"],
        )

    def get_embedded_mode_config(self) -> Dict[str, Any]:
        """Get embedded mode configuration."""
        return self.get_value(
            "authentication.embedded_mode", {"enabled": True, "bypass_auth": True}
        )

    def get_auth_permissions_config(self) -> Dict[str, Any]:
        """Get authentication permissions configuration."""
        return self.get_value(
            "authentication.permissions",
            {
                "default_permissions": ["read"],
                "admin_permissions": ["read", "write", "execute", "admin"],
                "execution_permissions": ["read", "execute"],
            },
        )

    def validate_auth_config(self) -> Dict[str, Any]:
        """
        Validate authentication configuration and return validation results.

        Returns:
            Dictionary with validation status:
            - 'valid': Boolean indicating if config is valid
            - 'warnings': List of non-critical issues
            - 'errors': List of critical issues
            - 'summary': Summary of validation results
        """
        warnings = []
        errors = []

        try:
            auth_config = self.get_auth_config()

            # Check if auth is enabled but no auth methods configured
            if auth_config.get("enabled", True):
                api_keys = auth_config.get("api_keys", {})
                jwt_secret = auth_config.get("jwt", {}).get("secret")
                supabase_config = auth_config.get("supabase", {})

                has_auth_method = (
                    bool(api_keys)
                    or bool(jwt_secret)
                    or (
                        bool(supabase_config.get("url"))
                        and bool(supabase_config.get("anon_key"))
                    )
                )

                if not has_auth_method:
                    warnings.append(
                        "Authentication is enabled but no auth methods are configured (API keys, JWT, or Supabase)"
                    )

            # Validate JWT configuration
            jwt_config = auth_config.get("jwt", {})
            if jwt_config.get("secret") and len(jwt_config["secret"]) < 32:
                warnings.append(
                    "JWT secret should be at least 32 characters long for security"
                )

            # Validate public endpoints
            public_endpoints = auth_config.get("public_endpoints", [])
            if not isinstance(public_endpoints, list):
                errors.append("Public endpoints configuration must be a list")
            elif not public_endpoints:
                warnings.append(
                    "No public endpoints configured - all endpoints will require authentication"
                )

            # Validate permissions configuration
            permissions_config = auth_config.get("permissions", {})
            if not isinstance(permissions_config, dict):
                errors.append("Permissions configuration must be a dictionary")
            else:
                default_perms = permissions_config.get("default_permissions", [])
                if not isinstance(default_perms, list):
                    errors.append("Default permissions must be a list")

        except Exception as e:
            errors.append(f"Error during auth config validation: {str(e)}")

        # Determine overall validity
        is_valid = len(errors) == 0

        # Create summary
        summary = {
            "total_issues": len(warnings) + len(errors),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "auth_enabled": self.is_authentication_enabled(),
            "public_endpoints_count": len(self.get_public_endpoints()),
            "has_api_keys": bool(self.get_api_keys_config()),
            "has_jwt_secret": bool(self.get_jwt_config().get("secret")),
            "has_supabase_config": bool(
                self.get_supabase_auth_config().get("url")
                and self.get_supabase_auth_config().get("anon_key")
            ),
        }

        # Log validation results
        if is_valid:
            if warnings:
                self._logger.info(
                    f"[AuthConfigManager] Auth config validation completed with {len(warnings)} warnings"
                )
            else:
                self._logger.debug("[AuthConfigManager] Auth config validation passed")
        else:
            self._logger.error(
                f"[AuthConfigManager] Auth config validation failed with {len(errors)} errors"
            )

        return {
            "valid": is_valid,
            "warnings": warnings,
            "errors": errors,
            "summary": summary,
        }
