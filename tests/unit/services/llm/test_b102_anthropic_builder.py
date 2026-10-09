"""The governed Anthropic path must not resolve ordinary wrappers."""

import builtins
from unittest.mock import Mock

from agentmap.services import llm_client_factory
from agentmap.services.llm_client_factory import LLMClientFactory


def test_governed_anthropic_builder_skips_ordinary_wrapper_imports__b102(
    monkeypatch,
):
    owner, expected = Mock(), object()
    observed = []
    real_import = builtins.__import__

    def observe(kwargs, actual_owner):
        observed.append((kwargs, actual_owner))
        return expected

    def reject_ordinary_wrapper_import(name, *args, **kwargs):
        if name == "langchain_anthropic" or name.startswith(
            ("langchain_community", "langchain.chat_models")
        ):
            raise AssertionError(f"ordinary Anthropic wrapper import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(llm_client_factory, "observed_anthropic_client", observe)
    monkeypatch.setattr(builtins, "__import__", reject_ordinary_wrapper_import)
    factory = LLMClientFactory(Mock())

    actual = factory._create_anthropic_client(
        "api-key",
        "model-name",
        0.25,
        max_tokens=17,
        streaming=True,
        governed=True,
        owner=owner,
    )

    assert actual is expected
    assert observed == [
        (
            {
                "model": "model-name",
                "temperature": 0.25,
                "anthropic_api_key": "api-key",
                "max_tokens": 17,
                "stream_usage": True,
            },
            owner,
        )
    ]
