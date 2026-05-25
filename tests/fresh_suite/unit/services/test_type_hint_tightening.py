"""
Tests for T-E05-F02-006: tighten async invoke_async_fn type + structured-message type alias.

Part A: LLMFallbackHandler.__init__ invoke_async_fn parameter must be typed
        Callable[..., Awaitable[LLMResponse]], not Callable[..., Awaitable[str]].

Part B: messages parameters across service_protocols.py and llm_service.py must
        accept Dict[str, Any] content (not str-only), consistent with
        LLMCallSpec.messages: List[Dict[str, Any]].

Production entrypoints:
  - LLMFallbackHandler.__init__ (invoke_async_fn kwarg)
  - LLMServiceProtocol.call_llm (messages param)
  - LLMServiceProtocol.call_llm_async (messages param)
  - LLMService.call_llm (messages param)
  - LLMService.call_llm_async (messages param)
"""

import inspect
import unittest
from typing import get_type_hints

from agentmap.models.llm_execution import LLMCallSpec, LLMResponse
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from agentmap.services.llm_service import LLMService
from agentmap.services.protocols.service_protocols import LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


def _make_fallback_handler(**overrides) -> LLMFallbackHandler:
    """Construct a minimal LLMFallbackHandler for type-hint tests."""
    mock_logging = MockServiceFactory.create_mock_logging_service()
    kwargs = dict(logging_service=mock_logging)
    kwargs.update(overrides)
    return LLMFallbackHandler(**kwargs)


class TestInvokeAsyncFnTypeHint(unittest.TestCase):
    """
    Part A: invoke_async_fn must be typed Callable[..., Awaitable[LLMResponse]].

    Counter-factual: if the type hint still says Awaitable[str], a static type
    checker would allow passing a function that returns str directly. The fix
    ensures that the declared return type matches what _invoke_client_async
    actually returns and what the broader async resilience layer produces.
    """

    def test_invoke_async_fn_annotation_returns_llm_response(self):
        """invoke_async_fn annotation must declare Awaitable[LLMResponse], not Awaitable[str]."""
        hints = get_type_hints(LLMFallbackHandler.__init__)
        async_fn_hint = hints.get("invoke_async_fn")
        self.assertIsNotNone(
            async_fn_hint,
            "invoke_async_fn parameter must have a type annotation on __init__",
        )
        # The annotation should NOT contain 'str' as the return type inside Awaitable
        # Stringify the hint so we can inspect it without importing typing internals
        hint_str = str(async_fn_hint)
        self.assertNotIn(
            "Awaitable[str]",
            hint_str,
            f"invoke_async_fn annotation still contains Awaitable[str]; got: {hint_str}",
        )

    def test_invoke_async_fn_annotation_references_llm_response(self):
        """invoke_async_fn annotation must reference LLMResponse."""
        hints = get_type_hints(LLMFallbackHandler.__init__)
        async_fn_hint = hints.get("invoke_async_fn")
        self.assertIsNotNone(async_fn_hint)
        # The resolved annotation should include LLMResponse somewhere in it
        # We walk the __args__ of the Optional[Callable[...]] to find it
        # Optional[X] == Union[X, None], so __args__ = (X, NoneType)
        args = getattr(async_fn_hint, "__args__", ())
        # args[0] should be the Callable itself
        callable_hint = next((a for a in args if a is not type(None)), None)
        self.assertIsNotNone(callable_hint, "Expected a Callable hint inside Optional")
        callable_str = str(callable_hint)
        self.assertIn(
            "LLMResponse",
            callable_str,
            f"invoke_async_fn Callable hint does not reference LLMResponse; got: {callable_str}",
        )

    def test_fallback_handler_accepts_llm_response_returning_callable(self):
        """LLMFallbackHandler can be instantiated with an LLMResponse-returning async fn."""

        async def fake_async_fn(client, msgs, provider, model) -> LLMResponse:
            return LLMResponse(
                text="ok",
                resolved_provider=provider,
                resolved_model=model,
                usage=None,
            )

        # This should not raise — the callable signature matches the declared type
        handler = _make_fallback_handler(invoke_async_fn=fake_async_fn)
        self.assertIs(handler._invoke_async_fn, fake_async_fn)


class TestMessagesTypeHintAllowsAny(unittest.TestCase):
    """
    Part B: messages parameters must accept Dict[str, Any], not just Dict[str, str].

    Counter-factual: if messages is still List[Dict[str, str]], a static type
    checker rejects structured content blocks (vision messages, cache-control
    dicts, list-valued content) that production callers pass. The fix widens
    the annotation to List[Dict[str, Any]] to match LLMCallSpec.messages.
    """

    def test_llm_call_spec_messages_type_is_any(self):
        """LLMCallSpec.messages field uses Dict[str, Any] — the reference contract."""
        hints = get_type_hints(LLMCallSpec)
        messages_hint = hints.get("messages")
        self.assertIsNotNone(messages_hint)
        hint_str = str(messages_hint)
        # Must NOT say str in the dict value position
        self.assertNotIn(
            "Dict[str, str]",
            hint_str,
            f"LLMCallSpec.messages should already use Dict[str, Any]; got: {hint_str}",
        )

    def test_service_protocols_call_llm_messages_accepts_any(self):
        """LLMServiceProtocol.call_llm messages param must be List[Dict[str, Any]]."""
        # Use inspect to get the annotation from the Protocol method signature
        sig = inspect.signature(LLMServiceProtocol.call_llm)
        messages_param = sig.parameters.get("messages")
        self.assertIsNotNone(
            messages_param,
            "LLMServiceProtocol.call_llm must have a 'messages' parameter",
        )
        annotation = messages_param.annotation
        if annotation is inspect.Parameter.empty:
            self.fail("LLMServiceProtocol.call_llm 'messages' has no annotation")
        annotation_str = str(annotation)
        self.assertNotIn(
            "Dict[str, str]",
            annotation_str,
            f"LLMServiceProtocol.call_llm messages still annotated as Dict[str, str]; "
            f"got: {annotation_str}",
        )

    def test_service_protocols_call_llm_async_messages_accepts_any(self):
        """LLMServiceProtocol.call_llm_async messages param must be List[Dict[str, Any]]."""
        sig = inspect.signature(LLMServiceProtocol.call_llm_async)
        messages_param = sig.parameters.get("messages")
        self.assertIsNotNone(
            messages_param,
            "LLMServiceProtocol.call_llm_async must have a 'messages' parameter",
        )
        annotation = messages_param.annotation
        if annotation is inspect.Parameter.empty:
            self.fail("LLMServiceProtocol.call_llm_async 'messages' has no annotation")
        annotation_str = str(annotation)
        self.assertNotIn(
            "Dict[str, str]",
            annotation_str,
            f"LLMServiceProtocol.call_llm_async messages still annotated as Dict[str, str]; "
            f"got: {annotation_str}",
        )

    def test_llm_service_call_llm_messages_accepts_any(self):
        """LLMService.call_llm messages param must be List[Dict[str, Any]]."""
        sig = inspect.signature(LLMService.call_llm)
        messages_param = sig.parameters.get("messages")
        self.assertIsNotNone(messages_param)
        annotation = messages_param.annotation
        if annotation is inspect.Parameter.empty:
            self.fail("LLMService.call_llm 'messages' has no annotation")
        annotation_str = str(annotation)
        self.assertNotIn(
            "Dict[str, str]",
            annotation_str,
            f"LLMService.call_llm messages still annotated as Dict[str, str]; "
            f"got: {annotation_str}",
        )

    def test_llm_service_call_llm_async_messages_accepts_any(self):
        """LLMService.call_llm_async messages param must be List[Dict[str, Any]]."""
        sig = inspect.signature(LLMService.call_llm_async)
        messages_param = sig.parameters.get("messages")
        self.assertIsNotNone(messages_param)
        annotation = messages_param.annotation
        if annotation is inspect.Parameter.empty:
            self.fail("LLMService.call_llm_async 'messages' has no annotation")
        annotation_str = str(annotation)
        self.assertNotIn(
            "Dict[str, str]",
            annotation_str,
            f"LLMService.call_llm_async messages still annotated as Dict[str, str]; "
            f"got: {annotation_str}",
        )

    def test_structured_message_content_accepted_at_runtime(self):
        """LLMCallSpec can be constructed with structured (non-str) content values."""
        # This tests the actual data model allows structured blocks
        structured_messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
            {
                "role": "user",
                "content": [{"type": "image_url", "url": "http://x.com/img.png"}],
            },
        ]
        spec = LLMCallSpec(
            spec_id="test-001",
            messages=structured_messages,
            provider="openai",
            model="gpt-4o",
        )
        self.assertEqual(spec.messages, structured_messages)

    def test_llm_message_type_alias_exported(self):
        """LLMMessage type alias must be importable from agentmap.models.llm_execution."""
        from agentmap.models import llm_execution as m

        self.assertTrue(
            hasattr(m, "LLMMessage"),
            "LLMMessage type alias must be defined in agentmap.models.llm_execution",
        )
        # LLMMessage should be equivalent to Dict[str, Any]
        alias = m.LLMMessage
        alias_str = str(alias)
        self.assertIn(
            "Any",
            alias_str,
            f"LLMMessage alias should reference Any; got: {alias_str}",
        )


if __name__ == "__main__":
    unittest.main()
