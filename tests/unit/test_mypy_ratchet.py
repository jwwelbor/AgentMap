from collections import Counter

import pytest

from tools.mypy_ratchet import Diagnostic, find_new_diagnostics, parse_diagnostics


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
