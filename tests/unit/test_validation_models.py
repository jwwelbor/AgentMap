
# tests/models/validation/test_models.py
from agentmap.models.validation.errors import ValidationResult, ValidationError, ValidationLevel

def test_validation_result_basic():
    result = ValidationResult(file_path="file.csv", file_type="csv", is_valid=True)
    assert result.total_issues == 0

    result.add_info("Info")
    result.add_warning("Warning")
    result.add_error("Error")

    assert result.has_errors
    assert result.has_warnings
    assert result.total_issues == 3


def test_validation_error_str():
    err = ValidationError(
        level=ValidationLevel.ERROR,
        message="Test error",
        line_number=2,
        field_name="Node",
        value="bad",
        suggestion="Fix it"
    )
    out = str(err)
    assert "ERROR" in out
    assert "Line 2" in out
    assert "Field: Node" in out
    assert "Value: 'bad'" in out
    assert "Suggestion: Fix it" in out
