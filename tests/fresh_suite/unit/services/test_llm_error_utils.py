"""
Unit tests for LLM error classification utilities.
"""

import unittest

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from agentmap.services.llm_error_utils import classify_llm_error, is_retryable


class TestClassifyLLMError(unittest.TestCase):
    """Tests for classify_llm_error()."""

    # -- pass-through ---------------------------------------------------------

    def test_already_typed_timeout_passes_through(self):
        err = LLMTimeoutError("timeout")
        result = classify_llm_error(err, "openai")
        self.assertIs(result, err)

    def test_already_typed_rate_limit_passes_through(self):
        err = LLMRateLimitError("rate limited")
        result = classify_llm_error(err, "openai")
        self.assertIs(result, err)

    def test_already_typed_config_passes_through(self):
        err = LLMConfigurationError("bad config")
        result = classify_llm_error(err, "openai")
        self.assertIs(result, err)

    def test_already_typed_dependency_passes_through(self):
        err = LLMDependencyError("missing dep")
        result = classify_llm_error(err, "openai")
        self.assertIs(result, err)

    # -- dependency -----------------------------------------------------------

    def test_import_error_classified_as_dependency(self):
        err = ImportError("No module named 'langchain_openai'")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMDependencyError)

    def test_message_with_install_classified_as_dependency(self):
        err = RuntimeError("Please install openai dependencies")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMDependencyError)

    # -- authentication / config ----------------------------------------------

    def test_api_key_classified_as_config(self):
        err = RuntimeError("Invalid api_key provided")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMConfigurationError)

    def test_authentication_classified_as_config(self):
        err = RuntimeError("Authentication failed: 401 Unauthorized")
        result = classify_llm_error(err, "anthropic")
        self.assertIsInstance(result, LLMConfigurationError)

    def test_model_not_found_classified_as_config(self):
        err = RuntimeError("model_not_found: gpt-99")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMConfigurationError)

    # -- rate limit -----------------------------------------------------------

    def test_rate_limit_classified(self):
        err = RuntimeError("Rate limit exceeded (429)")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMRateLimitError)

    def test_too_many_requests_classified(self):
        err = RuntimeError("Too many requests")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMRateLimitError)

    def test_quota_classified_as_rate_limit(self):
        err = RuntimeError("You have exceeded your quota")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMRateLimitError)

    # -- timeout / connection -------------------------------------------------

    def test_timeout_classified(self):
        err = RuntimeError("Request timed out after 30s")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMTimeoutError)

    def test_connection_error_classified(self):
        err = RuntimeError("Connection error: connection refused")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMTimeoutError)

    def test_502_classified(self):
        err = RuntimeError("502 Bad Gateway")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMTimeoutError)

    def test_503_classified(self):
        err = RuntimeError("503 Service Unavailable")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMTimeoutError)

    def test_server_error_classified(self):
        err = RuntimeError("Internal server error")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMTimeoutError)

    # -- default --------------------------------------------------------------

    def test_unknown_error_classified_as_provider_error(self):
        err = RuntimeError("Something completely unexpected")
        result = classify_llm_error(err, "openai")
        self.assertIsInstance(result, LLMProviderError)
        self.assertNotIsInstance(result, (LLMTimeoutError, LLMRateLimitError))


class TestIsRetryable(unittest.TestCase):
    """Tests for is_retryable()."""

    def test_timeout_is_retryable(self):
        self.assertTrue(is_retryable(LLMTimeoutError("timeout")))

    def test_rate_limit_is_retryable(self):
        self.assertTrue(is_retryable(LLMRateLimitError("rate limit")))

    def test_config_error_is_not_retryable(self):
        self.assertFalse(is_retryable(LLMConfigurationError("bad key")))

    def test_dependency_error_is_not_retryable(self):
        self.assertFalse(is_retryable(LLMDependencyError("missing")))

    def test_generic_provider_error_is_not_retryable(self):
        self.assertFalse(is_retryable(LLMProviderError("generic")))

    def test_unclassified_timeout_string_is_retryable(self):
        self.assertTrue(is_retryable(RuntimeError("connection timeout")))

    def test_unclassified_rate_limit_string_is_retryable(self):
        self.assertTrue(is_retryable(RuntimeError("429 Too Many Requests")))

    def test_unclassified_generic_is_not_retryable(self):
        self.assertFalse(is_retryable(RuntimeError("something else")))


if __name__ == "__main__":
    unittest.main()
