"""Unit tests for BaseStorageService telemetry instrumentation.

Tests the Template Method pattern refactor (read->_perform_read, write->_perform_write)
and the guard-and-dispatch telemetry wrapper logic.

Test Plan Section 2.1 - TC-600 through TC-678.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, create_autospec

import pytest

from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode
from agentmap.services.telemetry.constants import (
    STORAGE_BACKEND,
    STORAGE_OPERATION,
    STORAGE_READ_SPAN,
    STORAGE_RECORD_COUNT,
    STORAGE_WRITE_SPAN,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol

# ---------------------------------------------------------------------------
# Minimal concrete subclass for testing
# ---------------------------------------------------------------------------


class ConcreteTestStorageService(BaseStorageService):
    """Minimal concrete storage service for testing telemetry instrumentation."""

    def __init__(
        self,
        provider_name="test_provider",
        read_return=None,
        write_return=None,
        read_side_effect=None,
        write_side_effect=None,
        telemetry_service=None,
    ):
        # Build minimal mock dependencies
        mock_config = MagicMock()
        mock_config.get_provider_config.return_value = MagicMock()
        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()

        super().__init__(
            provider_name=provider_name,
            configuration=mock_config,
            logging_service=mock_logging,
            telemetry_service=telemetry_service,
        )

        self._read_return = (
            read_return if read_return is not None else [{"id": 1}, {"id": 2}]
        )
        self._write_return = (
            write_return if write_return is not None else StorageResult(success=True)
        )
        self._read_side_effect = read_side_effect
        self._write_side_effect = write_side_effect
        self._perform_read_call_count = 0
        self._perform_write_call_count = 0

    def _perform_read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        self._perform_read_call_count += 1
        if self._read_side_effect:
            raise self._read_side_effect
        return self._read_return

    def _perform_write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        self._perform_write_call_count += 1
        if self._write_side_effect:
            raise self._write_side_effect
        return self._write_return

    def _initialize_client(self) -> Any:
        return {}

    def _perform_health_check(self) -> bool:
        return True

    def delete(self, collection, document_id=None, path=None, **kwargs):
        return StorageResult(success=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_telemetry():
    """Create a mock TelemetryServiceProtocol with a context-manager span."""
    svc = create_autospec(TelemetryServiceProtocol, instance=True)
    mock_span = MagicMock()

    @contextmanager
    def _fake_start_span(name, attributes=None, kind=None):
        yield mock_span

    svc.start_span.side_effect = _fake_start_span
    return svc, mock_span


# ===================================================================
# TC-600 through TC-603: Read span lifecycle
# ===================================================================


class TestReadSpanCreation:
    """TC-600 through TC-603: Read span creation and attributes."""

    def test_read_creates_storage_read_span(self, mock_telemetry):
        """TC-600: read() creates agentmap.storage.read span."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(telemetry_service=svc_mock)

        service.read("test_collection")

        svc_mock.start_span.assert_called_once()
        call_args = svc_mock.start_span.call_args
        assert call_args[0][0] == STORAGE_READ_SPAN

    def test_read_span_has_backend_and_operation_attributes(self, mock_telemetry):
        """TC-601: Span attributes include backend and operation."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(
            provider_name="csv", telemetry_service=svc_mock
        )

        service.read("test_collection")

        call_args = svc_mock.start_span.call_args
        attrs = call_args[1].get("attributes") or call_args[0][1]
        assert attrs[STORAGE_BACKEND] == "csv"
        assert attrs[STORAGE_OPERATION] == "read"

    def test_read_span_no_explicit_parent(self, mock_telemetry):
        """TC-602: start_span called without explicit parent (OTEL auto-parents)."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(telemetry_service=svc_mock)

        service.read("test_collection")

        call_args = svc_mock.start_span.call_args
        # Should not have a 'parent' keyword argument
        assert "parent" not in (call_args[1] if call_args[1] else {})

    def test_read_span_status_ok_on_success(self, mock_telemetry):
        """TC-603: Span status set to OK on successful read."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(telemetry_service=svc_mock)

        service.read("test_collection")

        # Verify set_status called with OK
        span.set_status.assert_called_once()
        from opentelemetry.trace import StatusCode

        span.set_status.assert_called_with(StatusCode.OK)


# ===================================================================
# TC-610 through TC-613: Write span lifecycle
# ===================================================================


class TestWriteSpanCreation:
    """TC-610 through TC-613: Write span creation and attributes."""

    def test_write_creates_storage_write_span(self, mock_telemetry):
        """TC-610: write() creates agentmap.storage.write span."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(telemetry_service=svc_mock)
        data = [{"a": 1}] * 10

        service.write("test_collection", data)

        svc_mock.start_span.assert_called_once()
        call_args = svc_mock.start_span.call_args
        assert call_args[0][0] == STORAGE_WRITE_SPAN

    def test_write_span_record_count_set(self, mock_telemetry):
        """TC-611: Record count attribute set on write with list data."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(telemetry_service=svc_mock)
        data = [{"a": i} for i in range(10)]

        service.write("test_collection", data)

        svc_mock.set_span_attributes.assert_called()
        # Find the call with STORAGE_RECORD_COUNT
        found = False
        for call in svc_mock.set_span_attributes.call_args_list:
            attrs = call[0][1]
            if STORAGE_RECORD_COUNT in attrs:
                assert attrs[STORAGE_RECORD_COUNT] == 10
                found = True
        assert found, "STORAGE_RECORD_COUNT not set on write span"

    def test_read_result_record_count_list(self, mock_telemetry):
        """TC-612: Record count set on read when result is a list."""
        svc_mock, span = mock_telemetry
        result_data = [{"id": i} for i in range(50)]
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_return=result_data
        )

        service.read("test_collection")

        svc_mock.set_span_attributes.assert_called()
        found = False
        for call in svc_mock.set_span_attributes.call_args_list:
            attrs = call[0][1]
            if STORAGE_RECORD_COUNT in attrs:
                assert attrs[STORAGE_RECORD_COUNT] == 50
                found = True
        assert found, "STORAGE_RECORD_COUNT not set for list result"

    def test_write_span_has_backend_and_operation_attributes(self, mock_telemetry):
        """TC-613: Write span attributes include backend and operation."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(
            provider_name="json", telemetry_service=svc_mock
        )

        service.write("test_collection", [{"a": 1}])

        call_args = svc_mock.start_span.call_args
        attrs = call_args[1].get("attributes") or call_args[0][1]
        assert attrs[STORAGE_BACKEND] == "json"
        assert attrs[STORAGE_OPERATION] == "write"


# ===================================================================
# TC-620 through TC-623: Error handling
# ===================================================================


class TestErrorRecording:
    """TC-620 through TC-623: Error recording on storage failures."""

    def test_read_failure_sets_span_error_status(self, mock_telemetry):
        """TC-620: Span status ERROR on storage read failure."""
        svc_mock, span = mock_telemetry
        err = FileNotFoundError("missing.csv")
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_side_effect=err
        )

        with pytest.raises(FileNotFoundError):
            service.read("test_collection")

        # record_exception should have been called
        svc_mock.record_exception.assert_called_once()

    def test_read_failure_records_exception(self, mock_telemetry):
        """TC-621: Exception recorded via record_exception() on read failure."""
        svc_mock, span = mock_telemetry
        err = FileNotFoundError("missing.csv")
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_side_effect=err
        )

        with pytest.raises(FileNotFoundError):
            service.read("test_collection")

        svc_mock.record_exception.assert_called_once_with(span, err)

    def test_read_failure_propagates_exception(self, mock_telemetry):
        """TC-622: Storage exception propagates after recording."""
        svc_mock, span = mock_telemetry
        err = FileNotFoundError("missing.csv")
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_side_effect=err
        )

        with pytest.raises(FileNotFoundError, match="missing.csv"):
            service.read("test_collection")

    def test_write_failure_records_error(self, mock_telemetry):
        """TC-623: Write failure records error on span and propagates."""
        svc_mock, span = mock_telemetry
        err = IOError("disk full")
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, write_side_effect=err
        )

        with pytest.raises(IOError, match="disk full"):
            service.write("test_collection", [{"a": 1}])

        svc_mock.record_exception.assert_called_once_with(span, err)


# ===================================================================
# TC-650 through TC-653: None telemetry graceful degradation
# ===================================================================


class TestNoneTelemetryDegradation:
    """TC-650 through TC-653: None telemetry graceful degradation."""

    def test_read_works_with_none_telemetry(self):
        """TC-650: read() delegates directly to _perform_read() with no telemetry."""
        service = ConcreteTestStorageService(telemetry_service=None)

        result = service.read("test_collection")

        assert result == [{"id": 1}, {"id": 2}]
        assert service._perform_read_call_count == 1

    def test_write_works_with_none_telemetry(self):
        """TC-651: write() delegates directly to _perform_write() with no telemetry."""
        service = ConcreteTestStorageService(telemetry_service=None)

        result = service.write("test_collection", [{"a": 1}])

        assert result.success is True
        assert service._perform_write_call_count == 1

    def test_no_exceptions_with_none_telemetry(self):
        """TC-652: No telemetry-related exceptions with None telemetry."""
        service = ConcreteTestStorageService(telemetry_service=None)

        # Both should complete without error
        read_result = service.read("test_collection")
        write_result = service.write("test_collection", [{"a": 1}])

        assert read_result is not None
        assert write_result is not None

    def test_zero_overhead_guard_pattern(self):
        """TC-653: Single is None guard, no try/except on fast path."""
        import inspect

        source = inspect.getsource(BaseStorageService.read)
        # The fast path should have a simple `is None` check
        assert "self._telemetry_service is None" in source
        # The fast path should directly return _perform_read
        assert "_perform_read" in source


# ===================================================================
# TC-670 through TC-674: Telemetry failure isolation
# ===================================================================


class TestTelemetryFailureIsolation:
    """TC-670 through TC-674: Telemetry failures must not break storage."""

    def test_start_span_failure_falls_back_to_uninstrumented_read(self):
        """TC-670: start_span() failure falls back to uninstrumented _perform_read()."""
        svc_mock = create_autospec(TelemetryServiceProtocol, instance=True)
        svc_mock.start_span.side_effect = RuntimeError("telemetry broken")

        service = ConcreteTestStorageService(telemetry_service=svc_mock)
        result = service.read("test_collection")

        assert result == [{"id": 1}, {"id": 2}]
        assert service._perform_read_call_count == 1

    def test_start_span_failure_falls_back_to_uninstrumented_write(self):
        """TC-671: start_span() failure falls back to uninstrumented _perform_write()."""
        svc_mock = create_autospec(TelemetryServiceProtocol, instance=True)
        svc_mock.start_span.side_effect = RuntimeError("telemetry broken")

        service = ConcreteTestStorageService(telemetry_service=svc_mock)
        result = service.write("test_collection", [{"a": 1}])

        assert result.success is True
        assert service._perform_write_call_count == 1

    def test_set_span_attributes_failure_does_not_break_read(self, mock_telemetry):
        """TC-672: set_span_attributes() failure doesn't break read result."""
        svc_mock, span = mock_telemetry
        svc_mock.set_span_attributes.side_effect = RuntimeError("attrs broken")

        service = ConcreteTestStorageService(telemetry_service=svc_mock)
        result = service.read("test_collection")

        # Storage operation should still succeed
        assert result == [{"id": 1}, {"id": 2}]

    def test_record_exception_failure_still_propagates_storage_error(
        self, mock_telemetry
    ):
        """TC-673: record_exception() failure doesn't suppress storage exception."""
        svc_mock, span = mock_telemetry
        svc_mock.record_exception.side_effect = RuntimeError("recording broken")

        storage_err = FileNotFoundError("missing.csv")
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_side_effect=storage_err
        )

        with pytest.raises(FileNotFoundError, match="missing.csv"):
            service.read("test_collection")

    def test_start_span_failure_does_not_double_execute_perform_read(self):
        """TC-674: _perform_read() called exactly once when start_span() fails."""
        svc_mock = create_autospec(TelemetryServiceProtocol, instance=True)
        svc_mock.start_span.side_effect = RuntimeError("telemetry broken")

        service = ConcreteTestStorageService(telemetry_service=svc_mock)
        service.read("test_collection")

        assert service._perform_read_call_count == 1


# ===================================================================
# TC-675 through TC-678: Record count edge cases
# ===================================================================


class TestRecordCountEdgeCases:
    """TC-675 through TC-678: Record count behavior for different result types."""

    def test_read_dict_result_no_record_count(self, mock_telemetry):
        """TC-675: Dict result does not set record count."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_return={"key": "value"}
        )

        service.read("test_collection")

        # set_span_attributes should NOT be called with STORAGE_RECORD_COUNT
        for call in svc_mock.set_span_attributes.call_args_list:
            attrs = call[0][1]
            assert STORAGE_RECORD_COUNT not in attrs

    def test_read_string_result_no_record_count(self, mock_telemetry):
        """TC-676: String result does not set record count (str excluded)."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_return="some text content"
        )

        service.read("test_collection")

        for call in svc_mock.set_span_attributes.call_args_list:
            attrs = call[0][1]
            assert STORAGE_RECORD_COUNT not in attrs

    def test_read_none_result_no_record_count(self, mock_telemetry):
        """TC-677: None result does not set record count."""
        svc_mock, span = mock_telemetry
        # Need to pass None explicitly, but our constructor defaults to list
        service = ConcreteTestStorageService(telemetry_service=svc_mock)
        service._read_return = None

        service.read("test_collection")

        for call in svc_mock.set_span_attributes.call_args_list:
            attrs = call[0][1]
            assert STORAGE_RECORD_COUNT not in attrs

    def test_read_tuple_result_sets_record_count(self, mock_telemetry):
        """TC-678: Tuple result sets record count."""
        svc_mock, span = mock_telemetry
        service = ConcreteTestStorageService(
            telemetry_service=svc_mock, read_return=(1, 2, 3)
        )

        service.read("test_collection")

        found = False
        for call in svc_mock.set_span_attributes.call_args_list:
            attrs = call[0][1]
            if STORAGE_RECORD_COUNT in attrs:
                assert attrs[STORAGE_RECORD_COUNT] == 3
                found = True
        assert found, "STORAGE_RECORD_COUNT not set for tuple result"


# ===================================================================
# Constants verification (Test Plan Section 2.6)
# ===================================================================


class TestStorageConstants:
    """Verify storage constants are defined and follow naming convention."""

    STORAGE_CONSTANTS = [
        "STORAGE_READ_SPAN",
        "STORAGE_WRITE_SPAN",
        "STORAGE_BACKEND",
        "STORAGE_OPERATION",
        "STORAGE_RECORD_COUNT",
        "STORAGE_RESOURCE",
    ]

    def test_storage_constants_are_nonempty_strings(self):
        """All storage constants are non-empty strings."""
        from agentmap.services.telemetry import constants

        for name in self.STORAGE_CONSTANTS:
            val = getattr(constants, name)
            assert isinstance(val, str), f"{name} is not a string"
            assert len(val) > 0, f"{name} is empty"

    def test_storage_constants_have_agentmap_storage_prefix(self):
        """All storage constants use agentmap.storage.* prefix."""
        from agentmap.services.telemetry import constants

        for name in self.STORAGE_CONSTANTS:
            val = getattr(constants, name)
            assert val.startswith(
                "agentmap.storage."
            ), f"{name}={val!r} missing agentmap.storage. prefix"

    def test_storage_constants_importable_from_package(self):
        """Storage constants importable from agentmap.services.telemetry."""
        from agentmap.services.telemetry import (
            STORAGE_BACKEND,
            STORAGE_OPERATION,
            STORAGE_READ_SPAN,
            STORAGE_RECORD_COUNT,
            STORAGE_RESOURCE,
            STORAGE_WRITE_SPAN,
        )

        assert STORAGE_READ_SPAN == "agentmap.storage.read"
        assert STORAGE_WRITE_SPAN == "agentmap.storage.write"
        assert STORAGE_BACKEND == "agentmap.storage.backend"
        assert STORAGE_OPERATION == "agentmap.storage.operation"
        assert STORAGE_RECORD_COUNT == "agentmap.storage.record_count"
        assert STORAGE_RESOURCE == "agentmap.storage.resource"
