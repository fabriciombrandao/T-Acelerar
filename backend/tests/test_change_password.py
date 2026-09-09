import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("TACELERAR_DB_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("TACELERAR_BOOTSTRAP_SECRET", "test-secret")

    for mod in ["app.db", "app.auth", "app.repository", "app.api"]:
        sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient
    import app.api as api_module

    with TestClient(api_module.app) as c:
        c.post("/api/auth/bootstrap-admin", json={
            "email": "diretor@teste.com", "name": "Diretor",
            "password": "senha-original-123", "bootstrap_secret": "test-secret",
        })
        token = c.post("/api/auth/login", data={
            "username": "diretor@teste.com", "password": "senha-original-123",
        }).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def _payload(current="senha-original-123", new="senha-nova-456", confirm=None):
    return {
        "current_password": current,
        "new_password": new,
        "new_password_confirm": confirm if confirm is not None else new,
    }


def test_change_password_succeeds_with_correct_current_password(client):
    resp = client.post("/api/auth/change-password", json=_payload())
    assert resp.status_code == 200


def test_new_password_works_for_login_after_change(client):
    client.post("/api/auth/change-password", json=_payload())
    resp = client.post("/api/auth/login", data={
        "username": "diretor@teste.com", "password": "senha-nova-456",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_old_password_stops_working_after_change(client):
    client.post("/api/auth/change-password", json=_payload())
    resp = client.post("/api/auth/login", data={
        "username": "diretor@teste.com", "password": "senha-original-123",
    })
    assert resp.status_code == 401


def test_change_password_rejects_wrong_current_password(client):
    resp = client.post("/api/auth/change-password",
                        json=_payload(current="senha-errada"))
    assert resp.status_code == 400


def test_change_password_rejects_short_new_password(client):
    resp = client.post("/api/auth/change-password",
                        json=_payload(new="curta", confirm="curta"))
    assert resp.status_code == 400


def test_change_password_rejects_mismatched_confirmation(client):
    resp = client.post("/api/auth/change-password",
                        json=_payload(new="senha-nova-456", confirm="senha-nova-diferente"))
    assert resp.status_code == 400
    assert "confirma" in resp.json()["detail"].lower()


def test_change_password_rejects_new_password_equal_to_current(client):
    resp = client.post("/api/auth/change-password",
                        json=_payload(new="senha-original-123", confirm="senha-original-123"))
    assert resp.status_code == 400


def test_change_password_requires_auth(client):
    client.headers.pop("Authorization", None)
    resp = client.post("/api/auth/change-password", json=_payload())
    assert resp.status_code == 401
