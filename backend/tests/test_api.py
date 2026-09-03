import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_CSV = Path(__file__).parent.parent.parent / "sample_data" / "produtos_exemplo.csv"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Cada teste roda com um banco SQLite isolado em arquivo temporário."""
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("WINTHOR_DB_URL", f"sqlite:///{db_file}")

    for mod in ["app.db", "app.repository", "app.api"]:
        sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient
    import app.api as api_module

    with TestClient(api_module.app) as c:
        yield c


def _create_project(client, name="Cliente Teste"):
    resp = client.post("/projects", json={"name": name})
    assert resp.status_code == 200
    return resp.json()["id"]


def _upload_sample(client, project_id):
    with SAMPLE_CSV.open("rb") as f:
        return client.post(
            "/imports",
            data={"project_id": project_id},
            files={"file": ("produtos_exemplo.csv", f, "text/csv")},
        )


def test_create_project(client):
    resp = client.post("/projects", json={"name": "Distribuidora Norte"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Distribuidora Norte"


def test_import_requires_valid_project(client):
    with SAMPLE_CSV.open("rb") as f:
        resp = client.post(
            "/imports",
            data={"project_id": "inexistente"},
            files={"file": ("produtos_exemplo.csv", f, "text/csv")},
        )
    assert resp.status_code == 404


def test_import_creates_batch_with_exceptions(client):
    project_id = _create_project(client)
    resp = _upload_sample(client, project_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["total_records"] == 7
    assert data["exception_count"] > 0


def test_list_project_imports(client):
    project_id = _create_project(client)
    _upload_sample(client, project_id)
    resp = client.get(f"/projects/{project_id}/imports")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_exceptions_defaults_to_all_pending(client):
    project_id = _create_project(client)
    _upload_sample(client, project_id)
    resp = client.get("/exceptions", params={"status": "PENDING"})
    exceptions = resp.json()
    assert len(exceptions) > 0
    assert all(e["resolution_status"] == "PENDING" for e in exceptions)


def test_resolve_exception_updates_status(client):
    project_id = _create_project(client)
    _upload_sample(client, project_id)
    exceptions = client.get("/exceptions").json()
    target = exceptions[0]

    resp = client.post(
        f"/exceptions/{target['id']}/resolve",
        json={"decision": "APPROVED", "resolved_by": "consultor.teste", "note": "ok"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution_status"] == "APPROVED"
    assert body["resolved_by"] == "consultor.teste"


def test_readiness_gate_blocks_on_pending_blocker(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    gate_before = client.get(f"/imports/{batch_id}/readiness").json()
    assert gate_before["ready_for_dry_run"] is False
    assert gate_before["pending_blockers"] >= 1

    blockers = client.get(
        "/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()
    for e in blockers:
        if e["severity"] == "BLOCKER":
            client.post(
                f"/exceptions/{e['id']}/resolve",
                json={"decision": "APPROVED", "resolved_by": "consultor.teste"},
            )

    gate_after = client.get(f"/imports/{batch_id}/readiness").json()
    assert gate_after["ready_for_dry_run"] is True
    assert gate_after["pending_blockers"] == 0


def test_generate_script_blocked_while_pending_blocker(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    resp = client.get(f"/imports/{batch['id']}/script")
    assert resp.status_code == 409


def test_generate_script_defaults_to_texto_format(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    blockers = client.get(
        "/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()
    for e in blockers:
        if e["severity"] == "BLOCKER":
            client.post(
                f"/exceptions/{e['id']}/resolve",
                json={"decision": "APPROVED", "resolved_by": "consultor.teste"},
            )

    resp = client.get(f"/imports/{batch_id}/script")
    assert resp.status_code == 200
    assert resp.headers["X-Format"] == "texto"
    assert resp.headers["content-type"].startswith("text/plain")


def test_generate_script_sql_format_still_available(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    blockers = client.get(
        "/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()
    for e in blockers:
        if e["severity"] == "BLOCKER":
            client.post(
                f"/exceptions/{e['id']}/resolve",
                json={"decision": "APPROVED", "resolved_by": "consultor.teste"},
            )

    resp = client.get(f"/imports/{batch_id}/script", params={"format": "sql"})
    assert resp.status_code == 200
    assert "INSERT INTO PCPRODUT" in resp.text
    assert resp.text.strip().endswith("COMMIT;")
    assert int(resp.headers["X-Records-Included"]) > 0


def test_generate_script_invalid_format_returns_400(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    resp = client.get(f"/imports/{batch['id']}/script", params={"format": "xml"})
    assert resp.status_code == 400


def test_generate_script_excludes_rejected_records(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    pending = client.get(
        "/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()

    blocker_record_id = None
    for e in pending:
        decision = "REJECTED" if e["severity"] == "BLOCKER" else "APPROVED"
        if e["severity"] == "BLOCKER":
            blocker_record_id = e["record_id"]
        client.post(
            f"/exceptions/{e['id']}/resolve",
            json={"decision": decision, "resolved_by": "consultor.teste"},
        )

    resp = client.get(f"/imports/{batch_id}/script", params={"format": "sql"})
    assert resp.status_code == 200
    assert int(resp.headers["X-Records-Skipped"]) >= 1
    assert f"'{blocker_record_id}'" not in resp.text


# ---------- Wizard de aderência ----------

def test_get_segments_returns_config(client):
    resp = client.get("/adherence/segments")
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()["segmentos"]}
    assert {"distribuicao", "varejo"} <= ids


def test_get_modules_returns_config(client):
    resp = client.get("/adherence/modules")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["modulos"]}
    assert "enderecamento" in ids


def test_set_adherence_applies_preset(client):
    project_id = _create_project(client)
    resp = client.post(
        f"/projects/{project_id}/adherence",
        json={"segment": "varejo", "subsegment": "loja_unica"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["adherence_answers"]["enderecamento"] is False
    assert body["adherence_answers"]["paletizacao"] is False


def test_set_adherence_with_override_beats_preset(client):
    project_id = _create_project(client)
    resp = client.post(
        f"/projects/{project_id}/adherence",
        json={
            "segment": "varejo", "subsegment": "loja_unica",
            "overrides": {"enderecamento": True},
        },
    )
    body = resp.json()
    assert body["adherence_answers"]["enderecamento"] is True  # override venceu o preset
    assert body["adherence_answers"]["paletizacao"] is False   # resto do preset intacto


def test_get_adherence_after_set_persists(client):
    project_id = _create_project(client)
    client.post(
        f"/projects/{project_id}/adherence",
        json={"segment": "distribuicao", "subsegment": "distribuidor_fmcg"},
    )
    resp = client.get(f"/projects/{project_id}/adherence")
    body = resp.json()
    assert body["segment"] == "distribuicao"
    assert body["subsegment"] == "distribuidor_fmcg"
    assert body["adherence_answers"]["enderecamento"] is True


def test_set_adherence_invalid_subsegment_returns_400(client):
    project_id = _create_project(client)
    resp = client.post(
        f"/projects/{project_id}/adherence",
        json={"segment": "distribuicao", "subsegment": "nao_existe"},
    )
    assert resp.status_code == 400
