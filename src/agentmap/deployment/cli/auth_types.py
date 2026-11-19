"""Typed authentication configuration shapes for the CLI commands."""

from typing import NotRequired, TypedDict


class APIKeyConfiguration(TypedDict):
    key: str
    permissions: list[str]
    user_id: str
    metadata: dict[str, str]
    expires_at: NotRequired[str]
