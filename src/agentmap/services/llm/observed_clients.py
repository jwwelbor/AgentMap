"""Version-qualified SDK construction for pre-parse governed body observation."""

from functools import cached_property
from importlib.metadata import version
from threading import Lock
from typing import Any, Callable

import httpx

from agentmap.exceptions import LLMConfigurationError, LLMDependencyError
from agentmap.services.llm.response_observer import (
    ObservedAsyncTransport,
    ObservedSyncTransport,
    ObservedTransport,
)


class ObservedResources:
    """Explicit owner of governed HTTPX clients and Google's shared adapter."""

    def __init__(self) -> None:
        self.sync: list[Any] = []
        self.async_: list[Any] = []
        self._lock = Lock()
        self._closed = False

    def create_sync(self, build: Callable[[], Any]) -> Any:
        with self._lock:
            if self._closed:
                raise LLMConfigurationError("Governed client owner is shut down")
            client = build()
            self.sync.append(client)
            return client

    def create_async(self, build: Callable[[], Any]) -> Any:
        with self._lock:
            if self._closed:
                raise LLMConfigurationError("Governed client owner is shut down")
            client = build()
            self.async_.append(client)
            return client

    def create_shared(self, build: Callable[[], Any]) -> Any:
        with self._lock:
            if self._closed:
                raise LLMConfigurationError("Governed client owner is shut down")
            client = build()
            self.sync.append(client)
            self.async_.append(client)
            return client

    async def aclose(self) -> None:
        with self._lock:
            self._closed = True
            sync, async_ = self.sync, self.async_
            self.sync, self.async_ = [], []
        failures = []
        for resource in sync:
            try:
                resource.close()
            except Exception as error:
                failures.append(error)
        for resource in async_:
            try:
                await resource.aclose()
            except Exception as error:
                failures.append(error)
        if failures:
            raise ExceptionGroup("governed HTTP resource shutdown failed", failures)


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
    owner: ObservedResources | None = None,
) -> tuple[httpx.Client, httpx.AsyncClient]:
    def make_sync() -> httpx.Client:
        return httpx.Client(transport=ObservedSyncTransport(proxy=proxy))

    def make_async() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=ObservedAsyncTransport(proxy=proxy))

    sync = owner.create_sync(make_sync) if owner is not None else make_sync()
    async_client = owner.create_async(make_async) if owner is not None else make_async()
    return sync, async_client


def governed_openai_kwargs(owner: ObservedResources | None = None) -> dict[str, Any]:
    qualify_observation("openai")
    sync_client, async_client = observed_http_clients(owner=owner)
    return {
        "max_retries": 0,
        "http_client": sync_client,
        "http_async_client": async_client,
    }


def governed_google_kwargs(owner: ObservedResources | None = None) -> dict[str, Any]:
    from importlib.metadata import version as wrapper_version

    # v4 uses google-genai HttpRetryOptions: max_retries counts total attempts.
    if wrapper_version("langchain-google-genai").split(".")[0] != "4":
        raise LLMDependencyError(
            "Governed Google single-dispatch calls require "
            "langchain-google-genai 4.x; qualify other implementations first"
        )
    qualify_observation("google")
    transport = owner.create_shared(ObservedTransport) if owner else ObservedTransport()
    return {
        "max_retries": 1,
        "client_args": {"transport": transport, "follow_redirects": False},
    }


def observed_anthropic_client(
    kwargs: dict[str, Any], owner: ObservedResources | None = None
) -> Any:
    import anthropic
    from langchain_anthropic import ChatAnthropic

    qualify_observation("anthropic")
    kwargs["max_retries"] = 0

    class ObservedChatAnthropic(ChatAnthropic):
        # The qualified wrapper offers no public SDK HTTP-client field. These
        # two construction-only overrides leave generation/parsing untouched.
        @cached_property
        def _client(self) -> anthropic.Client:
            def build() -> httpx.Client:
                return httpx.Client(
                    transport=ObservedSyncTransport(proxy=self.anthropic_proxy)
                )

            http_client = owner.create_sync(build) if owner else build()
            return anthropic.Client(
                **self._client_params,
                http_client=http_client,
            )

        @cached_property
        def _async_client(self) -> anthropic.AsyncClient:
            def build() -> httpx.AsyncClient:
                return httpx.AsyncClient(
                    transport=ObservedAsyncTransport(proxy=self.anthropic_proxy)
                )

            http_client = owner.create_async(build) if owner else build()
            return anthropic.AsyncClient(
                **self._client_params,
                http_client=http_client,
            )

    return ObservedChatAnthropic(**kwargs)
