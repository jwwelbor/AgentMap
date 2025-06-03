# tests/services/validation/test_validation_service.py
import pytest
from unittest.mock import Mock
from pathlib import Path
from agentmap.services.validation.validation_service import ValidationService
from agentmap.models.validation.validation_models import ValidationResult


@pytest.fixture
def dummy_result():
    return ValidationResult(
        file_path="dummy.csv",
        file_type="csv",
        is_valid=True,
        file_hash="abc123"
    )


@pytest.fixture
def service_with_mocks(dummy_result):
    config_service = Mock()
    logging_service = Mock()
    csv_validator = Mock()
    config_validator = Mock()
    cache_service = Mock()

    csv_validator.validate_file.return_value = dummy_result
    config_validator.validate_file.return_value = dummy_result
    cache_service.calculate_file_hash.return_value = "abc123"
    cache_service.get_cached_result.return_value = None

    svc = ValidationService(
        config_service,
        logging_service,
        csv_validator,
        config_validator,
        cache_service
    )
    return svc, csv_validator, config_validator, cache_service


def test_validate_csv_calls_validator(service_with_mocks):
    svc, csv_validator, _, _ = service_with_mocks
    result = svc.validate_csv_file(Path("test.csv"))
    csv_validator.validate_file.assert_called_once()
    assert result.file_type == "csv"


def test_validate_config_calls_validator(service_with_mocks):
    svc, _, config_validator, _ = service_with_mocks
    result = svc.validate_config_file(Path("test.yaml"))
    config_validator.validate_file.assert_called_once()
    assert result.file_type == "csv"  # reused dummy_result


def test_validate_and_raise_raises_on_errors():
    bad_result = ValidationResult(
        file_path="bad.csv",
        file_type="csv",
        is_valid=False,
        file_hash="bad123"
    )
    bad_result.add_error("Test error")

    svc = ValidationService(Mock(), Mock(), Mock(), Mock(), Mock())
    svc.validate_csv_file = Mock(return_value=bad_result)

    with pytest.raises(Exception) as e:
        svc.validate_and_raise(Path("bad.csv"))
    assert "Validation failed" in str(e.value)