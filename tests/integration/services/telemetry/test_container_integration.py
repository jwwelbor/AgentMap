"""Integration tests for TelemetryContainer within ApplicationContainer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class TestContainerIntegration:
    """INT-001 through INT-003, INT-011, INT-020."""

    def test_telemetry_service_satisfies_protocol(self) -> None:
        """INT-001 (partial): telemetry_service from container satisfies protocol."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        container = TelemetryContainer(logging_service=mock_ls)
        svc = container.telemetry_service()
        assert isinstance(svc, TelemetryServiceProtocol)
        # All protocol methods should be callable
        with svc.start_span("integration.test"):
            pass

    def test_noop_fallback_with_patched_import(self) -> None:
        """INT-011: NoOp fallback when OTEL is not importable."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer
        from agentmap.services.telemetry.noop_telemetry_service import (
            NoOpTelemetryService,
        )

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()

        with patch.dict(
            "sys.modules",
            {"opentelemetry": None, "opentelemetry.trace": None},
        ):
            container = TelemetryContainer(logging_service=mock_ls)
            container.telemetry_service.reset()
            svc = container.telemetry_service()
            assert isinstance(svc, NoOpTelemetryService)
            # Warning should be logged
            mock_ls.get_logger.return_value.warning.assert_called()

    def test_import_isolation(self) -> None:
        """INT-020: opentelemetry imports exist only in designated files."""
        src_dir = Path(__file__).resolve().parents[4] / "src" / "agentmap"

        allowed_files = {
            "services/telemetry/otel_telemetry_service.py",
            "di/container_parts/telemetry.py",
            # base_agent.py uses a function-level import of StatusCode
            # inside _set_span_status_ok (ADR-E02F02-005: no module-level
            # OTEL dependency, but function-level is permitted).
            "agents/base_agent.py",
        }

        violations = []
        for py_file in src_dir.rglob("*.py"):
            rel = str(py_file.relative_to(src_dir))
            if rel in allowed_files:
                continue
            content = py_file.read_text()
            for line in content.split("\n"):
                stripped = line.strip()
                # Skip comments and docstrings
                if stripped.startswith("#"):
                    continue
                if "opentelemetry" in stripped and (
                    stripped.startswith("import ") or stripped.startswith("from ")
                ):
                    violations.append(f"{rel}: {stripped}")

        assert (
            violations == []
        ), "opentelemetry imports found outside designated files:\n" + "\n".join(
            violations
        )

    def test_singleton_across_resolutions(self) -> None:
        """INT-002 (partial): telemetry_service is a singleton."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        container = TelemetryContainer(logging_service=mock_ls)
        svc1 = container.telemetry_service()
        svc2 = container.telemetry_service()
        assert svc1 is svc2
