import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_CSV = Path(__file__).parent.parent.parent / "sample_data" / "produtos_exemplo.csv"
SPED_FIXTURE = Path(__file__).parent / "fixtures" / "sped_exemplo.txt"
NFE_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "nfe"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Cada teste roda com um banco SQLite isolado, um admin bootstrap já
    criado, e o TestClient já autenticado (headers persistem entre chamadas)."""
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("TACELERAR_DB_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("TACELERAR_BOOTSTRAP_SECRET", "test-secret")

    for mod in ["app.db", "app.auth", "app.repository", "app.api"]:
        sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient
    import app.api as api_module

    with TestClient(api_module.app) as c:
        c.post("/api/auth/bootstrap-admin", json={
            "email": "admin@teste.com", "name": "Admin Teste",
            "password": "senha-forte-123", "bootstrap_secret": "test-secret",
        })
        token = c.post("/api/auth/login", data={
            "username": "admin@teste.com", "password": "senha-forte-123",
        }).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def _create_project(client, name="Cliente Teste"):
    resp = client.post("/api/projects", json={"erp_type": "winthor", "name": name})
    assert resp.status_code == 200
    return resp.json()["id"]


def _ensure_adherence(client, project_id):
    """Configura um perfil simples (tudo opcional desligado) antes do upload
    — o gate de /api/imports exige isso desde que o motor de aderência foi
    conectado ao pipeline de verdade."""
    client.post(f"/api/projects/{project_id}/adherence",
                json={"segment": "varejo", "subsegment": "loja_unica"})


def _upload_sample(client, project_id):
    _ensure_adherence(client, project_id)
    with SAMPLE_CSV.open("rb") as f:
        return client.post(
            "/api/imports",
            data={"project_id": project_id, "source_type": "csv"},
            files=[("files", ("produtos_exemplo.csv", f, "text/csv"))],
        )


def test_create_project(client):
    resp = client.post("/api/projects", json={"erp_type": "winthor", "name": "Distribuidora Norte"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Distribuidora Norte"
    assert resp.json()["erp_type"] == "winthor"


def test_create_project_rejects_unsupported_erp(client):
    resp = client.post("/api/projects", json={"erp_type": "protheus", "name": "X"})
    assert resp.status_code == 400


def test_list_erps_returns_winthor(client):
    resp = client.get("/api/erps")
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()]
    assert ids == ["winthor"]


def test_import_requires_valid_project(client):
    with SAMPLE_CSV.open("rb") as f:
        resp = client.post(
            "/api/imports",
            data={"project_id": "inexistente"},
            files=[("files", ("produtos_exemplo.csv", f, "text/csv"))],
        )
    assert resp.status_code == 404


def test_import_requires_adherence_configured_first(client):
    """Gate: upload sem passar pelo wizard de aderência antes (POST
    /projects/{id}/adherence) é bloqueado — sem isso, o pipeline roda
    sem saber quais módulos são aplicáveis pro cliente."""
    project_id = _create_project(client)
    with SAMPLE_CSV.open("rb") as f:
        resp = client.post(
            "/api/imports", data={"project_id": project_id},
            files=[("files", ("produtos_exemplo.csv", f, "text/csv"))],
        )
    assert resp.status_code == 400
    assert "aderência" in resp.json()["detail"].lower()


def test_import_source_type_sped_works_end_to_end(client):
    project_id = _create_project(client)
    _ensure_adherence(client, project_id)
    with SPED_FIXTURE.open("rb") as f:
        resp = client.post(
            "/api/imports",
            data={"project_id": project_id, "source_type": "sped"},
            files=[("files", ("sped_exemplo.txt", f, "text/plain"))],
        )
    assert resp.status_code == 200
    batch = resp.json()
    assert batch["status"] == "DONE"
    assert batch["total_records"] > 0


def test_import_source_type_xml_requires_company_cnpj_on_project(client):
    """Projeto sem company_cnpj configurado não pode importar XML — sem
    isso não dá pra classificar entrada/saída de cada nota."""
    project_id = _create_project(client)  # _create_project não seta company_cnpj
    _ensure_adherence(client, project_id)
    with (NFE_FIXTURE_DIR / "saida_cliente_a.xml").open("rb") as f:
        resp = client.post(
            "/api/imports",
            data={"project_id": project_id, "source_type": "xml"},
            files=[("files", ("saida_cliente_a.xml", f, "application/xml"))],
        )
    assert resp.status_code == 400
    assert "cnpj" in resp.json()["detail"].lower()


def test_import_source_type_xml_works_with_company_cnpj_configured(client):
    resp = client.post("/api/projects", json={
        "erp_type": "winthor", "name": "Projeto com CNPJ",
        "company_cnpj": "11222333000181",
    })
    project_id = resp.json()["id"]
    _ensure_adherence(client, project_id)

    with (NFE_FIXTURE_DIR / "saida_cliente_a.xml").open("rb") as f:
        resp = client.post(
            "/api/imports",
            data={"project_id": project_id, "source_type": "xml"},
            files=[("files", ("saida_cliente_a.xml", f, "application/xml"))],
        )
    assert resp.status_code == 200
    assert resp.json()["total_records"] == 1


def test_import_source_type_csv_rejects_multiple_files(client):
    project_id = _create_project(client)
    _ensure_adherence(client, project_id)
    with SAMPLE_CSV.open("rb") as f1, SAMPLE_CSV.open("rb") as f2:
        resp = client.post(
            "/api/imports",
            data={"project_id": project_id, "source_type": "csv"},
            files=[
                ("files", ("a.csv", f1, "text/csv")),
                ("files", ("b.csv", f2, "text/csv")),
            ],
        )
    assert resp.status_code == 400


def test_import_rejects_unknown_source_type(client):
    project_id = _create_project(client)
    _ensure_adherence(client, project_id)
    with SAMPLE_CSV.open("rb") as f:
        resp = client.post(
            "/api/imports",
            data={"project_id": project_id, "source_type": "excel_magico"},
            files=[("files", ("a.csv", f, "text/csv"))],
        )
    assert resp.status_code == 400


def test_create_project_validates_company_cnpj_checksum(client):
    resp = client.post("/api/projects", json={
        "erp_type": "winthor", "name": "X", "company_cnpj": "11222333000199",
    })
    assert resp.status_code == 400


def test_create_project_accepts_valid_company_cnpj(client):
    resp = client.post("/api/projects", json={
        "erp_type": "winthor", "name": "X", "company_cnpj": "11222333000181",
    })
    assert resp.status_code == 200
    assert resp.json()["company_cnpj"] == "11222333000181"


def test_update_project_sets_company_cnpj(client):
    project_id = _create_project(client)
    resp = client.patch(f"/api/projects/{project_id}",
                         json={"company_cnpj": "11222333000181"})
    assert resp.status_code == 200
    assert resp.json()["company_cnpj"] == "11222333000181"


def test_update_project_validates_cnpj_checksum(client):
    project_id = _create_project(client)
    resp = client.patch(f"/api/projects/{project_id}",
                         json={"company_cnpj": "11222333000199"})
    assert resp.status_code == 400


def test_update_project_requires_authorized_access(client):
    resp = client.patch("/api/projects/inexistente",
                         json={"company_cnpj": "11222333000181"})
    assert resp.status_code == 404


def test_import_creates_batch_with_exceptions(client):
    project_id = _create_project(client)
    resp = _upload_sample(client, project_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["total_records"] == 7
    assert data["exception_count"] > 0


def test_import_batch_status_is_done_after_sync_processing(client):
    """Sem Redis configurado (ambiente de teste), a task roda em modo eager —
    o lote já deve estar DONE na resposta do POST, sem precisar dar poll."""
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    assert batch["status"] == "DONE"
    assert batch["error_message"] is None


def test_get_import_status_endpoint_reflects_current_state(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()

    resp = client.get(f"/api/imports/{batch['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "DONE"
    assert resp.json()["total_records"] == 7


def test_import_batch_marked_failed_on_pipeline_error(client, monkeypatch):
    """Se o pipeline lançar exceção durante o processamento, o lote deve
    ficar FAILED com a mensagem de erro, não travar silenciosamente."""
    import io

    import app.pipeline as pipeline_module

    def _boom(path, **kwargs):
        raise ValueError("arquivo corrompido de propósito")

    monkeypatch.setattr(pipeline_module, "run_pipeline_csv", _boom)

    project_id = _create_project(client)
    _ensure_adherence(client, project_id)
    fake_csv = io.BytesIO(b"codigo,descricao\n1,teste\n")

    # Modo eager propaga a exceção da task pra dentro da própria requisição.
    with pytest.raises(Exception):
        client.post(
            "/api/imports", data={"project_id": project_id},
            files=[("files", ("bogus.csv", fake_csv, "text/csv"))],
        )

    # O lote foi criado (PENDING) antes de disparar a task, então mesmo com
    # a exceção o registro existe — e mark_batch_failed já commitou FAILED
    # antes de a exceção subir.
    batches = client.get(f"/api/projects/{project_id}/imports").json()
    assert len(batches) == 1
    assert batches[0]["status"] == "FAILED"
    assert "arquivo corrompido" in (batches[0]["error_message"] or "")


def test_list_project_imports(client):
    project_id = _create_project(client)
    _upload_sample(client, project_id)
    resp = client.get(f"/api/projects/{project_id}/imports")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_exceptions_defaults_to_all_pending(client):
    project_id = _create_project(client)
    _upload_sample(client, project_id)
    resp = client.get("/api/exceptions", params={"status": "PENDING"})
    exceptions = resp.json()
    assert len(exceptions) > 0
    assert all(e["resolution_status"] == "PENDING" for e in exceptions)


def test_resolve_exception_updates_status(client):
    project_id = _create_project(client)
    _upload_sample(client, project_id)
    exceptions = client.get("/api/exceptions").json()
    target = exceptions[0]

    resp = client.post(
        f"/api/exceptions/{target['id']}/resolve",
        json={"decision": "APPROVED", "note": "ok"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution_status"] == "APPROVED"
    assert body["resolved_by"] == "admin@teste.com"


def test_readiness_gate_blocks_on_pending_blocker(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    gate_before = client.get(f"/api/imports/{batch_id}/readiness").json()
    assert gate_before["ready_for_dry_run"] is False
    assert gate_before["pending_blockers"] >= 1

    blockers = client.get(
        "/api/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()
    for e in blockers:
        if e["severity"] == "BLOCKER":
            client.post(
                f"/api/exceptions/{e['id']}/resolve",
                json={"decision": "APPROVED"},
            )

    gate_after = client.get(f"/api/imports/{batch_id}/readiness").json()
    assert gate_after["ready_for_dry_run"] is True
    assert gate_after["pending_blockers"] == 0


def test_generate_script_blocked_while_pending_blocker(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    resp = client.get(f"/api/imports/{batch['id']}/script")
    assert resp.status_code == 409


def test_generate_script_defaults_to_texto_format(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    blockers = client.get(
        "/api/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()
    for e in blockers:
        if e["severity"] == "BLOCKER":
            client.post(
                f"/api/exceptions/{e['id']}/resolve",
                json={"decision": "APPROVED"},
            )

    resp = client.get(f"/api/imports/{batch_id}/script")
    assert resp.status_code == 200
    assert resp.headers["X-Format"] == "texto"
    assert resp.headers["content-type"].startswith("text/plain")


def test_generate_script_sql_format_still_available(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    blockers = client.get(
        "/api/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()
    for e in blockers:
        if e["severity"] == "BLOCKER":
            client.post(
                f"/api/exceptions/{e['id']}/resolve",
                json={"decision": "APPROVED"},
            )

    resp = client.get(f"/api/imports/{batch_id}/script", params={"format": "sql"})
    assert resp.status_code == 200
    assert "INSERT INTO PCPRODUT" in resp.text
    assert resp.text.strip().endswith("COMMIT;")
    assert int(resp.headers["X-Records-Included"]) > 0


def test_generate_script_invalid_format_returns_400(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    resp = client.get(f"/api/imports/{batch['id']}/script", params={"format": "xml"})
    assert resp.status_code == 400


def test_generate_script_excludes_rejected_records(client):
    project_id = _create_project(client)
    batch = _upload_sample(client, project_id).json()
    batch_id = batch["id"]

    pending = client.get(
        "/api/exceptions", params={"batch_id": batch_id, "status": "PENDING"}
    ).json()

    blocker_record_id = None
    for e in pending:
        decision = "REJECTED" if e["severity"] == "BLOCKER" else "APPROVED"
        if e["severity"] == "BLOCKER":
            blocker_record_id = e["record_id"]
        client.post(
            f"/api/exceptions/{e['id']}/resolve",
            json={"decision": decision},
        )

    resp = client.get(f"/api/imports/{batch_id}/script", params={"format": "sql"})
    assert resp.status_code == 200
    assert int(resp.headers["X-Records-Skipped"]) >= 1
    assert f"'{blocker_record_id}'" not in resp.text


# ---------- Wizard de aderência ----------

def test_get_segments_returns_config(client):
    resp = client.get("/api/adherence/segments")
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()["segmentos"]}
    assert {"distribuicao", "varejo"} <= ids


def test_get_modules_returns_config(client):
    resp = client.get("/api/adherence/modules")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["modulos"]}
    assert "enderecamento" in ids


def test_set_adherence_applies_preset(client):
    project_id = _create_project(client)
    resp = client.post(
        f"/api/projects/{project_id}/adherence",
        json={"segment": "varejo", "subsegment": "loja_unica"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["adherence_answers"]["enderecamento"] is False
    assert body["adherence_answers"]["paletizacao"] is False


def test_set_adherence_with_override_beats_preset(client):
    project_id = _create_project(client)
    resp = client.post(
        f"/api/projects/{project_id}/adherence",
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
        f"/api/projects/{project_id}/adherence",
        json={"segment": "distribuicao", "subsegment": "distribuidor_fmcg"},
    )
    resp = client.get(f"/api/projects/{project_id}/adherence")
    body = resp.json()
    assert body["segment"] == "distribuicao"
    assert body["subsegment"] == "distribuidor_fmcg"
    assert body["adherence_answers"]["enderecamento"] is True


def test_set_adherence_invalid_subsegment_returns_400(client):
    project_id = _create_project(client)
    resp = client.post(
        f"/api/projects/{project_id}/adherence",
        json={"segment": "distribuicao", "subsegment": "nao_existe"},
    )
    assert resp.status_code == 400
