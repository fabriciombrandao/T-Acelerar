"""
Repository — traduz PipelineResult (em memória) para as tabelas ORM.

Duas fases, pensadas pra processamento assíncrono em volume grande:

1. create_pending_batch(): cria a linha do lote IMEDIATAMENTE, status
   PENDING, sem produtos/exceções ainda. É o que permite a API responder
   na hora (sem esperar o processamento) e o cliente ficar consultando
   status via polling.
2. finalize_pipeline_result(): roda depois (síncrono ou em worker
   assíncrono via Celery — ver app/tasks.py), grava produtos/exceções em
   massa (bulk insert, não um INSERT por linha via ORM) e marca status DONE.

Bulk insert via session.bulk_insert_mappings() é ordens de magnitude mais
rápido que criar um objeto ORM por linha e dar session.add() — para 100 mil+
linhas, a diferença é a diferença entre segundos e minutos.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.canonical.models import CanonicalParticipante, CanonicalProduct, ExceptionRecord
from app.db import ExceptionRow, ImportBatch, ParticipanteRecord, ProductRecord
from app.pipeline import ParticipanteResult, PipelineResult

BULK_INSERT_CHUNK_SIZE = 5000


def create_pending_batch(db: Session, project_id: str, source_file: str,
                          batch_id: str | None = None) -> ImportBatch:
    batch = ImportBatch(
        id=batch_id or str(uuid.uuid4()), project_id=project_id,
        source_file=source_file, status="PENDING",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def mark_batch_processing(db: Session, batch_id: str) -> None:
    db.query(ImportBatch).filter(ImportBatch.id == batch_id).update({"status": "PROCESSING"})
    db.commit()


def mark_batch_failed(db: Session, batch_id: str, error_message: str) -> None:
    db.query(ImportBatch).filter(ImportBatch.id == batch_id).update({
        "status": "FAILED", "error_message": error_message[:2000],
    })
    db.commit()


def finalize_pipeline_result(db: Session, batch_id: str, result: PipelineResult) -> ImportBatch:
    """Grava produtos + exceções em massa e marca o lote como DONE.
    Mantido como estava (CSV — nunca tem participante) por retrocompatibilidade;
    SPED/XML usam finalize_multi_entity_result, que também escreve participante."""
    return finalize_multi_entity_result(db, batch_id, product_result=result)


def finalize_multi_entity_result(
    db: Session, batch_id: str,
    product_result: PipelineResult | None = None,
    participante_result: ParticipanteResult | None = None,
) -> ImportBatch:
    """Grava produto e/ou participante do mesmo lote — um upload de SPED/XML
    gera as duas entidades de uma vez, não é 'ou um ou outro'. Contagem por
    entidade fica em colunas próprias de ImportBatch (product_count,
    participante_count, cliente_count, fornecedor_count) pra alimentar o
    breakdown na tela sem precisar reagregar do zero a cada request."""
    total_records = 0
    exception_count = 0
    product_count = 0
    participante_count = 0
    cliente_count = 0
    fornecedor_count = 0
    report: dict = {}
    readiness_scores = []

    if product_result is not None:
        product_rows = [_product_to_dict(p, batch_id) for p in product_result.products]
        exception_rows = [_exception_to_dict(e, batch_id) for e in product_result.exceptions]

        for chunk_start in range(0, len(product_rows), BULK_INSERT_CHUNK_SIZE):
            chunk = product_rows[chunk_start:chunk_start + BULK_INSERT_CHUNK_SIZE]
            db.bulk_insert_mappings(ProductRecord, chunk)
        for chunk_start in range(0, len(exception_rows), BULK_INSERT_CHUNK_SIZE):
            chunk = exception_rows[chunk_start:chunk_start + BULK_INSERT_CHUNK_SIZE]
            db.bulk_insert_mappings(ExceptionRow, chunk)

        product_count = len(product_result.products)
        total_records += product_count
        exception_count += len(product_result.exceptions)
        report.update(product_result.report)  # espalha no nível raiz — mesmo formato de sempre, retrocompatível
        readiness_scores.append(product_result.report.get("data_readiness_score", 0.0))

    if participante_result is not None:
        participante_rows = [_participante_to_dict(p, batch_id) for p in participante_result.participantes]
        exception_rows = [_exception_to_dict(e, batch_id) for e in participante_result.exceptions]

        for chunk_start in range(0, len(participante_rows), BULK_INSERT_CHUNK_SIZE):
            chunk = participante_rows[chunk_start:chunk_start + BULK_INSERT_CHUNK_SIZE]
            db.bulk_insert_mappings(ParticipanteRecord, chunk)
        for chunk_start in range(0, len(exception_rows), BULK_INSERT_CHUNK_SIZE):
            chunk = exception_rows[chunk_start:chunk_start + BULK_INSERT_CHUNK_SIZE]
            db.bulk_insert_mappings(ExceptionRow, chunk)

        participante_count = len(participante_result.participantes)
        cliente_count = sum(1 for p in participante_result.participantes if "cliente" in p.tipo)
        fornecedor_count = sum(1 for p in participante_result.participantes if "fornecedor" in p.tipo)
        total_records += participante_count
        exception_count += len(participante_result.exceptions)
        report["participante"] = {
            "total": participante_count, "clientes": cliente_count,
            "fornecedores": fornecedor_count,
            "exception_count": len(participante_result.exceptions),
        }

    db.query(ImportBatch).filter(ImportBatch.id == batch_id).update({
        "status": "DONE",
        "total_records": total_records,
        "product_count": product_count,
        "participante_count": participante_count,
        "cliente_count": cliente_count,
        "fornecedor_count": fornecedor_count,
        "exception_count": exception_count,
        "data_readiness_score": (sum(readiness_scores) / len(readiness_scores)) if readiness_scores else 0.0,
        "report": report,
    })
    db.commit()

    return db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()


def _product_to_dict(p: CanonicalProduct, batch_id: str) -> dict:
    return dict(
        batch_id=batch_id,
        external_id=p.external_id,
        sku=p.sku,
        description_raw=p.description_raw,
        description=p.description,
        barcode=p.barcode,
        ncm=p.ncm,
        cest=p.cest,
        unit=p.unit,
        brand=p.brand,
        family=p.family,
        department=p.department,
        weight=p.weight,
        origin_field=p.origin,
        status=p.status.value if hasattr(p.status, "value") else p.status,
        provenance=[pr.model_dump(mode="json") for pr in p.provenance],
        extra=p.extra,
    )


def _exception_to_dict(e: ExceptionRecord, batch_id: str) -> dict:
    return dict(
        batch_id=batch_id,
        record_id=e.record_id,
        entity=e.entity,
        reason_code=e.reason_code,
        description=e.description,
        severity=e.severity,
        payload=e.payload,
        resolution_status="PENDING",
    )


def _participante_to_dict(p: CanonicalParticipante, batch_id: str) -> dict:
    return dict(
        batch_id=batch_id,
        external_id=p.external_id,
        nome=p.nome,
        cnpj=p.cnpj,
        cpf=p.cpf,
        ie=p.ie,
        cod_municipio=p.cod_municipio,
        municipio=p.municipio,
        uf=p.uf,
        cep=p.cep,
        fone=p.fone,
        endereco=p.endereco,
        numero=p.numero,
        complemento=p.complemento,
        bairro=p.bairro,
        tipo=sorted(p.tipo),
        status=p.status.value if hasattr(p.status, "value") else p.status,
        provenance=[pr.model_dump(mode="json") for pr in p.provenance],
        extra=p.extra,
    )
