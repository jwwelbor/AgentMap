import shutil
import tempfile
from pathlib import Path

import pytest

from agentmap.di import create_container
from agentmap.exceptions.runtime_exceptions import GraphNotFound
from agentmap.runtime.workflow_ops import _resolve_csv_path


@pytest.fixture()
def temp_dir():
    """Create temporary directory for test config and CSV repo."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture()
def repo(temp_dir):
    """Create a dedicated repo dir for CSV files."""
    repo_dir = temp_dir / "csv_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    return repo_dir


@pytest.fixture()
def test_config_path(temp_dir, repo):
    """Create a test configuration file with the CSV repository path."""
    config_path = temp_dir / "test_config.yaml"
    storage_config_path = temp_dir / "storage_config.yaml"

    # Use forward slashes for YAML to avoid Windows backslash escaping issues
    storage_config_path_str = str(storage_config_path).replace("\\", "/")
    repo_path_str = str(repo).replace("\\", "/")

    config_content = f"""logging:
  version: 1
  level: DEBUG
  format: "[%(levelname)s] %(name)s: %(message)s"

llm:
  anthropic:
    api_key: "test_key"
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.7

paths:
  csv_repository: "{repo_path_str}"

storage_config_path: "{storage_config_path_str}"
"""

    storage_config_content = f"""csv:
  default_directory: "{repo_path_str}"
  collections: {{}}

vector:
  default_provider: "chroma"
  collections: {{}}

kv:
  default_provider: "local"
  collections: {{}}
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    with open(storage_config_path, "w") as f:
        f.write(storage_config_content)

    return config_path


@pytest.fixture()
def container(test_config_path):
    """Create real DI container for testing (following established patterns)."""
    return create_container(str(test_config_path))


def _touch_csv(repo: Path, name: str) -> Path:
    """Create an empty CSV in the repo with 'name.csv'."""
    path = repo / f"{name}.csv"
    path.write_text("")  # empty file is fine
    return path


# ---------- Simple identifier ----------


def test_simple_identifier_prefers_repo_csv(container, repo):
    _touch_csv(repo, "orders")
    csv_path, graph = _resolve_csv_path("orders", container)
    assert csv_path == repo / "orders.csv"
    assert graph == "orders"


def test_simple_identifier_falls_back_when_repo_missing(container, repo):
    # No repo CSV for "missing"
    csv_path, graph = _resolve_csv_path("missing", container)
    # Fallback is a relative path equal to the identifier
    assert csv_path == Path("missing")
    assert graph == "missing"


# ---------- Double colon syntax: workflow::graph ----------


def test_doublecolon_prefers_repo_csv(container, repo):
    _touch_csv(repo, "workflow")
    csv_path, graph = _resolve_csv_path("workflow::GraphA", container)
    assert csv_path == repo / "workflow.csv"
    assert graph == "GraphA"


def test_doublecolon_fallback_when_repo_missing(container, repo):
    csv_path, graph = _resolve_csv_path("wf::G", container)
    # Fallback is the LEFT side (workflow token) as a Path
    assert csv_path == Path("wf")
    assert graph == "G"


def test_doublecolon_invalid_multiple_delimiters(container):
    with pytest.raises(GraphNotFound):
        _resolve_csv_path("a::b::c", container)


def test_doublecolon_empty_left_or_right(container):
    with pytest.raises(GraphNotFound):
        _resolve_csv_path("::b", container)
    with pytest.raises(GraphNotFound):
        _resolve_csv_path("a::", container)


# ---------- Slash syntax: workflow/graph ----------


def test_slash_prefers_repo_csv(container, repo):
    _touch_csv(repo, "workflow2")
    csv_path, graph = _resolve_csv_path("workflow2/GraphB", container)
    assert csv_path == repo / "workflow2.csv"
    assert graph == "GraphB"


def test_slash_fallback_when_repo_missing(container):
    csv_path, graph = _resolve_csv_path("alpha/beta", container)
    # Fallback is the FULL original identifier as a Path
    assert csv_path == Path("alpha/beta")
    assert graph == "beta"


def test_slash_empty_left_or_right(container):
    with pytest.raises(GraphNotFound):
        _resolve_csv_path("/graph", container)  # empty workflow
    with pytest.raises(GraphNotFound):
        _resolve_csv_path("workflow/", container)  # empty graph


# ---------- General invalid inputs ----------


def test_empty_identifier_raises(container):
    with pytest.raises(GraphNotFound):
        _resolve_csv_path("", container)


def test_whitespace_identifier_raises(container):
    with pytest.raises(GraphNotFound):
        _resolve_csv_path("   \t  ", container)
