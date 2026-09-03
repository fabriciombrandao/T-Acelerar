import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def raw_client(tmp_path, monkeypatch):
    """Cliente SEM bootstrap/login automático — para testar o próprio fluxo de auth."""
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("WINTHOR_DB_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("WINTHOR_BOOTSTRAP_SECRET", "test-secret")

    for mod in ["app.db", "app.auth", "app.repository", "app.api"]:
        sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient
    import app.api as api_module

    with TestClient(api_module.app) as c:
        yield c


def _bootstrap(client, email="admin@teste.com", secret="test-secret"):
    return client.post("/auth/bootstrap-admin", json={
        "email": email, "name": "Admin", "password": "senha-forte-123",
        "bootstrap_secret": secret,
    })


def test_protected_endpoint_requires_token(raw_client):
    resp = raw_client.get("/projects")
    assert resp.status_code == 401


def test_bootstrap_admin_creates_first_user(raw_client):
    resp = _bootstrap(raw_client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    assert body["email"] == "admin@teste.com"


def test_bootstrap_admin_rejects_wrong_secret(raw_client):
    resp = _bootstrap(raw_client, secret="secret-errado")
    assert resp.status_code == 403


def test_bootstrap_admin_only_works_once(raw_client):
    _bootstrap(raw_client)
    resp = _bootstrap(raw_client, email="segundo@teste.com")
    assert resp.status_code == 409


def test_login_with_correct_credentials_returns_token(raw_client):
    _bootstrap(raw_client)
    resp = raw_client.post("/auth/login", data={
        "username": "admin@teste.com", "password": "senha-forte-123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_with_wrong_password_fails(raw_client):
    _bootstrap(raw_client)
    resp = raw_client.post("/auth/login", data={
        "username": "admin@teste.com", "password": "senha-errada",
    })
    assert resp.status_code == 401


def test_token_grants_access_to_protected_endpoint(raw_client):
    _bootstrap(raw_client)
    token = raw_client.post("/auth/login", data={
        "username": "admin@teste.com", "password": "senha-forte-123",
    }).json()["access_token"]

    resp = raw_client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_invalid_token_rejected(raw_client):
    resp = raw_client.get("/projects", headers={"Authorization": "Bearer token-invalido"})
    assert resp.status_code == 401


def test_non_admin_cannot_create_users(raw_client):
    _bootstrap(raw_client)
    admin_token = raw_client.post("/auth/login", data={
        "username": "admin@teste.com", "password": "senha-forte-123",
    }).json()["access_token"]

    # Admin cria um consultor comum
    raw_client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json={
        "email": "consultor@teste.com", "name": "Consultor", "password": "outra-senha-123",
        "is_admin": False,
    })
    consultor_token = raw_client.post("/auth/login", data={
        "username": "consultor@teste.com", "password": "outra-senha-123",
    }).json()["access_token"]

    resp = raw_client.post(
        "/users", headers={"Authorization": f"Bearer {consultor_token}"},
        json={"email": "outro@teste.com", "name": "Outro", "password": "x1234567", "is_admin": False},
    )
    assert resp.status_code == 403


def test_non_admin_can_use_normal_endpoints(raw_client):
    _bootstrap(raw_client)
    admin_token = raw_client.post("/auth/login", data={
        "username": "admin@teste.com", "password": "senha-forte-123",
    }).json()["access_token"]

    raw_client.post("/users", headers={"Authorization": f"Bearer {admin_token}"}, json={
        "email": "consultor@teste.com", "name": "Consultor", "password": "outra-senha-123",
        "is_admin": False,
    })
    consultor_token = raw_client.post("/auth/login", data={
        "username": "consultor@teste.com", "password": "outra-senha-123",
    }).json()["access_token"]

    resp = raw_client.post(
        "/projects", headers={"Authorization": f"Bearer {consultor_token}"},
        json={"name": "Projeto do Consultor"},
    )
    assert resp.status_code == 200


def test_resolve_exception_records_authenticated_user_not_client_input(raw_client):
    """resolved_by deve vir do token, não de texto livre no corpo da requisição."""
    _bootstrap(raw_client, email="real.consultor@teste.com")
    token = raw_client.post("/auth/login", data={
        "username": "real.consultor@teste.com", "password": "senha-forte-123",
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    project_id = raw_client.post("/projects", headers=headers,
                                  json={"name": "P"}).json()["id"]

    sample_csv = Path(__file__).parent.parent.parent / "sample_data" / "produtos_exemplo.csv"
    with sample_csv.open("rb") as f:
        batch = raw_client.post(
            "/imports", headers=headers,
            data={"project_id": project_id},
            files={"file": ("produtos_exemplo.csv", f, "text/csv")},
        ).json()

    exceptions = raw_client.get("/exceptions", headers=headers,
                                 params={"batch_id": batch["id"]}).json()
    target = exceptions[0]

    resp = raw_client.post(
        f"/exceptions/{target['id']}/resolve", headers=headers,
        json={"decision": "APPROVED", "resolved_by": "nome-forjado-qualquer"},
    )
    body = resp.json()
    assert body["resolved_by"] == "real.consultor@teste.com"
    assert body["resolved_by"] != "nome-forjado-qualquer"
