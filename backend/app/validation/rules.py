"""
Auditoria/Validação — checagens de integridade, cadastro e (parcialmente) fiscal.

Cada falha vira um ExceptionRecord. Nenhum registro com exceção BLOCKER
segue para mapeamento/carga sem aprovação humana.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.canonical.models import CanonicalProduct, ExceptionRecord, RecordStatus

NCM_RE = re.compile(r"^\d{8}$")


def validate_ean13(code: str) -> bool:
    """Valida dígito verificador de EAN-13/GTIN-13."""
    digits = re.sub(r"\D", "", code or "")
    if len(digits) not in (8, 12, 13, 14):
        return False
    # Normaliza para 13 dígitos (GTIN-13) para o cálculo padrão quando aplicável.
    if len(digits) == 13:
        body, check = digits[:-1], int(digits[-1])
    elif len(digits) == 12:  # UPC-A -> trata como GTIN, checksum próprio
        body, check = digits[:-1], int(digits[-1])
    elif len(digits) == 8:  # EAN-8
        body, check = digits[:-1], int(digits[-1])
    else:  # 14 -> ITF-14
        body, check = digits[:-1], int(digits[-1])

    total = 0
    # Algoritmo padrão GTIN: da direita para esquerda, pesos alternados 3/1.
    reversed_body = body[::-1]
    for i, d in enumerate(reversed_body):
        weight = 3 if i % 2 == 0 else 1
        total += int(d) * weight
    calculated_check = (10 - (total % 10)) % 10
    return calculated_check == check


def validate_product(product: CanonicalProduct) -> list[ExceptionRecord]:
    """Valida um único produto isoladamente (sem contexto do lote)."""
    exceptions: list[ExceptionRecord] = []

    if not product.sku or not product.description:
        exceptions.append(ExceptionRecord(
            record_id=product.external_id, entity="Product",
            reason_code="CAMPO_OBRIGATORIO_VAZIO",
            description="SKU ou descrição ausente após normalização.",
            severity="BLOCKER",
            payload={"sku": product.sku, "description": product.description},
        ))

    if product.barcode and not validate_ean13(product.barcode):
        exceptions.append(ExceptionRecord(
            record_id=product.external_id, entity="Product",
            reason_code="EAN_INVALIDO",
            description=f"Código de barras '{product.barcode}' falhou na validação de dígito verificador.",
            severity="HIGH",
            payload={"barcode": product.barcode},
        ))

    if product.ncm and not NCM_RE.match(product.ncm):
        exceptions.append(ExceptionRecord(
            record_id=product.external_id, entity="Product",
            reason_code="NCM_INVALIDO",
            description=f"NCM '{product.ncm}' não possui 8 dígitos numéricos.",
            severity="HIGH",
            payload={"ncm": product.ncm},
        ))

    if not product.ncm:
        exceptions.append(ExceptionRecord(
            record_id=product.external_id, entity="Product",
            reason_code="NCM_AUSENTE",
            description="Produto sem NCM cadastrado.",
            severity="MEDIUM",
            payload={},
        ))

    return exceptions


def validate_batch(products: list[CanonicalProduct]) -> tuple[list[CanonicalProduct], list[ExceptionRecord]]:
    """Valida o lote inteiro: checks individuais + integridade cruzada (duplicidade)."""
    all_exceptions: list[ExceptionRecord] = []

    seen_sku: dict[str, list[CanonicalProduct]] = defaultdict(list)
    seen_ean: dict[str, list[CanonicalProduct]] = defaultdict(list)

    for p in products:
        exs = validate_product(p)
        all_exceptions.extend(exs)
        seen_sku[p.sku].append(p)
        if p.barcode:
            seen_ean[p.barcode].append(p)

        if exs:
            p.status = RecordStatus.EXCEPTION
        else:
            p.status = RecordStatus.VALIDATED

    for sku, group in seen_sku.items():
        if len(group) > 1:
            for p in group:
                all_exceptions.append(ExceptionRecord(
                    record_id=p.external_id, entity="Product",
                    reason_code="SKU_DUPLICADO",
                    description=f"SKU '{sku}' aparece {len(group)} vezes no lote.",
                    severity="HIGH",
                    payload={"sku": sku, "count": len(group)},
                ))
                p.status = RecordStatus.EXCEPTION

    for ean, group in seen_ean.items():
        if len(group) > 1:
            for p in group:
                all_exceptions.append(ExceptionRecord(
                    record_id=p.external_id, entity="Product",
                    reason_code="EAN_DUPLICADO",
                    description=f"EAN '{ean}' aparece {len(group)} vezes no lote.",
                    severity="HIGH",
                    payload={"barcode": ean, "count": len(group)},
                ))
                p.status = RecordStatus.EXCEPTION

    return products, all_exceptions
