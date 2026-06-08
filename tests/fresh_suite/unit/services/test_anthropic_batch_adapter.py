"""
Unit tests for AnthropicBatchAdapter.

Covers:
- TC-SER-A1: resolved temperature appears in requests[i].params on the correct spec
- TC-SER-A2: resolved max_tokens appears in requests[i].params on the correct spec
- TC-SER-A3: passthrough (non-reserved) request_options key appears in params
- TC-SER-A4: per-spec params appear only on the correct custom_id (not every entry)
- TC-AC8-03: LLMDependencyError raised when anthropic package not importable
- TC-AC8-04: cache_control blocks pass through to Anthropic SDK unchanged
- TC-AC5-05: request_id requiring sanitization is correctly demuxed via custom_id
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


def _make_resolved(
    specs, model="claude-sonnet-4-6", max_tokens=100, request_options=None
):
    """Build a resolved_params list from old-style args (test helper only)."""
    rp = {"model": model, "max_tokens": max_tokens}
    if request_options:
        rp.update(request_options)
    return [dict(rp) for _ in specs]


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
            # Restore sys.modules to its exact prior state so we don't pollute
            # other test modules (e.g. test_llm_batch_di_wiring.py, which calls
            # importlib.reload on this adapter module and requires that the
            # in-sys.modules object match the one it imported).
            sys.modules.update(saved_modules)
            if saved_adapter is not None:
                sys.modules[adapter_key] = saved_adapter
            else:
                # Adapter was not loaded before this test; drop the fresh import
                # so the module returns to its original "not loaded" state.
                sys.modules.pop(adapter_key, None)

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
            else:
                sys.modules.pop(adapter_key, None)


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
                else:
                    sys.modules.pop(adapter_key, None)

    def test_cache_control_passes_through_to_sdk(self):
        """
        cache_control in message content must appear verbatim in the request
        passed to mock_sdk.messages.batches.create().
        """
        from agentmap.models.llm_execution import LLMRequest
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

            spec = LLMRequest(
                request_id="spec-1",
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
                resolved_params=_make_resolved([spec]),
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
    """TC-AC5-05: request_id requiring sanitization is correctly demuxed via custom_id."""

    def test_sanitized_request_id_stored_in_request_id_map(self):
        """
        When request_id contains chars outside ^[a-zA-Z0-9_-]{1,64}$,
        a sanitized custom_id must be used and stored in request_id_map.
        """
        from agentmap.models.llm_execution import LLMRequest
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

            dirty_request_id = "my spec/id"  # space and slash — violates regex
            spec = LLMRequest(
                request_id=dirty_request_id,
                messages=[{"role": "user", "content": "test"}],
            )

            _provider_batch_id, request_id_map, _expires_at = adapter.submit(
                specs=[spec],
                resolved_params=_make_resolved([spec]),
            )

        # The original request_id must be a key in the map
        assert (
            dirty_request_id in request_id_map
        ), "original request_id must be key in request_id_map"
        custom_id = request_id_map[dirty_request_id]

        # custom_id must be valid per Anthropic regex
        valid_pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
        assert valid_pattern.match(
            custom_id
        ), f"custom_id {custom_id!r} must match ^[a-zA-Z0-9_-]{{1,64}}$"

        # custom_id must differ from dirty request_id
        assert custom_id != dirty_request_id

    def test_clean_request_id_used_as_is(self):
        """When request_id is already valid, it must be used as-is (no hash)."""
        from agentmap.models.llm_execution import LLMRequest
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

            clean_request_id = "my-clean-spec"
            spec = LLMRequest(
                request_id=clean_request_id,
                messages=[{"role": "user", "content": "test"}],
            )

            _provider_batch_id, request_id_map, _expires_at = adapter.submit(
                specs=[spec],
                resolved_params=_make_resolved([spec]),
            )

        assert request_id_map[clean_request_id] == clean_request_id

    def test_fetch_results_demuxes_sanitized_custom_id(self):
        """
        fetch_results must yield records keyed by original request_id, not custom_id,
        when the request_id was sanitized.
        """
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        # Simulate JSONL-like result from SDK
        dirty_request_id = "my spec/id"
        # Compute what the adapter would produce for the sanitized custom_id
        import hashlib

        sanitized = hashlib.sha1(dirty_request_id.encode()).hexdigest()[:64]

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

        # request_id_map: dirty -> sanitized
        request_id_map = {dirty_request_id: sanitized}

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    request_id_map=request_id_map,
                )
            )

        assert len(records) == 1
        assert records[0].request_id == dirty_request_id


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

        request_id_map = {"spec-1": "spec-1"}

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    request_id_map=request_id_map,
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

        request_id_map = {"spec-2": "spec-2"}

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    request_id_map=request_id_map,
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
                request_id_map={},
            )

        import types

        assert isinstance(
            result, types.GeneratorType
        ), "fetch_results must be a lazy generator, not a list"


# ---------------------------------------------------------------------------
# Regression tests for UAT-rejected defects
# ---------------------------------------------------------------------------


def _make_adapter_with_client(client_instance):
    """Build adapter with a pre-made mock client instance."""
    from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

    mock_sdk = MagicMock()
    mock_sdk.Anthropic.return_value = client_instance
    with patch.dict(sys.modules, {"anthropic": mock_sdk}):
        return AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())


class TestFetchResultsErroredBranch:
    """F-HIGH-3: errored result must always produce a populated LLMExecutionError."""

    def test_errored_with_missing_error_payload_yields_structured_error(self):
        """
        When result.type == 'errored' but result.error is absent (None / missing
        attribute), fetch_results must yield a record with a populated
        LLMExecutionError, not error=None.

        RED before fix: error_data is None → error left as None.
        GREEN after fix: fallback LLMExecutionError synthesized.
        """
        from agentmap.models.llm_execution import LLMExecutionError
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        # Simulate provider item: errored, but .error returns None
        errored_item = MagicMock()
        errored_item.custom_id = "spec-err"
        errored_item.result.type = "errored"
        # .error attribute returns None (missing payload)
        errored_item.result.error = None

        client_instance.messages.batches.results.return_value = iter([errored_item])

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    request_id_map={"spec-err": "spec-err"},
                )
            )

        assert len(records) == 1
        record = records[0]
        assert record.status == "errored"
        assert record.error is not None, (
            "error must not be None for an errored result — "
            "REQ-F-007 requires a structured LLMExecutionError"
        )
        assert isinstance(record.error, LLMExecutionError)
        # The synthesized error must carry a meaningful type and message
        assert record.error.error_type is not None
        assert record.error.message  # non-empty string

    def test_errored_with_no_error_attr_yields_structured_error(self):
        """
        When result.error attribute does not exist at all (AttributeError path),
        fetch_results must still yield a structured LLMExecutionError.
        """
        from agentmap.models.llm_execution import LLMExecutionError
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        errored_item = MagicMock()
        errored_item.custom_id = "spec-noattr"
        errored_item.result.type = "errored"
        # Delete the .error attribute entirely so getattr returns default None
        del errored_item.result.error

        client_instance.messages.batches.results.return_value = iter([errored_item])

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    request_id_map={"spec-noattr": "spec-noattr"},
                )
            )

        assert len(records) == 1
        assert records[0].error is not None
        assert isinstance(records[0].error, LLMExecutionError)


class TestCustomIdCollisionDetection:
    """F-HIGH-4: custom_id sanitization collisions must be detected and raised."""

    def test_colliding_request_ids_raise_before_submit(self):
        """
        When two distinct request_ids sanitize to the same custom_id, submit()
        must raise LLMServiceError before calling the provider SDK.

        RED before fix: collision silently overwrites request_id_map.
        GREEN after fix: uniqueness check raises before batches.create().
        """
        from agentmap.exceptions import LLMServiceError
        from agentmap.models.llm_execution import LLMRequest
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        # Craft two request_ids that produce the same SHA-1 hex prefix.
        # The easiest way: one dirty request_id whose SHA-1 prefix equals a second
        # clean request_id that is already in ^[a-zA-Z0-9_-]{1,64}$ form.
        import hashlib

        dirty = "colliding spec/id"
        expected_hash = hashlib.sha1(dirty.encode()).hexdigest()[:64]
        # Make the second request_id exactly equal to the hash of the first
        clean_collider = expected_hash  # already alphanum — passes regex unchanged

        specs = [
            LLMRequest(request_id=dirty, messages=[{"role": "user", "content": "a"}]),
            LLMRequest(
                request_id=clean_collider, messages=[{"role": "user", "content": "b"}]
            ),
        ]

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            with pytest.raises(LLMServiceError):
                adapter.submit(
                    specs=specs,
                    resolved_params=_make_resolved(specs),
                )

        # SDK must NOT have been called
        client_instance.messages.batches.create.assert_not_called()

    def test_non_colliding_request_ids_succeed(self):
        """Non-colliding request_ids (mixed dirty/clean) must submit without error."""
        from agentmap.models.llm_execution import LLMRequest
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance
        batch_response = MagicMock()
        batch_response.id = "msgbatch_ok"
        batch_response.expires_at = None
        client_instance.messages.batches.create.return_value = batch_response

        specs = [
            LLMRequest(
                request_id="clean-id", messages=[{"role": "user", "content": "a"}]
            ),
            LLMRequest(
                request_id="another/dirty id",
                messages=[{"role": "user", "content": "b"}],
            ),
        ]

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            provider_batch_id, request_id_map, _ = adapter.submit(
                specs=specs,
                resolved_params=_make_resolved(specs),
            )

        assert provider_batch_id == "msgbatch_ok"
        assert len(request_id_map) == 2


class TestSucceededEmptyContent:
    """F-MED-2: succeeded result with empty/None content must not be reported as clean success."""

    def test_succeeded_with_empty_content_yields_errored_record(self):
        """
        A succeeded item with no content blocks (empty list or None) must yield
        an errored record (or raise), not a succeeded record with content=None.

        RED before fix: empty content → status='succeeded', content=None.
        GREEN after fix: empty content treated as errored with structured error.
        """
        from agentmap.models.llm_execution import LLMExecutionError
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        result_item = MagicMock()
        result_item.custom_id = "spec-empty"
        result_item.result.type = "succeeded"
        msg = MagicMock()
        msg.content = []  # empty — no content blocks
        msg.model = "claude-sonnet-4-6"
        msg.usage.input_tokens = 5
        msg.usage.output_tokens = 0
        msg.usage.cache_creation_input_tokens = None
        msg.usage.cache_read_input_tokens = None
        result_item.result.message = msg

        client_instance.messages.batches.results.return_value = iter([result_item])

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            records = list(
                adapter.fetch_results(
                    provider_batch_id="msgbatch_abc",
                    request_id_map={"spec-empty": "spec-empty"},
                )
            )

        assert len(records) == 1
        record = records[0]
        # Must NOT be a clean 'succeeded' with content=None
        assert not (
            record.status == "succeeded" and record.text is None
        ), "empty content must not be silently reported as succeeded with content=None"
        # Must be errored with a structured error
        assert record.status == "errored"
        assert isinstance(record.error, LLMExecutionError)


class TestSubmitMalformedSDKResponse:
    """F-MED-4: submit/poll must raise typed error on malformed SDK responses."""

    def test_submit_raises_typed_error_when_response_has_no_id(self):
        """
        When the SDK response object lacks a .id attribute, submit() must raise
        LLMServiceError (not AttributeError propagating to the caller).

        RED before fix: response.id → AttributeError.
        GREEN after fix: validated; raises LLMServiceError.
        """
        from agentmap.exceptions import LLMServiceError
        from agentmap.models.llm_execution import LLMRequest
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        # Response object with no .id attribute
        bad_response = MagicMock(spec=[])  # spec=[] means no attributes
        client_instance.messages.batches.create.return_value = bad_response

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
            specs_single = [
                LLMRequest(
                    request_id="s1", messages=[{"role": "user", "content": "hi"}]
                )
            ]
            with pytest.raises(LLMServiceError):
                adapter.submit(
                    specs=specs_single,
                    resolved_params=_make_resolved(specs_single),
                )


# ---------------------------------------------------------------------------
# T-E05-F04-004 tests: BatchAdapterProtocol conformance, normalized poll,
# result_ref arg
# ---------------------------------------------------------------------------


def _make_adapter():
    """Return a fully initialized AnthropicBatchAdapter with a mock SDK."""
    mock_sdk, client_instance = _make_mock_anthropic_module()
    with patch.dict(sys.modules, {"anthropic": mock_sdk}):
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
    # stash client for assertions
    adapter._client = client_instance
    return adapter


class TestBatchAdapterProtocolConformance:
    """AC-T1: isinstance(AnthropicBatchAdapter(...), BatchAdapterProtocol) is True."""

    def test_isinstance_batch_adapter_protocol(self):
        from agentmap.services.protocols.service_protocols import BatchAdapterProtocol

        mock_sdk, _ = _make_mock_anthropic_module()
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )

            adapter = AnthropicBatchAdapter(api_key="k", logger=MagicMock())

        assert isinstance(adapter, BatchAdapterProtocol)

    def test_provider_name_is_anthropic(self):
        mock_sdk, _ = _make_mock_anthropic_module()
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )

            assert AnthropicBatchAdapter.provider_name == "anthropic"
            adapter = AnthropicBatchAdapter(api_key="k", logger=MagicMock())
            assert adapter.provider_name == "anthropic"

    def test_supports_cancel_is_true(self):
        mock_sdk, _ = _make_mock_anthropic_module()
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )

            assert AnthropicBatchAdapter.supports_cancel is True
            adapter = AnthropicBatchAdapter(api_key="k", logger=MagicMock())
            assert adapter.supports_cancel is True


class TestNormalizedPoll:
    """AC-T2: poll returns BatchPollResult with already-normalized LLMBatchStatus."""

    def _make_batch_response(self, processing_status, results_url=None, ended_at=None):
        batch = MagicMock()
        batch.processing_status = processing_status
        batch.results_url = results_url
        batch.ended_at = ended_at
        rc = MagicMock()
        rc.processing = 1
        rc.succeeded = 2
        rc.errored = 0
        rc.canceled = 0
        rc.expired = 0
        batch.request_counts = rc
        return batch

    def test_poll_returns_batch_poll_result_instance(self):
        from agentmap.models.llm_execution import BatchPollResult

        adapter = _make_adapter()
        adapter._client.messages.batches.retrieve.return_value = (
            self._make_batch_response("in_progress")
        )
        result = adapter.poll("batch-123")
        assert isinstance(result, BatchPollResult)

    def test_poll_in_progress_maps_to_in_progress(self):
        from agentmap.models.llm_execution import LLMBatchStatus

        adapter = _make_adapter()
        adapter._client.messages.batches.retrieve.return_value = (
            self._make_batch_response("in_progress")
        )
        result = adapter.poll("batch-123")
        assert result.status == LLMBatchStatus.IN_PROGRESS

    def test_poll_ended_maps_to_ended(self):
        from agentmap.models.llm_execution import LLMBatchStatus

        adapter = _make_adapter()
        adapter._client.messages.batches.retrieve.return_value = (
            self._make_batch_response("ended", results_url="https://example.com/r")
        )
        result = adapter.poll("batch-123")
        assert result.status == LLMBatchStatus.ENDED
        assert result.results_url == "https://example.com/r"

    def test_poll_canceling_maps_to_canceling(self):
        from agentmap.models.llm_execution import LLMBatchStatus

        adapter = _make_adapter()
        adapter._client.messages.batches.retrieve.return_value = (
            self._make_batch_response("canceling")
        )
        result = adapter.poll("batch-123")
        assert result.status == LLMBatchStatus.CANCELING

    def test_poll_expired_maps_to_expired(self):
        from agentmap.models.llm_execution import LLMBatchStatus

        adapter = _make_adapter()
        adapter._client.messages.batches.retrieve.return_value = (
            self._make_batch_response("expired")
        )
        result = adapter.poll("batch-123")
        assert result.status == LLMBatchStatus.EXPIRED

    def test_poll_unknown_status_maps_to_failed(self):
        from agentmap.models.llm_execution import LLMBatchStatus

        adapter = _make_adapter()
        adapter._client.messages.batches.retrieve.return_value = (
            self._make_batch_response("some_unknown_status")
        )
        result = adapter.poll("batch-123")
        assert result.status == LLMBatchStatus.FAILED

    def test_poll_request_counts_populated(self):
        from agentmap.models.llm_execution import LLMBatchRequestCounts

        adapter = _make_adapter()
        adapter._client.messages.batches.retrieve.return_value = (
            self._make_batch_response("in_progress")
        )
        result = adapter.poll("batch-123")
        assert isinstance(result.request_counts, LLMBatchRequestCounts)
        assert result.request_counts.processing == 1
        assert result.request_counts.succeeded == 2


class TestFetchResultsResultRef:
    """AC-T3: fetch_results accepts result_ref argument (ignored for Anthropic)."""

    def test_fetch_results_accepts_result_ref_kwarg(self):
        adapter = _make_adapter()
        # Make SDK return one succeeded item
        item = MagicMock()
        item.custom_id = "spec__s1"
        item.result.type = "succeeded"
        item.result.message.content = [MagicMock(text="hello")]
        item.result.message.model = "claude-sonnet-4-6"
        usage = MagicMock()
        usage.input_tokens = 10
        usage.output_tokens = 5
        usage.cache_creation_input_tokens = None
        usage.cache_read_input_tokens = None
        item.result.message.usage = usage
        adapter._client.messages.batches.results.return_value = [item]

        request_id_map = {"s1": "spec__s1"}
        records = list(
            adapter.fetch_results("batch-123", request_id_map, result_ref="some-ref")
        )
        assert len(records) == 1
        assert records[0].request_id == "s1"

    def test_fetch_results_result_ref_none_is_default(self):
        """result_ref defaults to None — existing callers without the arg still work."""
        import inspect

        mock_sdk, _ = _make_mock_anthropic_module()
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )
        sig = inspect.signature(AnthropicBatchAdapter.fetch_results)
        assert sig.parameters["result_ref"].default is None


# ---------------------------------------------------------------------------
# T-E05-F04-010: Adapter-level serialization assertions
# ---------------------------------------------------------------------------


class TestAnthropicSubmitSerializesResolvedParams:
    """
    TC-SER-A1 through TC-SER-A4: prove that resolved_params values actually
    reach the dict passed to client.messages.batches.create(requests=...).

    The adapter builds ``params = {"messages": ...}`` then calls
    ``params.update(rp)`` for each spec, so temperature/max_tokens/passthroughs
    all end up nested inside ``requests[i]["params"]``.

    Counter-factual: removing the ``params.update(rp)`` line would make every
    assertion below fail, which is what we want.
    """

    def _make_adapter_and_client(self):
        """Return (adapter, client_instance) with SDK mocked."""
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        client_instance = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Anthropic.return_value = client_instance

        batch_response = MagicMock()
        batch_response.id = "msgbatch_ser_test"
        batch_response.expires_at = None
        client_instance.messages.batches.create.return_value = batch_response

        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            adapter = AnthropicBatchAdapter(api_key="test-key", logger=MagicMock())
        return adapter, client_instance

    def _extract_requests(self, client_instance):
        """Pull the ``requests`` list from the last batches.create call."""
        call_args = client_instance.messages.batches.create.call_args
        # submit calls create(requests=requests)
        if call_args.kwargs:
            return call_args.kwargs.get("requests", [])
        return call_args.args[0] if call_args.args else []

    def test_tc_ser_a1_temperature_appears_in_correct_spec_params(self):
        """
        TC-SER-A1: resolved temperature=0.7 must appear in requests[i].params
        on the exact spec that was submitted with that value.

        Counter-factual: if update(rp) is removed, params has no temperature key.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-temp", messages=[{"role": "user", "content": "hi"}]
        )
        resolved_params = [
            {"model": "claude-3-5-haiku", "max_tokens": 512, "temperature": 0.7}
        ]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        requests = self._extract_requests(client_instance)
        assert len(requests) == 1
        entry = requests[0]
        assert isinstance(entry, dict), "Each request entry must be a dict"
        params = entry["params"]
        assert "temperature" in params, (
            "temperature must be serialized into requests[0].params — "
            "counter-factual: removing params.update(rp) would drop this key"
        )
        assert params["temperature"] == 0.7

    def test_tc_ser_a2_max_tokens_appears_in_correct_spec_params(self):
        """
        TC-SER-A2: resolved max_tokens=256 must appear in requests[i].params
        on the correct spec entry.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-maxtok", messages=[{"role": "user", "content": "hi"}]
        )
        resolved_params = [{"model": "claude-3-5-haiku", "max_tokens": 256}]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        requests = self._extract_requests(client_instance)
        params = requests[0]["params"]
        assert "max_tokens" in params, "max_tokens must appear in SDK request params"
        assert params["max_tokens"] == 256

    def test_tc_ser_a3_passthrough_key_appears_in_correct_spec_params(self):
        """
        TC-SER-A3: a non-reserved key in resolved_params (simulating a
        passthrough from request_options) must appear verbatim in params.

        We use ``top_p=0.95`` as the passthrough — it is not in RESERVED_PARAMS
        and therefore flows through as-is after central resolution.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec = LLMRequest(
            request_id="spec-passthrough", messages=[{"role": "user", "content": "hi"}]
        )
        resolved_params = [
            {"model": "claude-3-5-haiku", "max_tokens": 100, "top_p": 0.95}
        ]

        adapter.submit(specs=[spec], resolved_params=resolved_params)

        requests = self._extract_requests(client_instance)
        params = requests[0]["params"]
        assert "top_p" in params, (
            "passthrough key top_p must appear in SDK request params — "
            "proves non-reserved request_options fills are applied"
        )
        assert params["top_p"] == 0.95

    def test_tc_ser_a4_params_appear_on_correct_spec_not_all(self):
        """
        TC-SER-A4: per-spec resolved params must land on the RIGHT spec entry
        (matched by custom_id), not bleed into every entry.

        Two specs with different temperatures; verify each entry has only its own value.
        """
        from agentmap.models.llm_execution import LLMRequest

        adapter, client_instance = self._make_adapter_and_client()

        spec_a = LLMRequest(
            request_id="spec-a", messages=[{"role": "user", "content": "a"}]
        )
        spec_b = LLMRequest(
            request_id="spec-b", messages=[{"role": "user", "content": "b"}]
        )
        resolved_params = [
            {"model": "claude-3-5-haiku", "max_tokens": 100, "temperature": 0.2},
            {"model": "claude-3-5-haiku", "max_tokens": 100, "temperature": 0.9},
        ]

        adapter.submit(specs=[spec_a, spec_b], resolved_params=resolved_params)

        requests = self._extract_requests(client_instance)
        assert len(requests) == 2

        # Build map: custom_id -> params
        by_custom_id = {r["custom_id"]: r["params"] for r in requests}

        # spec-a is clean — custom_id == spec-a
        assert (
            by_custom_id["spec-a"]["temperature"] == 0.2
        ), "spec-a must carry its own temperature=0.2, not spec-b's 0.9"
        assert (
            by_custom_id["spec-b"]["temperature"] == 0.9
        ), "spec-b must carry its own temperature=0.9, not spec-a's 0.2"
