import json
from typing import Any, Dict


class RequestParser:
    """Utility class for parsing different request formats."""

    @staticmethod
    def parse_json_body(body: str) -> Dict[str, Any]:
        """Parse JSON body with error handling."""
        if not body:
            return {}

        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in request body: {e}")

    @staticmethod
    def extract_query_params(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract query parameters from event."""
        return event.get("queryStringParameters") or {}

    @staticmethod
    def extract_path_params(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract path parameters from event."""
        return event.get("pathParameters") or {}

    @staticmethod
    def get_http_method(event: Dict[str, Any]) -> str:
        """Get HTTP method from event."""
        return event.get("httpMethod", "POST").upper()
