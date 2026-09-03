"""
API — expõe o pipeline, a Exception Queue e a geração de script Oracle como serviço.

Fluxo real de uso (sem API do Winthor disponível):
  abrir/criar projeto -> subir arquivo -> validar (pipeline automático) ->
  tratar exceções -> gerar script .sql -> rodar manualmente no Oracle do cliente.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db import ExceptionRow, ImportBatch, Project, ProductRecord, get_session, init_db
from app.pipeline import run_pipeline_csv
from app.repository import persist_pipeline_result
from app.winthor.oracle_generator import generate_insert_script

STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend"
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "output" / "scripts"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Winthor Data Deploy API",
    description="Ingestão, saneamento, auditoria, Exception Queue e geração de script Oracle.",
    version="0.2.0",
    lifespan=lifespan,
)


def get_db():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


# ---------- Schemas ----------

class ProjectOut(BaseModel):
    id: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class ProjectIn(BaseModel):
    name: str


class BatchSummary(BaseModel):
    id: str
    project_id: str
    source_file: str
    total_records: int
    exception_count: int
    data_readiness_score: float
    model_config = ConfigDict(from_attributes=True)


class ExceptionOut(BaseModel):
    id: int
    batch_id: str
    record_id: str
    entity: str
    reason_code: str
    description: str
    severity: str
    payload: dict
    resolution_status: str
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ResolveExceptionIn(BaseModel):
    decision: str  # "APPROVED" | "REJECTED"
    resolved_by: str
    note: Optional[str] = None


# ---------- Projetos ----------

@app.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectIn, db: Session = Depends(get_db)):
    project = Project(id=str(uuid.uuid4()), name=payload.name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@app.get("/projects/{project_id}/imports", response_model=list[BatchSummary])
def list_project_imports(project_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ImportBatch)
        .filter(ImportBatch.project_id == project_id)
        .order_by(ImportBatch.created_at.desc())
        .all()
    )


# ---------- Imports / Pipeline ----------

@app.post("/imports", response_model=BatchSummary)
async def create_import(project_id: str = Form(...), file: UploadFile = None,
                         db: Session = Depends(get_db)):
    """Sobe um CSV de produtos dentro de um projeto, roda o pipeline e persiste."""
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(404, "Projeto não encontrado.")
    if not file or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Envie um arquivo .csv.")

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = run_pipeline_csv(tmp_path)
        batch = persist_pipeline_result(db, result, source_file=file.filename,
                                         project_id=project_id)
    finally:
        tmp_path.unlink(missing_ok=True)

    return batch


@app.get("/imports/{batch_id}/report")
def get_report(batch_id: str, db: Session = Depends(get_db)):
    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Lote não encontrado.")
    return batch.report


@app.get("/imports/{batch_id}/products")
def list_products(batch_id: str, db: Session = Depends(get_db)):
    products = db.query(ProductRecord).filter(ProductRecord.batch_id == batch_id).all()
    return [
        {
            "external_id": p.external_id, "sku": p.sku, "description": p.description,
            "status": p.status, "ncm": p.ncm, "barcode": p.barcode,
        }
        for p in products
    ]


# ---------- Exception Queue ----------

@app.get("/exceptions", response_model=list[ExceptionOut])
def list_exceptions(batch_id: Optional[str] = None, status: Optional[str] = None,
                     db: Session = Depends(get_db)):
    query = db.query(ExceptionRow)
    if batch_id:
        query = query.filter(ExceptionRow.batch_id == batch_id)
    if status:
        query = query.filter(ExceptionRow.resolution_status == status)
    return query.order_by(ExceptionRow.severity.desc()).all()


@app.post("/exceptions/{exception_id}/resolve", response_model=ExceptionOut)
def resolve_exception(exception_id: int, decision: ResolveExceptionIn,
                       db: Session = Depends(get_db)):
    if decision.decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(400, "decision deve ser APPROVED ou REJECTED.")

    row = db.query(ExceptionRow).filter(ExceptionRow.id == exception_id).first()
    if not row:
        raise HTTPException(404, "Exceção não encontrada.")

    row.resolution_status = decision.decision
    row.resolved_by = decision.resolved_by
    row.resolution_note = decision.note
    row.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@app.get("/imports/{batch_id}/readiness")
def readiness_gate(batch_id: str, db: Session = Depends(get_db)):
    """Só libera geração de script se não houver BLOCKER pendente (Dry Run obrigatório)."""
    pending_blockers = (
        db.query(ExceptionRow)
        .filter(
            ExceptionRow.batch_id == batch_id,
            ExceptionRow.severity == "BLOCKER",
            ExceptionRow.resolution_status == "PENDING",
        )
        .count()
    )
    ready = pending_blockers == 0
    return {"batch_id": batch_id, "ready_for_dry_run": ready, "pending_blockers": pending_blockers}


# ---------- Geração de script Oracle ----------

@app.get("/imports/{batch_id}/script")
def generate_script(batch_id: str, db: Session = Depends(get_db)):
    """Gera o .sql de INSERT para o Oracle do Winthor. Bloqueia se houver BLOCKER pendente."""
    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Lote não encontrado.")

    pending_blockers = (
        db.query(ExceptionRow)
        .filter(ExceptionRow.batch_id == batch_id, ExceptionRow.severity == "BLOCKER",
                ExceptionRow.resolution_status == "PENDING")
        .count()
    )
    if pending_blockers:
        raise HTTPException(
            409,
            f"{pending_blockers} exceção(ões) BLOCKER pendente(s). "
            "Resolva na Exception Queue antes de gerar o script.",
        )

    # Registros com qualquer exceção REJECTED ficam de fora do script (decisão do consultor).
    rejected_ids = {
        e.record_id for e in db.query(ExceptionRow).filter(
            ExceptionRow.batch_id == batch_id, ExceptionRow.resolution_status == "REJECTED",
        )
    }

    products = db.query(ProductRecord).filter(ProductRecord.batch_id == batch_id).all()
    product_dicts = [
        {
            "external_id": p.external_id, "sku": p.sku, "description": p.description,
            "barcode": p.barcode, "ncm": p.ncm, "cest": p.cest, "unit": p.unit,
            "brand": p.brand, "family": p.family, "department": p.department,
            "weight": p.weight,
        }
        for p in products
    ]

    result = generate_insert_script(product_dicts, blocked_record_ids=rejected_ids,
                                     batch_id=batch_id)

    script_path = SCRIPTS_DIR / f"{batch_id}.sql"
    script_path.write_text(result.sql, encoding="utf-8")

    return PlainTextResponse(
        content=result.sql,
        media_type="application/sql",
        headers={
            "Content-Disposition": f'attachment; filename="winthor_carga_{batch_id[:8]}.sql"',
            "X-Records-Included": str(result.records_included),
            "X-Records-Skipped": str(len(result.records_skipped)),
            "X-Warnings-Count": str(len(result.warnings)),
        },
    )


# ---------- Frontend estático ----------

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")
