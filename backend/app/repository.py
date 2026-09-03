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

from app.canonical.models import CanonicalProduct, ExceptionRecord
from app.db import ExceptionRow, ImportBatch, ProductRecord
from app.pipeline import PipelineResult

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
    """Grava produtos + exceções em massa e marca o lote como DONE."""
    product_rows = [_product_to_dict(p, batch_id) for p in result.products]
    exception_rows = [_exception_to_dict(e, batch_id) for e in result.exceptions]

    for chunk_start in range(0, len(product_rows), BULK_INSERT_CHUNK_SIZE):
        chunk = product_rows[chunk_start:chunk_start + BULK_INSERT_CHUNK_SIZE]
        db.bulk_insert_mappings(ProductRecord, chunk)

    for chunk_start in range(0, len(exception_rows), BULK_INSERT_CHUNK_SIZE):
        chunk = exception_rows[chunk_start:chunk_start + BULK_INSERT_CHUNK_SIZE]
        db.bulk_insert_mappings(ExceptionRow, chunk)

    db.query(ImportBatch).filter(ImportBatch.id == batch_id).update({
        "status": "DONE",
        "total_records": len(result.products),
        "exception_count": len(result.exceptions),
        "data_readiness_score": result.report.get("data_readiness_score", 0.0),
        "report": result.report,
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
