"""
API — expõe o pipeline, a Exception Queue e a geração de script Oracle como serviço.

Fluxo real de uso (sem API do Winthor disponível):
  login -> abrir/criar projeto -> subir arquivo -> validar (pipeline automático) ->
  tratar exceções -> gerar script -> rodar manualmente no Oracle/Winthor do cliente.

Autenticação obrigatória a partir da decisão de rodar em VPS compartilhado
por vários consultores (ver app/auth.py).
"""

from __future__ import annotations

import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import (Role, authenticate_user, can_see_owner, create_access_token,
                       create_user, get_current_coordenador_ou_acima,
                       get_current_diretor, get_current_user, hash_password,
                       visible_owner_ids)
from app.db import (ExceptionRow, ImportBatch, Project, ProductRecord, User,
                     get_db, init_db)
from app.repository import create_pending_batch
from app.tasks import process_import_task
from app.winthor.adherence import (load_modules_config, load_segments_config,
                                    preset_for_subsegment)
from app.winthor.oracle_generator import generate_insert_script
from app.winthor.text_file_generator import generate_text_file

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "output" / "scripts"
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "output" / "uploads"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Winthor Data Deploy API",
    description="Ingestão, saneamento, auditoria, Exception Queue e geração de script Winthor.",
    version="0.4.0",
    lifespan=lifespan,
)

# Frontend é container separado do backend (nginx unifica sob o mesmo
# domínio em produção via /api/ vs /, então CORS não entra em jogo lá).
# Isso só importa pra rodar local sem Docker/nginx, com frontend e backend
# em portas diferentes. Autenticação usa Bearer token (não cookie), então
# allow_origins="*" não expõe sessão de ninguém — o token só vai se o JS
# da própria página o enviar explicitamente no header.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Sem autenticação de propósito — é só pra Docker healthcheck (padrão
    do time: mesmo formato usado no TNORTEANDO). Confirma que a API está de
    pé E que o banco responde, não só que o processo está vivo."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# Tudo abaixo fica sob /api — nginx roteia /api/* pro backend e o resto
# pro container de frontend (padrão do time, ver deploy/nginx-*.conf).
router = APIRouter(prefix="/api")


# ---------- Autorização por projeto ----------
# Admin vê/mexe em tudo. Consultor só acessa projetos dos quais é owner
# (decisão do time: >5 consultores, projetos de clientes diferentes —
# consultor de um cliente não deve ver dado de outro).

def _get_authorized_project(db: Session, project_id: str, user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Projeto não encontrado.")
    if not can_see_owner(db, user, project.owner_id):
        raise HTTPException(403, "Sem acesso a este projeto.")
    return project


def _get_authorized_batch(db: Session, batch_id: str, user: User) -> ImportBatch:
    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Lote não encontrado.")
    project = db.query(Project).filter(Project.id == batch.project_id).first()
    if not project or not can_see_owner(db, user, project.owner_id):
        raise HTTPException(403, "Sem acesso a este projeto.")
    return batch


# ---------- Schemas ----------

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    manager_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class UserCreateIn(BaseModel):
    email: str
    name: str
    password: str
    role: str  # "diretor" | "coordenador" | "analista"
    manager_email: Optional[str] = None  # obrigatório se role="analista" e quem cria for diretor


class BootstrapAdminIn(BaseModel):
    email: str
    name: str
    password: str
    bootstrap_secret: str


class ProjectOut(BaseModel):
    id: str
    name: str
    owner_id: Optional[str] = None
    segment: Optional[str] = None
    subsegment: Optional[str] = None
    adherence_answers: dict = {}
    model_config = ConfigDict(from_attributes=True)


class ProjectIn(BaseModel):
    name: str
    owner_email: Optional[str] = None  # só admin pode atribuir a outro consultor


class AdherenceIn(BaseModel):
    segment: str
    subsegment: str
    overrides: Optional[dict] = None  # {module_id: bool} — sobrescreve o preset


class AdherenceOut(BaseModel):
    segment: Optional[str]
    subsegment: Optional[str]
    adherence_answers: dict


class BatchSummary(BaseModel):
    id: str
    project_id: str
    source_file: str
    status: str
    error_message: Optional[str] = None
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
    note: Optional[str] = None


# ---------- Autenticação ----------

@router.post("/auth/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Email ou senha incorretos.",
                             headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=create_access_token(user))


@router.get("/auth/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/auth/bootstrap-admin", response_model=UserOut)
def bootstrap_admin(payload: BootstrapAdminIn, db: Session = Depends(get_db)):
    """Cria o primeiro DIRETOR. Só funciona uma vez (enquanto não houver
    nenhum usuário) e exige o secret de ambiente TACELERAR_BOOTSTRAP_SECRET."""
    expected_secret = os.environ.get("TACELERAR_BOOTSTRAP_SECRET")
    if not expected_secret:
        raise HTTPException(503, "TACELERAR_BOOTSTRAP_SECRET não configurado no servidor.")
    if payload.bootstrap_secret != expected_secret:
        raise HTTPException(403, "Secret de bootstrap incorreto.")
    if db.query(User).count() > 0:
        raise HTTPException(409, "Já existe usuário cadastrado. Bootstrap só funciona uma vez.")

    return create_user(db, payload.email, payload.name, payload.password, role=Role.DIRETOR.value)


# ---------- Usuários (diretor gerencia todos; coordenador só sua equipe) ----------

@router.post("/users", response_model=UserOut)
def create_user_endpoint(payload: UserCreateIn, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_coordenador_ou_acima)):
    if payload.role not in {r.value for r in Role}:
        raise HTTPException(400, f"role deve ser um de: {[r.value for r in Role]}.")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, "Já existe usuário com esse email.")

    if current_user.role == Role.COORDENADOR:
        if payload.role != Role.ANALISTA.value:
            raise HTTPException(403, "Coordenador só pode criar usuários com perfil analista.")
        manager_id = current_user.id  # equipe do próprio coordenador, sem exceção
    else:  # diretor
        manager_id = None
        if payload.role == Role.ANALISTA.value:
            if not payload.manager_email:
                raise HTTPException(400, "manager_email é obrigatório para criar um analista.")
            manager = db.query(User).filter(User.email == payload.manager_email).first()
            if not manager or manager.role != Role.COORDENADOR.value:
                raise HTTPException(400, "manager_email deve ser um coordenador existente.")
            manager_id = manager.id

    return create_user(db, payload.email, payload.name, payload.password,
                        role=payload.role, manager_id=manager_id)


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db),
               current_user: User = Depends(get_current_coordenador_ou_acima)):
    if current_user.role == Role.DIRETOR:
        query = db.query(User)
    else:  # coordenador: só a própria equipe + ele mesmo
        ids = visible_owner_ids(db, current_user)
        query = db.query(User).filter(User.id.in_(ids))
    return query.order_by(User.created_at.desc()).all()


# ---------- Projetos ----------

@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectIn, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    owner_id = current_user.id

    if payload.owner_email:
        target = db.query(User).filter(User.email == payload.owner_email).first()
        if not target:
            raise HTTPException(404, f"Usuário '{payload.owner_email}' não encontrado.")
        # Só pode atribuir a alguém cujos projetos você já enxergaria de qualquer
        # forma: diretor -> qualquer um; coordenador -> a própria equipe; analista -> só ele mesmo.
        if not can_see_owner(db, current_user, target.id):
            raise HTTPException(
                403, "Sem permissão para atribuir projeto a este usuário.",
            )
        owner_id = target.id

    project = Project(id=str(uuid.uuid4()), name=payload.name, owner_id=owner_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Project)
    ids = visible_owner_ids(db, current_user)
    if ids is not None:
        query = query.filter(Project.owner_id.in_(ids))
    return query.order_by(Project.created_at.desc()).all()


@router.get("/projects/{project_id}/imports", response_model=list[BatchSummary])
def list_project_imports(project_id: str, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    _get_authorized_project(db, project_id, current_user)
    return (
        db.query(ImportBatch)
        .filter(ImportBatch.project_id == project_id)
        .order_by(ImportBatch.created_at.desc())
        .all()
    )


# ---------- Wizard de aderência ----------

@router.get("/adherence/segments")
def get_segments(_user: User = Depends(get_current_user)):
    """Segmentos/subsegmentos disponíveis, com preset de módulos por subsegmento."""
    return load_segments_config()


@router.get("/adherence/modules")
def get_modules(_user: User = Depends(get_current_user)):
    """Definição dos módulos de aderência do PCPRODUT (para montar o wizard)."""
    return load_modules_config()


@router.post("/projects/{project_id}/adherence", response_model=AdherenceOut)
def set_project_adherence(project_id: str, payload: AdherenceIn, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """Salva segmento/subsegmento escolhidos + aplica preset, com overrides opcionais."""
    project = _get_authorized_project(db, project_id, current_user)

    preset = preset_for_subsegment(payload.segment, payload.subsegment)
    if not preset and payload.overrides is None:
        raise HTTPException(400, "Segmento/subsegmento não encontrado em segments.json.")

    merged = {**preset, **(payload.overrides or {})}

    project.segment = payload.segment
    project.subsegment = payload.subsegment
    project.adherence_answers = merged
    db.commit()
    db.refresh(project)

    return AdherenceOut(segment=project.segment, subsegment=project.subsegment,
                         adherence_answers=project.adherence_answers)


@router.get("/projects/{project_id}/adherence", response_model=AdherenceOut)
def get_project_adherence(project_id: str, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    project = _get_authorized_project(db, project_id, current_user)
    return AdherenceOut(segment=project.segment, subsegment=project.subsegment,
                         adherence_answers=project.adherence_answers or {})


# ---------- Imports / Pipeline ----------

@router.post("/imports", response_model=BatchSummary)
async def create_import(project_id: str = Form(...), file: UploadFile = None,
                         db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    """Sobe um CSV de produtos dentro de um projeto e dispara o processamento.

    Responde imediatamente com o lote em status PENDING (ou já DONE, se
    estiver rodando sem Redis configurado — modo síncrono de dev/teste).
    Use GET /imports/{id} para acompanhar o progresso em arquivo grande.
    """
    _get_authorized_project(db, project_id, current_user)
    if not file or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Envie um arquivo .csv.")

    batch = create_pending_batch(db, project_id=project_id, source_file=file.filename)

    persistent_path = UPLOADS_DIR / f"{batch.id}.csv"
    with persistent_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    process_import_task.delay(batch.id, str(persistent_path))

    db.refresh(batch)  # em modo síncrono (sem Redis), a task já rodou e commitou
    return batch


@router.get("/imports/{batch_id}", response_model=BatchSummary)
def get_import_status(batch_id: str, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    """Polling de status — use enquanto o lote estiver PENDING/PROCESSING."""
    batch = _get_authorized_batch(db, batch_id, current_user)
    return batch


@router.get("/imports/{batch_id}/report")
def get_report(batch_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    batch = _get_authorized_batch(db, batch_id, current_user)
    return batch.report


@router.get("/imports/{batch_id}/products")
def list_products(batch_id: str, response: Response, limit: int = 200, offset: int = 0,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """Paginado — batch de 1M linhas não pode virar um JSON só. Default 200,
    máximo 1000 por página; total real vem no header X-Total-Count."""
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    _get_authorized_batch(db, batch_id, current_user)
    base_query = db.query(ProductRecord).filter(ProductRecord.batch_id == batch_id)
    total = base_query.count()
    products = base_query.order_by(ProductRecord.id).offset(offset).limit(limit).all()

    response.headers["X-Total-Count"] = str(total)
    return [
        {
            "external_id": p.external_id, "sku": p.sku, "description": p.description,
            "status": p.status, "ncm": p.ncm, "barcode": p.barcode,
        }
        for p in products
    ]


# ---------- Exception Queue ----------

@router.get("/exceptions", response_model=list[ExceptionOut])
def list_exceptions(response: Response, batch_id: Optional[str] = None,
                     status: Optional[str] = None, limit: int = 200, offset: int = 0,
                     db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """Paginado — mesma lógica: default 200, máximo 1000, total no header."""
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    if batch_id:
        _get_authorized_batch(db, batch_id, current_user)
        query = db.query(ExceptionRow).filter(ExceptionRow.batch_id == batch_id)
    else:
        query = db.query(ExceptionRow)
        ids = visible_owner_ids(db, current_user)
        if ids is not None:
            query = (
                query.join(ImportBatch, ExceptionRow.batch_id == ImportBatch.id)
                .join(Project, ImportBatch.project_id == Project.id)
                .filter(Project.owner_id.in_(ids))
            )
    if status:
        query = query.filter(ExceptionRow.resolution_status == status)

    total = query.count()
    response.headers["X-Total-Count"] = str(total)
    return (
        query.order_by(ExceptionRow.severity.desc(), ExceptionRow.id)
        .offset(offset).limit(limit).all()
    )


@router.post("/exceptions/{exception_id}/resolve", response_model=ExceptionOut)
def resolve_exception(exception_id: int, decision: ResolveExceptionIn,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    if decision.decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(400, "decision deve ser APPROVED ou REJECTED.")

    row = db.query(ExceptionRow).filter(ExceptionRow.id == exception_id).first()
    if not row:
        raise HTTPException(404, "Exceção não encontrada.")
    _get_authorized_batch(db, row.batch_id, current_user)

    row.resolution_status = decision.decision
    # resolved_by vem do usuário autenticado, não de texto livre enviado pelo
    # cliente — é dado de auditoria, não deve poder ser forjado na requisição.
    row.resolved_by = current_user.email
    row.resolution_note = decision.note
    row.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.get("/imports/{batch_id}/readiness")
def readiness_gate(batch_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Só libera geração de script se não houver BLOCKER pendente (Dry Run obrigatório)."""
    _get_authorized_batch(db, batch_id, current_user)
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


# ---------- Geração de script ----------

@router.get("/imports/{batch_id}/script")
def generate_script(batch_id: str, format: str = "texto", db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """Gera o arquivo de carga para o Winthor.

    format=texto (default) -> arquivo delimitado oficial (DA.RPI.010), o que
        o Winthor realmente importa via VALIDADORMIGRACAO.
    format=sql -> INSERT Oracle (mantido como segunda opção; útil quando o
        time prefere carregar direto via banco em vez do fluxo oficial de
        arquivo texto — cenário e mapping ainda precisam de validação
        específica por cliente antes de usar em produção).
    Bloqueia com 409 se houver exceção BLOCKER pendente, nos dois formatos.
    """
    if format not in ("texto", "sql"):
        raise HTTPException(400, "format deve ser 'texto' ou 'sql'.")

    _get_authorized_batch(db, batch_id, current_user)

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

    rejected_ids = {
        e.record_id for e in db.query(ExceptionRow).filter(
            ExceptionRow.batch_id == batch_id, ExceptionRow.resolution_status == "REJECTED",
        )
    }

    products = db.query(ProductRecord).filter(ProductRecord.batch_id == batch_id).all()

    if format == "sql":
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
        content = result.sql
        media_type = "application/sql"
        filename = f"winthor_carga_{batch_id[:8]}.sql"
    else:
        product_dicts = [
            {
                "external_id": p.external_id, "sku": p.sku, "description": p.description,
                "unit": p.unit, "barcode": p.barcode, "ncm": p.ncm, "weight": p.weight,
                "extra": p.extra or {},
            }
            for p in products
        ]
        result = generate_text_file(product_dicts, blocked_record_ids=rejected_ids)
        content = result.content
        media_type = "text/plain"
        filename = f"winthor_carga_{batch_id[:8]}.txt"

    script_path = SCRIPTS_DIR / f"{batch_id}_{format}.{'sql' if format == 'sql' else 'txt'}"
    script_path.write_text(content, encoding="utf-8")

    return PlainTextResponse(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Records-Included": str(result.records_included),
            "X-Records-Skipped": str(len(result.records_skipped)),
            "X-Warnings-Count": str(len(result.warnings)),
            "X-Format": format,
        },
    )


# Frontend agora é um serviço/container separado (nginx servindo
# frontend/index.html) — não é mais servido por esta API. Ver
# frontend/Dockerfile e deploy/nginx-*.conf.
app.include_router(router)
