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


def observed_http_clients(
    proxy: str | None = None,
) -> tuple[httpx.Client, httpx.AsyncClient]:
    return (
        httpx.Client(transport=ObservedTransport(proxy=proxy)),
        httpx.AsyncClient(transport=ObservedTransport(proxy=proxy)),
    )


def governed_openai_kwargs() -> dict[str, Any]:
    qualify_observation("openai")
    sync_client, async_client = observed_http_clients()
    return {
        "max_retries": 0,
        "http_client": sync_client,
        "http_async_client": async_client,
    }


def governed_google_kwargs() -> dict[str, Any]:
    from importlib.metadata import version as wrapper_version

    # v4 uses google-genai HttpRetryOptions: max_retries counts total attempts.
    if wrapper_version("langchain-google-genai").split(".")[0] != "4":
        raise LLMDependencyError(
            "Governed Google single-dispatch calls require "
            "langchain-google-genai 4.x; qualify other implementations first"
        )
    qualify_observation("google")
    return {
        "max_retries": 1,
        "client_args": {"transport": ObservedTransport(), "follow_redirects": False},
    }


def observed_anthropic_client(kwargs: dict[str, Any]) -> Any:
    import anthropic
    from langchain_anthropic import ChatAnthropic

    qualify_observation("anthropic")
    kwargs["max_retries"] = 0

    class ObservedChatAnthropic(ChatAnthropic):
        # The qualified wrapper offers no public SDK HTTP-client field. These
        # two construction-only overrides leave generation/parsing untouched.
        @cached_property
        def _client(self) -> anthropic.Client:
            return anthropic.Client(
                **self._client_params,
                http_client=httpx.Client(
                    transport=ObservedTransport(proxy=self.anthropic_proxy)
                ),
            )

        @cached_property
        def _async_client(self) -> anthropic.AsyncClient:
            return anthropic.AsyncClient(
                **self._client_params,
                http_client=httpx.AsyncClient(
                    transport=ObservedTransport(proxy=self.anthropic_proxy)
                ),
            )

    return ObservedChatAnthropic(**kwargs)
