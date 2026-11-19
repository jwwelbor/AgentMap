"""Malformed auth YAML should produce a CLI error instead of a traceback."""

import yaml
from typer.testing import CliRunner

from agentmap.deployment.cli.auth_command import auth_app, load_yaml_config


def test_auth_view_rejects_non_mapping_api_keys(tmp_path):
    config_path = tmp_path / "auth.yaml"
    config_path.write_text(
        yaml.safe_dump({"authentication": {"api_keys": ["not-a-mapping"]}}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(auth_app, ["view", "--config", str(config_path)])

    assert result.exit_code == 1
    assert "api_keys must be a mapping" in result.output


def test_auth_yaml_loader_rejects_non_mapping_roots_and_keeps_empty_files(tmp_path):
    empty_path = tmp_path / "empty.yaml"
    empty_path.write_text("", encoding="utf-8")
    assert load_yaml_config(str(empty_path)) == {}

    runner = CliRunner()
    for index, yaml_root in enumerate((["section"], "section")):
        config_path = tmp_path / f"root-{index}.yaml"
        config_path.write_text(yaml.safe_dump(yaml_root), encoding="utf-8")

        result = runner.invoke(auth_app, ["view", "--config", str(config_path)])

        assert result.exit_code == 1
        assert "YAML configuration must contain a mapping" in result.output
