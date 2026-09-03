"""
Canonical Data Model — Produto.

Toda fonte (Excel, CSV, banco legado) é convertida para este modelo
antes de qualquer saneamento, auditoria ou mapeamento para o Winthor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RecordStatus(str, Enum):
    RAW = "RAW"
    PARSED = "PARSED"
    NORMALIZED = "NORMALIZED"
    VALIDATED = "VALIDATED"
    MAPPED = "MAPPED"
    APPROVED = "APPROVED"
    LOADED = "LOADED"
    EXCEPTION = "EXCEPTION"


class FieldProvenance(BaseModel):
    """Rastreabilidade de um campo enriquecido/transformado."""
    field: str
    origin: str          # ex: "SPED", "planilha_cliente", "regra:normalize_unit"
    evidence: Optional[str] = None
    confidence: float = 1.0
    rule: Optional[str] = None


class CanonicalProduct(BaseModel):
    external_id: str
    sku: str
    description_raw: str
    description: Optional[str] = None
    barcode: Optional[str] = None
    ncm: Optional[str] = None
    cest: Optional[str] = None
    unit: Optional[str] = None
    brand: Optional[str] = None
    family: Optional[str] = None
    department: Optional[str] = None
    weight: Optional[float] = None
    origin: Optional[str] = None
    status: RecordStatus = RecordStatus.RAW

    source_file: Optional[str] = None
    import_batch_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    provenance: list[FieldProvenance] = Field(default_factory=list)

    def add_provenance(self, field: str, origin: str, rule: str | None = None,
                        confidence: float = 1.0, evidence: str | None = None) -> None:
        self.provenance.append(
            FieldProvenance(field=field, origin=origin, rule=rule,
                             confidence=confidence, evidence=evidence)
        )


class ExceptionRecord(BaseModel):
    """Registro que exige decisão humana (Exception Queue)."""
    record_id: str
    entity: str            # ex: "Product"
    reason_code: str       # ex: "EAN_INVALIDO", "NCM_DIVERGENTE_SPED"
    description: str
    severity: str = "MEDIUM"   # LOW | MEDIUM | HIGH | BLOCKER
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
