"""Version-qualified SDK construction for pre-parse governed body observation."""

from functools import cached_property
from importlib.metadata import version
from typing import Any

import httpx

from agentmap.exceptions import LLMDependencyError
from agentmap.services.llm.response_observer import ObservedTransport

# These exact generations were inspected and exercised with real wrappers.
QUALIFIED_VERSIONS = {
    "openai": {"langchain-openai": "1.1.14", "openai": "2.32.0"},
    "anthropic": {"langchain-anthropic": "0.3.21", "anthropic": "0.75.0"},
    "google": {"langchain-google-genai": "4.0.0", "google-genai": "1.55.0"},
}


def qualify_observation(provider: str) -> None:
    for package, qualified in QUALIFIED_VERSIONS[provider].items():
        if version(package) != qualified:
            raise LLMDependencyError(
                "Governed single-dispatch response observation requires "
                f"qualified {package}=={qualified}"
            )


def observed_http_clients() -> tuple[httpx.Client, httpx.AsyncClient]:
    return (
        httpx.Client(transport=ObservedTransport()),
        httpx.AsyncClient(transport=ObservedTransport()),
    )


def observed_anthropic_client(kwargs: dict[str, Any]) -> Any:
    import anthropic
    from langchain_anthropic import ChatAnthropic

    class ObservedChatAnthropic(ChatAnthropic):
        # The qualified wrapper offers no public SDK HTTP-client field. These
        # two construction-only overrides leave generation/parsing untouched.
        @cached_property
        def _client(self) -> anthropic.Client:
            return anthropic.Client(
                **self._client_params,
                http_client=httpx.Client(transport=ObservedTransport()),
            )

        @cached_property
        def _async_client(self) -> anthropic.AsyncClient:
            return anthropic.AsyncClient(
                **self._client_params,
                http_client=httpx.AsyncClient(transport=ObservedTransport()),
            )

    return ObservedChatAnthropic(**kwargs)
