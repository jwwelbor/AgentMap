"""Version-qualified SDK construction for pre-parse governed body observation."""

import asyncio
from functools import cached_property
from importlib.metadata import version
from threading import Lock
from typing import Any, Callable

import httpx

from agentmap.async_lifecycle import await_terminal_task, create_task_or_close
from agentmap.exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMLifecycleCleanupError,
)
from agentmap.services.llm.observed_transports import (
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
        self._state = "open"
        self._close_task: asyncio.Task[None] | None = None
        self._sync_retry_safe: dict[int, bool] = {}
        self._async_retry_safe: dict[int, bool] = {}
        self._sync_failures: dict[int, BaseException] = {}
        self._async_failures: dict[int, BaseException] = {}
        self._cleanup_error: LLMLifecycleCleanupError | None = None

    def create_sync(
        self, build: Callable[[], Any], *, retry_safe_close: bool = False
    ) -> Any:
        with self._lock:
            if self._state != "open":
                raise LLMConfigurationError("Governed client owner is shut down")
            client = build()
            self.sync.append(client)
            self._sync_retry_safe[id(client)] = retry_safe_close
            return client

    def create_async(
        self, build: Callable[[], Any], *, retry_safe_close: bool = False
    ) -> Any:
        with self._lock:
            if self._state != "open":
                raise LLMConfigurationError("Governed client owner is shut down")
            client = build()
            self.async_.append(client)
            self._async_retry_safe[id(client)] = retry_safe_close
            return client

    def create_shared(
        self,
        build: Callable[[], Any],
        *,
        retry_safe_sync_close: bool = False,
        retry_safe_async_close: bool = False,
    ) -> Any:
        with self._lock:
            if self._state != "open":
                raise LLMConfigurationError("Governed client owner is shut down")
            client = build()
            self.sync.append(client)
            self.async_.append(client)
            self._sync_retry_safe[id(client)] = retry_safe_sync_close
            self._async_retry_safe[id(client)] = retry_safe_async_close
            return client

    async def aclose(self) -> None:
        """Retain unfinished close obligations until they actually complete."""
        with self._lock:
            if self._state == "closed":
                return
            task = self._close_task
            if task is not None and not task.done():
                pass
            elif task is not None:
                if not self._has_retryable_failures_locked():
                    assert self._cleanup_error is not None
                    raise self._cleanup_error
                self._state = "closing"
                task = create_task_or_close(self._close_all())
                self._close_task = task
            else:
                self._state = "closing"
                task = create_task_or_close(self._close_all())
                self._close_task = task
        outcome = await await_terminal_task(task)
        outcome.result()

    def _has_retryable_failures_locked(self) -> bool:
        return any(
            self._sync_retry_safe.get(id(resource), False)
            for resource in self.sync
            if id(resource) in self._sync_failures
        ) or any(
            self._async_retry_safe.get(id(resource), False)
            for resource in self.async_
            if id(resource) in self._async_failures
        )

    async def _close_all(self) -> None:
        await asyncio.sleep(0)
        with self._lock:
            sync, async_ = list(self.sync), list(self.async_)
        failures = self._close_sync_resources(sync)
        failures.extend(await self._close_async_resources(async_))
        cleanup_error: LLMLifecycleCleanupError | None
        with self._lock:
            if failures:
                self._state = "cleanup_failed"
                cleanup_error = LLMLifecycleCleanupError(
                    "resource_close", tuple(failures)
                )
                self._cleanup_error = cleanup_error
            else:
                self._state = "closed"
                self._cleanup_error = None
                cleanup_error = None
        if cleanup_error is not None:
            raise cleanup_error from None

    def _close_sync_resources(self, resources: list[Any]) -> list[BaseException]:
        failures: list[BaseException] = []
        for resource in resources:
            identity = id(resource)
            with self._lock:
                previous_failure = self._sync_failures.get(identity)
                retry_safe = self._sync_retry_safe.get(identity, False)
            if previous_failure is not None and not retry_safe:
                failures.append(previous_failure)
                continue
            try:
                resource.close()
            except BaseException as close_error:
                failures.append(close_error)
                with self._lock:
                    self._sync_failures[identity] = close_error
            else:
                self._remove_obligation(
                    self.sync, identity, self._sync_retry_safe, self._sync_failures
                )
        return failures

    async def _close_async_resources(self, resources: list[Any]) -> list[BaseException]:
        failures: list[BaseException] = []
        for resource in resources:
            identity = id(resource)
            with self._lock:
                previous_failure = self._async_failures.get(identity)
                retry_safe = self._async_retry_safe.get(identity, False)
            if previous_failure is not None and not retry_safe:
                failures.append(previous_failure)
                continue
            try:
                await resource.aclose()
            except BaseException as close_error:
                failures.append(close_error)
                with self._lock:
                    self._async_failures[identity] = close_error
            else:
                self._remove_obligation(
                    self.async_, identity, self._async_retry_safe, self._async_failures
                )
        return failures

    def _remove_obligation(
        self,
        resources: list[Any],
        identity: int,
        retry_safe: dict[int, bool],
        failures: dict[int, BaseException],
    ) -> None:
        with self._lock:
            for index, resource in enumerate(resources):
                if id(resource) == identity:
                    del resources[index]
                    break
            retry_safe.pop(identity, None)
            failures.pop(identity, None)


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
