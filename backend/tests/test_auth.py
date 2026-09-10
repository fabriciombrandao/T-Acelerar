import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_CSV = Path(__file__).parent.parent.parent / "sample_data" / "produtos_exemplo.csv"


@pytest.fixture()
def raw_client(tmp_path, monkeypatch):
    """Cliente SEM bootstrap/login automático — para testar o próprio fluxo de auth."""
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("TACELERAR_DB_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("TACELERAR_BOOTSTRAP_SECRET", "test-secret")

    for mod in ["app.db", "app.auth", "app.repository", "app.api"]:
        sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient
    import app.api as api_module

    with TestClient(api_module.app) as c:
        yield c


def _bootstrap(client, email="diretor@teste.com", secret="test-secret"):
    return client.post("/api/auth/bootstrap-admin", json={
        "email": email, "name": "Diretor", "password": "senha-forte-123",
        "bootstrap_secret": secret,
    })


def _login(client, email, password="senha-forte-123"):
    token = client.post("/api/auth/login", data={
        "username": email, "password": password,
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_user(client, actor_headers, email, role, manager_email=None, name="User"):
    payload = {"email": email, "name": name, "password": "senha-forte-123", "role": role}
    if manager_email:
        payload["manager_email"] = manager_email
    resp = client.post("/api/users", headers=actor_headers, json=payload)
    return resp


def _upload_sample(client, headers, project_id):
    client.post(f"/api/projects/{project_id}/adherence", headers=headers,
                json={"segment": "varejo", "subsegment": "loja_unica"})
    with SAMPLE_CSV.open("rb") as f:
        return client.post(
            "/api/imports", headers=headers, data={"project_id": project_id},
            files=[("files", ("produtos_exemplo.csv", f, "text/csv"))],
        )


# ---------- Fluxo básico de autenticação ----------

def test_protected_endpoint_requires_token(raw_client):
    resp = raw_client.get("/api/projects")
    assert resp.status_code == 401


def test_bootstrap_admin_creates_first_diretor(raw_client):
    resp = _bootstrap(raw_client)
    assert resp.status_code == 200
    assert resp.json()["role"] == "diretor"


def test_bootstrap_admin_rejects_wrong_secret(raw_client):
    resp = _bootstrap(raw_client, secret="secret-errado")
    assert resp.status_code == 403


def test_bootstrap_admin_only_works_once(raw_client):
    _bootstrap(raw_client)
    resp = _bootstrap(raw_client, email="segundo@teste.com")
    assert resp.status_code == 409


def test_login_with_correct_credentials_returns_token(raw_client):
    _bootstrap(raw_client)
    resp = raw_client.post("/api/auth/login", data={
        "username": "diretor@teste.com", "password": "senha-forte-123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_with_wrong_password_fails(raw_client):
    _bootstrap(raw_client)
    resp = raw_client.post("/api/auth/login", data={
        "username": "diretor@teste.com", "password": "senha-errada",
    })
    assert resp.status_code == 401


def test_invalid_token_rejected(raw_client):
    resp = raw_client.get("/api/projects", headers={"Authorization": "Bearer token-invalido"})
    assert resp.status_code == 401


def test_resolve_exception_records_authenticated_user_not_client_input(raw_client):
    """resolved_by deve vir do token, não de texto livre no corpo da requisição."""
    _bootstrap(raw_client, email="real.consultor@teste.com")
    headers = _login(raw_client, "real.consultor@teste.com")

    project_id = raw_client.post("/api/projects", headers=headers, json={"erp_type": "winthor", "name": "P"}).json()["id"]
    batch = _upload_sample(raw_client, headers, project_id).json()

    exceptions = raw_client.get("/api/exceptions", headers=headers,
                                 params={"batch_id": batch["id"]}).json()
    target = exceptions[0]

    resp = raw_client.post(
        f"/api/exceptions/{target['id']}/resolve", headers=headers,
        json={"decision": "APPROVED", "resolved_by": "nome-forjado-qualquer"},
    )
    body = resp.json()
    assert body["resolved_by"] == "real.consultor@teste.com"
    assert body["resolved_by"] != "nome-forjado-qualquer"


# ---------- Criação de usuários por papel ----------

def test_diretor_creates_coordenador(raw_client):
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    resp = _create_user(raw_client, diretor, "coord@teste.com", "coordenador")
    assert resp.status_code == 200
    assert resp.json()["role"] == "coordenador"
    assert resp.json()["manager_id"] is None


def test_diretor_creates_analista_requires_manager_email(raw_client):
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    resp = _create_user(raw_client, diretor, "analista1@teste.com", "analista")
    assert resp.status_code == 400  # faltou manager_email


def test_diretor_creates_analista_with_valid_coordenador(raw_client):
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    _create_user(raw_client, diretor, "coord@teste.com", "coordenador")

    resp = _create_user(raw_client, diretor, "analista1@teste.com", "analista",
                         manager_email="coord@teste.com")
    assert resp.status_code == 200
    assert resp.json()["role"] == "analista"
    assert resp.json()["manager_id"] is not None


def test_coordenador_can_only_create_analista(raw_client):
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    _create_user(raw_client, diretor, "coord@teste.com", "coordenador")
    coord = _login(raw_client, "coord@teste.com")

    resp = _create_user(raw_client, coord, "outro-coord@teste.com", "coordenador")
    assert resp.status_code == 403


def test_coordenador_created_analista_auto_assigned_to_team(raw_client):
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    coord_id = _create_user(raw_client, diretor, "coord@teste.com", "coordenador").json()["id"]
    coord = _login(raw_client, "coord@teste.com")

    resp = _create_user(raw_client, coord, "analista1@teste.com", "analista")
    assert resp.status_code == 200
    assert resp.json()["manager_id"] == coord_id


def test_analista_cannot_create_users(raw_client):
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    _create_user(raw_client, diretor, "coord@teste.com", "coordenador")
    coord = _login(raw_client, "coord@teste.com")
    _create_user(raw_client, coord, "analista1@teste.com", "analista")
    analista = _login(raw_client, "analista1@teste.com")

    resp = _create_user(raw_client, analista, "outro@teste.com", "analista")
    assert resp.status_code == 403


def test_analista_can_use_normal_endpoints(raw_client):
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    _create_user(raw_client, diretor, "coord@teste.com", "coordenador")
    coord = _login(raw_client, "coord@teste.com")
    _create_user(raw_client, coord, "analista1@teste.com", "analista")
    analista = _login(raw_client, "analista1@teste.com")

    resp = raw_client.post("/api/projects", headers=analista, json={"erp_type": "winthor", "name": "Projeto"})
    assert resp.status_code == 200


# ---------- Visibilidade hierárquica ----------

def _setup_two_teams(raw_client):
    """diretor -> coord_a -> analista_a1 ; diretor -> coord_b -> analista_b1"""
    _bootstrap(raw_client)
    diretor = _login(raw_client, "diretor@teste.com")
    _create_user(raw_client, diretor, "coord_a@teste.com", "coordenador")
    _create_user(raw_client, diretor, "coord_b@teste.com", "coordenador")
    coord_a = _login(raw_client, "coord_a@teste.com")
    coord_b = _login(raw_client, "coord_b@teste.com")
    _create_user(raw_client, coord_a, "analista_a1@teste.com", "analista")
    _create_user(raw_client, coord_b, "analista_b1@teste.com", "analista")
    return {
        "diretor": diretor, "coord_a": coord_a, "coord_b": coord_b,
        "analista_a1": _login(raw_client, "analista_a1@teste.com"),
        "analista_b1": _login(raw_client, "analista_b1@teste.com"),
    }


def test_diretor_sees_all_projects(raw_client):
    headers = _setup_two_teams(raw_client)
    p = raw_client.post("/api/projects", headers=headers["analista_a1"],
                         json={"erp_type": "winthor", "name": "Cliente A"}).json()

    lista = raw_client.get("/api/projects", headers=headers["diretor"]).json()
    assert p["id"] in [x["id"] for x in lista]


def test_coordenador_sees_own_teams_project(raw_client):
    headers = _setup_two_teams(raw_client)
    p = raw_client.post("/api/projects", headers=headers["analista_a1"],
                         json={"erp_type": "winthor", "name": "Cliente A"}).json()

    lista = raw_client.get("/api/projects", headers=headers["coord_a"]).json()
    assert p["id"] in [x["id"] for x in lista]


def test_coordenador_cannot_see_other_teams_project(raw_client):
    headers = _setup_two_teams(raw_client)
    p = raw_client.post("/api/projects", headers=headers["analista_a1"],
                         json={"erp_type": "winthor", "name": "Cliente A"}).json()

    lista = raw_client.get("/api/projects", headers=headers["coord_b"]).json()
    assert p["id"] not in [x["id"] for x in lista]

    resp = raw_client.get(f"/api/projects/{p['id']}/imports", headers=headers["coord_b"])
    assert resp.status_code == 403


def test_analista_cannot_see_peer_analista_project_same_team(raw_client):
    headers = _setup_two_teams(raw_client)
    # analista_a1 e um segundo analista da mesma equipe (coord_a)
    _create_user(raw_client, headers["coord_a"], "analista_a2@teste.com", "analista")
    analista_a2 = _login(raw_client, "analista_a2@teste.com")

    p = raw_client.post("/api/projects", headers=headers["analista_a1"],
                         json={"erp_type": "winthor", "name": "Cliente A"}).json()

    resp = raw_client.get(f"/api/projects/{p['id']}/imports", headers=analista_a2)
    assert resp.status_code == 403  # mesmo mesmo coordenador, analistas não veem uns dos outros


def test_coordenador_cannot_resolve_exception_of_other_teams_project(raw_client):
    headers = _setup_two_teams(raw_client)
    project = raw_client.post("/api/projects", headers=headers["analista_a1"],
                               json={"erp_type": "winthor", "name": "P"}).json()
    batch = _upload_sample(raw_client, headers["analista_a1"], project["id"]).json()

    exceptions = raw_client.get("/api/exceptions", headers=headers["coord_a"],
                                 params={"batch_id": batch["id"]}).json()
    target = exceptions[0]

    resp = raw_client.post(f"/api/exceptions/{target['id']}/resolve", headers=headers["coord_b"],
                            json={"decision": "APPROVED"})
    assert resp.status_code == 403


def test_coordenador_cannot_delete_project_of_other_team(raw_client):
    headers = _setup_two_teams(raw_client)
    project = raw_client.post("/api/projects", headers=headers["analista_a1"],
                               json={"erp_type": "winthor", "name": "P"}).json()

    resp = raw_client.delete(f"/api/projects/{project['id']}", headers=headers["coord_b"])
    assert resp.status_code == 403


def test_diretor_can_delete_any_project(raw_client):
    headers = _setup_two_teams(raw_client)
    project = raw_client.post("/api/projects", headers=headers["analista_a1"],
                               json={"erp_type": "winthor", "name": "P"}).json()

    resp = raw_client.delete(f"/api/projects/{project['id']}", headers=headers["diretor"])
    assert resp.status_code == 204


# ---------- Atribuição de projeto ----------

def test_coordenador_can_assign_project_to_team_member(raw_client):
    headers = _setup_two_teams(raw_client)
    resp = raw_client.post("/api/projects", headers=headers["coord_a"],
                            json={"erp_type": "winthor", "name": "Atribuído", "owner_email": "analista_a1@teste.com"})
    assert resp.status_code == 200
    assert resp.json()["owner_id"] is not None


def test_coordenador_cannot_assign_project_outside_team(raw_client):
    headers = _setup_two_teams(raw_client)
    resp = raw_client.post("/api/projects", headers=headers["coord_a"],
                            json={"erp_type": "winthor", "name": "X", "owner_email": "analista_b1@teste.com"})
    assert resp.status_code == 403


def test_analista_cannot_assign_project_to_anyone_else(raw_client):
    headers = _setup_two_teams(raw_client)
    resp = raw_client.post("/api/projects", headers=headers["analista_a1"],
                            json={"erp_type": "winthor", "name": "X", "owner_email": "analista_b1@teste.com"})
    assert resp.status_code == 403


def test_diretor_can_assign_project_to_anyone(raw_client):
    headers = _setup_two_teams(raw_client)
    resp = raw_client.post("/api/projects", headers=headers["diretor"],
                            json={"erp_type": "winthor", "name": "X", "owner_email": "analista_b1@teste.com"})
    assert resp.status_code == 200
