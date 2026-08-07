"""
Unit tests for AppConfigService.get_sse_config() accessor.

Tests the http.sse.* config section accessor added for E06-F05.
Test cases per test-plan.md §Acceptance Test Cases (T-E06-F05-001 scope):
  - TC-F05-005/006/007 depend on this accessor; these tests cover the
    accessor itself (defaults, individual overrides, round-trip from yaml).

Caller-Path Contract (per test-plan.md §Caller-Path Contracts):
  - Production entrypoint: AppConfigService.get_sse_config() → Dict[str, Any]
  - Lowest allowed mock seam: ConfigService.get_value_from_config (same as
    all other AppConfigService unit tests — mock the underlying config service,
    exercise the accessor logic directly)
  - Forbidden mocks: Do NOT mock get_value() or the accessor logic itself;
    only mock at the ConfigService boundary
  - Counter-factual: A buggy accessor that returns no defaults when http.sse
    is absent would return {} — the assertion
    assertEqual(result["max_stream_duration_seconds"], 1800) would fail.
    A buggy accessor that ignores overrides would always return the default
    for max_concurrent_streams even when config has 50 — failing the
    assertEqual(result["max_concurrent_streams"], 50) assertion.
"""

import unittest
from unittest.mock import Mock

from agentmap.exceptions.base_exceptions import ConfigurationException
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.config_service import ConfigService

# ---------------------------------------------------------------------------
# Helper: build an AppConfigService with a controlled in-memory config dict
# ---------------------------------------------------------------------------


def _make_service(config_data: dict) -> AppConfigService:
    """
    Create an AppConfigService backed by a mock ConfigService
    that returns config_data from load_config().

    The mock's get_value_from_config implements a real dot-path traversal
    so that get_value() (and therefore get_sse_config()) exercises the
    actual accessor logic rather than a short-circuit.
    """
    mock_config_service = Mock(spec=ConfigService)
    mock_config_service.load_config.return_value = config_data

    def _get_value_from_config(cfg, path, default=None):
        parts = path.split(".")
        current = cfg
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    mock_config_service.get_value_from_config.side_effect = _get_value_from_config

    return AppConfigService(
        config_service=mock_config_service,
        config_path="test_config.yaml",
    )


# ---------------------------------------------------------------------------
# SSE Config Defaults (AC ref: spec.md §A.4; task spec AC-1 for this task)
# ---------------------------------------------------------------------------


class TestGetSseConfigDefaults(unittest.TestCase):
    """
    get_sse_config() returns the §A.4 defaults when http.sse is absent.

    Counter-factual: if the accessor returned {} instead of applying defaults,
    every assertIn / assertEqual against the four default keys would fail.
    """

    def setUp(self):
        # Config with NO http section at all
        self.service = _make_service(
            {
                "logging": {"level": "INFO"},
            }
        )

    def test_returns_dict(self):
        result = self.service.get_sse_config()
        self.assertIsInstance(result, dict)

    def test_default_max_stream_duration_seconds(self):
        """Default max_stream_duration_seconds must be 1800 (30 min)."""
        result = self.service.get_sse_config()
        self.assertEqual(result["max_stream_duration_seconds"], 1800)

    def test_default_idle_timeout_seconds(self):
        """Default idle_timeout_seconds must be 30."""
        result = self.service.get_sse_config()
        self.assertEqual(result["idle_timeout_seconds"], 30)

    def test_default_heartbeat_interval_seconds(self):
        """Default heartbeat_interval_seconds must be 15."""
        result = self.service.get_sse_config()
        self.assertEqual(result["heartbeat_interval_seconds"], 15)

    def test_default_max_concurrent_streams(self):
        """Default max_concurrent_streams must be 100."""
        result = self.service.get_sse_config()
        self.assertEqual(result["max_concurrent_streams"], 100)

    def test_all_four_keys_present(self):
        """All four §A.4 keys must be present even with no http.sse config."""
        result = self.service.get_sse_config()
        self.assertIn("max_stream_duration_seconds", result)
        self.assertIn("idle_timeout_seconds", result)
        self.assertIn("heartbeat_interval_seconds", result)
        self.assertIn("max_concurrent_streams", result)

    def test_absent_http_section_gives_defaults(self):
        """Config with http key absent entirely still returns full defaults."""
        service_no_http = _make_service({})
        result = service_no_http.get_sse_config()
        self.assertEqual(result["max_stream_duration_seconds"], 1800)
        self.assertEqual(result["idle_timeout_seconds"], 30)
        self.assertEqual(result["heartbeat_interval_seconds"], 15)
        self.assertEqual(result["max_concurrent_streams"], 100)


# ---------------------------------------------------------------------------
# SSE Config Overrides (AC ref: task spec AC-2 — individual key overrides)
# ---------------------------------------------------------------------------


class TestGetSseConfigOverrides(unittest.TestCase):
    """
    Each key is individually overridable; non-overridden keys fall back to
    defaults.

    Counter-factual: an accessor that ignores config values and always returns
    the hardcoded defaults would return max_concurrent_streams=100 when config
    has 50, failing assertEqual(result["max_concurrent_streams"], 50).
    """

    def _make_with_sse(self, sse_overrides: dict) -> AppConfigService:
        return _make_service({"http": {"sse": sse_overrides}})

    def test_override_max_concurrent_streams(self):
        """Overriding max_concurrent_streams=50 is reflected; others default."""
        service = self._make_with_sse({"max_concurrent_streams": 50})
        result = service.get_sse_config()
        self.assertEqual(result["max_concurrent_streams"], 50)
        # Other keys still default
        self.assertEqual(result["max_stream_duration_seconds"], 1800)
        self.assertEqual(result["idle_timeout_seconds"], 30)
        self.assertEqual(result["heartbeat_interval_seconds"], 15)

    def test_override_max_stream_duration_seconds(self):
        """Overriding max_stream_duration_seconds is reflected; others default."""
        service = self._make_with_sse({"max_stream_duration_seconds": 3600})
        result = service.get_sse_config()
        self.assertEqual(result["max_stream_duration_seconds"], 3600)
        self.assertEqual(result["idle_timeout_seconds"], 30)
        self.assertEqual(result["heartbeat_interval_seconds"], 15)
        self.assertEqual(result["max_concurrent_streams"], 100)

    def test_override_idle_timeout_seconds(self):
        """Overriding idle_timeout_seconds is reflected; others default."""
        service = self._make_with_sse({"idle_timeout_seconds": 60})
        result = service.get_sse_config()
        self.assertEqual(result["idle_timeout_seconds"], 60)
        self.assertEqual(result["max_stream_duration_seconds"], 1800)
        self.assertEqual(result["heartbeat_interval_seconds"], 15)
        self.assertEqual(result["max_concurrent_streams"], 100)

    def test_override_heartbeat_interval_seconds(self):
        """Overriding heartbeat_interval_seconds is reflected; others default."""
        service = self._make_with_sse({"heartbeat_interval_seconds": 10})
        result = service.get_sse_config()
        self.assertEqual(result["heartbeat_interval_seconds"], 10)
        self.assertEqual(result["max_stream_duration_seconds"], 1800)
        self.assertEqual(result["idle_timeout_seconds"], 30)
        self.assertEqual(result["max_concurrent_streams"], 100)

    def test_override_all_keys(self):
        """All four keys can be overridden simultaneously."""
        service = self._make_with_sse(
            {
                "max_stream_duration_seconds": 900,
                "idle_timeout_seconds": 20,
                "heartbeat_interval_seconds": 5,
                "max_concurrent_streams": 200,
            }
        )
        result = service.get_sse_config()
        self.assertEqual(result["max_stream_duration_seconds"], 900)
        self.assertEqual(result["idle_timeout_seconds"], 20)
        self.assertEqual(result["heartbeat_interval_seconds"], 5)
        self.assertEqual(result["max_concurrent_streams"], 200)

    def test_partial_sse_section_leaves_other_keys_at_defaults(self):
        """
        A partial http.sse section (only one key set) leaves all other
        keys at their defaults — not absent.
        """
        service = self._make_with_sse({"max_concurrent_streams": 50})
        result = service.get_sse_config()
        # The overridden key reflects the config value
        self.assertEqual(result["max_concurrent_streams"], 50)
        # Non-overridden keys must still be present (not KeyError)
        self.assertIn("max_stream_duration_seconds", result)
        self.assertIn("idle_timeout_seconds", result)
        self.assertIn("heartbeat_interval_seconds", result)
        # And their values must be the §A.4 defaults
        self.assertEqual(result["max_stream_duration_seconds"], 1800)
        self.assertEqual(result["idle_timeout_seconds"], 30)
        self.assertEqual(result["heartbeat_interval_seconds"], 15)


# ---------------------------------------------------------------------------
# SSE Config type expectations (values are ints, not strings)
# ---------------------------------------------------------------------------


class TestGetSseConfigTypes(unittest.TestCase):
    """
    Default values are integers, not strings. The YAML section stores them
    as integers; the accessor should not coerce them to strings.
    """

    def setUp(self):
        self.service = _make_service({})

    def test_default_values_are_integers(self):
        """All four defaults must be int, not str or float."""
        result = self.service.get_sse_config()
        self.assertIsInstance(result["max_stream_duration_seconds"], int)
        self.assertIsInstance(result["idle_timeout_seconds"], int)
        self.assertIsInstance(result["heartbeat_interval_seconds"], int)
        self.assertIsInstance(result["max_concurrent_streams"], int)

    def test_overridden_integer_values_remain_integers(self):
        """Integer values loaded from config stay as int."""
        service = _make_service({"http": {"sse": {"max_concurrent_streams": 50}}})
        result = service.get_sse_config()
        self.assertIsInstance(result["max_concurrent_streams"], int)
        self.assertEqual(result["max_concurrent_streams"], 50)


# ---------------------------------------------------------------------------
# YAML round-trip: agentmap_config.yaml parses without error (AC-3 for task)
# ---------------------------------------------------------------------------


class TestSseConfigYamlRoundTrip(unittest.TestCase):
    """
    agentmap_config.yaml's http.sse section round-trips correctly through
    get_sse_config().

    This test exercises the REAL ConfigService + REAL yaml file rather than
    a mock, verifying that the yaml addition parses cleanly and the accessor
    reads the defaults through the real stack.

    Counter-factual: if http.sse were missing from the yaml (or mis-indented
    so it doesn't parse as a nested dict), the accessor would still return
    defaults (which is correct behaviour), but this test also confirms the
    yaml file is valid YAML by importing it without error.
    """

    def test_agentmap_config_yaml_parses_without_error(self):
        """agentmap_config.yaml must be loadable without a YAML parse error."""
        import pathlib

        import yaml  # pyyaml is already a project dependency

        yaml_path = pathlib.Path(__file__).resolve().parents[5] / "agentmap_config.yaml"
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        self.assertIsInstance(data, dict, "agentmap_config.yaml must parse to a dict")

    def test_agentmap_config_yaml_sse_section_has_correct_defaults(self):
        """
        If the yaml contains http.sse, the values must match §A.4.
        If the section is absent, the accessor supplies defaults — also valid.
        """
        import pathlib

        import yaml

        yaml_path = pathlib.Path(__file__).resolve().parents[5] / "agentmap_config.yaml"
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        http_section = data.get("http", {})
        sse_section = http_section.get("sse", {})

        # If present, values must match §A.4 defaults (or be operator-tuned)
        if "max_stream_duration_seconds" in sse_section:
            self.assertIsInstance(sse_section["max_stream_duration_seconds"], int)
        if "idle_timeout_seconds" in sse_section:
            self.assertIsInstance(sse_section["idle_timeout_seconds"], int)
        if "heartbeat_interval_seconds" in sse_section:
            self.assertIsInstance(sse_section["heartbeat_interval_seconds"], int)
        if "max_concurrent_streams" in sse_section:
            self.assertIsInstance(sse_section["max_concurrent_streams"], int)

    def test_real_config_service_round_trip(self):
        """
        AppConfigService built from the real agentmap_config.yaml returns
        the expected SSE defaults (or configured values if present).
        """
        import pathlib

        from agentmap.services.config.config_service import ConfigService

        yaml_path = pathlib.Path(__file__).resolve().parents[5] / "agentmap_config.yaml"
        if not yaml_path.exists():
            self.skipTest("agentmap_config.yaml not found — skipping round-trip test")

        real_config_service = ConfigService()
        real_app_config = AppConfigService(
            config_service=real_config_service,
            config_path=str(yaml_path),
        )

        result = real_app_config.get_sse_config()

        # Result must be a dict with all four keys
        self.assertIsInstance(result, dict)
        self.assertIn("max_stream_duration_seconds", result)
        self.assertIn("idle_timeout_seconds", result)
        self.assertIn("heartbeat_interval_seconds", result)
        self.assertIn("max_concurrent_streams", result)

        # Values must be positive integers
        self.assertGreater(result["max_stream_duration_seconds"], 0)
        self.assertGreater(result["idle_timeout_seconds"], 0)
        self.assertGreater(result["heartbeat_interval_seconds"], 0)
        self.assertGreater(result["max_concurrent_streams"], 0)


# ---------------------------------------------------------------------------
# TD-035: http.sse.* validation — negative/zero/non-numeric values must raise
# a controlled ConfigurationException, not propagate to an uncontrolled 500
# at semaphore-construction or deadline-arithmetic time.
# ---------------------------------------------------------------------------


class TestGetSseConfigValidation(unittest.TestCase):
    """
    get_sse_config() must validate http.sse.* values eagerly and raise
    ConfigurationException (not AttributeError/ValueError/TypeError) for
    invalid configuration.

    Counter-factual: an accessor that merges without validating would return
    the raw invalid value (e.g. max_concurrent_streams=-1) and let the
    exception surface later from asyncio.Semaphore(int(-1)) as an
    uncontrolled ValueError/500 instead of here as a ConfigurationException.
    """

    def _make_with_sse(self, sse_overrides) -> AppConfigService:
        return _make_service({"http": {"sse": sse_overrides}})

    # -- max_concurrent_streams --------------------------------------------

    def test_negative_max_concurrent_streams_raises_configuration_exception(self):
        service = self._make_with_sse({"max_concurrent_streams": -1})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_zero_max_concurrent_streams_raises_configuration_exception(self):
        """max_concurrent_streams=0 is type-valid but semantically poisons the
        semaphore (permanently locked, silent 503s) — must be rejected."""
        service = self._make_with_sse({"max_concurrent_streams": 0})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_non_numeric_max_concurrent_streams_raises_configuration_exception(self):
        service = self._make_with_sse({"max_concurrent_streams": "abc"})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    # -- max_stream_duration_seconds ----------------------------------------

    def test_negative_max_stream_duration_seconds_raises(self):
        service = self._make_with_sse({"max_stream_duration_seconds": -100})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_zero_max_stream_duration_seconds_raises(self):
        service = self._make_with_sse({"max_stream_duration_seconds": 0})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_non_numeric_max_stream_duration_seconds_raises(self):
        service = self._make_with_sse({"max_stream_duration_seconds": "abc"})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    # -- idle_timeout_seconds -------------------------------------------------

    def test_negative_idle_timeout_seconds_raises(self):
        service = self._make_with_sse({"idle_timeout_seconds": -30})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_zero_idle_timeout_seconds_raises(self):
        service = self._make_with_sse({"idle_timeout_seconds": 0})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_non_numeric_idle_timeout_seconds_raises(self):
        service = self._make_with_sse({"idle_timeout_seconds": "abc"})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    # -- heartbeat_interval_seconds: 0 is VALID, negative/non-numeric is not --

    def test_zero_heartbeat_interval_seconds_is_valid(self):
        """heartbeat_interval_seconds=0 disables keepalive; must NOT raise."""
        service = self._make_with_sse({"heartbeat_interval_seconds": 0})
        result = service.get_sse_config()
        self.assertEqual(result["heartbeat_interval_seconds"], 0)

    def test_negative_heartbeat_interval_seconds_raises(self):
        service = self._make_with_sse({"heartbeat_interval_seconds": -1})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_non_numeric_heartbeat_interval_seconds_raises(self):
        service = self._make_with_sse({"heartbeat_interval_seconds": "abc"})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    # -- http.sse section itself must be a dict ------------------------------

    def test_null_sse_section_raises_configuration_exception(self):
        """http: {sse: null} must not crash _merge_with_defaults with
        AttributeError; it must raise a controlled ConfigurationException."""
        service = _make_service({"http": {"sse": None}})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_non_dict_sse_section_raises_configuration_exception(self):
        service = _make_service({"http": {"sse": "not-a-dict"}})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_list_sse_section_raises_configuration_exception(self):
        service = _make_service({"http": {"sse": []}})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    # -- error message must be actionable ------------------------------------

    def test_error_message_names_the_offending_key(self):
        service = self._make_with_sse({"max_concurrent_streams": -1})
        with self.assertRaises(ConfigurationException) as ctx:
            service.get_sse_config()
        self.assertIn("max_concurrent_streams", str(ctx.exception))

    # -- valid boolean-typed values must still be rejected (bool is an int) --

    def test_boolean_max_concurrent_streams_raises(self):
        """bool is a subclass of int in Python; True/False must not silently
        pass as valid integers for a concurrency cap."""
        service = self._make_with_sse({"max_concurrent_streams": True})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    # -- numeric strings (env:VAR resolution always yields str) must pass ----

    def test_numeric_string_max_concurrent_streams_is_valid(self):
        """ConfigService._resolve_env_vars() resolves env:VAR_NAME entries via
        os.environ.get(), which always returns str — a valid numeric string
        (e.g. from env-var substitution) must not be rejected."""
        service = self._make_with_sse({"max_concurrent_streams": "50"})
        result = service.get_sse_config()
        self.assertEqual(result["max_concurrent_streams"], "50")

    def test_negative_numeric_string_max_concurrent_streams_raises(self):
        service = self._make_with_sse({"max_concurrent_streams": "-1"})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    # -- non-finite floats (NaN/Infinity, parseable by YAML/float()) rejected -

    def test_nan_max_concurrent_streams_raises(self):
        service = self._make_with_sse({"max_concurrent_streams": float("nan")})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()

    def test_infinity_max_stream_duration_seconds_raises(self):
        service = self._make_with_sse({"max_stream_duration_seconds": float("inf")})
        with self.assertRaises(ConfigurationException):
            service.get_sse_config()


if __name__ == "__main__":
    unittest.main()
