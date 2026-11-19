"""Typed third-party and YAML configuration shapes for the auth commands."""

from importlib import import_module
from typing import IO, NotRequired, Protocol, TypedDict, cast


class _YamlModule(Protocol):
    """Small typed surface used from the dynamically loaded PyYAML module."""

    YAMLError: type[Exception]

    def safe_load(self, stream: IO[str]) -> object: ...

    def dump(
        self,
        data: object,
        stream: IO[str],
        *,
        default_flow_style: bool,
        sort_keys: bool,
        indent: int,
    ) -> None: ...


class APIKeyConfiguration(TypedDict):
    key: str
    permissions: list[str]
    user_id: str
    metadata: dict[str, str]
    expires_at: NotRequired[str]


# Keep the third-party surface constrained to the methods used by the CLI.
yaml = cast(_YamlModule, import_module("yaml"))
