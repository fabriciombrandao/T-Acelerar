"""
Repository — traduz PipelineResult (em memória) para as tabelas ORM.

Mantém pipeline.py independente de banco: o pipeline continua puro/testável
sem precisar de uma sessão de banco ativa.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.canonical.models import CanonicalProduct, ExceptionRecord
from app.db import ExceptionRow, ImportBatch, ProductRecord
from app.pipeline import PipelineResult


def persist_pipeline_result(session: Session, result: PipelineResult,
                             source_file: str, project_id: str) -> ImportBatch:
    batch_id = str(uuid.uuid4())

    batch = ImportBatch(
        id=batch_id,
        project_id=project_id,
        source_file=source_file,
        total_records=len(result.products),
        exception_count=len(result.exceptions),
        data_readiness_score=result.report.get("data_readiness_score", 0.0),
        report=result.report,
    )
    session.add(batch)

    for p in result.products:
        session.add(_product_to_row(p, batch_id))

    for e in result.exceptions:
        session.add(_exception_to_row(e, batch_id))

    session.commit()
    session.refresh(batch)
    return batch


def _product_to_row(p: CanonicalProduct, batch_id: str) -> ProductRecord:
    return ProductRecord(
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
    )


def _exception_to_row(e: ExceptionRecord, batch_id: str) -> ExceptionRow:
    return ExceptionRow(
        batch_id=batch_id,
        record_id=e.record_id,
        entity=e.entity,
        reason_code=e.reason_code,
        description=e.description,
        severity=e.severity,
        payload=e.payload,
        resolution_status="PENDING",
    )
