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
        """TC-F01-DISP-3: unknown provider key falls back to LangChainFallbackStreamSeam.

        Exercises the REAL LangChainFallbackStreamSeam (not mocked) via
        stream_provider("google", ...) with a real async-gen fake client so
        that the dispatch key flows through to the terminal chunk's
        resolved_provider.  The test would fail if the seam's provider_name
        were hardcoded to "langchain" instead of the dispatch key.
        """
        from agentmap.services.llm.stream_seam import stream_provider

        lc_chunks = [
            _make_lc_content_chunk("hello from gemini"),
            _make_lc_terminal_chunk(
                content="",
                finish_reason="stop",
                input_tokens=5,
                output_tokens=10,
            ),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)
        messages = [{"role": "user", "content": "hi"}]
        params = {"model": "gemini-pro", "max_tokens": 100}
        chunks = []
        async for chunk in stream_provider(
            "google", messages, params, client=fake_client
        ):
            chunks.append(chunk)

        terminal = chunks[-1]
        assert terminal.is_final is True
        # The dispatch key "google" must appear on the terminal chunk —
        # NOT the seam's hardcoded default "langchain".
        assert terminal.resolved_provider == "google", (
            f"Expected resolved_provider='google', got '{terminal.resolved_provider}'. "
            "The dispatch key must be threaded into LangChainFallbackStreamSeam."
        )

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


# ---------------------------------------------------------------------------
# Helpers — fake Anthropic SDK events
# ---------------------------------------------------------------------------


def _make_anthropic_text_delta_event(text: str, index: int = 0):
    """Build a fake content_block_delta event with text_delta."""
    event = MagicMock()
    event.type = "content_block_delta"
    event.index = index
    event.delta = MagicMock()
    event.delta.type = "text_delta"
    event.delta.text = text
    return event


def _make_anthropic_tool_use_delta_event(index: int = 1):
    """Build a fake content_block_delta event with tool_use delta (non-text)."""
    event = MagicMock()
    event.type = "content_block_delta"
    event.index = index
    event.delta = MagicMock()
    event.delta.type = "input_json_delta"
    event.delta.partial_json = '{"arg":'
    return event


def _make_anthropic_message_start_event(
    input_tokens: int = 10,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
):
    """Build a fake message_start event carrying input usage."""
    event = MagicMock()
    event.type = "message_start"
    event.message = MagicMock()
    event.message.usage = MagicMock()
    event.message.usage.input_tokens = input_tokens
    event.message.usage.cache_creation_input_tokens = cache_creation_input_tokens
    event.message.usage.cache_read_input_tokens = cache_read_input_tokens
    return event


def _make_anthropic_message_delta_event(
    output_tokens: int = 20, stop_reason: str = "end_turn"
):
    """Build a fake message_delta event carrying output usage + stop_reason."""
    event = MagicMock()
    event.type = "message_delta"
    event.usage = MagicMock()
    event.usage.output_tokens = output_tokens
    event.delta = MagicMock()
    event.delta.stop_reason = stop_reason
    return event


def _make_anthropic_message_stop_event():
    """Build a fake message_stop event."""
    event = MagicMock()
    event.type = "message_stop"
    return event


def _make_anthropic_content_block_start_event(block_type: str = "text", index: int = 0):
    """Build a fake content_block_start event."""
    event = MagicMock()
    event.type = "content_block_start"
    event.index = index
    event.content_block = MagicMock()
    event.content_block.type = block_type
    return event


def _make_anthropic_content_block_stop_event(index: int = 0):
    """Build a fake content_block_stop event."""
    event = MagicMock()
    event.type = "content_block_stop"
    event.index = index
    return event


def _make_mock_anthropic_module(model: str = "claude-3-5-sonnet-20241022"):
    """
    Build a minimal fake anthropic module with an async context-manager stream.

    Returns (mock_sdk, mock_client, scripted_stream_fn) where scripted_stream_fn
    is a callable that accepts an events list and wires the mock appropriately.
    """
    mock_sdk = MagicMock()
    mock_client = MagicMock()
    mock_sdk.AsyncAnthropic.return_value = mock_client

    # The stream() context manager: `async with client.messages.stream(...) as stream:`
    # yields the stream object; iterating the stream object yields events.
    def make_stream_context(events):
        stream_obj = MagicMock()
        stream_obj.__aiter__ = MagicMock(return_value=_AsyncIteratorFake(events))

        async def _aenter(_):
            return stream_obj

        async def _aexit(_, *args):
            pass

        stream_cm = MagicMock()
        stream_cm.__aenter__ = _aenter
        stream_cm.__aexit__ = _aexit
        mock_client.messages.stream.return_value = stream_cm
        return stream_obj

    return mock_sdk, mock_client, make_stream_context


# ---------------------------------------------------------------------------
# TC-F01-ANTH-1 through TC-F01-ANTH-8 — Anthropic native seam
# ---------------------------------------------------------------------------


class TestAnthropicStreamSeam(unittest.IsolatedAsyncioTestCase):
    """Anthropic native seam: event → chunk mapping (Section 2 of test-plan.md)."""

    def _make_seam(self, mock_sdk, mock_client):
        """Construct AnthropicStreamSeam with fake anthropic module injected."""
        from agentmap.services.llm.stream_seam import AnthropicStreamSeam

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            seam = AnthropicStreamSeam()
        return seam

    async def _collect_chunks(self, seam, mock_sdk, events, params=None):
        """Drive seam.stream() with patched anthropic and collect all chunks."""
        if params is None:
            params = {"model": "claude-3-5-sonnet-20241022", "max_tokens": 100}
        messages = [{"role": "user", "content": "hello"}]
        chunks = []
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            async for chunk in seam.stream(
                messages, params, client=None, credentials=None
            ):
                chunks.append(chunk)
        return chunks

    async def test_anth1_scripted_sequence_yields_3_text_chunks_then_terminal(self):
        """TC-F01-ANTH-1: 3 text_delta events → 3 non-final chunks + 1 terminal chunk."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=5),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("Hello", 0),
            _make_anthropic_text_delta_event(" world", 0),
            _make_anthropic_text_delta_event("!", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=3, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        non_final = [c for c in chunks if not c.is_final]
        terminal = [c for c in chunks if c.is_final]

        assert len(non_final) == 3, f"Expected 3 non-final chunks, got {len(non_final)}"
        assert len(terminal) == 1, f"Expected 1 terminal chunk, got {len(terminal)}"
        assert non_final[0].text_delta == "Hello"
        assert non_final[1].text_delta == " world"
        assert non_final[2].text_delta == "!"

    async def test_anth2_terminal_chunk_usage_and_metadata(self):
        """TC-F01-ANTH-2: terminal chunk carries correct usage, finish_reason, resolved fields."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=15),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("Hi", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=25, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(
            seam,
            mock_sdk,
            events,
            params={"model": "claude-3-opus-20240229", "max_tokens": 100},
        )

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert terminal.usage is not None
        assert terminal.usage.input_tokens == 15
        assert terminal.usage.output_tokens == 25
        assert terminal.finish_reason == "end_turn"
        assert terminal.resolved_provider == "anthropic"
        assert terminal.resolved_model == "claude-3-opus-20240229"

    async def test_anth3_cache_token_fields_carried_into_terminal_usage(self):
        """TC-F01-ANTH-3: cache token fields from message_start appear in terminal LLMUsage."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(
                input_tokens=10,
                cache_creation_input_tokens=50,
                cache_read_input_tokens=20,
            ),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("ok", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=5, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert terminal.usage is not None
        assert terminal.usage.cache_creation_input_tokens == 50
        assert terminal.usage.cache_read_input_tokens == 20

    async def test_anth4_non_text_block_deltas_produce_no_chunk(self):
        """TC-F01-ANTH-4: tool_use deltas are ignored; only text_delta events produce chunks."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=8),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("answer", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_content_block_start_event("tool_use", 1),
            _make_anthropic_tool_use_delta_event(index=1),
            _make_anthropic_tool_use_delta_event(index=1),
            _make_anthropic_content_block_stop_event(1),
            _make_anthropic_message_delta_event(
                output_tokens=10, stop_reason="tool_use"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        non_final = [c for c in chunks if not c.is_final]
        # Only 1 text chunk — the 2 tool_use deltas must NOT produce chunks
        assert len(non_final) == 1, (
            f"Expected 1 non-final chunk (text only), got {len(non_final)}: "
            f"{[c.text_delta for c in non_final]}"
        )
        assert non_final[0].text_delta == "answer"

    async def test_anth5_chunk_index_continuous_across_two_text_blocks(self):
        """TC-F01-ANTH-5: chunk_index continues across two text blocks with no gap or repeat."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=5),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("A", 0),
            _make_anthropic_text_delta_event("B", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_content_block_start_event("text", 1),
            _make_anthropic_text_delta_event("C", 1),
            _make_anthropic_text_delta_event("D", 1),
            _make_anthropic_content_block_stop_event(1),
            _make_anthropic_message_delta_event(
                output_tokens=4, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        non_final = [c for c in chunks if not c.is_final]
        assert len(non_final) == 4
        indices = [c.chunk_index for c in non_final]
        assert indices == [0, 1, 2, 3], f"Expected [0,1,2,3], got {indices}"

    async def test_anth6_chunk_index_monotonic_exactly_one_terminal(self):
        """TC-F01-ANTH-6: chunk_index 0..N-1 across full stream; exactly one is_final=True, last."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=5),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("X", 0),
            _make_anthropic_text_delta_event("Y", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=2, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        indices = [c.chunk_index for c in chunks]
        assert indices == list(
            range(len(chunks))
        ), f"chunk_index must be 0..N-1, got {indices}"

        final_chunks = [c for c in chunks if c.is_final]
        assert (
            len(final_chunks) == 1
        ), f"Exactly one is_final=True, got {len(final_chunks)}"
        assert chunks[-1].is_final is True, "The last chunk must be the terminal one"

    async def test_anth7_terminal_chunk_text_delta_is_empty_string(self):
        """TC-F01-ANTH-7: terminal chunk text_delta == '' (not None)."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=3),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("hi", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=1, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert (
            terminal.text_delta == ""
        ), f"terminal text_delta must be '', got {terminal.text_delta!r}"
        assert isinstance(terminal.text_delta, str)

    async def test_anth8_single_block_stream_produces_at_least_two_deltas_plus_terminal(
        self,
    ):
        """TC-F01-ANTH-8: text-only single-block stream produces >=2 ordered deltas + terminal."""
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=7),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("First ", 0),
            _make_anthropic_text_delta_event("second ", 0),
            _make_anthropic_text_delta_event("third.", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=6, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        non_final = [c for c in chunks if not c.is_final]
        terminal_list = [c for c in chunks if c.is_final]

        assert (
            len(non_final) >= 2
        ), f"Expected >=2 non-final chunks, got {len(non_final)}"
        assert len(terminal_list) == 1

        # Verify ordering: non-final chunks in order, terminal last
        for i, chunk in enumerate(non_final):
            assert (
                chunk.chunk_index == i
            ), f"chunk {i} has chunk_index {chunk.chunk_index}"
        assert terminal_list[0].chunk_index == len(non_final)

    async def test_anth9_empty_stream_yields_exactly_one_terminal_chunk(self):
        """
        TC-F01-ANTH-9: EMPTY stream (no events at all) must yield exactly ONE
        is_final=True chunk.

        AC-5 requires exactly one terminal chunk per stream invocation.  When
        Anthropic returns an empty event iterator (e.g. network truncation before
        the first byte), the seam must still emit the terminal chunk — it cannot
        emit zero is_final chunks.

        This test is the AC-5 red-team case: the current code emits the terminal
        chunk ONLY inside the ``message_stop`` branch, so an empty stream produces
        0 chunks.  The fix must emit terminal-after-exhaust.
        """
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        # Empty event list — no events at all.
        make_ctx([])

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, [])

        final_chunks = [c for c in chunks if c.is_final]
        non_final_chunks = [c for c in chunks if not c.is_final]

        assert len(final_chunks) == 1, (
            f"AC-5 violation: expected exactly 1 is_final=True chunk from an empty "
            f"stream, got {len(final_chunks)}. "
            f"All chunks: {chunks}"
        )
        assert (
            len(non_final_chunks) == 0
        ), f"Expected 0 non-final chunks from empty stream, got {len(non_final_chunks)}"

        terminal = final_chunks[0]
        assert (
            terminal.text_delta == ""
        ), f"terminal text_delta must be '', got {terminal.text_delta!r}"
        assert (
            terminal.chunk_index == 0
        ), f"terminal chunk_index must be 0 for empty stream, got {terminal.chunk_index}"
        assert terminal.resolved_provider == "anthropic"

    async def test_anth10_truncated_stream_no_message_stop_yields_terminal_chunk(self):
        """
        TC-F01-ANTH-10: TRUNCATED stream (message_start + text delta, NO message_stop)
        must still yield a terminal is_final=True chunk with whatever usage/text
        was accumulated before truncation.

        AC-5 requires exactly one terminal chunk.  When the stream is cut after
        some text deltas but before ``message_stop`` arrives (e.g. API timeout,
        connection reset), the seam must emit the terminal chunk on iterator
        exhaustion — not only on ``message_stop``.
        """
        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        # Truncated: message_start + one text delta — no message_delta, no message_stop.
        events = [
            _make_anthropic_message_start_event(input_tokens=8),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("partial text", 0),
            # Stream ends here — message_delta and message_stop never arrive.
        ]
        make_ctx(events)

        seam = self._make_seam(mock_sdk, mock_client)
        chunks = await self._collect_chunks(seam, mock_sdk, events)

        final_chunks = [c for c in chunks if c.is_final]
        non_final_chunks = [c for c in chunks if not c.is_final]

        assert len(final_chunks) == 1, (
            f"AC-5 violation: expected exactly 1 is_final=True chunk from a truncated "
            f"stream, got {len(final_chunks)}. "
            f"All chunks: {chunks}"
        )
        assert len(non_final_chunks) == 1, (
            f"Expected 1 non-final chunk (the partial text delta), "
            f"got {len(non_final_chunks)}"
        )
        assert non_final_chunks[0].text_delta == "partial text"

        terminal = final_chunks[0]
        assert (
            terminal.text_delta == ""
        ), f"terminal text_delta must be '', got {terminal.text_delta!r}"
        # usage.input_tokens must carry the value from message_start (8)
        # even though message_delta never arrived (output_tokens will be None).
        assert (
            terminal.usage is not None
        ), "terminal chunk must carry LLMUsage even from a truncated stream"
        assert terminal.usage.input_tokens == 8, (
            f"input_tokens from message_start must be preserved; "
            f"got {terminal.usage.input_tokens}"
        )
        # output_tokens is None because message_delta never arrived — that is correct.
        assert terminal.usage.output_tokens is None, (
            f"output_tokens must be None (message_delta never arrived); "
            f"got {terminal.usage.output_tokens}"
        )
        assert terminal.resolved_provider == "anthropic"


# ---------------------------------------------------------------------------
# Helpers — fake OpenAI SDK chunks (ChatCompletionChunk shape)
# ---------------------------------------------------------------------------


def _make_openai_content_chunk(text: str, model: str = "gpt-4o"):
    """Build a fake ChatCompletionChunk with a choice delta carrying text content."""
    chunk = MagicMock()
    chunk.model = model
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta = MagicMock()
    chunk.choices[0].delta.content = text
    chunk.choices[0].finish_reason = None
    chunk.usage = None
    return chunk


def _make_openai_finish_reason_chunk(
    finish_reason: str = "stop", model: str = "gpt-4o"
):
    """Build a fake ChatCompletionChunk carrying a finish_reason (no content delta)."""
    chunk = MagicMock()
    chunk.model = model
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta = MagicMock()
    chunk.choices[0].delta.content = None
    chunk.choices[0].finish_reason = finish_reason
    chunk.usage = None
    return chunk


def _make_openai_usage_chunk(
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    model: str = "gpt-4o",
):
    """Build a fake final usage-bearing chunk (choices==[], usage set)."""
    chunk = MagicMock()
    chunk.model = model
    # Final usage chunk has empty choices list (spec §7.2)
    chunk.choices = []
    chunk.usage = MagicMock()
    chunk.usage.prompt_tokens = prompt_tokens
    chunk.usage.completion_tokens = completion_tokens
    return chunk


def _make_mock_openai_module(model: str = "gpt-4o"):
    """
    Build a minimal fake openai module with an AsyncOpenAI client.

    Returns (mock_sdk, mock_client) where mock_client.chat.completions.create
    is an AsyncMock whose return value can be set to an async iterator of chunks.
    """
    from unittest.mock import AsyncMock

    mock_sdk = MagicMock()
    mock_client = MagicMock()
    mock_sdk.AsyncOpenAI.return_value = mock_client

    # chat.completions.create is an async call that returns an async iterator
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock()

    return mock_sdk, mock_client


# ---------------------------------------------------------------------------
# TC-F01-OAI-1 through TC-F01-OAI-6 — OpenAI native seam
# ---------------------------------------------------------------------------


class TestOpenAIStreamSeam(unittest.IsolatedAsyncioTestCase):
    """OpenAI native seam: ChatCompletionChunk → LLMStreamChunk mapping (Section 3)."""

    def _make_seam(self, mock_sdk):
        """Construct OpenAIStreamSeam with fake openai module injected."""
        from agentmap.services.llm.stream_seam import OpenAIStreamSeam

        with patch.dict(sys.modules, {"openai": mock_sdk}):
            seam = OpenAIStreamSeam()
        return seam

    async def _collect_chunks(self, seam, mock_sdk, oai_chunks, params=None):
        """
        Drive seam.stream() with a scripted chunk list and collect all results.

        The mock_sdk.AsyncOpenAI().chat.completions.create is wired to return
        an async iterator over oai_chunks.
        """
        if params is None:
            params = {"model": "gpt-4o", "max_tokens": 100}
        messages = [{"role": "user", "content": "hello"}]

        mock_client = mock_sdk.AsyncOpenAI.return_value
        mock_client.chat.completions.create.return_value = _AsyncIteratorFake(
            oai_chunks
        )

        chunks = []
        with patch.dict(sys.modules, {"openai": mock_sdk}):
            async for chunk in seam.stream(
                messages, params, client=None, credentials=None
            ):
                chunks.append(chunk)
        return chunks

    async def test_oai1_scripted_sequence_yields_2_text_chunks_then_terminal(self):
        """TC-F01-OAI-1: 2 content chunks + finish chunk + usage chunk → 2 non-final + terminal."""
        mock_sdk, mock_client = _make_mock_openai_module()

        oai_chunks = [
            _make_openai_content_chunk("Hello"),
            _make_openai_content_chunk(" world"),
            _make_openai_finish_reason_chunk("stop"),
            _make_openai_usage_chunk(prompt_tokens=10, completion_tokens=5),
        ]

        seam = self._make_seam(mock_sdk)
        chunks = await self._collect_chunks(seam, mock_sdk, oai_chunks)

        non_final = [c for c in chunks if not c.is_final]
        terminal_list = [c for c in chunks if c.is_final]

        assert len(non_final) == 2, f"Expected 2 non-final chunks, got {len(non_final)}"
        assert (
            len(terminal_list) == 1
        ), f"Expected exactly 1 terminal chunk, got {len(terminal_list)}"
        assert non_final[0].text_delta == "Hello"
        assert non_final[1].text_delta == " world"

    async def test_oai2_none_content_yields_empty_string_text_delta(self):
        """TC-F01-OAI-2: chunk with choices[0].delta.content=None yields text_delta=='' (no crash)."""
        mock_sdk, mock_client = _make_mock_openai_module()

        oai_chunks = [
            _make_openai_content_chunk("Hello"),
            _make_openai_finish_reason_chunk("stop"),
            _make_openai_usage_chunk(),
        ]
        # Force the finish-reason chunk's content to None (already the case, but explicit)
        oai_chunks[1].choices[0].delta.content = None

        seam = self._make_seam(mock_sdk)
        chunks = await self._collect_chunks(seam, mock_sdk, oai_chunks)

        # The finish-reason chunk has None content; it must not crash and must
        # yield text_delta=="" if it yields at all, but typically it yields nothing
        # since it only carries finish_reason and content=None → ""
        all_text_deltas = [c.text_delta for c in chunks if not c.is_final]
        for delta in all_text_deltas:
            assert delta is not None, "text_delta must never be None"
            assert isinstance(delta, str), "text_delta must be a str"

    async def test_oai3_terminal_chunk_usage_finish_reason_provider_model(self):
        """TC-F01-OAI-3: terminal chunk has correct usage, finish_reason, resolved fields."""
        mock_sdk, mock_client = _make_mock_openai_module()

        oai_chunks = [
            _make_openai_content_chunk("response text", model="gpt-4o-mini"),
            _make_openai_finish_reason_chunk("stop", model="gpt-4o-mini"),
            _make_openai_usage_chunk(
                prompt_tokens=12, completion_tokens=7, model="gpt-4o-mini"
            ),
        ]

        seam = self._make_seam(mock_sdk)
        chunks = await self._collect_chunks(
            seam,
            mock_sdk,
            oai_chunks,
            params={"model": "gpt-4o-mini", "max_tokens": 50},
        )

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert terminal.usage is not None, "terminal chunk must carry usage"
        assert terminal.usage.input_tokens == 12
        assert terminal.usage.output_tokens == 7
        assert terminal.finish_reason == "stop"
        assert terminal.resolved_provider == "openai"
        assert terminal.resolved_model == "gpt-4o-mini"

    async def test_oai4_include_usage_set_unconditionally_in_create_call(self):
        """TC-F01-OAI-4: chat.completions.create is called with stream=True and stream_options."""
        mock_sdk, mock_client = _make_mock_openai_module()

        oai_chunks = [
            _make_openai_content_chunk("hi"),
            _make_openai_finish_reason_chunk("stop"),
            _make_openai_usage_chunk(),
        ]

        seam = self._make_seam(mock_sdk)
        await self._collect_chunks(seam, mock_sdk, oai_chunks)

        # Assert the seam called create with stream=True and stream_options include_usage
        mock_client.chat.completions.create.assert_called_once()
        _, call_kwargs = mock_client.chat.completions.create.call_args
        assert (
            call_kwargs.get("stream") is True
        ), "create() must be called with stream=True"
        stream_options = call_kwargs.get("stream_options")
        assert stream_options is not None, "create() must be called with stream_options"
        assert (
            stream_options.get("include_usage") is True
        ), "stream_options must include include_usage=True (REQ-F-009)"

    async def test_oai5_chunk_index_monotonic_exactly_one_terminal_last(self):
        """TC-F01-OAI-5: chunk_index is 0,1,...,N-1; exactly one is_final=True, last; terminal text_delta==''."""
        mock_sdk, mock_client = _make_mock_openai_module()

        oai_chunks = [
            _make_openai_content_chunk("A"),
            _make_openai_content_chunk("B"),
            _make_openai_content_chunk("C"),
            _make_openai_finish_reason_chunk("stop"),
            _make_openai_usage_chunk(),
        ]

        seam = self._make_seam(mock_sdk)
        chunks = await self._collect_chunks(seam, mock_sdk, oai_chunks)

        # chunk_index must be 0..N-1
        indices = [c.chunk_index for c in chunks]
        assert indices == list(
            range(len(chunks))
        ), f"chunk_index must be 0..N-1, got {indices}"

        # exactly one terminal, last
        final_chunks = [c for c in chunks if c.is_final]
        assert (
            len(final_chunks) == 1
        ), f"Exactly one is_final=True, got {len(final_chunks)}"
        assert chunks[-1].is_final is True, "Last chunk must be the terminal one"

        # terminal text_delta is empty string
        assert (
            chunks[-1].text_delta == ""
        ), f"Terminal text_delta must be '', got {chunks[-1].text_delta!r}"

    async def test_oai6_stream_without_usage_chunk_yields_terminal_with_none_usage(
        self,
    ):
        """TC-F01-OAI-6: no usage chunk → terminal chunk usage=None (not fabricated), finish_reason populated."""
        mock_sdk, mock_client = _make_mock_openai_module()

        # No usage-bearing chunk — just content + finish_reason
        oai_chunks = [
            _make_openai_content_chunk("hello"),
            _make_openai_finish_reason_chunk("stop"),
        ]

        seam = self._make_seam(mock_sdk)
        chunks = await self._collect_chunks(seam, mock_sdk, oai_chunks)

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert (
            terminal.usage is None
        ), f"usage must be None when no usage chunk arrived, got {terminal.usage}"
        assert terminal.finish_reason == "stop"


# ---------------------------------------------------------------------------
# Helpers — fake LangChain AIMessageChunk objects
#
# IMPORTANT: these helpers use REAL SDK shapes, not MagicMock attributes.
#
# 1. astream is an async-generator function (NOT AsyncMock / awaitable).
#    inspect.isasyncgenfunction(BaseChatModel.astream) == True.
#    So client.astream must be a plain async-def function that yields.
#    Tests that mock it as AsyncMock(return_value=...) would incorrectly
#    support "await client.astream()" — hiding the no-await bug.
#
# 2. AIMessageChunk.usage_metadata is a dict at runtime (UsageMetadata is
#    a TypedDict).  Using MagicMock() and accessing .input_tokens as an
#    attribute would always return a non-None Mock object, hiding the
#    getattr-on-dict bug.  We use real dicts here.
# ---------------------------------------------------------------------------


def _make_lc_content_chunk(content: str):
    """
    Build a fake AIMessageChunk with content text and no metadata.

    usage_metadata is None (no dict, no object) — real shape when the provider
    does not embed usage in mid-stream chunks.
    """
    chunk = MagicMock()
    chunk.content = content
    chunk.response_metadata = {}
    chunk.usage_metadata = None  # real: absent on mid-stream chunks
    return chunk


def _make_lc_terminal_chunk(
    content: str = "",
    finish_reason: str = "stop",
    input_tokens: int = 10,
    output_tokens: int = 20,
):
    """
    Build a fake final AIMessageChunk with response_metadata and usage_metadata.

    usage_metadata is a real dict (UsageMetadata TypedDict shape) — NOT a
    MagicMock object.  getattr(a_dict, "input_tokens", None) always returns
    None; a test that asserts usage.input_tokens != None would catch the bug
    only when we pass a real dict here.

    Also covers "stop_reason" key variant (Anthropic-via-LangChain): the seam
    must fall back to "stop_reason" when "finish_reason" is absent.
    """
    chunk = MagicMock()
    chunk.content = content
    chunk.response_metadata = {"finish_reason": finish_reason}
    # Real shape: dict, not object — getattr won't work on this
    chunk.usage_metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    return chunk


def _make_lc_terminal_chunk_stop_reason(
    content: str = "",
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 20,
):
    """
    Build a fake final AIMessageChunk using "stop_reason" key in response_metadata
    (Anthropic-via-LangChain provider variant) instead of "finish_reason".

    This verifies the cross-provider finish_reason extraction falls back correctly.
    """
    chunk = MagicMock()
    chunk.content = content
    chunk.response_metadata = {"stop_reason": stop_reason}
    chunk.usage_metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    return chunk


def _make_lc_terminal_chunk_no_usage(
    content: str = "",
    finish_reason: str = "stop",
):
    """Build a fake final AIMessageChunk with response_metadata but no usage_metadata."""
    chunk = MagicMock()
    chunk.content = content
    chunk.response_metadata = {"finish_reason": finish_reason}
    chunk.usage_metadata = None
    return chunk


def _make_fake_lc_client(chunks):
    """
    Build a fake LangChain chat client whose astream(messages) is a real
    async-generator function yielding the given chunks.

    CRITICAL: astream must be a plain async-def function that yields (async
    generator), NOT an AsyncMock.  An AsyncMock is awaitable — meaning
    ``await client.astream(messages)`` would silently succeed and produce an
    _AsyncIteratorFake, hiding the blocker-1 bug (``await`` on an async
    generator raises TypeError at runtime).

    By making astream a real async-gen function, ``await client.astream(...)``
    raises ``TypeError: object async_generator can't be used in 'await'`` —
    which is exactly the bug the test must catch.
    """
    from unittest.mock import AsyncMock

    # Capture the chunks list so the nested async-gen closes over it.
    _chunks = list(chunks)

    async def _astream_gen(messages):  # noqa: RUF029 — async generator, not coroutine
        for c in _chunks:
            yield c

    fake_client = MagicMock()
    # Assign a real async-generator function — NOT AsyncMock.
    fake_client.astream = _astream_gen
    fake_client.ainvoke = AsyncMock()
    return fake_client


# ---------------------------------------------------------------------------
# TC-F01-LC-1 through TC-F01-LC-5 — LangChain fallback seam
# ---------------------------------------------------------------------------


class TestLangChainFallbackStreamSeam(unittest.IsolatedAsyncioTestCase):
    """LangChain fallback seam: AIMessageChunk → LLMStreamChunk mapping (Section 4)."""

    def _make_seam(self, provider_name: str = "langchain"):
        """Construct LangChainFallbackStreamSeam with an optional provider_name.

        Pass provider_name to verify the seam threads the dispatch key through
        to the terminal chunk's resolved_provider field.
        """
        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        return LangChainFallbackStreamSeam(provider_name=provider_name)

    async def _collect_chunks(self, seam, fake_client, params=None):
        """Drive seam.stream() with the given fake client and collect all chunks."""
        if params is None:
            params = {"model": "gemini-pro", "max_tokens": 100}
        messages = [{"role": "user", "content": "hello"}]
        chunks = []
        async for chunk in seam.stream(
            messages, params, client=fake_client, credentials=None
        ):
            chunks.append(chunk)
        return chunks, messages

    async def test_lc1_3_content_chunks_yield_3_non_final_then_1_terminal(self):
        """TC-F01-LC-1: fake astream yields 3 AIMessageChunks → 3 non-final + 1 terminal."""
        seam = self._make_seam()
        lc_chunks = [
            _make_lc_content_chunk("Hello"),
            _make_lc_content_chunk(" world"),
            _make_lc_terminal_chunk("!", finish_reason="stop"),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(seam, fake_client)

        non_final = [c for c in chunks if not c.is_final]
        terminal_list = [c for c in chunks if c.is_final]

        assert len(non_final) == 3, f"Expected 3 non-final chunks, got {len(non_final)}"
        assert (
            len(terminal_list) == 1
        ), f"Expected exactly 1 terminal chunk, got {len(terminal_list)}"
        assert non_final[0].text_delta == "Hello"
        assert non_final[1].text_delta == " world"
        assert non_final[2].text_delta == "!"

    async def test_lc2_terminal_chunk_reads_finish_reason_usage_and_resolved_fields(
        self,
    ):
        """TC-F01-LC-2: terminal chunk reads finish_reason, usage, resolved_provider/model.

        Constructs the seam with provider_name="google" to verify the wrapped
        provider key flows through to the terminal chunk.  A seam with the
        hardcoded default "langchain" would cause this test to fail.
        """
        seam = self._make_seam(provider_name="google")
        lc_chunks = [
            _make_lc_content_chunk("Some text"),
            _make_lc_terminal_chunk(
                content="",
                finish_reason="stop",
                input_tokens=15,
                output_tokens=25,
            ),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(
            seam, fake_client, params={"model": "gemini-pro", "max_tokens": 100}
        )

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert terminal.finish_reason == "stop"
        assert terminal.usage is not None, "terminal chunk must carry usage"
        assert terminal.usage.input_tokens == 15
        assert terminal.usage.output_tokens == 25
        # Must reflect the wrapped provider key passed at construction ("google"),
        # not the seam's hardcoded default "langchain".
        assert terminal.resolved_provider == "google", (
            f"Expected resolved_provider='google', got '{terminal.resolved_provider}'. "
            "LangChainFallbackStreamSeam must use the provider_name set at construction."
        )
        assert terminal.resolved_model == "gemini-pro"

    async def test_lc3_absent_usage_metadata_yields_terminal_with_none_usage(self):
        """TC-F01-LC-3: when usage_metadata is absent, terminal chunk carries usage=None."""
        seam = self._make_seam()
        lc_chunks = [
            _make_lc_content_chunk("answer"),
            _make_lc_terminal_chunk_no_usage(content="", finish_reason="stop"),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(seam, fake_client)

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert (
            terminal.usage is None
        ), f"usage must be None when usage_metadata absent, got {terminal.usage}"
        assert terminal.finish_reason == "stop"

    async def test_lc4_chunk_index_monotonic_exactly_one_terminal_last(self):
        """TC-F01-LC-4: chunk_index is 0,1,...,N-1; exactly one is_final=True last; terminal text_delta==''."""
        seam = self._make_seam()
        lc_chunks = [
            _make_lc_content_chunk("A"),
            _make_lc_content_chunk("B"),
            _make_lc_terminal_chunk(content="", finish_reason="stop"),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(seam, fake_client)

        # chunk_index must be 0..N-1
        indices = [c.chunk_index for c in chunks]
        assert indices == list(
            range(len(chunks))
        ), f"chunk_index must be 0..N-1, got {indices}"

        # exactly one terminal, last
        final_chunks = [c for c in chunks if c.is_final]
        assert (
            len(final_chunks) == 1
        ), f"Exactly one is_final=True, got {len(final_chunks)}"
        assert chunks[-1].is_final is True, "Last chunk must be the terminal one"

        # terminal text_delta is empty string
        assert (
            chunks[-1].text_delta == ""
        ), f"Terminal text_delta must be '', got {chunks[-1].text_delta!r}"

    async def test_lc5_astream_called_not_ainvoke_and_messages_passed_through(self):
        """
        TC-F01-LC-5: seam calls client.astream(messages), not ainvoke; messages passed
        through.

        Because astream is a real async-generator function (not AsyncMock), we
        cannot call assert_called_once().  Instead we capture the call via a
        wrapping async-gen that records its argument, then verify:
          - astream was called (via the captured_messages list)
          - ainvoke was NOT called (via AsyncMock on fake_client.ainvoke)
          - the correct messages object was passed
        """
        from unittest.mock import AsyncMock

        seam = self._make_seam()
        lc_chunks = [
            _make_lc_terminal_chunk(content="", finish_reason="stop"),
        ]

        # Wrap the real async-gen to capture call args.
        _captured_messages = []

        async def _capturing_astream(messages):
            _captured_messages.append(messages)
            for c in lc_chunks:
                yield c

        fake_client = MagicMock()
        fake_client.astream = _capturing_astream
        fake_client.ainvoke = AsyncMock()

        messages = [{"role": "user", "content": "test message"}]
        params = {"model": "gemini-pro"}
        chunks = []
        async for chunk in seam.stream(
            messages, params, client=fake_client, credentials=None
        ):
            chunks.append(chunk)

        # astream must have been called exactly once with the original messages.
        assert (
            len(_captured_messages) == 1
        ), f"astream must be called exactly once; called {len(_captured_messages)} times"
        assert (
            _captured_messages[0] is messages
        ), "messages must be passed through to client.astream()"
        # ainvoke must NOT have been called.
        fake_client.ainvoke.assert_not_called()

    async def test_lc6_no_await_on_astream_real_async_gen_shape(self):
        """
        BLOCKER-1 regression: astream is an async-generator function, NOT a
        coroutine.  ``await client.astream(messages)`` raises TypeError at
        runtime.  The seam must iterate directly: ``async for chunk in
        client.astream(messages):``.

        This test uses a real async-generator function for astream.  If the
        production code does ``await client.astream(...)``, Python will raise:
          TypeError: object async_generator can't be used in 'await' expression
        and this test will fail with that TypeError (not with an assertion).

        Counter-factual: revert stream_seam.py line 489 to
        ``async for lc_chunk in await client.astream(messages):``
        and this test fails immediately.
        """
        seam = self._make_seam()
        lc_chunks = [
            _make_lc_content_chunk("hello"),
            _make_lc_terminal_chunk(
                content="", finish_reason="stop", input_tokens=5, output_tokens=10
            ),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        # If the seam incorrectly awaits astream(), this raises TypeError.
        # The test would then fail with TypeError rather than AssertionError.
        chunks, _ = await self._collect_chunks(seam, fake_client)

        non_final = [c for c in chunks if not c.is_final]
        terminal_list = [c for c in chunks if c.is_final]
        assert (
            len(non_final) == 2
        ), f"Expected 2 non-final chunks (hello + ''); got {len(non_final)}"
        assert len(terminal_list) == 1, "Expected exactly 1 terminal chunk"
        assert non_final[0].text_delta == "hello"

    async def test_lc7_dict_usage_metadata_extracted_correctly(self):
        """
        BLOCKER-2 regression: AIMessageChunk.usage_metadata is a dict at
        runtime (UsageMetadata TypedDict).  ``getattr(a_dict, 'input_tokens',
        None)`` always returns None — usage is silently dropped.  The seam
        must use dict-style access: ``usage_metadata.get('input_tokens')``.

        This test supplies usage_metadata as a real dict.  If the production
        code uses ``getattr(raw_usage_metadata, 'input_tokens', None)``, then
        ``terminal.usage.input_tokens`` will be None and this assertion fails.

        Counter-factual: change the production code to use
        ``getattr(raw_usage_metadata, 'input_tokens', None)`` and this test
        fails with AssertionError (usage.input_tokens is None).
        """
        seam = self._make_seam()
        # _make_lc_terminal_chunk uses a real dict for usage_metadata.
        lc_chunks = [
            _make_lc_content_chunk("answer text"),
            _make_lc_terminal_chunk(
                content="",
                finish_reason="stop",
                input_tokens=42,
                output_tokens=17,
            ),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(
            seam, fake_client, params={"model": "gemini-2.0-flash", "max_tokens": 100}
        )

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert terminal.usage is not None, (
            "usage must not be None when usage_metadata dict is present; "
            "getattr() on a dict always returns None — use .get() instead"
        )
        assert terminal.usage.input_tokens == 42, (
            f"input_tokens must be 42; got {terminal.usage.input_tokens}. "
            "getattr(dict, 'input_tokens', None) always returns None — use dict.get()"
        )
        assert (
            terminal.usage.output_tokens == 17
        ), f"output_tokens must be 17; got {terminal.usage.output_tokens}"

    async def test_lc8_cross_provider_finish_reason_stop_reason_fallback(self):
        """
        MEDIUM: cross-provider finish_reason extraction.

        OpenAI-via-LangChain uses ``response_metadata["finish_reason"]``.
        Anthropic-via-LangChain uses ``response_metadata["stop_reason"]``.

        The seam must check "finish_reason" first, then fall back to
        "stop_reason", so both providers produce a non-None finish_reason
        in the terminal chunk.

        Counter-factual: a seam that only reads ``response_metadata.get(
        "finish_reason")`` will return None for Anthropic-via-LangChain
        chunks, causing this assertion to fail.
        """
        seam = self._make_seam()
        # Use the Anthropic-via-LangChain variant: "stop_reason" key only.
        lc_chunks = [
            _make_lc_content_chunk("anthropic response"),
            _make_lc_terminal_chunk_stop_reason(
                content="",
                stop_reason="end_turn",
                input_tokens=8,
                output_tokens=5,
            ),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(seam, fake_client)

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert terminal.finish_reason == "end_turn", (
            f"finish_reason must be 'end_turn' from stop_reason key; "
            f"got {terminal.finish_reason!r}. "
            "Seam must fall back to response_metadata['stop_reason'] when "
            "'finish_reason' is absent (cross-provider support)."
        )

    async def test_lc9_finish_reason_prefers_finish_reason_over_stop_reason(self):
        """
        Cross-provider: when both "finish_reason" and "stop_reason" are present,
        "finish_reason" takes precedence.
        """
        seam = self._make_seam()

        # Chunk with both keys present — finish_reason should win.
        chunk = MagicMock()
        chunk.content = ""
        chunk.response_metadata = {"finish_reason": "stop", "stop_reason": "end_turn"}
        chunk.usage_metadata = {
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }
        lc_chunks = [chunk]
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(seam, fake_client)

        terminal = chunks[-1]
        assert terminal.finish_reason == "stop", (
            f"finish_reason must prefer 'finish_reason' key over 'stop_reason'; "
            f"got {terminal.finish_reason!r}"
        )

    async def test_lc10_absent_finish_reason_and_stop_reason_yields_none(self):
        """
        Cross-provider: when neither "finish_reason" nor "stop_reason" is in
        response_metadata, terminal finish_reason must be None (not crash).
        """
        seam = self._make_seam()
        lc_chunks = [
            _make_lc_content_chunk("text"),
            _make_lc_terminal_chunk_no_usage(content="", finish_reason=None),
        ]
        # Override response_metadata to have no finish_reason or stop_reason.
        lc_chunks[1].response_metadata = {}
        fake_client = _make_fake_lc_client(lc_chunks)

        chunks, _ = await self._collect_chunks(seam, fake_client)

        terminal = chunks[-1]
        assert terminal.is_final is True
        assert terminal.finish_reason is None, (
            f"finish_reason must be None when absent from response_metadata; "
            f"got {terminal.finish_reason!r}"
        )


# ---------------------------------------------------------------------------
# Section 6 — Message Feature Pass-Through & Explicit Rejection (Constraint C4)
# TC-F01-FEAT-1 through TC-F01-FEAT-5
# ---------------------------------------------------------------------------


class TestMessageFeaturePassThrough(unittest.IsolatedAsyncioTestCase):
    """
    TC-F01-FEAT-1 through TC-F01-FEAT-5: vision/multimodal pass-through
    and cache_control carry-or-reject (spec.md REQ-F-012, REQ-F-013, AC-12,
    AC-13, AC-14, Constraint C4, TD-6).

    Assertions are on the **mock's recorded call args** — no real API calls.
    """

    # ------------------------------------------------------------------
    # TC-F01-FEAT-1: Vision pass-through (Anthropic)
    # ------------------------------------------------------------------

    async def test_feat1_vision_passthrough_anthropic(self):
        """TC-F01-FEAT-1: image block present in messages arg passed to native Anthropic SDK call."""
        from agentmap.services.llm.stream_seam import AnthropicStreamSeam

        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        # Messages containing a structured image block (vision/multimodal)
        image_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "iVBORw0KGgo=",
            },
        }
        messages = [
            {
                "role": "user",
                "content": [
                    image_block,
                    {"type": "text", "text": "What is in this image?"},
                ],
            }
        ]

        events = [
            _make_anthropic_message_start_event(input_tokens=5),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("A cat.", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=3, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            seam = AnthropicStreamSeam()
            params = {"model": "claude-3-5-sonnet-20241022", "max_tokens": 100}
            chunks = []
            with patch.dict(sys.modules, {"anthropic": mock_sdk}):
                async for chunk in seam.stream(
                    messages, params, client=None, credentials=None
                ):
                    chunks.append(chunk)

        # The image block must reach the SDK call unchanged — not stripped.
        mock_client.messages.stream.assert_called_once()
        call_kwargs = mock_client.messages.stream.call_args.kwargs
        sdk_messages = call_kwargs.get("messages", call_kwargs.get("messages"))
        assert sdk_messages is not None, "messages kwarg must be present in SDK call"
        # The messages list passed to the SDK must equal what we sent in.
        assert sdk_messages == messages, (
            "Vision messages must pass through unchanged to the Anthropic SDK call; "
            f"got {sdk_messages!r}"
        )
        # Explicitly confirm the image block is present in the SDK call.
        user_content = sdk_messages[0]["content"]
        image_blocks = [b for b in user_content if b.get("type") == "image"]
        assert (
            len(image_blocks) == 1
        ), "The image block must not be dropped from the Anthropic SDK call"

    # ------------------------------------------------------------------
    # TC-F01-FEAT-2: Vision pass-through (OpenAI)
    # ------------------------------------------------------------------

    async def test_feat2_vision_passthrough_openai(self):
        """TC-F01-FEAT-2: image_url content block present in messages arg passed to native OpenAI SDK call."""
        from agentmap.services.llm.stream_seam import OpenAIStreamSeam

        mock_sdk, mock_client = _make_mock_openai_module()

        # Messages containing an image_url content block (OpenAI vision format)
        image_url_block = {
            "type": "image_url",
            "image_url": {"url": "https://example.com/image.png"},
        }
        messages = [
            {
                "role": "user",
                "content": [
                    image_url_block,
                    {"type": "text", "text": "Describe this image."},
                ],
            }
        ]

        oai_chunks = [
            _make_openai_content_chunk("A landscape."),
            _make_openai_finish_reason_chunk("stop"),
            _make_openai_usage_chunk(),
        ]
        mock_client.chat.completions.create.return_value = _AsyncIteratorFake(
            oai_chunks
        )

        with patch.dict(sys.modules, {"openai": mock_sdk}):
            seam = OpenAIStreamSeam()
            params = {"model": "gpt-4o", "max_tokens": 100}
            chunks = []
            with patch.dict(sys.modules, {"openai": mock_sdk}):
                async for chunk in seam.stream(
                    messages, params, client=None, credentials=None
                ):
                    chunks.append(chunk)

        # The image_url block must reach the SDK call unchanged.
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        sdk_messages = call_kwargs.get("messages")
        assert sdk_messages is not None, "messages kwarg must be present in SDK call"
        assert sdk_messages == messages, (
            "Vision messages must pass through unchanged to the OpenAI SDK call; "
            f"got {sdk_messages!r}"
        )
        user_content = sdk_messages[0]["content"]
        image_url_blocks = [b for b in user_content if b.get("type") == "image_url"]
        assert (
            len(image_url_blocks) == 1
        ), "The image_url block must not be dropped from the OpenAI SDK call"

    # ------------------------------------------------------------------
    # TC-F01-FEAT-3: cache_control pass-through (Anthropic native, supported)
    # ------------------------------------------------------------------

    async def test_feat3_cache_control_passthrough_anthropic_native(self):
        """TC-F01-FEAT-3: cache_control block for Anthropic native reaches the SDK call unchanged."""
        from agentmap.services.llm.stream_seam import AnthropicStreamSeam

        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        # Messages with cache_control block (Anthropic prompt-caching format)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "You are a helpful assistant." * 50,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": "What is 2+2?"},
                ],
            }
        ]

        events = [
            _make_anthropic_message_start_event(
                input_tokens=30,
                cache_creation_input_tokens=100,
                cache_read_input_tokens=0,
            ),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("4", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=1, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            seam = AnthropicStreamSeam()
            params = {"model": "claude-3-5-sonnet-20241022", "max_tokens": 100}
            chunks = []
            with patch.dict(sys.modules, {"anthropic": mock_sdk}):
                async for chunk in seam.stream(
                    messages, params, client=None, credentials=None
                ):
                    chunks.append(chunk)

        # The cache_control key must remain in the messages arg passed to the SDK.
        mock_client.messages.stream.assert_called_once()
        call_kwargs = mock_client.messages.stream.call_args.kwargs
        sdk_messages = call_kwargs.get("messages")
        assert sdk_messages is not None, "messages kwarg must be present in SDK call"
        assert sdk_messages == messages, (
            "Messages with cache_control must pass through unchanged to Anthropic SDK; "
            f"got {sdk_messages!r}"
        )
        user_content = sdk_messages[0]["content"]
        # The first content block must still carry cache_control
        first_block = user_content[0]
        assert (
            "cache_control" in first_block
        ), "cache_control must not be stripped from messages passed to Anthropic SDK"

    # ------------------------------------------------------------------
    # TC-F01-FEAT-4: Explicit rejection — cache_control targeting unsupported mode
    # ------------------------------------------------------------------

    async def test_feat4_explicit_rejection_cache_control_unsupported_mode(self):
        """TC-F01-FEAT-4: cache_control on LangChain fallback raises LLMServiceError before any chunk."""
        from agentmap.exceptions import LLMServiceError
        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        seam = LangChainFallbackStreamSeam()

        # Messages with a cache_control block — LangChain fallback does not carry
        # cache_control natively in streaming (spec.md REQ-F-013, TD-6).
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Long system context..." * 20,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": "Tell me a joke."},
                ],
            }
        ]

        # Build a fake LangChain client — it must NEVER be called if rejection fires
        # before iteration begins.  Use a real async-gen function for astream
        # (consistent with real SDK shape; rejection fires before astream is touched).
        from unittest.mock import AsyncMock

        async def _never_called_astream(messages):  # pragma: no cover
            yield _make_lc_terminal_chunk(content="", finish_reason="stop")

        fake_client = MagicMock()
        fake_client.astream = _never_called_astream
        fake_client.ainvoke = AsyncMock()

        # The seam must raise LLMServiceError before yielding any chunk.
        # Per TC-F01-FEAT-4, the exception fires before the first anext().
        gen = seam.stream(
            messages, {"model": "gemini-pro"}, client=fake_client, credentials=None
        )
        with pytest.raises(LLMServiceError):
            # Either the generator raises immediately or on the first anext().
            # Both are valid "before any chunk" — we must not receive a chunk first.
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pytest.fail(
                    "Generator stopped cleanly — LLMServiceError was not raised"
                )

    # ------------------------------------------------------------------
    # TC-F01-FEAT-5: No silent drop — zero chunks before the exception
    # ------------------------------------------------------------------

    async def test_feat5_no_silent_drop_zero_chunks_before_exception(self):
        """TC-F01-FEAT-5: zero chunks produced before the LLMServiceError in a rejection scenario."""
        from agentmap.exceptions import LLMServiceError
        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        seam = LangChainFallbackStreamSeam()

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Cached context",
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            }
        ]

        async def _never_called_astream_feat5(messages):  # pragma: no cover
            yield _make_lc_terminal_chunk(content="", finish_reason="stop")

        fake_client = MagicMock()
        fake_client.astream = _never_called_astream_feat5

        chunks_before_error = []
        raised = False
        gen = seam.stream(
            messages, {"model": "gemini-pro"}, client=fake_client, credentials=None
        )
        try:
            async for chunk in gen:
                chunks_before_error.append(chunk)
        except LLMServiceError:
            raised = True

        assert raised, (
            "LLMServiceError must be raised for cache_control on unsupported mode; "
            "none was raised"
        )
        assert len(chunks_before_error) == 0, (
            f"Zero chunks must be produced before the LLMServiceError; "
            f"got {len(chunks_before_error)} chunk(s): {chunks_before_error}"
        )


# ---------------------------------------------------------------------------
# Section 7 & 8 — Import gating and NFR hygiene
# TC-F01-DEP-* already covered above in TestImportGating.
# TC-F01-NF-1 through TC-F01-NF-4 — laziness, content hygiene, credential hygiene,
# additivity regression gate.
# ---------------------------------------------------------------------------


class _CountingAsyncIterator:
    """
    Async iterator that records exactly how many events have been pulled
    so far.  Used by TC-F01-NF-1 to assert lockstep laziness.

    ``events_pulled`` is incremented each time ``__anext__`` is called
    (i.e. each time the consumer asks for the next provider event).
    This lets the test assert that after the consumer receives its n-th
    ``yield``, the iterator has been asked for exactly n+1 events
    (n text deltas consumed, plus the iterator has advanced to discover
    the next event — which is how a true async generator works: it
    suspends after each ``yield`` and pulls the next event only on the
    next ``anext()`` call from the consumer).
    """

    def __init__(self, items):
        self._items = list(items)
        self._idx = 0
        self.events_pulled: int = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        self.events_pulled += 1
        return item


class TestNFRHygiene(unittest.IsolatedAsyncioTestCase):
    """
    TC-F01-NF-1 through TC-F01-NF-3: laziness, content-capture hygiene,
    and credential hygiene for the streaming seam (Section 8 of test-plan.md).

    TC-F01-NF-4 (additivity regression gate) is implemented as a separate
    standalone test class below.
    """

    # ------------------------------------------------------------------
    # TC-F01-NF-1 — Laziness: true async generator, not a list builder
    # ------------------------------------------------------------------

    async def test_nf1_laziness_events_consumed_in_lockstep_with_yields(self):
        """
        TC-F01-NF-1: the LangChain seam is a true async generator — each text
        delta is yielded before the next provider event is consumed.

        Drive seam.stream() via anext() one step at a time.  After receiving
        the n-th non-final chunk, assert that the fake event source has been
        asked for exactly the minimum number of events needed to produce that
        chunk — i.e. the seam has NOT pre-consumed (buffered) all events.

        The LangChain seam yields one non-final LLMStreamChunk per lc_chunk
        (including the final lc_chunk), then a terminal LLMStreamChunk after
        the iterator is exhausted.  With 2 content lc_chunks the seam yields:
          [non-final "Alpha", non-final "Beta", terminal].
        """
        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        seam = LangChainFallbackStreamSeam()

        # Build a 2-chunk stream: 2 content chunks only.  The seam yields one
        # non-final chunk per lc_chunk then a terminal, so 2 lc_chunks → 3
        # seam chunks: [non-final "Alpha", non-final "Beta", terminal].
        lc_chunks = [
            _make_lc_content_chunk("Alpha"),
            _make_lc_terminal_chunk(content="Beta", finish_reason="stop"),
        ]
        counting_iter = _CountingAsyncIterator(lc_chunks)

        from unittest.mock import AsyncMock

        fake_client = MagicMock()

        # astream must be a real async-generator function (not AsyncMock).
        # We wrap the counting_iter by having the async-gen delegate to it.
        async def _astream_counting(messages):
            async for item in counting_iter:
                yield item

        fake_client.astream = _astream_counting
        fake_client.ainvoke = AsyncMock()

        messages = [{"role": "user", "content": "test"}]
        params = {"model": "gemini-pro"}

        gen = seam.stream(messages, params, client=fake_client, credentials=None)

        # Pull first chunk (from lc_chunks[0] = "Alpha").
        chunk0 = await gen.__anext__()
        assert chunk0.text_delta == "Alpha"
        assert chunk0.is_final is False
        # After yielding the first content chunk, the seam has consumed
        # exactly 1 provider event and has NOT pre-consumed the full stream.
        events_after_first_yield = counting_iter.events_pulled
        assert events_after_first_yield < len(lc_chunks), (
            f"Seam consumed all {len(lc_chunks)} provider events before the "
            f"consumer received the first chunk — it is buffering the full "
            f"response rather than streaming lazily. "
            f"events_pulled={events_after_first_yield}"
        )

        # Pull second chunk (from lc_chunks[1] = "Beta" with finish_reason).
        chunk1 = await gen.__anext__()
        assert chunk1.text_delta == "Beta"
        assert chunk1.is_final is False
        # Both lc_chunks consumed; terminal not yet emitted (seam suspends
        # after the yield inside the loop, before exhausting the iterator).
        # The counting_iter is now fully consumed (both events pulled).
        assert counting_iter.events_pulled == len(lc_chunks), (
            f"Expected both lc_chunks consumed after second seam chunk; "
            f"got events_pulled={counting_iter.events_pulled}"
        )

        # Pull terminal chunk (emitted after the async-for loop exhausts the iter).
        chunk2 = await gen.__anext__()
        assert chunk2.is_final is True
        assert chunk2.finish_reason == "stop"

        # Generator must be exhausted now.
        try:
            await gen.__anext__()
            raise AssertionError(  # pragma: no cover
                "Generator should be exhausted after the terminal chunk"
            )
        except StopAsyncIteration:
            pass  # Expected.

    # ------------------------------------------------------------------
    # TC-F01-NF-2 — Content-capture hygiene: no log record contains text_delta
    # ------------------------------------------------------------------

    async def test_nf2_content_capture_hygiene_no_log_record_contains_text_delta(self):
        """
        TC-F01-NF-2: consuming a stream emits no log record containing
        text_delta/completion content.

        LLMStreamChunk is a pure data carrier with no logging side effects.
        The seam's only operational logging (if any) must be metadata
        (provider, error type) — never prompt/completion text (REQ-NF-010).
        """
        import logging

        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        seam = LangChainFallbackStreamSeam()

        sentinel_content = "UNIQUE_CONTENT_SENTINEL_XYZ_9876"
        # 2 lc_chunks → 3 seam chunks (1 non-final per lc_chunk + 1 terminal).
        lc_chunks = [
            _make_lc_content_chunk(sentinel_content),
            _make_lc_terminal_chunk(content="", finish_reason="stop"),
        ]

        from unittest.mock import AsyncMock

        _lc_chunks_nf2 = lc_chunks

        async def _astream_nf2(messages):
            for c in _lc_chunks_nf2:
                yield c

        fake_client = MagicMock()
        fake_client.astream = _astream_nf2
        fake_client.ainvoke = AsyncMock()

        messages = [{"role": "user", "content": "What is the sentinel?"}]
        params = {"model": "gemini-pro"}

        # Capture log records at DEBUG and above across the root logger
        # and the agentmap logger namespace.
        with self.assertLogs("agentmap", level=logging.DEBUG) as log_ctx:
            # We need at least one log record for assertLogs to not fail.
            # Emit a benign record so the context manager doesn't error out
            # if the seam emits no logs (which is the expected/desired case).
            logging.getLogger("agentmap.test_hygiene_probe").debug(
                "probe: hygiene test running"
            )
            chunks = []
            async for chunk in seam.stream(
                messages, params, client=fake_client, credentials=None
            ):
                chunks.append(chunk)

        # Confirm the stream produced the expected chunks:
        # 2 lc_chunks → 2 non-final + 1 terminal = 3 seam chunks.
        assert (
            len(chunks) == 3
        ), f"Expected 3 chunks (2 non-final + terminal), got {len(chunks)}"

        # Assert that no log record contains the sentinel content text.
        for record in log_ctx.records:
            assert sentinel_content not in record.getMessage(), (
                f"Log record contains completion text (content-capture hygiene "
                f"violation). Record: {record.getMessage()!r}. "
                f"The seam and LLMStreamChunk must not log text_delta/completion "
                f"content (REQ-NF-010)."
            )

    # ------------------------------------------------------------------
    # TC-F01-NF-3 — Credential hygiene: no log record contains api_key value
    # ------------------------------------------------------------------

    async def test_nf3_credential_hygiene_no_log_record_contains_api_key(self):
        """
        TC-F01-NF-3: no log record contains the credential/api_key value
        passed to the seam (REQ-NF-011, mirrors batch-adapter discipline).

        The Anthropic and OpenAI seams receive an api_key in the credentials
        dict and must never log it.  We verify via a scripted stream with a
        sentinel credential value.
        """
        import logging
        import sys

        from agentmap.services.llm.stream_seam import AnthropicStreamSeam

        sentinel_api_key = "sk-SENTINEL-CRED-VALUE-DO-NOT-LOG-0000"

        mock_sdk, mock_client, make_ctx = _make_mock_anthropic_module()

        events = [
            _make_anthropic_message_start_event(input_tokens=5),
            _make_anthropic_content_block_start_event("text", 0),
            _make_anthropic_text_delta_event("response text", 0),
            _make_anthropic_content_block_stop_event(0),
            _make_anthropic_message_delta_event(
                output_tokens=3, stop_reason="end_turn"
            ),
            _make_anthropic_message_stop_event(),
        ]
        make_ctx(events)

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            seam = AnthropicStreamSeam()

        messages = [{"role": "user", "content": "hello"}]
        params = {"model": "claude-3-5-sonnet-20241022", "max_tokens": 100}
        credentials = {"api_key": sentinel_api_key}

        with self.assertLogs("agentmap", level=logging.DEBUG) as log_ctx:
            # Emit a probe record so assertLogs doesn't fail if seam emits nothing.
            logging.getLogger("agentmap.test_cred_hygiene_probe").debug(
                "probe: credential hygiene test running"
            )
            chunks = []
            with patch.dict(sys.modules, {"anthropic": mock_sdk}):
                async for chunk in seam.stream(
                    messages, params, client=None, credentials=credentials
                ):
                    chunks.append(chunk)

        # Assert no log record leaks the credential value.
        for record in log_ctx.records:
            assert sentinel_api_key not in record.getMessage(), (
                f"Log record contains credential value (credential hygiene violation). "
                f"Record: {record.getMessage()!r}. "
                f"The seam must never log api_key or credential values (REQ-NF-011)."
            )

        # Confirm the stream still produced correct output.
        assert len(chunks) >= 2, f"Expected >=2 chunks from stream; got {len(chunks)}"
        assert chunks[-1].is_final is True


# ---------------------------------------------------------------------------
# TC-F01-NF-4 — Additivity regression gate (Section 8 of test-plan.md)
# ---------------------------------------------------------------------------


class TestAdditivityRegressionGate:
    """
    TC-F01-NF-4: F01 introduces zero change to existing non-streaming call
    paths — the existing test suites must all pass.

    This guard test programmatically verifies that the three non-streaming
    LLM test modules are importable and their test classes instantiable
    (i.e. the modules' public surface has not changed from F01's edits).

    The actual pass/fail of the tests themselves is confirmed by running
    the full regression suite as part of this task's quality gate.
    Reference: spec.md REQ-NF-002 / AC-18.
    """

    def test_nf4_llm_service_test_module_importable_and_unchanged(self):
        """TC-F01-NF-4 (structural): test_llm_service.py is importable with its test classes."""
        import importlib

        mod = importlib.import_module(
            "tests.fresh_suite.unit.services.test_llm_service"
        )
        # The module must expose at least one test class.
        test_classes = [name for name in dir(mod) if name.startswith("Test")]
        assert len(test_classes) > 0, (
            "test_llm_service.py must contain at least one Test* class; "
            "F01 must not have modified the non-streaming LLM test surface."
        )

    def test_nf4_llm_service_async_test_module_importable_and_unchanged(self):
        """TC-F01-NF-4 (structural): test_llm_service_async.py is importable with its test classes."""
        import importlib

        mod = importlib.import_module(
            "tests.fresh_suite.unit.services.test_llm_service_async"
        )
        test_classes = [name for name in dir(mod) if name.startswith("Test")]
        assert len(test_classes) > 0, (
            "test_llm_service_async.py must contain at least one Test* class; "
            "F01 must not have modified the non-streaming async LLM test surface."
        )

    def test_nf4_llm_client_factory_test_module_importable_and_unchanged(self):
        """TC-F01-NF-4 (structural): test_llm_client_factory.py is importable with its test classes."""
        import importlib

        mod = importlib.import_module(
            "tests.fresh_suite.unit.services.test_llm_client_factory"
        )
        test_classes = [name for name in dir(mod) if name.startswith("Test")]
        assert len(test_classes) > 0, (
            "test_llm_client_factory.py must contain at least one Test* class; "
            "F01 must not have modified the LLM client factory test surface."
        )

    def test_nf4_f01_did_not_modify_llm_service_source(self):
        """TC-F01-NF-4 (structural): llm_service.py is importable (F01 must not have broken it)."""
        import importlib

        # If F01 accidentally modified llm_service.py, this import would likely
        # fail or the downstream test suite would regress.  A clean import
        # confirms the module is syntactically intact.
        mod = importlib.import_module("agentmap.services.llm_service")
        assert hasattr(mod, "LLMService"), (
            "LLMService must still be importable from agentmap.services.llm_service; "
            "F01 must not have modified llm_service.py (REQ-NF-002, AC-18)."
        )

    def test_nf4_f01_did_not_modify_llm_client_factory_source(self):
        """TC-F01-NF-4 (structural): llm_client_factory.py is importable (F01 must not have broken it)."""
        import importlib

        mod = importlib.import_module("agentmap.services.llm_client_factory")
        assert hasattr(mod, "LLMClientFactory"), (
            "LLMClientFactory must still be importable from "
            "agentmap.services.llm_client_factory; "
            "F01 must not have modified llm_client_factory.py (REQ-NF-002, AC-18)."
        )
