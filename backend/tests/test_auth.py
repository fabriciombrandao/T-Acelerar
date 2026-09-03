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


# ---------- Isolamento por projeto (admin vê tudo, consultor só o seu) ----------

def _login(client, email, password="senha-forte-123"):
    token = client.post("/auth/login", data={
        "username": email, "password": password,
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_consultant(raw_client, admin_headers, email, name="Consultor"):
    raw_client.post("/users", headers=admin_headers, json={
        "email": email, "name": name, "password": "senha-forte-123", "is_admin": False,
    })
    return _login(raw_client, email)


def test_consultant_cannot_see_another_consultants_project(raw_client):
    _bootstrap(raw_client)
    admin_headers = _login(raw_client, "admin@teste.com")

    consultor_a = _create_consultant(raw_client, admin_headers, "a@teste.com")
    consultor_b = _create_consultant(raw_client, admin_headers, "b@teste.com")

    project = raw_client.post("/projects", headers=consultor_a,
                               json={"name": "Cliente da A"}).json()

    # Consultor B não vê no listing...
    lista_b = raw_client.get("/projects", headers=consultor_b).json()
    assert project["id"] not in [p["id"] for p in lista_b]

    # ...e não acessa diretamente por id.
    resp = raw_client.get(f"/projects/{project['id']}/imports", headers=consultor_b)
    assert resp.status_code == 403


def test_admin_sees_all_projects(raw_client):
    _bootstrap(raw_client)
    admin_headers = _login(raw_client, "admin@teste.com")
    consultor_a = _create_consultant(raw_client, admin_headers, "a2@teste.com")

    project = raw_client.post("/projects", headers=consultor_a,
                               json={"name": "Cliente da A2"}).json()

    lista_admin = raw_client.get("/projects", headers=admin_headers).json()
    assert project["id"] in [p["id"] for p in lista_admin]

    resp = raw_client.get(f"/projects/{project['id']}/imports", headers=admin_headers)
    assert resp.status_code == 200


def test_admin_can_assign_project_to_another_consultant(raw_client):
    _bootstrap(raw_client)
    admin_headers = _login(raw_client, "admin@teste.com")
    consultor = _create_consultant(raw_client, admin_headers, "c@teste.com")

    project = raw_client.post("/projects", headers=admin_headers,
                               json={"name": "Atribuído", "owner_email": "c@teste.com"}).json()
    assert project["owner_id"] is not None

    lista_consultor = raw_client.get("/projects", headers=consultor).json()
    assert project["id"] in [p["id"] for p in lista_consultor]


def test_non_admin_cannot_assign_project_to_others(raw_client):
    _bootstrap(raw_client)
    admin_headers = _login(raw_client, "admin@teste.com")
    consultor_a = _create_consultant(raw_client, admin_headers, "a3@teste.com")
    _create_consultant(raw_client, admin_headers, "b3@teste.com")

    resp = raw_client.post("/projects", headers=consultor_a,
                            json={"name": "X", "owner_email": "b3@teste.com"})
    assert resp.status_code == 403


def test_consultant_cannot_resolve_exception_of_others_project(raw_client):
    _bootstrap(raw_client)
    admin_headers = _login(raw_client, "admin@teste.com")
    consultor_a = _create_consultant(raw_client, admin_headers, "a4@teste.com")
    consultor_b = _create_consultant(raw_client, admin_headers, "b4@teste.com")

    project = raw_client.post("/projects", headers=consultor_a, json={"name": "P"}).json()
    sample_csv = Path(__file__).parent.parent.parent / "sample_data" / "produtos_exemplo.csv"
    with sample_csv.open("rb") as f:
        batch = raw_client.post(
            "/imports", headers=consultor_a, data={"project_id": project["id"]},
            files={"file": ("produtos_exemplo.csv", f, "text/csv")},
        ).json()

    exceptions = raw_client.get("/exceptions", headers=consultor_a,
                                 params={"batch_id": batch["id"]}).json()
    target = exceptions[0]

    resp = raw_client.post(f"/exceptions/{target['id']}/resolve", headers=consultor_b,
                            json={"decision": "APPROVED"})
    assert resp.status_code == 403
