"""
Validação de Participante — mesmo princípio de validate_product: cada
falha vira ExceptionRecord, BLOCKER trava geração de carga.
"""

from __future__ import annotations

from app.canonical.models import CanonicalParticipante, ExceptionRecord
from app.validation.br_documents import validate_cnpj, validate_cpf


def validate_participante(p: CanonicalParticipante) -> list[ExceptionRecord]:
    exceptions: list[ExceptionRecord] = []

    if not p.nome:
        exceptions.append(ExceptionRecord(
            record_id=p.external_id, entity="Participante",
            reason_code="CAMPO_OBRIGATORIO_VAZIO",
            description="Nome/razão social ausente.",
            severity="BLOCKER", payload={},
        ))

    if not p.cnpj and not p.cpf:
        exceptions.append(ExceptionRecord(
            record_id=p.external_id, entity="Participante",
            reason_code="DOCUMENTO_AUSENTE",
            description="Sem CNPJ nem CPF identificável.",
            severity="BLOCKER", payload={},
        ))

    if p.cnpj and not validate_cnpj(p.cnpj):
        exceptions.append(ExceptionRecord(
            record_id=p.external_id, entity="Participante",
            reason_code="CNPJ_INVALIDO",
            description=f"CNPJ '{p.cnpj}' falhou na validação de dígito verificador.",
            severity="HIGH", payload={"cnpj": p.cnpj},
        ))

    if p.cpf and not validate_cpf(p.cpf):
        exceptions.append(ExceptionRecord(
            record_id=p.external_id, entity="Participante",
            reason_code="CPF_INVALIDO",
            description=f"CPF '{p.cpf}' falhou na validação de dígito verificador.",
            severity="HIGH", payload={"cpf": p.cpf},
        ))

    if not p.tipo:
        exceptions.append(ExceptionRecord(
            record_id=p.external_id, entity="Participante",
            reason_code="SEM_CLASSIFICACAO",
            description="Participante extraído mas nunca aparece como cliente nem "
                        "fornecedor em nenhum documento processado.",
            severity="MEDIUM", payload={},
        ))

    return exceptions


def validate_participantes_batch(
    participantes: list[CanonicalParticipante],
) -> list[ExceptionRecord]:
    exceptions: list[ExceptionRecord] = []
    for p in participantes:
        exceptions.extend(validate_participante(p))
    return exceptions
