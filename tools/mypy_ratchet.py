"""Compare repository mypy diagnostics with the reviewed baseline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "tools" / "mypy-baseline.json"
MYPY_COMMAND = (
    sys.executable,
    "-m",
    "mypy",
    "--no-incremental",
    "--no-pretty",
    "--show-column-numbers",
    "--show-error-codes",
    "--no-error-summary",
    "src",
)
DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?\.py)(?::\d+(?::\d+)?)?: error: "
    r"(?P<message>.*?) \[(?P<code>[a-z0-9-]+)\]$"
)


@dataclass(frozen=True, order=True)
class Diagnostic:
    """A location-independent finding signature."""

    file: str
    code: str
    message: str


def normalize_file(value: str, root: Path = ROOT) -> str:
    """Return a repository-relative POSIX path for a mypy diagnostic."""
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute():
        try:
            normalized = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError as error:
            raise ValueError(f"Diagnostic path is outside repository: {value}") from error
    else:
        normalized = path.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def parse_diagnostics(output: str, root: Path = ROOT) -> list[Diagnostic]:
    """Parse mypy's non-pretty output, rejecting lines that could hide errors."""
    diagnostics = []
    for line in output.splitlines():
        if not line.strip() or re.search(r": note:", line):
            continue
        match = DIAGNOSTIC_PATTERN.match(line)
        if match is None:
            raise ValueError(f"Unrecognized mypy output: {line}")
        message = " ".join(match.group("message").split())
        diagnostics.append(
            Diagnostic(
                file=normalize_file(match.group("file"), root),
                code=match.group("code"),
                message=message,
            )
        )
    return diagnostics


def find_new_diagnostics(
    baseline: Counter[Diagnostic], candidate: Counter[Diagnostic]
) -> Counter[Diagnostic]:
    """Return diagnostic signatures whose multiplicity grew from the baseline."""
    return candidate - baseline


def diagnostic_counts(diagnostics: Iterable[Diagnostic]) -> dict[str, object]:
    """Summarize the diagnostic multiset for a reviewable baseline."""
    items = Counter(diagnostics)
    by_code: Counter[str] = Counter()
    by_file: Counter[str] = Counter()
    for diagnostic, count in items.items():
        by_code[diagnostic.code] += count
        by_file[diagnostic.file] += count
    return {
        "total": sum(items.values()),
        "by_code": dict(sorted(by_code.items())),
        "by_file": dict(sorted(by_file.items())),
        "signatures": [
            {**asdict(diagnostic), "count": count}
            for diagnostic, count in sorted(items.items())
        ],
    }


def load_diagnostics(baseline: dict[str, object]) -> Counter[Diagnostic]:
    """Load the baseline multiset, retaining repeated findings."""
    counts = baseline.get("diagnostics")
    if not isinstance(counts, list):
        raise ValueError("Baseline must contain a diagnostics list")
    result: Counter[Diagnostic] = Counter()
    for item in counts:
        if not isinstance(item, dict):
            raise ValueError("Each baseline diagnostic must be an object")
        try:
            diagnostic = Diagnostic(
                file=str(item["file"]),
                code=str(item["code"]),
                message=str(item["message"]),
            )
            count = int(item["count"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid baseline diagnostic: {item}") from error
        if count < 1:
            raise ValueError("Baseline diagnostic counts must be positive")
        result[diagnostic] = count
    return result


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(root: Path = ROOT) -> str:
    """Hash source paths and contents in a deterministic order."""
    digest = hashlib.sha256()
    for path in sorted((root / "src").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def dependency_manifest_digest(root: Path = ROOT) -> str:
    """Hash installed versions of packages selected from the project lock."""
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    locked_names = {
        re.sub(r"[-_.]+", "-", package["name"]).lower()
        for package in lock["package"]
    }
    installed = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            normalized_name = re.sub(r"[-_.]+", "-", name).lower()
            if normalized_name in locked_names:
                installed[normalized_name] = distribution.version
    manifest = sorted(installed.items())
    encoded = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def mypy_version(root: Path = ROOT) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to determine mypy version")
    return result.stdout.strip()


def current_environment(root: Path = ROOT) -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "mypy_version": mypy_version(root),
        "uv_lock_sha256": sha256_file(root / "uv.lock"),
        "dependency_manifest_sha256": dependency_manifest_digest(root),
        "mypy_ini_sha256": sha256_file(root / "mypy.ini"),
        "source_sha256": source_digest(root),
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "command": "uv run mypy src (non-incremental, machine-readable output)",
    }


def run_mypy(root: Path = ROOT) -> list[Diagnostic]:
    result = subprocess.run(
        MYPY_COMMAND,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    diagnostics = parse_diagnostics(output, root)
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"mypy exited with unexpected status {result.returncode}: {output.strip()}"
        )
    if result.returncode == 0 and diagnostics:
        raise RuntimeError("mypy reported diagnostics with a successful exit status")
    if result.returncode == 1 and not diagnostics:
        raise RuntimeError("mypy failed without any parsed diagnostics")
    return diagnostics


def write_baseline(diagnostics: list[Diagnostic], root: Path = ROOT) -> None:
    payload = {
        "schema_version": 1,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": current_environment(root),
        "counts": {
            key: value
            for key, value in diagnostic_counts(diagnostics).items()
            if key != "signatures"
        },
        "diagnostics": diagnostic_counts(diagnostics)["signatures"],
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {BASELINE_PATH.relative_to(root)} with {len(diagnostics)} findings")


def check_environment(baseline: dict[str, object], root: Path = ROOT) -> None:
    expected = baseline.get("environment")
    if not isinstance(expected, dict):
        raise ValueError("Baseline must contain environment metadata")
    actual = current_environment(root)
    keys = (
        "python_version",
        "mypy_version",
        "uv_lock_sha256",
        "dependency_manifest_sha256",
        "mypy_ini_sha256",
    )
    differences = [
        f"{key}: baseline={expected.get(key)!r}, current={actual[key]!r}"
        for key in keys
        if expected.get(key) != actual[key]
    ]
    if differences:
        raise RuntimeError(
            "Mypy baseline environment mismatch; review and update the baseline:\n"
            + "\n".join(differences)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="replace the reviewed diagnostic baseline with the current result",
    )
    arguments = parser.parse_args()

    diagnostics = run_mypy()
    if arguments.update:
        write_baseline(diagnostics)
        return 0

    if not BASELINE_PATH.exists():
        print(f"Missing baseline: {BASELINE_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 2
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    check_environment(baseline)
    existing = load_diagnostics(baseline)
    current = Counter(diagnostics)
    added = find_new_diagnostics(existing, current)
    if added:
        print("New mypy diagnostic signatures detected:", file=sys.stderr)
        for diagnostic, count in sorted(added.items()):
            print(
                f"  {diagnostic.file}: [{diagnostic.code}] {diagnostic.message} "
                f"(new occurrences: {count})",
                file=sys.stderr,
            )
        print("Review the findings, then use --update for an approved baseline change.", file=sys.stderr)
        return 1

    removed = sum(existing.values()) - sum(current.values())
    print(
        f"Mypy ratchet passed: {sum(current.values())} findings, "
        f"{removed} fewer than baseline."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
