"""
FastAPI Middleware

This package contains FastAPI-specific middleware implementations
including authentication, error handling, and request processing.
"""

from .auth import FastAPIAuthAdapter, create_auth_adapter

__all__ = ["FastAPIAuthAdapter", "create_auth_adapter"]
