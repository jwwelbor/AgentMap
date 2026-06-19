"""
Unit tests for stream_seam.py — dispatch and Protocol shape.

Covers TC-F01-DISP-1 through TC-F01-DISP-4 (Section 5 of test-plan.md).
These tests verify that:
  - stream_provider() dispatches to the correct per-provider seam class
  - StreamSeamProtocol is @runtime_checkable with the required members
  - Each per-provider class exposes provider_name and passes isinstance

Framework: pytest + unittest.IsolatedAsyncioTestCase for async dispatch tests.
No real API calls — seam classes are stubbed via sys.modules patching.
"""

import sys
import unittest
from typing import Any, AsyncIterator, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from agentmap.exceptions import LLMDependencyError, LLMServiceError
from agentmap.models.llm_execution import LLMStreamChunk
from agentmap.services.protocols.service_protocols import StreamSeamProtocol

# ---------------------------------------------------------------------------
# Helpers — async iterator fake
# ---------------------------------------------------------------------------


class _AsyncIteratorFake:
    """Simple async iterator that yields scripted items."""

    def __init__(self, items):
        self._items = list(items)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


# ---------------------------------------------------------------------------
# TC-F01-DISP-4 — Protocol shape and runtime_checkable
# ---------------------------------------------------------------------------


class TestStreamSeamProtocolShape:
    """TC-F01-DISP-4: StreamSeamProtocol is @runtime_checkable with correct surface."""

    def test_protocol_is_runtime_checkable(self):
        """isinstance check does not raise TypeError — Protocol is @runtime_checkable."""
        try:
            result = isinstance(object(), StreamSeamProtocol)
        except TypeError:
            pytest.fail("StreamSeamProtocol is not @runtime_checkable")
        assert result is False

    def test_protocol_has_stream_method(self):
        """Protocol declares a stream() method."""
        assert hasattr(
            StreamSeamProtocol, "stream"
        ), "StreamSeamProtocol must declare a 'stream' method"

    def test_protocol_has_provider_name_member(self):
        """Protocol declares provider_name as a member (via __annotations__)."""
        annotations = getattr(StreamSeamProtocol, "__annotations__", {})
        assert (
            "provider_name" in annotations
        ), "StreamSeamProtocol must declare 'provider_name: str'"

    def test_minimal_conforming_object_passes_isinstance(self):
        """An object with provider_name + stream() satisfies StreamSeamProtocol."""

        class _MinimalSeam:
            provider_name: str = "test"

            def stream(
                self,
                messages: List[Any],
                params: Dict[str, Any],
                *,
                client: Optional[Any] = None,
                credentials: Optional[Dict[str, Any]] = None,
            ) -> AsyncIterator[LLMStreamChunk]:  # type: ignore[empty-body]
                ...

        assert isinstance(_MinimalSeam(), StreamSeamProtocol)

    def test_missing_provider_name_fails_isinstance(self):
        """Object missing provider_name does NOT satisfy StreamSeamProtocol."""

        class _NoName:
            def stream(self, messages, params, *, client=None, credentials=None): ...

        assert isinstance(_NoName(), StreamSeamProtocol) is False

    def test_missing_stream_method_fails_isinstance(self):
        """Object missing stream() does NOT satisfy StreamSeamProtocol."""

        class _NoStream:
            provider_name: str = "test"

        assert isinstance(_NoStream(), StreamSeamProtocol) is False


# ---------------------------------------------------------------------------
# TC-F01-DISP-1, DISP-2 — per-provider class isinstance checks
# ---------------------------------------------------------------------------


class TestPerProviderClassConformance:
    """TC-F01-DISP-4: Each seam class exposes provider_name and conforms to protocol."""

    def test_anthropic_seam_satisfies_protocol(self):
        """AnthropicStreamSeam must satisfy StreamSeamProtocol."""
        from agentmap.services.llm.stream_seam import AnthropicStreamSeam

        # Build a fake anthropic module so __init__ doesn't raise LLMDependencyError
        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            seam = AnthropicStreamSeam()
        assert isinstance(seam, StreamSeamProtocol)

    def test_anthropic_seam_has_provider_name_anthropic(self):
        """AnthropicStreamSeam.provider_name == 'anthropic'."""
        from agentmap.services.llm.stream_seam import AnthropicStreamSeam

        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            seam = AnthropicStreamSeam()
        assert seam.provider_name == "anthropic"

    def test_openai_seam_satisfies_protocol(self):
        """OpenAIStreamSeam must satisfy StreamSeamProtocol."""
        from agentmap.services.llm.stream_seam import OpenAIStreamSeam

        mock_openai = MagicMock()
        with patch.dict(sys.modules, {"openai": mock_openai}):
            seam = OpenAIStreamSeam()
        assert isinstance(seam, StreamSeamProtocol)

    def test_openai_seam_has_provider_name_openai(self):
        """OpenAIStreamSeam.provider_name == 'openai'."""
        from agentmap.services.llm.stream_seam import OpenAIStreamSeam

        mock_openai = MagicMock()
        with patch.dict(sys.modules, {"openai": mock_openai}):
            seam = OpenAIStreamSeam()
        assert seam.provider_name == "openai"

    def test_langchain_fallback_seam_satisfies_protocol(self):
        """LangChainFallbackStreamSeam must satisfy StreamSeamProtocol."""
        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        seam = LangChainFallbackStreamSeam()
        assert isinstance(seam, StreamSeamProtocol)

    def test_langchain_fallback_seam_has_provider_name(self):
        """LangChainFallbackStreamSeam exposes a non-empty provider_name."""
        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        seam = LangChainFallbackStreamSeam()
        assert isinstance(seam.provider_name, str)
        assert seam.provider_name  # non-empty


# ---------------------------------------------------------------------------
# TC-F01-DISP-1, DISP-2, DISP-3 — dispatch routing
# ---------------------------------------------------------------------------


class TestStreamProviderDispatch(unittest.IsolatedAsyncioTestCase):
    """TC-F01-DISP-1/2/3: stream_provider dispatches by provider key."""

    async def test_disp1_anthropic_key_dispatches_to_anthropic_seam(self):
        """TC-F01-DISP-1: provider='anthropic' routes to AnthropicStreamSeam."""
        from agentmap.services.llm.stream_seam import stream_provider

        # Fake one LLMStreamChunk to yield
        fake_chunk = LLMStreamChunk(text_delta="hello", chunk_index=0, is_final=False)
        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=1,
            is_final=True,
            finish_reason="stop",
            resolved_provider="anthropic",
            resolved_model="claude-3",
        )

        async def fake_anthropic_stream(
            messages, params, *, client=None, credentials=None
        ):
            yield fake_chunk
            yield terminal

        with patch(
            "agentmap.services.llm.stream_seam.AnthropicStreamSeam.stream",
            side_effect=fake_anthropic_stream,
        ) as mock_stream:
            messages = [{"role": "user", "content": "hi"}]
            params: Dict[str, Any] = {}
            chunks = []
            async for chunk in stream_provider("anthropic", messages, params):
                chunks.append(chunk)

        mock_stream.assert_called_once()
        assert len(chunks) == 2
        assert chunks[0].text_delta == "hello"
        assert chunks[1].is_final is True
        assert chunks[1].resolved_provider == "anthropic"

    async def test_disp2_openai_key_dispatches_to_openai_seam(self):
        """TC-F01-DISP-2: provider='openai' routes to OpenAIStreamSeam."""
        from agentmap.services.llm.stream_seam import stream_provider

        fake_chunk = LLMStreamChunk(text_delta="world", chunk_index=0, is_final=False)
        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=1,
            is_final=True,
            finish_reason="stop",
            resolved_provider="openai",
            resolved_model="gpt-4o",
        )

        async def fake_openai_stream(
            messages, params, *, client=None, credentials=None
        ):
            yield fake_chunk
            yield terminal

        with patch(
            "agentmap.services.llm.stream_seam.OpenAIStreamSeam.stream",
            side_effect=fake_openai_stream,
        ) as mock_stream:
            messages = [{"role": "user", "content": "hi"}]
            chunks = []
            async for chunk in stream_provider("openai", messages, {}):
                chunks.append(chunk)

        mock_stream.assert_called_once()
        assert len(chunks) == 2
        assert chunks[0].text_delta == "world"
        assert chunks[1].resolved_provider == "openai"

    async def test_disp3_unknown_provider_falls_back_to_langchain(self):
        """TC-F01-DISP-3: unknown provider key falls back to LangChainFallbackStreamSeam."""
        from agentmap.services.llm.stream_seam import stream_provider

        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            finish_reason="stop",
            resolved_provider="google",
            resolved_model="gemini-pro",
        )

        async def fake_lc_stream(messages, params, *, client=None, credentials=None):
            yield terminal

        with patch(
            "agentmap.services.llm.stream_seam.LangChainFallbackStreamSeam.stream",
            side_effect=fake_lc_stream,
        ) as mock_stream:
            messages = [{"role": "user", "content": "hi"}]
            chunks = []
            async for chunk in stream_provider("google", messages, {}):
                chunks.append(chunk)

        mock_stream.assert_called_once()
        assert len(chunks) == 1
        assert chunks[0].is_final is True

    async def test_dispatch_passes_messages_and_params(self):
        """Dispatch passes messages and params through to the seam unchanged."""
        from agentmap.services.llm.stream_seam import stream_provider

        received: Dict[str, Any] = {}

        async def capture_stream(messages, params, *, client=None, credentials=None):
            received["messages"] = messages
            received["params"] = params
            yield LLMStreamChunk(text_delta="", chunk_index=0, is_final=True)

        messages = [{"role": "user", "content": "test message"}]
        params = {"model": "claude-sonnet-4-6", "max_tokens": 100}

        with patch(
            "agentmap.services.llm.stream_seam.AnthropicStreamSeam.stream",
            side_effect=capture_stream,
        ):
            async for _ in stream_provider("anthropic", messages, params):
                pass

        assert received["messages"] is messages
        assert received["params"] is params

    async def test_dispatch_passes_client_and_credentials_kwargs(self):
        """Dispatch forwards optional client and credentials kwargs to the seam."""
        from agentmap.services.llm.stream_seam import stream_provider

        received: Dict[str, Any] = {}

        async def capture_stream(messages, params, *, client=None, credentials=None):
            received["client"] = client
            received["credentials"] = credentials
            yield LLMStreamChunk(text_delta="", chunk_index=0, is_final=True)

        fake_client = MagicMock()
        fake_creds = {"api_key": "test-key"}

        with patch(
            "agentmap.services.llm.stream_seam.AnthropicStreamSeam.stream",
            side_effect=capture_stream,
        ):
            async for _ in stream_provider(
                "anthropic",
                [{"role": "user", "content": "hi"}],
                {},
                client=fake_client,
                credentials=fake_creds,
            ):
                pass

        assert received["client"] is fake_client
        assert received["credentials"] is fake_creds


# ---------------------------------------------------------------------------
# TC-F01-DEP-1, DEP-2 — Import gating (Section 7 of test-plan.md)
# ---------------------------------------------------------------------------


class TestImportGating:
    """TC-F01-DEP-1/2: Missing native SDK raises LLMDependencyError, not bare ImportError."""

    def test_anthropic_seam_raises_dependency_error_when_sdk_missing(self):
        """TC-F01-DEP-1: constructing AnthropicStreamSeam without anthropic pkg raises LLMDependencyError."""
        import builtins
        import importlib

        original_import = builtins.__import__

        def import_fails_for_anthropic(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return original_import(name, *args, **kwargs)

        seam_module_key = "agentmap.services.llm.stream_seam"

        # Remove any cached anthropic from sys.modules
        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key == "anthropic" or key.startswith("anthropic."):
                saved_modules[key] = sys.modules.pop(key)

        saved_seam = sys.modules.pop(seam_module_key, None)

        try:
            with patch("builtins.__import__", side_effect=import_fails_for_anthropic):
                if seam_module_key in sys.modules:
                    del sys.modules[seam_module_key]

                seam_mod = importlib.import_module(seam_module_key)
                AnthropicStreamSeam = seam_mod.AnthropicStreamSeam

                with pytest.raises(LLMDependencyError):
                    AnthropicStreamSeam()
        finally:
            sys.modules.update(saved_modules)
            if saved_seam is not None:
                sys.modules[seam_module_key] = saved_seam
            else:
                sys.modules.pop(seam_module_key, None)

    def test_openai_seam_raises_dependency_error_when_sdk_missing(self):
        """TC-F01-DEP-2: constructing OpenAIStreamSeam without openai pkg raises LLMDependencyError."""
        import builtins
        import importlib

        original_import = builtins.__import__

        def import_fails_for_openai(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("No module named 'openai'")
            return original_import(name, *args, **kwargs)

        seam_module_key = "agentmap.services.llm.stream_seam"

        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key == "openai" or key.startswith("openai."):
                saved_modules[key] = sys.modules.pop(key)

        saved_seam = sys.modules.pop(seam_module_key, None)

        try:
            with patch("builtins.__import__", side_effect=import_fails_for_openai):
                if seam_module_key in sys.modules:
                    del sys.modules[seam_module_key]

                seam_mod = importlib.import_module(seam_module_key)
                OpenAIStreamSeam = seam_mod.OpenAIStreamSeam

                with pytest.raises(LLMDependencyError):
                    OpenAIStreamSeam()
        finally:
            sys.modules.update(saved_modules)
            if saved_seam is not None:
                sys.modules[seam_module_key] = saved_seam
            else:
                sys.modules.pop(seam_module_key, None)

    def test_dependency_error_is_subclass_of_llm_service_error(self):
        """LLMDependencyError is a subclass of LLMServiceError (hierarchy check)."""
        assert issubclass(LLMDependencyError, LLMServiceError)
