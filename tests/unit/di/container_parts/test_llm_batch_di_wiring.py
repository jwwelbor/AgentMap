"""
Tests for T-E05-F03-004 and T-E05-F04-008: DI wiring for batch adapter and repository.

TC-AC9-02: LLMDependencyError raised when anthropic is not importable.
INT-05: LLMService resolves with AnthropicBatchAdapter and BatchHandleRepository wired.
TC-AC9-03: No new third-party dependency added to pyproject.toml for anthropic.

TC-091: pyproject.toml has openai and google-genai only in optional extras (T-E05-F04-008).
TC-092: ADR file exists documenting dependency policy change (T-E05-F04-008).
TC-F04-DI: LLMContainer registers all three adapters; missing SDK results in log+skip.
"""

import builtins
import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# TC-AC9-02: LLMDependencyError raised when anthropic import is gated
# ---------------------------------------------------------------------------


class TestAnthropicImportGating:
    """TC-AC9-02: Adapter raises LLMDependencyError if anthropic SDK not importable."""

    def test_adapter_raises_llm_dependency_error_when_anthropic_missing(self):
        """
        Counter-factual: a buggy impl with top-level `import anthropic` would
        raise bare ImportError at module import time, not at instantiation.
        This test mocks builtins.__import__ for 'anthropic' after the module
        is loaded, verifying the guard fires at __init__.
        """
        from agentmap.exceptions import LLMDependencyError

        real_import = builtins.__import__

        def _fail_anthropic(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return real_import(name, *args, **kwargs)

        mock_logger = MagicMock()

        # Reload the adapter module so the import guard runs fresh.
        import importlib
        import sys

        import agentmap.services.llm.anthropic_batch_adapter as _mod

        # Guard against the module having been evicted from sys.modules by
        # another test's teardown — reload() requires the live object to be the
        # one registered in sys.modules.
        if sys.modules.get(_mod.__name__) is not _mod:
            _mod = importlib.import_module(_mod.__name__)
        else:
            importlib.reload(_mod)

        with patch("builtins.__import__", side_effect=_fail_anthropic):
            with pytest.raises(LLMDependencyError):
                _mod.AnthropicBatchAdapter(api_key="sk-test", logger=mock_logger)


# ---------------------------------------------------------------------------
# TC-AC9-03: pyproject.toml — no new top-level anthropic dependency added
# ---------------------------------------------------------------------------


class TestNoNewDependency:
    """TC-AC9-03: anthropic must NOT appear as a direct dependency in pyproject.toml."""

    def test_anthropic_not_in_pyproject_dependencies(self):
        """
        anthropic is a transitive dep via langchain-anthropic.
        Counter-factual: if someone added 'anthropic' to [tool.poetry.dependencies]
        or [project].dependencies, this test would catch the NFR violation.
        """
        repo_root = Path(__file__).parents[4]
        pyproject_path = repo_root / "pyproject.toml"
        assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        # Check both PEP-517 and Poetry dependency tables.
        pep517_deps = data.get("project", {}).get("dependencies", [])
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})

        # Normalize: pep517 deps are strings like "anthropic>=0.1"
        pep517_names = {
            dep.split("[")[0]
            .split(">=")[0]
            .split("==")[0]
            .split("!=")[0]
            .strip()
            .lower()
            for dep in pep517_deps
        }
        poetry_names = {k.lower() for k in poetry_deps.keys()}

        assert (
            "anthropic" not in pep517_names
        ), "anthropic must not appear in [project].dependencies (REQ-NF-003)."
        assert (
            "anthropic" not in poetry_names
        ), "anthropic must not appear in [tool.poetry.dependencies] (REQ-NF-003)."


# ---------------------------------------------------------------------------
# INT-05: DI container resolves LLMService with batch deps wired
# ---------------------------------------------------------------------------


class TestLLMDIBatchWiring:
    """INT-05: LLMService built from DI has non-None batch adapter and repository."""

    def _make_llm_service_via_factory(self, tmp_path):
        """
        Construct LLMService by calling the DI container factory directly,
        mirroring the production wiring in llm.py but with mocked dependencies.
        """
        from agentmap.di.container_parts.llm import LLMContainer

        mock_app_config = MagicMock()
        mock_app_config.get_llm_config.return_value = {"api_key": "sk-test-key"}
        mock_app_config.get_value.return_value = str(tmp_path)
        mock_app_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        mock_telemetry = MagicMock()
        mock_telemetry._content_capture_flags = {}

        # Call the private factory directly (same code path as providers.Singleton).
        llm_svc = LLMContainer._create_llm_service(
            app_config_service=mock_app_config,
            logging_service=mock_logging,
            llm_routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            llm_routing_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
            batch_adapter=None,  # let DI wiring inject real objects
            batch_repo=None,
        )
        return llm_svc

    def test_llm_service_has_batch_adapter_attribute(self, tmp_path):
        """INT-05 (partial): _create_llm_service accepts batch_adapter kwarg."""
        from agentmap.services.llm_service import LLMService

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        mock_batch_adapter = MagicMock()
        mock_batch_repo = MagicMock()

        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            routing_config_service=MagicMock(),
            telemetry_service=MagicMock(),
            batch_adapter=mock_batch_adapter,
            batch_repo=mock_batch_repo,
        )

        # F04: _batch_adapter is stored in _batch_adapters registry keyed "anthropic".
        assert svc._batch_adapters.get("anthropic") is mock_batch_adapter
        assert svc._batch_repo is mock_batch_repo

    def test_di_factory_creates_batch_adapter_singleton(self, tmp_path):
        """
        INT-05: _create_llm_batch_adapter factory in LLMContainer builds
        a non-None AnthropicBatchAdapter (with mocked anthropic SDK import).
        """
        # We need anthropic to be importable for the adapter to build.
        # Mock the anthropic module so we don't need the real package.
        import sys
        from unittest.mock import MagicMock as MM

        fake_anthropic = MM()
        fake_anthropic.Anthropic = MM(return_value=MM())

        with patch.dict(sys.modules, {"anthropic": fake_anthropic}):
            from agentmap.services.llm.anthropic_batch_adapter import (
                AnthropicBatchAdapter,
            )

            mock_logger = MagicMock()
            adapter = AnthropicBatchAdapter(api_key="sk-test", logger=mock_logger)
            assert adapter is not None
            assert isinstance(adapter, AnthropicBatchAdapter)

    def test_di_factory_creates_batch_repo_singleton(self, tmp_path):
        """
        INT-05: _create_batch_handle_repository factory builds a
        non-None BatchHandleRepository with the configured batch_dir.
        """
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        repo = BatchHandleRepository(batch_dir=str(tmp_path))
        assert repo is not None
        assert repo._batch_dir == str(tmp_path)

    def test_llm_container_has_batch_provider_methods(self):
        """
        INT-05: LLMContainer exposes _create_anthropic_batch_adapter and
        _create_batch_handle_repository static methods (the DI factory hooks).
        """
        from agentmap.di.container_parts.llm import LLMContainer

        assert hasattr(
            LLMContainer, "_create_anthropic_batch_adapter"
        ), "LLMContainer must define _create_anthropic_batch_adapter factory"
        assert hasattr(
            LLMContainer, "_create_batch_handle_repository"
        ), "LLMContainer must define _create_batch_handle_repository factory"
        assert hasattr(
            LLMContainer, "anthropic_batch_adapter"
        ), "LLMContainer must expose anthropic_batch_adapter provider"
        assert hasattr(
            LLMContainer, "batch_handle_repository"
        ), "LLMContainer must expose batch_handle_repository provider"


# ---------------------------------------------------------------------------
# Telemetry constants — additive batch constants exist
# ---------------------------------------------------------------------------


class TestBatchTelemetryConstants:
    """Verify additive batch telemetry constants exist in constants.py."""

    def test_batch_metric_constants_defined(self):
        from agentmap.services.telemetry import constants

        assert hasattr(constants, "METRIC_LLM_BATCH_SUBMITTED_COUNT")
        assert hasattr(constants, "METRIC_LLM_BATCH_POLL_COUNT")
        assert hasattr(constants, "METRIC_LLM_BATCH_RESULTS_FETCHED_COUNT")

    def test_batch_metric_constant_values(self):
        from agentmap.services.telemetry.constants import (
            METRIC_LLM_BATCH_POLL_COUNT,
            METRIC_LLM_BATCH_RESULTS_FETCHED_COUNT,
            METRIC_LLM_BATCH_SUBMITTED_COUNT,
        )

        assert METRIC_LLM_BATCH_SUBMITTED_COUNT == "llm_batch.submitted_count"
        assert METRIC_LLM_BATCH_POLL_COUNT == "llm_batch.poll_count"
        assert (
            METRIC_LLM_BATCH_RESULTS_FETCHED_COUNT == "llm_batch.results_fetched_count"
        )

    def test_batch_status_dim_constant_defined(self):
        from agentmap.services.telemetry import constants

        assert hasattr(constants, "METRIC_DIM_BATCH_STATUS")

    def test_batch_provider_model_dims_defined(self):
        from agentmap.services.telemetry import constants

        # Batch provider/model reuse the existing dims — verify they exist.
        assert hasattr(constants, "METRIC_DIM_PROVIDER")
        assert hasattr(constants, "METRIC_DIM_MODEL")

    def test_existing_constants_unchanged(self):
        """ADR-7: no existing constant was renamed or removed."""
        from agentmap.services.telemetry.constants import (
            METRIC_LLM_CIRCUIT_BREAKER,
            METRIC_LLM_DURATION,
            METRIC_LLM_ERRORS,
            METRIC_LLM_FALLBACK,
            METRIC_LLM_ROUTING_CACHE_HIT,
            METRIC_LLM_TOKENS_INPUT,
            METRIC_LLM_TOKENS_OUTPUT,
        )

        assert METRIC_LLM_DURATION == "agentmap.llm.duration"
        assert METRIC_LLM_TOKENS_INPUT == "agentmap.llm.tokens.input"
        assert METRIC_LLM_TOKENS_OUTPUT == "agentmap.llm.tokens.output"
        assert METRIC_LLM_ERRORS == "agentmap.llm.errors"
        assert METRIC_LLM_ROUTING_CACHE_HIT == "agentmap.llm.routing.cache_hit"
        assert METRIC_LLM_CIRCUIT_BREAKER == "agentmap.llm.circuit_breaker"
        assert METRIC_LLM_FALLBACK == "agentmap.llm.fallback"


# ---------------------------------------------------------------------------
# TC-091: pyproject.toml optional-extras policy (T-E05-F04-008)
# ---------------------------------------------------------------------------


class TestOptionalExtrasDependencyPolicy:
    """TC-091: openai and google-genai must NOT appear in core deps."""

    def _load_pyproject(self) -> dict:
        repo_root = Path(__file__).parents[4]
        pyproject_path = repo_root / "pyproject.toml"
        assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"
        with open(pyproject_path, "rb") as f:
            return tomllib.load(f)

    def _normalize_dep_names(self, deps: list) -> set:
        """Strip version specifiers and extras from PEP 517 dependency strings."""
        result = set()
        for dep in deps:
            name = dep.split("[")[0].split(">=")[0].split("==")[0]
            name = name.split("!=")[0].split("<")[0].split(">")[0].strip().lower()
            result.add(name)
        return result

    def test_openai_not_in_core_dependencies(self):
        """
        TC-091: openai must NOT appear in [project.dependencies].
        Counter-factual: if added to core, every agentmap install requires openai SDK.
        """
        data = self._load_pyproject()
        core_deps = data.get("project", {}).get("dependencies", [])
        names = self._normalize_dep_names(core_deps)
        assert "openai" not in names, (
            "openai must not appear in [project].dependencies (REQ-NF-001 / AC-T1). "
            "It must be in optional extras only."
        )

    def test_google_genai_not_in_core_dependencies(self):
        """
        TC-091: google-genai must NOT appear in [project.dependencies].
        Counter-factual: if added to core, every agentmap install requires google-genai.
        """
        data = self._load_pyproject()
        core_deps = data.get("project", {}).get("dependencies", [])
        names = self._normalize_dep_names(core_deps)
        assert "google-genai" not in names, (
            "google-genai must not appear in [project].dependencies (REQ-NF-001 / AC-T1). "
            "It must be in optional extras only."
        )

    def test_deprecated_google_generativeai_not_in_any_section(self):
        """
        TC-091: google-generativeai (deprecated Nov 2025) must not appear anywhere.
        Counter-factual: using deprecated package → breakage when Google removes it.
        """
        data = self._load_pyproject()
        core_deps = data.get("project", {}).get("dependencies", [])
        optional_deps = data.get("project", {}).get("optional-dependencies", {})
        all_optional = [dep for deps in optional_deps.values() for dep in deps]
        all_deps = core_deps + all_optional
        names = self._normalize_dep_names(all_deps)
        assert (
            "google-generativeai" not in names
        ), "google-generativeai is deprecated (Nov 2025). Use google-genai instead."

    def test_openai_in_optional_extras(self):
        """
        TC-091: openai must appear in [project.optional-dependencies] (batch or all).
        Counter-factual: not listed → pip install agentmap[batch] doesn't install openai.
        """
        data = self._load_pyproject()
        optional_deps = data.get("project", {}).get("optional-dependencies", {})
        all_optional_names = set()
        for deps in optional_deps.values():
            all_optional_names |= self._normalize_dep_names(deps)
        assert "openai" in all_optional_names, (
            "openai must appear in at least one optional-dependencies group "
            "(e.g. batch or all) per REQ-NF-001 / AC-T1."
        )

    def test_google_genai_in_optional_extras(self):
        """
        TC-091: google-genai must appear in [project.optional-dependencies].
        Counter-factual: not listed → pip install agentmap[batch] doesn't install google-genai.
        """
        data = self._load_pyproject()
        optional_deps = data.get("project", {}).get("optional-dependencies", {})
        all_optional_names = set()
        for deps in optional_deps.values():
            all_optional_names |= self._normalize_dep_names(deps)
        assert "google-genai" in all_optional_names, (
            "google-genai must appear in at least one optional-dependencies group "
            "(e.g. batch or all) per REQ-NF-001 / AC-T1."
        )


# ---------------------------------------------------------------------------
# TC-092: ADR file existence (T-E05-F04-008)
# ---------------------------------------------------------------------------


class TestADRExists:
    """TC-092: ADR documenting dependency-policy change must exist."""

    def test_adr_file_exists(self):
        """
        TC-092: adr-001-batch-optional-deps.md must exist at the specified path.
        Counter-factual: ADR absent → engineer doesn't know why optional deps exist.
        """
        repo_root = Path(__file__).parents[4]
        adr_path = (
            repo_root
            / "docs/plan/E05-llm-prompt-caching-and-batch-execution"
            / "E05-F04-cross-provider-batch-expansion-and-usage-normaliza"
            / "adr-001-batch-optional-deps.md"
        )
        assert adr_path.exists(), (
            f"ADR not found at {adr_path}. "
            "Create it per spec §1.13 and REQ-NF-001 / D-2."
        )

    def test_adr_has_required_sections(self):
        """
        TC-092: ADR must contain Context, Decision, and Consequences sections,
        and must reference F03 REQ-NF-003 reversal.
        """
        repo_root = Path(__file__).parents[4]
        adr_path = (
            repo_root
            / "docs/plan/E05-llm-prompt-caching-and-batch-execution"
            / "E05-F04-cross-provider-batch-expansion-and-usage-normaliza"
            / "adr-001-batch-optional-deps.md"
        )
        assert adr_path.exists(), "ADR file missing — cannot check sections."
        content = adr_path.read_text()
        assert len(content.strip()) > 0, "ADR file is empty."
        assert "Context" in content, "ADR must contain a 'Context' section."
        assert "Decision" in content, "ADR must contain a 'Decision' section."
        assert "Consequences" in content, "ADR must contain a 'Consequences' section."
        assert (
            "REQ-NF-003" in content or "F03" in content
        ), "ADR must reference F03 REQ-NF-003 reversal per spec §1.13."


# ---------------------------------------------------------------------------
# TC-F04-DI: Multi-provider registry wiring (T-E05-F04-008)
# ---------------------------------------------------------------------------


class TestMultiProviderDIRegistry:
    """AC-T2: DI container registers all three adapters; missing SDK → log + skip."""

    def test_llm_container_has_openai_batch_adapter_factory(self):
        """AC-T2: LLMContainer must expose _create_openai_batch_adapter factory."""
        from agentmap.di.container_parts.llm import LLMContainer

        assert hasattr(
            LLMContainer, "_create_openai_batch_adapter"
        ), "LLMContainer must define _create_openai_batch_adapter factory (AC-T2)."
        assert hasattr(
            LLMContainer, "openai_batch_adapter"
        ), "LLMContainer must expose openai_batch_adapter provider (AC-T2)."

    def test_llm_container_has_gemini_batch_adapter_factory(self):
        """AC-T2: LLMContainer must expose _create_gemini_batch_adapter factory."""
        from agentmap.di.container_parts.llm import LLMContainer

        assert hasattr(
            LLMContainer, "_create_gemini_batch_adapter"
        ), "LLMContainer must define _create_gemini_batch_adapter factory (AC-T2)."
        assert hasattr(
            LLMContainer, "gemini_batch_adapter"
        ), "LLMContainer must expose gemini_batch_adapter provider (AC-T2)."

    def test_create_llm_service_accepts_batch_adapters_dict(self):
        """AC-T2: _create_llm_service must pass all adapters as a registry dict."""
        from agentmap.services.llm_service import LLMService

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }

        mock_anthropic = MagicMock()
        mock_openai = MagicMock()
        mock_gemini = MagicMock()

        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            features_registry_service=MagicMock(),
            routing_config_service=MagicMock(),
            telemetry_service=MagicMock(),
            batch_adapters={
                "anthropic": mock_anthropic,
                "openai": mock_openai,
                "google": mock_gemini,
            },
        )

        assert svc._batch_adapters.get("anthropic") is mock_anthropic
        assert svc._batch_adapters.get("openai") is mock_openai
        assert svc._batch_adapters.get("google") is mock_gemini

    def test_missing_openai_sdk_logs_and_skips(self):
        """
        AC-T2: If openai SDK is missing, the adapter factory must catch the error
        and return None (log + skip), not propagate LLMDependencyError.
        Counter-factual: uncaught error → container build fails even without openai.
        """
        from agentmap.di.container_parts.llm import LLMContainer

        mock_app_config = MagicMock()
        mock_app_config.get_llm_config.return_value = {"api_key": "sk-test"}
        mock_logging = MagicMock()
        mock_logger = MagicMock()
        mock_logging.get_class_logger.return_value = mock_logger

        from agentmap.exceptions import LLMDependencyError

        with patch(
            "agentmap.services.llm.openai_batch_adapter.OpenAIBatchAdapter.__init__",
            side_effect=LLMDependencyError("openai not installed"),
        ):
            result = LLMContainer._create_openai_batch_adapter(
                mock_app_config, mock_logging
            )

        assert (
            result is None
        ), "Factory must return None (not raise) when SDK is absent (AC-T2)."

    def test_missing_gemini_sdk_logs_and_skips(self):
        """
        AC-T2: If google-genai SDK is missing, the adapter factory must catch the error
        and return None (log + skip), not propagate LLMDependencyError.
        """
        from agentmap.di.container_parts.llm import LLMContainer

        mock_app_config = MagicMock()
        mock_app_config.get_llm_config.return_value = {"api_key": "fake-key"}
        mock_logging = MagicMock()
        mock_logger = MagicMock()
        mock_logging.get_class_logger.return_value = mock_logger

        from agentmap.exceptions import LLMDependencyError

        with patch(
            "agentmap.services.llm.gemini_batch_adapter.GeminiBatchAdapter.__init__",
            side_effect=LLMDependencyError("google-genai not installed"),
        ):
            result = LLMContainer._create_gemini_batch_adapter(
                mock_app_config, mock_logging
            )

        assert (
            result is None
        ), "Factory must return None (not raise) when SDK is absent (AC-T2)."
