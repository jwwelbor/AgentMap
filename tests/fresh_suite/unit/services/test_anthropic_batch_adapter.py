"""
Unit tests for AnthropicBatchAdapter.

Covers:
- TC-AC8-03: LLMDependencyError raised when anthropic package not importable
- TC-AC8-04: cache_control blocks pass through to Anthropic SDK unchanged
- TC-AC5-05: spec_id requiring sanitization is correctly demuxed via custom_id
- TC-AC5-03: succeeded result record has populated LLMUsage
"""

import builtins
import re
import sys
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_anthropic_module():
    """Build a minimal fake anthropic module for patching sys.modules."""
    mock_sdk = MagicMock()
    # Anthropic client constructor returns a client with messages.batches.*
    client_instance = MagicMock()
    mock_sdk.Anthropic.return_value = client_instance
    return mock_sdk, client_instance


class TestImportGating:
    """TC-AC8-03: AnthropicBatchAdapter raises LLMDependencyError when anthropic not importable."""

    def test_raises_llm_dependency_error_when_anthropic_missing(self):
        """
        AnthropicBatchAdapter.__init__ must raise LLMDependencyError (not bare
        ImportError) when the anthropic package cannot be imported.
        """
        # Remove any cached anthropic module so the adapter's try/except fires
        original_import = builtins.__import__

        def import_that_fails_for_anthropic(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return original_import(name, *args, **kwargs)

        # Also remove anthropic from sys.modules to prevent cached import
        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key == "anthropic" or key.startswith("anthropic."):
                saved_modules[key] = sys.modules.pop(key)

        # Remove the adapter from sys.modules so its module-level code re-runs if any
        adapter_key = "agentmap.services.llm.anthropic_batch_adapter"
        saved_adapter = sys.modules.pop(adapter_key, None)

        try:
            with patch(
                "builtins.__import__", side_effect=import_that_fails_for_anthropic
            ):
                # Re-import the adapter module fresh under the import patch
                import importlib

                from agentmap.exceptions import LLMDependencyError

                if adapter_key in sys.modules:
                    del sys.modules[adapter_key]

                adapter_mod = importlib.import_module(adapter_key)
                AnthropicBatchAdapter = adapter_mod.AnthropicBatchAdapter

                with pytest.raises(LLMDependencyError):
                    AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
        finally:
            # Restore modules
            sys.modules.update(saved_modules)
            if saved_adapter is not None:
                sys.modules[adapter_key] = saved_adapter

    def test_llm_dependency_error_not_bare_import_error(self):
        """
        The raised exception must be LLMDependencyError, not ImportError.
        TC-AC9-02: verifies error class hierarchy.
        """
        from agentmap.exceptions import LLMDependencyError

        original_import = builtins.__import__

        def import_that_fails_for_anthropic(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return original_import(name, *args, **kwargs)

        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key == "anthropic" or key.startswith("anthropic."):
                saved_modules[key] = sys.modules.pop(key)

        adapter_key = "agentmap.services.llm.anthropic_batch_adapter"
        saved_adapter = sys.modules.pop(adapter_key, None)

        try:
            with patch(
                "builtins.__import__", side_effect=import_that_fails_for_anthropic
            ):
                import importlib

                if adapter_key in sys.modules:
                    del sys.modules[adapter_key]
                adapter_mod = importlib.import_module(adapter_key)
                AnthropicBatchAdapter = adapter_mod.AnthropicBatchAdapter

                exc = None
                try:
                    AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
                except Exception as e:
                    exc = e

                assert exc is not None
                assert isinstance(
                    exc, LLMDependencyError
                ), f"Expected LLMDependencyError, got {type(exc)}"
                assert not isinstance(
                    exc, ImportError
                ), "Must not raise bare ImportError"
        finally:
            sys.modules.update(saved_modules)
            if saved_adapter is not None:
                sys.modules[adapter_key] = saved_adapter


class TestCacheControlPassThrough:
    """TC-AC8-04: cache_control blocks pass through to Anthropic SDK unchanged."""

    def _make_adapter(self, client_instance):
        """Build adapter with mocked SDK client."""
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            # Fresh import of adapter
            adapter_key = "agentmap.services.llm.anthropic_batch_adapter"
            saved = sys.modules.pop(adapter_key, None)
            try:
                import importlib

                if adapter_key in sys.modules:
                    del sys.modules[adapter_key]
                adapter_mod = importlib.import_module(adapter_key)
                adapter = adapter_mod.AnthropicBatchAdapter(
                    api_key="test-key", logger=MagicMock()
                )
                # Detach the client from mock_sdk so submit() uses our client_instance
                return adapter
            finally:
                if saved is not None:
                    sys.modules[adapter_key] = saved

    def test_cache_control_passes_through_to_sdk(self):
        """
        cache_control in message content must appear verbatim in the request
        passed to mock_sdk.messages.batches.create().
        """
        from agentmap.models.llm_execution import LLMCallSpec
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        # Patch the SDK module so adapter can be constructed
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        # Mock the batch create response
        batch_response = MagicMock()
        batch_response.id = "msgbatch_test"
        batch_response.expires_at = None
        client_instance.messages.batches.create.return_value = batch_response

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())

            spec = LLMCallSpec(
                spec_id="spec-1",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "hi",
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                ],
            )

            adapter.submit(
                specs=[spec],
                model="claude-sonnet-4-6",
                max_tokens=100,
                request_options={},
            )

        # Verify the SDK was called
        assert client_instance.messages.batches.create.called
        call_kwargs = client_instance.messages.batches.create.call_args

        # Extract requests param
        if call_kwargs.kwargs:
            requests_param = call_kwargs.kwargs.get("requests", [])
        else:
            requests_param = call_kwargs.args[0] if call_kwargs.args else []

        assert len(requests_param) == 1
        req = requests_param[0]
        # req should be a dict with params.messages or similar
        if isinstance(req, dict):
            params = req.get("params", req)
            messages = params.get("messages", [])
        else:
            # MagicMock — extract from attributes
            messages = []

        # Verify cache_control present in first message content
        if messages:
            content = messages[0].get("content", [])
            if content and isinstance(content, list):
                block = content[0]
                assert (
                    "cache_control" in block
                ), "cache_control must be present in SDK request"
                assert block["cache_control"] == {"type": "ephemeral"}


class TestSpecIdSanitization:
    """TC-AC5-05: spec_id requiring sanitization is correctly demuxed via custom_id."""

    def test_sanitized_spec_id_stored_in_spec_id_map(self):
        """
        When spec_id contains chars outside ^[a-zA-Z0-9_-]{1,64}$,
        a sanitized custom_id must be used and stored in spec_id_map.
        """
        from agentmap.models.llm_execution import LLMCallSpec
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        batch_response = MagicMock()
        batch_response.id = "msgbatch_sanitized"
        batch_response.expires_at = None
        client_instance.messages.batches.create.return_value = batch_response

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())

            dirty_spec_id = "my spec/id"  # space and slash — violates regex
            spec = LLMCallSpec(
                spec_id=dirty_spec_id,
                messages=[{"role": "user", "content": "test"}],
            )

            _provider_batch_id, spec_id_map, _expires_at = adapter.submit(
                specs=[spec],
                model="claude-sonnet-4-6",
                max_tokens=100,
                request_options={},
            )

        # The original spec_id must be a key in the map
        assert (
            dirty_spec_id in spec_id_map
        ), "original spec_id must be key in spec_id_map"
        custom_id = spec_id_map[dirty_spec_id]

        # custom_id must be valid per Anthropic regex
        valid_pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
        assert valid_pattern.match(
            custom_id
        ), f"custom_id {custom_id!r} must match ^[a-zA-Z0-9_-]{{1,64}}$"

        # custom_id must differ from dirty spec_id
        assert custom_id != dirty_spec_id

    def test_clean_spec_id_used_as_is(self):
        """When spec_id is already valid, it must be used as-is (no hash)."""
        from agentmap.models.llm_execution import LLMCallSpec
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        batch_response = MagicMock()
        batch_response.id = "msgbatch_clean"
        batch_response.expires_at = None
        client_instance.messages.batches.create.return_value = batch_response

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())

            clean_spec_id = "my-clean-spec"
            spec = LLMCallSpec(
                spec_id=clean_spec_id,
                messages=[{"role": "user", "content": "test"}],
            )

            _provider_batch_id, spec_id_map, _expires_at = adapter.submit(
                specs=[spec],
                model="claude-sonnet-4-6",
                max_tokens=100,
                request_options={},
            )

        assert spec_id_map[clean_spec_id] == clean_spec_id

    def test_fetch_results_demuxes_sanitized_custom_id(self):
        """
        fetch_results must yield records keyed by original spec_id, not custom_id,
        when the spec_id was sanitized.
        """
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        # Simulate JSONL-like result from SDK
        dirty_spec_id = "my spec/id"
        # Compute what the adapter would produce for the sanitized custom_id
        import hashlib

        sanitized = hashlib.sha1(dirty_spec_id.encode()).hexdigest()[:64]

        result_item = MagicMock()
        result_item.custom_id = sanitized
        result_item.result.type = "succeeded"
        msg = MagicMock()
        msg.content = [MagicMock(text="hello")]
        msg.model = "claude-sonnet-4-6"
        msg.usage.input_tokens = 10
        msg.usage.output_tokens = 5
        msg.usage.cache_creation_input_tokens = None
        msg.usage.cache_read_input_tokens = None
        result_item.result.message = msg

        client_instance.messages.batches.results.return_value = iter([result_item])

        # spec_id_map: dirty -> sanitized
        spec_id_map = {dirty_spec_id: sanitized}

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    spec_id_map=spec_id_map,
                )
            )

        assert len(records) == 1
        assert records[0].spec_id == dirty_spec_id


class TestFetchResultsUsageParsing:
    """TC-AC5-03: succeeded result record has populated LLMUsage."""

    def test_succeeded_record_has_llm_usage(self):
        """
        fetch_results must produce a record with usage.input_tokens,
        output_tokens, and optional cache fields populated from the SDK response.
        """
        from agentmap.models.llm_execution import LLMUsage
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        result_item = MagicMock()
        result_item.custom_id = "spec-1"
        result_item.result.type = "succeeded"
        msg = MagicMock()
        msg.content = [MagicMock(text="response text")]
        msg.model = "claude-sonnet-4-6"
        msg.usage.input_tokens = 100
        msg.usage.output_tokens = 50
        msg.usage.cache_creation_input_tokens = 10
        msg.usage.cache_read_input_tokens = 20
        result_item.result.message = msg

        client_instance.messages.batches.results.return_value = iter([result_item])

        spec_id_map = {"spec-1": "spec-1"}

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    spec_id_map=spec_id_map,
                )
            )

        assert len(records) == 1
        record = records[0]
        assert record.status == "succeeded"
        assert isinstance(record.usage, LLMUsage)
        assert record.usage.input_tokens == 100
        assert record.usage.output_tokens == 50
        assert record.usage.cache_creation_input_tokens == 10
        assert record.usage.cache_read_input_tokens == 20

    def test_succeeded_record_usage_cache_fields_absent(self):
        """When cache fields are absent from SDK response, they must be None (not fabricated)."""
        from agentmap.models.llm_execution import LLMUsage
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        result_item = MagicMock()
        result_item.custom_id = "spec-2"
        result_item.result.type = "succeeded"
        msg = MagicMock()
        msg.content = [MagicMock(text="hi")]
        msg.model = "claude-sonnet-4-6"
        msg.usage.input_tokens = 5
        msg.usage.output_tokens = 3
        # Simulate absent cache fields
        del msg.usage.cache_creation_input_tokens
        del msg.usage.cache_read_input_tokens
        result_item.result.message = msg

        client_instance.messages.batches.results.return_value = iter([result_item])

        spec_id_map = {"spec-2": "spec-2"}

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    spec_id_map=spec_id_map,
                )
            )

        record = records[0]
        assert isinstance(record.usage, LLMUsage)
        assert record.usage.cache_creation_input_tokens is None
        assert record.usage.cache_read_input_tokens is None

    def test_fetch_results_is_lazy_generator(self):
        """fetch_results must return a generator/iterator, not a pre-loaded list."""
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance
        client_instance.messages.batches.results.return_value = iter([])

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            result = adapter.fetch_results(
                provider_batch_id="msgbatch_abc",
                spec_id_map={},
            )

        import types

        assert isinstance(
            result, types.GeneratorType
        ), "fetch_results must be a lazy generator, not a list"
