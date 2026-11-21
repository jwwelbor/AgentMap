import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from agentmap.services.llm.attempt_lifecycle import (
    file_attempt_logger,
    get_async_client,
)
from agentmap.services.llm_client_factory import LLMClientFactory


def test_single_dispatch_builds_and_caches_separately_from_default(monkeypatch):
    factory = LLMClientFactory(Mock())
    created = []

    def build(_provider, _config, _streaming=False, *, single_dispatch=False):
        client = object()
        created.append((client, single_dispatch))
        return client

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    config = {"api_key": "secret", "model": "model"}

    ordinary = factory.get_or_create_client("openai", config)
    logged = factory.get_or_create_client("openai", config, single_dispatch=True)

    assert ordinary is not logged
    assert created == [(ordinary, False), (logged, True)]
    assert (
        factory.get_or_create_client("openai", config, single_dispatch=True) is logged
    )


@pytest.mark.asyncio
async def test_file_logger_uses_ordinary_single_dispatch_client():
    factory = Mock()
    factory.get_or_create_client.return_value = object()
    token = file_attempt_logger.set(Mock())
    try:
        client = await get_async_client(factory, "openai", {"model": "model"})
    finally:
        file_attempt_logger.reset(token)

    assert client is factory.get_or_create_client.return_value
    factory.get_or_create_client.assert_called_once_with(
        "openai", {"model": "model"}, single_dispatch=True
    )
    factory.get_or_create_governed_client.assert_not_called()


@pytest.mark.parametrize(
    ("provider", "module_name", "class_name", "retry_setting"),
    [
        ("openai", "langchain_openai", "ChatOpenAI", 0),
        ("anthropic", None, None, 0),
        ("google", "langchain_google_genai", "ChatGoogleGenerativeAI", 1),
    ],
)
def test_provider_builders_configure_one_sdk_attempt(
    monkeypatch, provider, module_name, class_name, retry_setting
):
    send = Mock(side_effect=RuntimeError("provider failed"))
    constructed = {}

    class FakeClient:
        def __init__(self, **kwargs):
            constructed.update(kwargs)

        def invoke(self, _messages):
            max_retries = constructed["max_retries"]
            total_attempts = max_retries if provider == "google" else max_retries + 1
            for attempt in range(total_attempts):
                try:
                    return send()
                except RuntimeError:
                    if attempt + 1 == total_attempts:
                        raise

    factory = LLMClientFactory(Mock())
    if module_name:
        module = ModuleType(module_name)
        setattr(module, class_name, FakeClient)
        monkeypatch.setitem(sys.modules, module_name, module)
    else:
        monkeypatch.setattr(factory, "_load_anthropic_client_class", lambda: FakeClient)

    client = factory._create_langchain_client(
        provider,
        {"api_key": "key", "model": "model"},
        single_dispatch=True,
    )

    assert constructed["max_retries"] == retry_setting
    with pytest.raises(RuntimeError, match="provider failed"):
        client.invoke([])
    send.assert_called_once_with()
