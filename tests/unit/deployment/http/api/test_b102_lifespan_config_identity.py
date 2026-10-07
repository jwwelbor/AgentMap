"""HTTP lifespans share a runtime only for the same effective config file."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI

from agentmap.deployment.http.api.server import create_lifespan
from agentmap.di import initialize_di
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.lifespan_mixin import effective_config_file
from agentmap.runtime.runtime_manager import RuntimeManager


@pytest.fixture
def runtime_setup(monkeypatch):
    service = SimpleNamespace(shutdown=AsyncMock())
    container = SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )
    RuntimeManager.reset()
    install = Mock(return_value=container)
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", install)
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    yield container, service, install
    RuntimeManager.reset()


def test_effective_identity_matches_real_di_discovery__b102(tmp_path, monkeypatch):
    config = tmp_path / "agentmap_config.yaml"
    config.write_text("{}\n")
    monkeypatch.chdir(tmp_path)

    container = initialize_di()
    explicit = initialize_di("./agentmap_config.yaml")

    assert effective_config_file(None) == str(config.resolve())
    assert effective_config_file("./agentmap_config.yaml") == str(config.resolve())
    assert container.config.path() == str(config)
    assert explicit.config.path() == "agentmap_config.yaml"


@pytest.mark.parametrize("argument", [None, "./agentmap_config.yaml"])
def test_runtime_records_real_di_effective_identity__b102(
    tmp_path, monkeypatch, argument
):
    config = tmp_path / "agentmap_config.yaml"
    config.write_text("{}\n")
    monkeypatch.chdir(tmp_path)
    RuntimeManager.reset()
    try:
        RuntimeManager.initialize(config_file=argument)
        assert RuntimeManager._runtime_config_file == str(config.resolve())
    finally:
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_default_config_rejects_discovery_after_cwd_change__b102(
    tmp_path, monkeypatch, runtime_setup
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "agentmap_config.yaml").write_text("first: true\n")
    (second / "agentmap_config.yaml").write_text("second: true\n")
    container, service, install = runtime_setup
    monkeypatch.chdir(first)

    async with create_lifespan()(FastAPI()):
        monkeypatch.chdir(second)
        with pytest.raises(AgentMapNotInitialized, match="config differs"):
            async with create_lifespan()(FastAPI()):
                pytest.fail("different discovered config must not share a runtime")
        assert RuntimeManager.get_container() is container
        service.shutdown.assert_not_awaited()
    install.assert_called_once_with(None)
    service.shutdown.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_first", [False, True])
@pytest.mark.parametrize("use_symlink", [False, True])
async def test_default_and_explicit_same_file_share_runtime__b102(
    tmp_path, monkeypatch, runtime_setup, explicit_first, use_symlink
):
    config = tmp_path / "agentmap_config.yaml"
    config.write_text("shared: true\n")
    alias = tmp_path / "alias.yml"
    alias.symlink_to(config)
    monkeypatch.chdir(tmp_path)
    container, service, install = runtime_setup
    explicit = str(alias if use_symlink else config)
    outer = explicit if explicit_first else None
    inner = None if explicit_first else explicit

    async with create_lifespan(outer)(FastAPI()):
        async with create_lifespan(inner)(FastAPI()):
            assert RuntimeManager.get_container() is container
        service.shutdown.assert_not_awaited()
    install.assert_called_once_with(outer)
    service.shutdown.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_equal_relative_names_reject_different_resolved_files__b102(
    tmp_path, monkeypatch, runtime_setup
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "same.yml").write_text("first: true\n")
    (second / "same.yml").write_text("second: true\n")
    container, service, install = runtime_setup
    monkeypatch.chdir(first)

    async with create_lifespan("same.yml")(FastAPI()):
        monkeypatch.chdir(second)
        with pytest.raises(AgentMapNotInitialized, match="config differs"):
            async with create_lifespan("same.yml")(FastAPI()):
                pytest.fail("relative name from another cwd must not share runtime")
        assert RuntimeManager.get_container() is container
        service.shutdown.assert_not_awaited()
    install.assert_called_once_with("same.yml")
    service.shutdown.assert_awaited_once_with()
