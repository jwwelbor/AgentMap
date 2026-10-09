"""B102 cleanup errors do not replace storage initialization failures."""

import pytest

import agentmap.services.storage.gcp_storage_connector as gcp_connector_module
from agentmap.exceptions import StorageConnectionError
from agentmap.services.storage.gcp_storage_connector import GCPStorageConnector


class ControlFlowFailure(BaseException):
    pass


def test_missing_configured_credentials_preserve_ambient_environment(
    monkeypatch, tmp_path
):
    ambient_credentials = "/ambient/application-default.json"
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", ambient_credentials)
    configured_file = tmp_path / "missing-credentials.json"

    def create_client(**kwargs):
        return object()

    monkeypatch.setattr("google.cloud.storage.Client", create_client)

    GCPStorageConnector({"credentials_file": str(configured_file)})._initialize_client()

    assert (
        gcp_connector_module.os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        == ambient_credentials
    )


def test_configured_credentials_are_removed_only_after_temporary_change(
    monkeypatch, tmp_path
):
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}\n")
    observed = []

    def create_client(**kwargs):
        observed.append(
            gcp_connector_module.os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        )
        return object()

    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr("google.cloud.storage.Client", create_client)

    GCPStorageConnector(
        {"credentials_file": str(credentials_file)}
    )._initialize_client()

    assert observed == [str(credentials_file)]
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in gcp_connector_module.os.environ


def test_credential_restore_failure_is_secondary_to_client_failure(
    monkeypatch, tmp_path
):
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}\n")
    client_error = RuntimeError("client initialization failed")
    restore_error = ControlFlowFailure("private environment restore detail")

    class Environment(dict):
        def __setitem__(self, key, value):
            if key == "GOOGLE_APPLICATION_CREDENTIALS" and value == "original":
                raise restore_error
            super().__setitem__(key, value)

    environment = Environment({"GOOGLE_APPLICATION_CREDENTIALS": "original"})
    monkeypatch.setattr(gcp_connector_module.os, "environ", environment)
    monkeypatch.setattr(
        "google.cloud.storage.Client",
        lambda **kwargs: (_ for _ in ()).throw(client_error),
    )
    connector = GCPStorageConnector({"credentials_file": str(credentials_file)})

    try:
        connector._initialize_client()
    except StorageConnectionError as caught:
        primary = caught.__context__
    else:
        raise AssertionError("client initialization failure must propagate")

    assert primary is client_error
    assert primary.__notes__ == [
        "GCP credential environment restore failed with ControlFlowFailure"
    ]
    assert "private environment restore detail" not in " ".join(primary.__notes__)


def failing_environment_restore(monkeypatch, tmp_path, restore_error):
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}\n")

    class Environment(dict):
        def __setitem__(self, key, value):
            if key == "GOOGLE_APPLICATION_CREDENTIALS" and value == "original":
                raise restore_error
            super().__setitem__(key, value)

    environment = Environment({"GOOGLE_APPLICATION_CREDENTIALS": "original"})
    monkeypatch.setattr(gcp_connector_module.os, "environ", environment)
    return GCPStorageConnector({"credentials_file": str(credentials_file)})


@pytest.mark.parametrize("restore_type", [RuntimeError, ControlFlowFailure])
def test_success_inside_caller_except_surfaces_restore_failure(
    monkeypatch, tmp_path, restore_type
):
    unrelated = ValueError("unrelated caller recovery")
    restore = restore_type("restore failed")
    connector = failing_environment_restore(monkeypatch, tmp_path, restore)
    monkeypatch.setattr("google.cloud.storage.Client", lambda **kwargs: object())
    try:
        raise unrelated
    except ValueError:
        with pytest.raises(
            StorageConnectionError if isinstance(restore, Exception) else restore_type
        ) as caught:
            connector._initialize_client()
    observed = (
        caught.value.__context__ if isinstance(restore, Exception) else caught.value
    )
    assert observed is restore
    assert not hasattr(unrelated, "__notes__")
    assert (
        gcp_connector_module.os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        == connector.credentials_file
    )


@pytest.mark.parametrize("client_type", [RuntimeError, ControlFlowFailure])
@pytest.mark.parametrize("restore_type", [RuntimeError, ControlFlowFailure])
def test_client_inside_caller_except_preserves_local_failure(
    monkeypatch, tmp_path, client_type, restore_type
):
    unrelated = ValueError("caller recovery")
    client_error, restore = client_type("client failed"), restore_type("restore failed")
    connector = failing_environment_restore(monkeypatch, tmp_path, restore)
    monkeypatch.setattr(
        "google.cloud.storage.Client", lambda **kw: (_ for _ in ()).throw(client_error)
    )
    try:
        raise unrelated
    except ValueError:
        with pytest.raises(
            StorageConnectionError
            if isinstance(client_error, Exception)
            else client_type
        ) as caught:
            connector._initialize_client()
    observed = (
        caught.value.__context__
        if isinstance(client_error, Exception)
        else caught.value
    )
    assert observed is client_error
    assert not hasattr(unrelated, "__notes__")
    assert client_error.__notes__ == [
        f"GCP credential environment restore failed with {restore_type.__name__}"
    ]


def test_translated_credentials_failure_owns_restore_evidence(monkeypatch, tmp_path):
    from google.auth.exceptions import DefaultCredentialsError

    sdk_error = DefaultCredentialsError("missing credentials")
    restore = ControlFlowFailure("restore failed")
    connector = failing_environment_restore(monkeypatch, tmp_path, restore)
    monkeypatch.setattr(
        "google.cloud.storage.Client", lambda **kw: (_ for _ in ()).throw(sdk_error)
    )
    with pytest.raises(StorageConnectionError) as caught:
        connector._initialize_client()
    translated = caught.value.__context__
    assert isinstance(translated, StorageConnectionError)
    assert translated.__context__ is sdk_error
    assert translated.__notes__ == [
        "GCP credential environment restore failed with ControlFlowFailure"
    ]
    assert not hasattr(sdk_error, "__notes__")


def test_success_inside_caller_except_restores_environment_without_failure(
    monkeypatch, tmp_path
):
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}\n")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "original")
    client = object()
    monkeypatch.setattr("google.cloud.storage.Client", lambda **kw: client)
    connector = GCPStorageConnector({"credentials_file": str(credentials_file)})
    unrelated = ValueError("caller recovery")
    try:
        raise unrelated
    except ValueError:
        connector._initialize_client()
    assert connector._client is client
    assert (
        gcp_connector_module.os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "original"
    )
    assert not hasattr(unrelated, "__notes__")
