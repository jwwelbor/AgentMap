"""
Colon collision scan for CSV fixture files.

Validates that no existing CSV files use ':' in Input_Fields column values,
confirming that deferring REQ-F-010 (colon escape syntax) introduces no
regression risk.

AC Coverage: AC-04 (No existing field names conflict with colon syntax)
"""

import csv
import unittest
from pathlib import Path


class TestColonCollisionScan(unittest.TestCase):
    """Scan all CSV fixtures and examples for colon characters in field names."""

    # Column name variants that the parser might recognize
    INPUT_FIELD_COLUMN_VARIANTS = {"Input_Fields", "input_fields", "InputFields"}

    def _get_repo_root(self) -> Path:
        """Walk up from this test file to find the repository root."""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return parent
        raise RuntimeError("Could not find repository root (no pyproject.toml found)")

    def _scan_csv_for_colon_fields(self, csv_path: Path) -> list:
        """Scan a single CSV file for Input_Fields values containing ':'."""
        violations = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    return violations

                # Find the actual column name used in this CSV
                input_col = None
                for variant in self.INPUT_FIELD_COLUMN_VARIANTS:
                    if variant in reader.fieldnames:
                        input_col = variant
                        break

                if input_col is None:
                    return violations

                for row_idx, row in enumerate(reader, start=2):
                    raw_value = row.get(input_col, "")
                    if not raw_value or not raw_value.strip():
                        continue

                    # Split on pipe delimiter to get individual field names
                    field_names = [f.strip() for f in raw_value.split("|")]
                    for field_name in field_names:
                        if ":" in field_name:
                            violations.append(
                                {
                                    "file": str(csv_path),
                                    "row": row_idx,
                                    "field": field_name,
                                }
                            )
        except (UnicodeDecodeError, csv.Error):
            # Skip files that cannot be parsed as CSV
            pass

        return violations

    def test_no_existing_csv_fields_contain_colon(self) -> None:
        """No CSV file in examples/ or tests/ should have ':' in Input_Fields values."""
        repo_root = self._get_repo_root()

        search_dirs = [repo_root / "examples", repo_root / "tests"]
        all_violations = []

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for csv_path in search_dir.rglob("*.csv"):
                violations = self._scan_csv_for_colon_fields(csv_path)
                all_violations.extend(violations)

        if all_violations:
            msg_lines = [f"Found {len(all_violations)} CSV field(s) containing ':':"]
            for v in all_violations[:20]:  # Show first 20
                msg_lines.append(f"  {v['file']}:row {v['row']} field='{v['field']}'")
            if len(all_violations) > 20:
                msg_lines.append(f"  ... and {len(all_violations) - 20} more")
            self.fail("\n".join(msg_lines))

    def test_csv_files_exist_for_scanning(self) -> None:
        """Sanity check: at least some CSV files exist to scan."""
        repo_root = self._get_repo_root()
        csv_count = 0
        for search_dir in [repo_root / "examples", repo_root / "tests"]:
            if search_dir.exists():
                csv_count += len(list(search_dir.rglob("*.csv")))

        self.assertGreater(
            csv_count,
            0,
            "Expected at least one CSV file in examples/ or tests/ for scanning",
        )


if __name__ == "__main__":
    unittest.main()
