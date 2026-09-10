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

    # Campos específicos do layout Winthor (PCPRODUT tem ~40 campos; só uma
    # fração vira campo "de primeira classe" no canônico, porque são os que
    # o saneamento/dedup/validação de negócio genérico usam). O resto
    # (endereçamento, paletização, percentuais de compra, etc.) fica aqui,
    # chaveado pelo nome do campo Winthor (ex: "LASTROPAL", "CODSEC"),
    # e é regido pelos módulos de aderência (app/winthor/adherence.py),
    # não pelo pipeline de saneamento genérico.
    extra: dict = Field(default_factory=dict)

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


class CanonicalParticipante(BaseModel):
    """Cliente e/ou Fornecedor — mesma entidade fiscal (CNPJ/CPF), podendo
    ser as duas coisas ao mesmo tempo pra uma empresa real (compra E vende
    pra outra empresa). `tipo` guarda os papéis observados nos documentos
    fiscais processados: {"cliente"}, {"fornecedor"} ou {"cliente", "fornecedor"}.

    Só uma fração pequena do PCCLIENT/PCFORNEC (64 e ~20 campos
    respectivamente) vem de documento fiscal — nome, CNPJ/CPF, IE,
    endereço. O resto (limite de crédito, vendedor responsável, forma de
    pagamento, praça) é dado comercial que não existe em NF-e/SPED —
    mesmo padrão do PCPRODUT: fica pra um motor de aderência tratar depois,
    não inventado aqui.
    """
    external_id: str          # COD_PART do SPED, ou CNPJ/CPF quando vem de XML sem código próprio
    nome: str
    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    ie: Optional[str] = None
    cod_municipio: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    cep: Optional[str] = None
    fone: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    tipo: set[str] = Field(default_factory=set)  # {"cliente"} | {"fornecedor"} | ambos
    status: RecordStatus = RecordStatus.RAW

    extra: dict = Field(default_factory=dict)

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
