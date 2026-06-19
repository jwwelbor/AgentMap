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
# ---------------------------------------------------------------------------


def _make_lc_content_chunk(content: str):
    """Build a fake AIMessageChunk with content text and no metadata."""
    chunk = MagicMock()
    chunk.content = content
    chunk.response_metadata = {}
    chunk.usage_metadata = None
    return chunk


def _make_lc_terminal_chunk(
    content: str = "",
    finish_reason: str = "stop",
    input_tokens: int = 10,
    output_tokens: int = 20,
):
    """Build a fake final AIMessageChunk with response_metadata and usage_metadata."""
    chunk = MagicMock()
    chunk.content = content
    chunk.response_metadata = {"finish_reason": finish_reason}
    chunk.usage_metadata = MagicMock()
    chunk.usage_metadata.input_tokens = input_tokens
    chunk.usage_metadata.output_tokens = output_tokens
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
    Build a fake LangChain chat client whose astream(messages) returns a scripted
    async iterator of the given chunks.

    The fake client has:
      - astream: an AsyncMock returning an _AsyncIteratorFake over chunks
      - ainvoke: an AsyncMock (must NOT be called by the seam)
    """
    from unittest.mock import AsyncMock

    fake_client = MagicMock()
    # astream must be an AsyncMock that returns an async iterator
    fake_client.astream = AsyncMock(return_value=_AsyncIteratorFake(chunks))
    fake_client.ainvoke = AsyncMock()
    return fake_client


# ---------------------------------------------------------------------------
# TC-F01-LC-1 through TC-F01-LC-5 — LangChain fallback seam
# ---------------------------------------------------------------------------


class TestLangChainFallbackStreamSeam(unittest.IsolatedAsyncioTestCase):
    """LangChain fallback seam: AIMessageChunk → LLMStreamChunk mapping (Section 4)."""

    def _make_seam(self):
        """Construct LangChainFallbackStreamSeam (no SDK gating needed)."""
        from agentmap.services.llm.stream_seam import LangChainFallbackStreamSeam

        return LangChainFallbackStreamSeam()

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
        """TC-F01-LC-2: terminal chunk reads finish_reason, usage, resolved_provider/model."""
        seam = self._make_seam()
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
        assert terminal.resolved_provider is not None
        assert isinstance(terminal.resolved_provider, str)
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
        """TC-F01-LC-5: seam calls client.astream(messages), not ainvoke; messages passed through."""
        seam = self._make_seam()
        lc_chunks = [
            _make_lc_terminal_chunk(content="", finish_reason="stop"),
        ]
        fake_client = _make_fake_lc_client(lc_chunks)

        messages = [{"role": "user", "content": "test message"}]
        params = {"model": "gemini-pro"}
        chunks = []
        async for chunk in seam.stream(
            messages, params, client=fake_client, credentials=None
        ):
            chunks.append(chunk)

        # astream must have been called (not ainvoke)
        fake_client.astream.assert_called_once()
        fake_client.ainvoke.assert_not_called()

        # messages must have been passed through to astream
        call_args = fake_client.astream.call_args
        # astream(messages) — positional or keyword
        called_messages = (
            call_args[0][0] if call_args[0] else call_args[1].get("messages")
        )
        assert (
            called_messages is messages
        ), "messages must be passed through to client.astream()"
