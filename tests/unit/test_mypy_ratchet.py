from collections import Counter

import pytest

import tools.mypy_ratchet as mypy_ratchet
from tools.mypy_ratchet import (
    Diagnostic,
    find_new_diagnostics,
    load_diagnostics,
    parse_baseline,
    parse_diagnostics,
)


def test_parse_diagnostics_records_portable_signature_without_line_numbers():
    output = (
        "src/agentmap/service.py:12:3: error:  Incompatible   return value "
        "[return-value]\n"
    )

    diagnostics = parse_diagnostics(output)

    assert diagnostics == [
        Diagnostic(
            file="src/agentmap/service.py",
            code="return-value",
            message="Incompatible return value",
        )
    ]


def test_parse_diagnostics_accepts_file_level_findings_and_ignores_notes():
    output = (
        "src/agentmap/service.py: error: Cannot find implementation "
        "or library stub [import-not-found]\n"
        "src/agentmap/service.py: note: See https://mypy.readthedocs.io/\n"
    )

    diagnostics = parse_diagnostics(output)

    assert diagnostics == [
        Diagnostic(
            file="src/agentmap/service.py",
            code="import-not-found",
            message="Cannot find implementation or library stub",
        )
    ]


def test_parse_diagnostics_fails_closed_on_unrecognized_output():
    with pytest.raises(ValueError, match="Unrecognized mypy output"):
        parse_diagnostics("mypy.ini: Source contains parsing errors\n")


def test_find_new_diagnostics_compares_signatures_and_multiplicity():
    existing = Diagnostic("src/one.py", "attr-defined", "missing member")
    new = Diagnostic("src/one.py", "name-defined", "missing name")
    baseline = Counter([existing, existing])
    candidate = Counter([existing, new])

    assert find_new_diagnostics(baseline, candidate) == Counter([new])


def test_find_new_diagnostics_allows_reviewed_reductions():
    existing = Diagnostic("src/one.py", "attr-defined", "missing member")

    assert (
        find_new_diagnostics(Counter([existing, existing]), Counter([existing]))
        == Counter()
    )


def test_check_environment_rejects_mypy_command_drift(monkeypatch):
    environment = {
        "python_version": "3.12.0",
        "mypy_version": "1.0",
        "uv_lock_sha256": "lock",
        "dependency_manifest_sha256": "dependencies",
        "mypy_ini_sha256": "config",
        "command": '["<python>","-m","mypy","src"]',
    }
    monkeypatch.setattr(mypy_ratchet, "current_environment", lambda root: environment)
    baseline = {"environment": {**environment, "command": '["mypy","src"]'}}

    with pytest.raises(RuntimeError, match="command"):
        mypy_ratchet.check_environment(baseline)


def test_check_environment_reports_runtime_and_package_drift_without_blocking(
    monkeypatch,
):
    baseline_environment = {
        "python_version": "3.11.14",
        "mypy_version": "mypy 1.19.1",
        "uv_lock_sha256": "lock",
        "dependency_manifest_sha256": "linux-packages",
        "mypy_ini_sha256": "config",
        "command": '["<python>","-m","mypy","src"]',
    }
    current_environment = {
        **baseline_environment,
        "python_version": "3.12.0",
        "dependency_manifest_sha256": "platform-packages",
    }
    monkeypatch.setattr(
        mypy_ratchet, "current_environment", lambda root: current_environment
    )

    notes = mypy_ratchet.check_environment({"environment": baseline_environment})

    assert notes == [
        "python_version: baseline='3.11.14', current='3.12.0'",
        "dependency_manifest_sha256: baseline='linux-packages', "
        "current='platform-packages'",
    ]


def test_write_baseline_uses_supplied_root(tmp_path, monkeypatch):
    repository_baseline = mypy_ratchet.BASELINE_PATH.read_bytes()
    monkeypatch.setattr(mypy_ratchet, "current_environment", lambda root: {})

    mypy_ratchet.write_baseline([], tmp_path)

    alternate_baseline = tmp_path / "tools" / "mypy-baseline.json"
    assert alternate_baseline.is_file()
    assert mypy_ratchet.BASELINE_PATH.read_bytes() == repository_baseline


@pytest.mark.parametrize("payload", ["[]", "null", '"baseline"', "1"])
def test_parse_baseline_rejects_non_object_json_roots(payload):
    with pytest.raises(ValueError, match="JSON object"):
        parse_baseline(payload)


def test_parse_baseline_rejects_invalid_json():
    with pytest.raises(ValueError, match="Invalid baseline JSON"):
        parse_baseline("{")


@pytest.mark.parametrize(
    "item",
    [
        {"file": 7, "code": "attr-defined", "message": "bad", "count": 1},
        {"file": "src/a.py", "code": [], "message": "bad", "count": 1},
        {"file": "src/a.py", "code": "attr-defined", "message": 3, "count": 1},
        {"file": "src/a.py", "code": "attr-defined", "message": "bad", "count": True},
    ],
)
def test_load_diagnostics_rejects_invalid_signature_field_types(item):
    with pytest.raises(ValueError, match="Invalid baseline diagnostic"):
        load_diagnostics({"diagnostics": [item]})
