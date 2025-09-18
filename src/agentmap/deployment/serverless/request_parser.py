"""
Request parser for serverless deployment handlers.

This is a stub implementation to resolve import dependencies.
"""

from typing import Any, Dict


class RequestParser:
    """Request parser for handling different event formats."""

    @staticmethod
    def get_http_method(event: Dict[str, Any]) -> str:
        """Get HTTP method from event."""
        return event.get("httpMethod", "POST")

    @staticmethod
    def parse_json_body(body: str) -> Dict[str, Any]:
        """Parse JSON body from string."""
        import json

        try:
            return json.loads(body) if body else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def extract_query_params(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract query parameters from event."""
        return event.get("queryStringParameters") or {}

    @staticmethod
    def extract_path_params(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract path parameters from event."""
        return event.get("pathParameters") or {}
